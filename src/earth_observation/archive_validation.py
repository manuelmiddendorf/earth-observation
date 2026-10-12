"""Inspect extracted map evidence while complete RGB validation is still pending.

Reference-only measurements cannot assign a retrieval candidate or a test split.
All reference computations use the existing unchanged three-state implementation.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from earth_observation.archives import selected_raster_members
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
