"""Bounded official text acquisition and independent exact annotation identity.

Parquet column ranges locate rows; annotation answers never enter reference
construction. Byte receipts identify snapshots when the rows API cannot pin a
repository revision.
"""

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from earth_observation.data import fetch_asset


def acquire_text_asset(
    url: str,
    cache: Path,
    name: str,
    budget: dict,
    *,
    expected_size: int | None = None,
    byte_range: tuple[int, int] | None = None,
    total_size: int | None = None,
) -> tuple[bytes, dict]:
    """Discover/cache an official response under a cumulative transfer ceiling.

    Parameters
    ----------
    url : str
        HTTPS Hugging Face dataset or dataset-server source URL.
    cache : Path
        Local response directory. Each response has a SHA-256 identity sidecar.
    name : str
        Simple cache filename; existing unidentified files are refused.
    budget : dict
        Mutable explicit ledger with limit_bytes, transferred_bytes and
        reserved_bytes. Failed requests retain their reserved allocation so a
        retry cannot silently erase potentially transferred partial bytes.
    expected_size : int, optional
        Exact range payload length; ordinary JSON responses are capped at 100 KB.
    byte_range : tuple of int, optional
        Inclusive bounds; require exact HTTP 206 before any body read.
    total_size : int, optional
        Published parent Parquet size in bytes, required for ranges.

    Returns
    -------
    tuple
        Exact response bytes and URL/name/size/SHA-256 receipt. Valid cache reuse
        performs no network transfer; changed or unidentified cache is rejected.

    Raises
    ------
    ValueError
        Unsafe source/path, exceeded budget, ignored range or changed bytes.
    """
    host = urllib.parse.urlparse(url)
    if (
        host.scheme != "https"
        or host.hostname not in {"huggingface.co", "datasets-server.huggingface.co"}
        or Path(name).name != name
        or name in {"", ".", ".."}
    ):
        raise ValueError("Expected official source and simple cache name")
    maximum = expected_size if expected_size is not None else 100_000
    if maximum <= 0:
        raise ValueError("Positive bounded response size required")
    if byte_range is not None:
        start, end = byte_range
        if (
            total_size is None
            or start < 0
            or end >= total_size
            or end - start + 1 != maximum
        ):
            raise ValueError("Inconsistent exact text range")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    identity = cache / (name + ".source.json")
    if target.is_symlink() or identity.is_symlink():
        raise ValueError("Text cache must not use symbolic links")
    if target.exists():
        if not identity.is_file():
            raise ValueError("Unidentified text cache")
        asset = json.loads(identity.read_text())
        if (
            asset["url"] != url
            or asset["name"] != name
            or (expected_size is not None and asset["size_bytes"] != maximum)
        ):
            raise ValueError("Text cache source identity changed")
        if byte_range is not None and (
            asset.get("byte_range") != list(byte_range)
            or asset.get("archive_size_bytes") != total_size
        ):
            raise ValueError("Text cache range identity changed")
        return fetch_asset(asset, cache, max_bytes=maximum).read_bytes(), asset
    if budget["reserved_bytes"] + maximum + 1 > budget["limit_bytes"]:
        raise ValueError("Total text transfer would exceed authorized budget")
    budget["reserved_bytes"] += maximum + 1
    headers = {"Accept-Encoding": "identity"}
    if byte_range is not None:
        headers["Range"] = f"bytes={start}-{end}"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=40
    ) as response:
        if byte_range is not None and (
            response.status != 206
            or response.headers.get("Content-Range")
            != f"bytes {start}-{end}/{total_size}"
            or response.headers.get("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError("Exact Parquet range was not honored")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > maximum:
            raise ValueError("Response exceeds bounded size before transfer")
        content = response.read(maximum + 1)
        budget["transferred_bytes"] += len(content)
        if len(content) > maximum or (
            expected_size is not None and len(content) != maximum
        ):
            raise ValueError("Response exceeds or differs from bounded size")
    budget["reserved_bytes"] -= maximum + 1 - len(content)
    asset = {
        "url": url,
        "name": name,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if byte_range is not None:
        asset.update(byte_range=list(byte_range), archive_size_bytes=total_size)
    target.write_bytes(content)
    identity.write_text(json.dumps(asset, indent=2) + "\n")
    return content, asset


def original_annotation(page: dict, patch_id: str, row_index: int) -> dict:
    """Validate one untruncated original row against its indexed identity.

    Parameters
    ----------
    page : dict
        Actual official rows response, including feature dtypes and row_idx.
    patch_id : str
        Exact planned patch identity, never a neighboring replacement.
    row_index : int
        Zero-based position independently found in the pinned Parquet ID column.

    Returns
    -------
    dict
        Unmodified original annotation plus its provenance row_idx.

    Raises
    ------
    ValueError
        Truncation, missing/mistyped schema or incorrect row/patch identity.
    """
    if len(page["rows"]) != 1:
        raise ValueError("Expected exactly one requested original row")
    item = page["rows"][0]
    row = item["row"]
    if (
        item["row_idx"] != row_index
        or item["truncated_cells"]
        or row["patch_id"] != patch_id
    ):
        raise ValueError("Original row does not match indexed position/ID")
    expected = {
        name: "string"
        for name in (
            "s1_name",
            "patch_id",
            "input",
            "output",
            "type",
            "category",
            "split",
            "country",
            "season",
            "climate_zone",
        )
    }
    expected.update(ID="int64", latitude="float64", longitude="float64")
    features = {f["name"]: f["type"]["dtype"] for f in page["features"]}
    if set(row) != set(expected) or features != expected:
        raise ValueError("Original text schema changed")
    if (
        type(row["ID"]) is not int
        or any(
            not isinstance(row[k], str) for k, v in expected.items() if v == "string"
        )
        or any(type(row[k]) not in (int, float) for k in ("latitude", "longitude"))
    ):
        raise ValueError("Original annotation value types changed")
    return row | {"row_idx": item["row_idx"]}
