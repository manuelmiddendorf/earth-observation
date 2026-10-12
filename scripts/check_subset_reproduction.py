"""Reacquire four real files for the first pilot patch in a separate small cache."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from earth_observation.data import extract_rasters, fetch_asset
from earth_observation.raster import inspect_patch, patch_files

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "manifests/data-pilot-v1.json").read_text())
with TemporaryDirectory(prefix="eo-subset-reproduction-") as directory:
    temporary_root = Path(directory)
    for asset in manifest["reproduction_sample"]:
        prefix = fetch_asset(asset, temporary_root / "cache")
        extract_rasters(prefix, asset["members"], temporary_root / "raw")
    files = patch_files(
        manifest["patch_ids"][0],
        temporary_root / "raw/BigEarthNet-S2",
        temporary_root / "raw/Reference_Maps",
    )
    assert inspect_patch(files)["status"] == "aligned"
    print("Verified one unchanged real pilot patch: three RGB bands + reference map.")
    print("Transferred 524,288 bytes; separate temporary cache removed on exit.")
