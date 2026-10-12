"""Bounded source caching and explicit text-to-patch identity validation."""

import hashlib
import json
import urllib.request
from pathlib import Path

import pandas as pd


def fetch_asset(asset: dict, cache: Path, max_bytes: int = 5_000_000) -> Path:
    """Cache an exact source snapshot without accepting stale or oversized data.

    Parameters
    ----------
    asset : dict
        URL, simple cache filename, byte size, and SHA-256 of expected content.
    cache : Path
        Local directory; never serialized into the public manifest.
    max_bytes : int
        Hard per-request byte limit, including when Content-Length is absent.

    Returns
    -------
    Path
        Checksum-verified local file. Valid existing files need no network access.

    Raises
    ------
    ValueError
        Unsafe filename, excessive size, or mismatched source/cache identity.
    """
    name = asset["name"]
    if Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("Expected a simple cache filename")
    if not 0 < asset["size_bytes"] <= max_bytes:
        raise ValueError("Asset exceeds the download budget")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if target.exists():
        if target.stat().st_size != asset["size_bytes"]:
            raise ValueError(f"Source/cache identity mismatch: {name}")
        content = target.read_bytes()
    else:
        with urllib.request.urlopen(asset["url"], timeout=40) as response:
            content = response.read(max_bytes + 1)
    if (
        len(content) != asset["size_bytes"]
        or hashlib.sha256(content).hexdigest() != asset["sha256"]
    ):
        raise ValueError(f"Source/cache identity mismatch: {name}")
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(target)
    return target


def select_patches(pages: list[dict], count: int = 10) -> list[dict]:
    """Select first distinct patch IDs in a finite, ordered annotation snapshot.

    Parameters
    ----------
    pages : list of dict
        Dataset-server responses containing row_idx, row and truncated_cells.
    count : int
        Positive patch count; insufficient coverage raises an error.

    Returns
    -------
    list of dict
        First annotation per selected patch, with original server row index.
        This is a technical convenience sample, not a retrieval benchmark.

    Raises
    ------
    ValueError
        Duplicate row/sample IDs, truncated/missing identity, or too few patches.
    """
    if count < 1:
        raise ValueError("count must be positive")
    rows = sorted((r for p in pages for r in p["rows"]), key=lambda r: r["row_idx"])
    if len({r["row_idx"] for r in rows}) != len(rows):
        raise ValueError("Duplicate server row indices")
    ids = [r["row"]["ID"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate annotation IDs")
    selected = {}
    for record in rows:
        row = record["row"]
        if (
            record["truncated_cells"]
            or not isinstance(row["patch_id"], str)
            or not row["patch_id"]
            or not isinstance(row["s1_name"], str)
            or not row["s1_name"]
        ):
            raise ValueError("Missing or truncated annotation identity")
        if (
            row["patch_id"] in selected
            and selected[row["patch_id"]]["s1_name"] != row["s1_name"]
        ):
            raise ValueError("Contradictory pair names within annotations")
        selected.setdefault(row["patch_id"], {"row_idx": record["row_idx"], **row})
    if len(selected) < count:
        raise ValueError("Not enough distinct patches in the bounded snapshot")
    return list(selected.values())[:count]


def match_metadata(patches: list[dict], metadata: pd.DataFrame) -> pd.DataFrame:
    """Verify exact S2 IDs and S1 pair names against independent v2 metadata.

    Parameters
    ----------
    patches : list of dict
        Unique patch_id and s1_name values; no coercion is performed.
    metadata : pandas.DataFrame
        Official v2 metadata with patch_id and s1_name columns.

    Returns
    -------
    pandas.DataFrame
        Joined rows in pilot order. Metadata absence is explicit as unknown.
        A matching pair verifies catalog identity, not raster alignment.

    Raises
    ------
    ValueError
        Duplicate/missing IDs or contradictory Sentinel-1 pair identities.
    """
    pilot = pd.DataFrame(patches)
    for frame in (pilot, metadata):
        if not {"patch_id", "s1_name"}.issubset(frame.columns):
            raise ValueError("Missing catalog identity columns")
        if not frame["s1_name"].map(lambda x: isinstance(x, str) and bool(x)).all():
            raise ValueError("S1 identities must be nonempty strings")
        if (
            frame["patch_id"].isna().any()
            or not frame["patch_id"].map(lambda x: isinstance(x, str) and bool(x)).all()
            or frame["patch_id"].duplicated().any()
        ):
            raise ValueError("Patch IDs must be unique nonempty strings")
    joined = pilot.merge(
        metadata,
        on="patch_id",
        how="left",
        sort=False,
        suffixes=("", "_metadata"),
        validate="one_to_one",
        indicator=True,
    )
    found = joined["_merge"] == "both"
    if (joined.loc[found, "s1_name"] != joined.loc[found, "s1_name_metadata"]).any():
        raise ValueError("Contradictory S1/S2 pairing")
    joined["catalog_status"] = found.map({True: "verified", False: "unknown"})
    return joined.drop(columns="_merge")


def load_pilot(manifest_path: Path, cache: Path) -> tuple[list[dict], pd.DataFrame]:
    """Load and validate cached official sources described by a pilot manifest.

    Parameters
    ----------
    manifest_path : Path
        Versioned manifest with assets and exact selected patch IDs.
    cache : Path
        Local cache; source assets are downloaded only within the byte budget.

    Returns
    -------
    tuple
        Selected original annotations and independently joined metadata.

    Raises
    ------
    ValueError
        Source drift, stale cache, or changed deterministic selection.
    """
    manifest = json.loads(manifest_path.read_text())
    paths = {a["name"]: fetch_asset(a, cache) for a in manifest["assets"]}
    pages = [json.loads(paths[n].read_text()) for n in manifest["text_pages"]]
    patches = select_patches(pages, manifest["patch_count"])
    if [r["patch_id"] for r in patches] != manifest["patch_ids"]:
        raise ValueError("Pilot selection differs from the frozen manifest")
    metadata = pd.read_parquet(paths["metadata.parquet"])
    return patches, match_metadata(patches, metadata)
