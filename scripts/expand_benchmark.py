"""Run the one authorized 2,000-ID local-archive feasibility step."""

import argparse
import fcntl
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from earth_observation.archives import (
    extract_archive_selection,
    selected_raster_members,
    verify_archive,
)
from earth_observation.benchmark import select_catalog


def main() -> None:
    """Extract once per local archive, then validate without models or text access."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["extract", "validate", "all"], default="all"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    access = json.loads((root / "manifests/archive-data-access-v3.json").read_text())
    design = json.loads((root / access["design_file"]).read_text())
    path = root / access["selection_file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != access["selection_sha256"]:
        raise ValueError("Predeclared 2000-ID selection changed")
    selection = pd.read_csv(path)
    catalog_path = root / "data/cache/metadata.parquet"
    pilot = json.loads((root / "manifests/data-pilot-v1.json").read_text())
    asset = next(a for a in pilot["assets"] if a["name"] == "metadata.parquet")
    if hashlib.sha256(catalog_path.read_bytes()).hexdigest() != asset["sha256"]:
        raise ValueError("Pinned catalog changed")
    pd.testing.assert_frame_equal(
        selection, select_catalog(pd.read_parquet(catalog_path), design["selection"])
    )
    ids = selection.patch_id.tolist()
    if len(ids) != 2000 or ids != access["planned_patch_ids"]:
        raise ValueError("Only the explicit unchanged 2000-ID inventory is authorized")
    for name, digest in access["provenance_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Earlier selection/access provenance changed")
    previous = pd.read_csv(root / access["previous_selection_file"])
    for country in previous.country.unique():
        if (
            previous.loc[previous.country.eq(country), "patch_id"].tolist()
            != selection.loc[selection.country.eq(country), "patch_id"]
            .head(25)
            .tolist()
        ):
            raise ValueError("Previous country prefixes changed")
    output = root / "data/cache/archive-access-v3"
    output.mkdir(parents=True, exist_ok=True)
    if args.stage in {"extract", "all"}:
        if shutil.disk_usage(root / "data/raw").free < access["budget_bytes"]:
            raise OSError("Less than the 256-MiB extraction reserve remains")
        store = root / "data/cache/archives"
        with (store / "acquisition.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for asset in access["archives"]:
                verify_archive(
                    store / asset["name"],
                    asset,
                    store / (asset["name"] + ".progress.json"),
                )
            names = selected_raster_members(ids)
            receipts, remaining = [], access["budget_bytes"]
            for asset in access["archives"]:
                prefix = asset["name"].removesuffix(".tar.zst") + "/"
                receipt = extract_archive_selection(
                    store / asset["name"],
                    asset,
                    [n for n in names if n.startswith(prefix)],
                    root / "data/raw",
                    selected_budget_bytes=remaining,
                    verification_receipt=store / (asset["name"] + ".progress.json"),
                )
                receipts.append(receipt)
                remaining -= receipt["selected_bytes"]
                (output / "extraction-results.json").write_text(
                    json.dumps(receipts, indent=2) + "\n"
                )
            if sum(len(r["members"]) for r in receipts) != 8000:
                raise ValueError("Exact 8000-TIFF completeness failed")
    if args.stage in {"validate", "all"}:
        from earth_observation.benchmark_expansion import assess_expansion

        result = assess_expansion(root)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "status",
                        "technical_patches",
                        "split_counts",
                        "spatial_groups",
                        "extraction",
                        "blockers",
                    )
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
