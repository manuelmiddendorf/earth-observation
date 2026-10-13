"""Validate native archive members separately from map accuracy and retrieval.

Reference-only measurements cannot assign a retrieval candidate or a test split.
All reference computations use the existing unchanged three-state implementation.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform

from earth_observation.archives import selected_raster_members
from earth_observation.data import match_metadata
from earth_observation.raster import (
    RGB_BANDS,
    inspect_patch,
    patch_files,
    read_rgb_bands,
)
from earth_observation.reference import evaluate_intents, summarize_reference


def inspect_reference_selection(
    extraction: dict,
    patch_ids: list[str],
    raw_root: Path,
    rules: dict,
    queries: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Check exact map bytes and measure provisional map-only intent evidence.

    Parameters
    ----------
    extraction : dict
        Reference archive extraction receipt with measured member sizes/SHA-256.
    patch_ids : list of str
        Unchanged predeclared IDs in selection order.
    raw_root : Path
        Native extracted files; rasters are read without resampling.
    rules, queries : dict
        Validated existing reference/query specifications, not caption answers.

    Returns
    -------
    tuple
        Map-source measurements (native CRS, extent, transform, shape, dtype,
        resolution in CRS units, NoData/mask count), patch × intent states and
        patch-keyed reference summaries. None establishes image/map alignment,
        visual truth, complete candidate validity or a spatial/test assignment.

    Raises
    ------
    ValueError
        Missing/extra/duplicate exact maps, changed member bytes, non-single-band
        or missing CRS, or the existing reference geometry contract fails.
    """
    names = [
        n for n in selected_raster_members(patch_ids) if n.startswith("Reference_Maps/")
    ]
    members = {member["name"]: member for member in extraction["members"]}
    if len(members) != len(extraction["members"]) or set(members) != set(names):
        raise ValueError("Reference receipt must match the exact selected maps")
    pairs = [
        tuple(i["classes"]) for i in queries["intents"] if i["kind"] == "adjacency"
    ]
    measurements, decisions, summaries = [], {}, {}
    for pid, name in zip(patch_ids, names, strict=True):
        path = raw_root / name
        member = members[name]
        content = path.read_bytes()
        if (
            len(content) != member["size_bytes"]
            or hashlib.sha256(content).hexdigest() != member["sha256"]
        ):
            raise ValueError("Extracted map source identity mismatch")
        with rasterio.open(path) as raster:
            if raster.count != 1 or raster.crs is None:
                raise ValueError("Expected one reference band and an explicit CRS")
            labels = raster.read(1, masked=True)
            summaries[pid] = summarize_reference(
                labels, raster.transform, raster.crs, rules, pairs
            )
            measurements.append(
                {
                    "patch_id": pid,
                    "crs": raster.crs.to_string(),
                    "height": raster.height,
                    "width": raster.width,
                    "dtype": raster.dtypes[0],
                    "resolution": list(raster.res),
                    "transform": list(raster.transform),
                    "bounds": list(raster.bounds),
                    "nodata": raster.nodata,
                    "masked_pixels": int(np.ma.getmaskarray(labels).sum()),
                }
            )
            decisions[pid] = evaluate_intents(summaries[pid], queries)
    table = pd.DataFrame.from_dict(decisions, orient="index")
    table.index.name = "patch_id"
    return pd.DataFrame(measurements).set_index("patch_id"), table, summaries


