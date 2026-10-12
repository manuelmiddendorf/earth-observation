"""Acquire authorized archives and extract the explicit predeclared batch."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import pandas as pd

from earth_observation.archives import (
    download_archive,
    extract_archive_selection,
    selected_raster_members,
    verify_archive,
)
from earth_observation.benchmark import select_catalog
from earth_observation.data import fetch_asset


def main() -> None:
    """Run one sequential, locked download/extraction with explicit local outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["download", "extract", "all"], default="all"
    )
    parser.add_argument("--manifest", default="manifests/archive-data-access-v1.json")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / arguments.manifest).read_text())
    selection = root / manifest["selection_file"]
    if (
        hashlib.sha256(selection.read_bytes()).hexdigest()
        != (manifest["selection_sha256"])
    ):
        raise ValueError("Predeclared coverage selection changed")
    pilot = json.loads((root / "manifests/data-pilot-v1.json").read_text())
    catalog_asset = next(a for a in pilot["assets"] if a["name"] == "metadata.parquet")
    catalog = pd.read_parquet(fetch_asset(catalog_asset, root / "data/cache"))
    design = json.loads((root / "config/benchmark-design-v1.json").read_text())
    selected = pd.read_csv(selection)
    pd.testing.assert_frame_equal(
        selected, select_catalog(catalog, design["selection"])
    )
    first, last = manifest["selection_rows"]
    if [first, last] not in ([1, 25], [1, 250]):
        raise ValueError("Unsupported selection scope")
    ids = selected.iloc[first - 1 : last].patch_id.tolist()
    names = selected_raster_members(ids)
    if (
        len(ids) != last
        or len(names) != 4 * last
        or ids != manifest["planned_patch_ids"]
        or names != manifest["required_members"]
    ):
        raise ValueError("Only the unchanged explicitly authorized IDs are permitted")
    store = root / "data/cache/archives"
    output = root / manifest.get("cache_output", "data/cache/archive-access")
    store.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    with (store / "acquisition.lock").open("a") as lock:
        # A second invocation must not append to the same partial file.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if last == 250 and arguments.stage != "extract":
            raise ValueError("Full selection uses existing archives only")
        if arguments.stage in {"download", "all"}:
            downloads = []
            for asset in manifest["archives"]:
                downloads.append(download_archive(asset, store))
                (output / "latest-download-results.json").write_text(
                    json.dumps(downloads, indent=2) + "\n"
                )
        if arguments.stage in {"extract", "all"}:
            # Verify both complete sources before using any new partial source.
            for asset in manifest["archives"]:
                verify_archive(
                    store / asset["name"],
                    asset,
                    store / (asset["name"] + ".progress.json"),
                )
            extracted = []
            remaining_budget = design["selection"]["additional_raster_budget_bytes"]
            for asset in manifest["archives"]:
                prefix = asset["name"].removesuffix(".tar.zst") + "/"
                exact_names = [n for n in names if n.startswith(prefix)]
                extracted.append(
                    extract_archive_selection(
                        store / asset["name"],
                        asset,
                        exact_names,
                        root / "data/raw",
                        selected_budget_bytes=remaining_budget,
                        verification_receipt=store / (asset["name"] + ".progress.json"),
                    )
                )
                remaining_budget -= extracted[-1]["selected_bytes"]
                (output / "extraction-results.json").write_text(
                    json.dumps(extracted, indent=2) + "\n"
                )
            observed = [m["name"] for result in extracted for m in result["members"]]
            if len(observed) != len(names) or set(observed) != set(names):
                raise ValueError("Exact selected-TIFF completeness check failed")
            print(
                "Verified archives and exact selected TIFFs; raster validation is next."
            )


if __name__ == "__main__":
    main()
