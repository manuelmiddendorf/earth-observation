"""Validate the fixed 25-patch extraction and measure coverage without models."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from earth_observation.archive_validation import (
    inspect_reference_selection,
    validate_raster_selection,
)
from earth_observation.benchmark import (
    coverage_tables,
    freeze_blockers,
    load_benchmark_record,
    spatial_split,
    verified_footprints,
)
from earth_observation.data import fetch_asset
from earth_observation.reference import evaluate_pilot, load_specifications
from earth_observation.validation import validate_development_sources


def validate(root: Path) -> dict:
    """Reproduce complete native-source and split coverage from local files only.

    Parameters
    ----------
    root : Path
        Repository with verified archives' extraction receipts, pinned catalog,
        native TIFFs and existing development caches. No downloads are started.

    Returns
    -------
    dict
        Completion measurements, exact spatial assignments and separate all,
        Development/Test main and both-present control coverage. Existing
        benchmark candidates and their loader protections are unchanged.

    Raises
    ------
    ValueError
        Changed selection, source identity, geometry or metadata contracts.
    FileNotFoundError
        Missing extraction receipts or required local source caches.
    """
    access = json.loads((root / "manifests/archive-data-access-v1.json").read_text())
    selection = root / access["selection_file"]
    if hashlib.sha256(selection.read_bytes()).hexdigest() != access["selection_sha256"]:
        raise ValueError("Predeclared selection changed")
    planned = pd.read_csv(selection)
    ids = planned.head(25).patch_id.tolist()
    if ids != access["planned_patch_ids"]:
        raise ValueError("Only the unchanged first 25 IDs are permitted")
    cache = root / "data/cache"
    raw = root / "data/raw"
    development_path = root / "manifests/development-validation-v2.json"
    development = json.loads(development_path.read_text())
    for asset in development["assets"] + development["raster_prefixes"]:
        if not (cache / asset["name"]).is_file():
            raise FileNotFoundError(f"Required local source missing: {asset['name']}")
    catalog_asset = next(
        a for a in development["assets"] if a["name"] == "metadata.parquet"
    )
    catalog = pd.read_parquet(fetch_asset(catalog_asset, cache))
    extraction_path = cache / "archive-access/extraction-results.json"
    extractions = json.loads(extraction_path.read_text())
    for result in extractions:
        asset = next(
            a for a in access["archives"] if a["name"] == result["archive"]["name"]
        )
        if any(result["archive"][key] != asset[key] for key in ["size_bytes", "md5"]):
            raise ValueError(
                "Extraction receipt differs from published archive identity"
            )
    annotations = access.get("text_annotations", [])
    for asset in access.get("text_assets", []):
        if not (cache / asset["name"]).is_file():
            raise FileNotFoundError("Pinned text snapshot is unavailable")
        fetch_asset(asset, cache)
    sources = validate_raster_selection(extractions, ids, raw, catalog, annotations)
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    map_receipt = next(
        r for r in extractions if r["archive"]["name"] == "Reference_Maps.tar.zst"
    )
    _, new_decisions, _ = inspect_reference_selection(
        map_receipt, ids, raw, rules, queries
    )
    models = json.loads((root / "config/frozen-models-v1.json").read_text())
    old_sources = validate_development_sources(
        development_path, cache, raw, models["rgb"]["upper_dn"]
    )
    _, old_decisions = evaluate_pilot(development_path, cache, raw, rules, queries)
    old_ids = old_decisions.index.tolist()
    if set(ids).intersection(old_ids):
        raise ValueError("New selection duplicates existing development identities")
    all_ids = old_ids + ids
    footprints = verified_footprints(all_ids, raw)
    duplicate_footprints, development_overlaps = [], []
    for new_id in ids:
        new = footprints.loc[new_id]
        for old_id in old_ids:
            old = footprints.loc[old_id]
            if (
                new.native_crs == old.native_crs
                and new.native_bounds == old.native_bounds
            ):
                duplicate_footprints.append({"new": new_id, "development": old_id})
            if max(new.left, old.left) < min(new.right, old.right) and max(
                new.bottom, old.bottom
            ) < min(new.top, old.top):
                development_overlaps.append({"new": new_id, "development": old_id})
    design = json.loads((root / "config/benchmark-design-v1.json").read_text())
    assignments = spatial_split(footprints, old_ids, design["spatial"])
    decisions = pd.concat([old_decisions, new_decisions])
    output = root / "outputs/archive-data-access-v1"
    output.mkdir(parents=True, exist_ok=True)
    sources.to_csv(output / "source-checks.csv")
    decisions.to_csv(output / "intent-states.csv")
    footprints.to_csv(output / "spatial-footprints.csv")
    assignments.to_csv(output / "spatial-assignments.csv")
    coverage, controls = {}, {}
    for split in ["all", "development", "test"]:
        selected_ids = (
            all_ids
            if split == "all"
            else assignments.index[assignments.split.eq(split)].tolist()
        )
        intent, family, relations, control_ids = coverage_tables(
            decisions.loc[selected_ids],
            queries,
            assignments.loc[selected_ids, "group_id"],
        )
        for name, frame in [
            ("intent", intent),
            ("family", family),
            ("relations", relations),
        ]:
            frame.to_csv(output / f"{split}-{name}.csv")
        coverage[split] = {
            "intent": json.loads(intent.reset_index().to_json(orient="records")),
            "family": json.loads(family.reset_index().to_json(orient="records")),
            "relations": json.loads(relations.reset_index().to_json(orient="records")),
        }
        controls[split] = control_ids
        if split == "test":
            blockers = freeze_blockers(
                intent, relations, design["coverage"], len(planned) - len(ids), queries
            )
    existing = load_benchmark_record(
        root / "manifests/benchmark-candidate-v2.json", root, require_frozen=False
    )
    if not sources.text_status.eq("verified").all():
        blockers.append(
            f"{int(sources.text_status.eq('unknown').sum())} selected patches lack "
            "matching text annotation evidence"
        )
    result = {
        "version": "archive-data-access-v1-completion",
        "source_tiffs": sum(len(r["members"]) for r in extractions),
        "created_files": sum(r["created_files"] for r in extractions),
        "reused_files": sum(r["reused_files"] for r in extractions),
        "selected_payload_bytes": sum(r["selected_bytes"] for r in extractions),
        "new_technically_validated_patches": len(sources),
        "new_text_verified_patches": int(sources.text_status.eq("verified").sum()),
        "new_text_unknown_patches": int(sources.text_status.eq("unknown").sum()),
        "existing_validated_patches": len(old_sources),
        "distinct_validated_patches": len(all_ids),
        "duplicate_patch_ids": 0,
        "duplicate_native_footprints_with_development": duplicate_footprints,
        "projected_envelope_overlaps_with_development": development_overlaps,
        "spatial_groups": int(assignments.group_id.nunique()),
        "split_counts": assignments.split.value_counts().to_dict(),
        "new_split_counts": assignments.loc[ids].split.value_counts().to_dict(),
        "new_images_in_anchored_development_groups": int(
            assignments.loc[ids, "group_id"]
            .isin(assignments.loc[old_ids, "group_id"])
            .sum()
        ),
        "spatial_assignments": assignments.reset_index().to_dict("records"),
        "coverage": coverage,
        "relation_controls": controls,
        "benchmark_status": existing["status"],
        "freeze_blockers": blockers,
        "no_model_execution": True,
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    summary = validate(Path(__file__).resolve().parents[1])
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in {"coverage", "spatial_assignments", "relation_controls"}
            },
            indent=2,
        )
    )