def validate_raster_selection(
    extractions: list[dict],
    patch_ids: list[str],
    raw_root: Path,
    metadata: pd.DataFrame,
    annotations: list[dict] | None = None,
) -> pd.DataFrame:
    """Verify exact RGB/map sources, native grids and available text identities.

    Parameters
    ----------
    extractions : list of dict
        Complete S2/map extraction receipts with original member sizes/SHA-256.
    patch_ids : list of str
        Unique predeclared IDs, in selection order.
    raw_root : Path
        Native extracted rasters; no resampling or repair is performed.
    metadata : pandas.DataFrame
        Checksum-pinned official catalog, with unique patch_id and S1 pair names.
    annotations : list of dict, optional
        Original text records, at most one selected record per patch. Missing
        records remain unknown. Supplied records must match catalog identities,
        country and WGS84 raster center to absolute tolerance 1e-8 degree.

    Returns
    -------
    pandas.DataFrame
        Per-patch technical result, separate text status, native grid/extent,
        band order, dtypes/NoData, masked counts and valid DN ranges. Finite
        uint16 RGB values and projected metre grids are required. Matching maps
        may have a different native resolution; it is recorded, never repaired.

    Raises
    ------
    ValueError
        Incomplete/duplicate/changed member identity, missing catalog identity,
        incompatible geometry or invalid/contradictory supplied text records.
    """
    names = selected_raster_members(patch_ids)
    original = [member for result in extractions for member in result["members"]]
    members = {member["name"]: member for member in original}
    if len(members) != len(original) or set(members) != set(names):
        raise ValueError("Receipts must contain exactly four unique TIFFs per patch")
    for name in names:
        content = (raw_root / name).read_bytes()
        if (
            len(content) != members[name]["size_bytes"]
            or hashlib.sha256(content).hexdigest() != members[name]["sha256"]
        ):
            raise ValueError("Extracted raster source identity mismatch")
    if metadata.patch_id.duplicated().any():
        raise ValueError("Official catalog patch IDs must be unique")
    catalog = metadata.set_index("patch_id")
    if not set(patch_ids).issubset(catalog.index):
        raise ValueError("Selected raster lacks an official catalog identity")
    text = {row["patch_id"]: row for row in (annotations or [])}
    if len(text) != len(annotations or []) or not set(text).issubset(patch_ids):
        raise ValueError("Text selection must have unique in-scope patch identities")
    if annotations:
        paired = match_metadata(annotations, metadata)
        if not paired.catalog_status.eq("verified").all():
            raise ValueError("Supplied annotations require verified catalog pairing")
    rows = []
    for pid in patch_ids:
        files = patch_files(
            pid, raw_root / "BigEarthNet-S2", raw_root / "Reference_Maps"
        )
        checked = inspect_patch(files)
        if checked["status"] != "aligned":
            raise ValueError("Complete aligned RGB/map pair required")
        rgb = read_rgb_bands({band: files[band] for band in RGB_BANDS})
        if rgb.dtype != np.uint16 or rgb.count() == 0 or not np.isfinite(rgb).all():
            raise ValueError("Expected finite, nonempty native uint16 RGB values")
        red, reference = checked["rasters"]["B04"], checked["rasters"]["reference"]
        crs = rasterio.crs.CRS.from_string(red["crs"])
        if not crs.is_projected or crs.linear_units_factor[1] != 1:
            raise ValueError("Native measurements require a projected metre CRS")
        residual = None
        if pid in text:
            row = text[pid]
            if row["country"] != catalog.loc[pid, "country"]:
                raise ValueError("Text country does not match official catalog")
            left, bottom, right, top = red["bounds"]
            longitude, latitude = transform(
                red["crs"], "EPSG:4326", [(left + right) / 2], [(bottom + top) / 2]
            )
            residual = max(
                abs(longitude[0] - row["longitude"]), abs(latitude[0] - row["latitude"])
            )
            if not np.isfinite(residual) or residual > 1e-8:
                raise ValueError("Text coordinate does not match native raster center")
        rows.append(
            {
                "patch_id": pid,
                "technical_status": "verified",
                "catalog_status": "verified",
                "country": catalog.loc[pid, "country"],
                "text_status": "verified" if pid in text else "unknown",
                "annotation_id": text[pid]["ID"] if pid in text else None,
                "text_center_error_deg": residual,
                "band_order": list(RGB_BANDS),
                "rgb_dtype": str(rgb.dtype),
                "rgb_shape": list(rgb.shape),
                "rgb_masked_values": int(np.ma.getmaskarray(rgb).sum()),
                "rgb_valid_min_dn": int(rgb.min()),
                "rgb_valid_max_dn": int(rgb.max()),
                "crs": red["crs"],
                "bounds": list(red["bounds"]),
                "transform": list(red["transform"]),
                "rgb_resolution_m": red["resolution"],
                "rgb_nodata": {
                    band: checked["rasters"][band]["nodata"] for band in RGB_BANDS
                },
                "map_shape": list(reference["shape"]),
                "map_dtype": reference["dtype"],
                "map_resolution_m": reference["resolution"],
                "map_nodata": reference["nodata"],
                "identical_rgb_map_grid": red["transform"] == reference["transform"]
                and red["shape"] == reference["shape"],
            }
        )
    return pd.DataFrame(rows).set_index("patch_id")
