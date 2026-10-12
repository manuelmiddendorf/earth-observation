"""Bounded source caching and explicit text-to-patch identity validation."""

import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path

import pandas as pd
import zstandard


def fetch_asset(asset: dict, cache: Path, max_bytes: int = 5_000_000) -> Path:
    """Cache an exact source snapshot without accepting stale or oversized data.

    Parameters
    ----------
    asset : dict
        URL, simple cache filename, byte size, and SHA-256 of expected content.
        Optional byte_range and archive_size_bytes require an exact HTTP 206.
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
        headers = {}
        if "byte_range" in asset:
            start, end = asset["byte_range"]
            if start < 0 or end - start + 1 != asset["size_bytes"]:
                raise ValueError("Inconsistent byte range and asset size")
            headers["Range"] = f"bytes={start}-{end}"
        request = urllib.request.Request(asset["url"], headers=headers)
        with urllib.request.urlopen(request, timeout=40) as response:
            if "byte_range" in asset:
                expected_range = f"bytes {start}-{end}/{asset['archive_size_bytes']}"
                if (
                    response.status != 206
                    or response.headers.get("Content-Range") != expected_range
                ):
                    raise ValueError("Server did not honor the exact archive range")
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


def extract_rasters(
    prefix: Path, members: list[dict], raw_root: Path, max_tar_bytes: int = 8_000_000
) -> list[Path]:
    """Extract only complete, checksum-pinned TIFF members from a zstd tar prefix.

    Parameters
    ----------
    prefix : Path
        Verified partial archive starting at byte zero; not a complete zstd frame.
    members : list of dict
        Exact archive member names, sizes and SHA-256 digests from the pilot.
    raw_root : Path
        Local destination containing BigEarthNet-S2 and Reference_Maps roots.
    max_tar_bytes : int
        Limit on scanned uncompressed tar extent, including skipped members.

    Returns
    -------
    list of Path
        Validated TIFF paths in requested order. Existing matching files are
        reused. Only selected members are persisted; other bands are skipped.

    Raises
    ------
    ValueError
        Incomplete prefix, unsafe/duplicate member, links, excessive scan size,
        checksum mismatch or incompatible existing data. Never silently repairs
        a cache. Prefix hashes do not verify the full archive's published MD5.
    """
    expected = {m["name"]: m for m in members}
    if len(expected) != len(members) or not members:
        raise ValueError("Expected unique, nonempty raster members")
    paths = []
    for name in expected:
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in {"BigEarthNet-S2", "Reference_Maps"}
            or relative.suffix != ".tif"
        ):
            raise ValueError("Unsafe raster member path")
        paths.append(raw_root / relative)
    present = {}
    for member, path in zip(members, paths, strict=True):
        if path.exists():
            content = path.read_bytes()
            if (
                len(content) != member["size_bytes"]
                or hashlib.sha256(content).hexdigest() != member["sha256"]
            ):
                raise ValueError(f"Existing raster identity mismatch: {member['name']}")
            present[member["name"]] = content
    if len(present) == len(expected):
        return paths
    found = {}
    try:
        with prefix.open("rb") as compressed:
            with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
                with tarfile.open(fileobj=stream, mode="r|") as archive:
                    for member in archive:
                        if archive.offset > max_tar_bytes:
                            raise ValueError("Uncompressed tar scan exceeds budget")
                        if member.name not in expected:
                            continue
                        if not member.isfile() or member.name in found:
                            raise ValueError("Selected raster is a link or duplicate")
                        specification = expected[member.name]
                        if member.size != specification["size_bytes"]:
                            raise ValueError("Raster member size mismatch")
                        with archive.extractfile(member) as source:
                            content = source.read(member.size + 1)
                        if (
                            len(content) != member.size
                            or hashlib.sha256(content).hexdigest()
                            != specification["sha256"]
                        ):
                            raise ValueError("Raster member checksum mismatch")
                        found[member.name] = content
                        if len(found) == len(expected):
                            break
    except (tarfile.TarError, zstandard.ZstdError) as error:
        raise ValueError(
            "Archive prefix does not contain complete pilot members"
        ) from error
    if len(found) != len(expected):
        raise ValueError("Archive prefix does not contain all requested rasters")
    for name, content in found.items():
        path = raw_root / name
        if name not in present:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tif.part")
            temporary.write_bytes(content)
            temporary.replace(path)
    return paths


def acquire_rasters(manifest_path: Path, cache: Path, raw_root: Path) -> list[Path]:
    """Acquire the unchanged ten-patch pilot through two finite archive prefixes.

    Parameters
    ----------
    manifest_path : Path
        Pilot manifest containing raster_prefixes and exact member inventories.
    cache : Path
        Local checksum-validated prefix cache.
    raw_root : Path
        Local extracted raster directory, excluded from version control.

    Returns
    -------
    list of Path
        Thirty RGB files and ten native reference maps. No full archive is read.

    Raises
    ------
    ValueError
        Source drift, ignored HTTP ranges, incomplete or mismatched members.
    """
    manifest = json.loads(manifest_path.read_text())
    paths = []
    for asset in manifest["raster_prefixes"]:
        prefix = fetch_asset(asset, cache)
        paths.extend(extract_rasters(prefix, asset["members"], raw_root))
    return paths
