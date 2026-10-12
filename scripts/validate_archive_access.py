"""Validate the explicit planned extraction and measure coverage without models."""

import argparse
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
    write_benchmark_record,
)
from earth_observation.data import fetch_asset
from earth_observation.encoding import file_digest
from earth_observation.reference import evaluate_pilot, load_specifications
from earth_observation.text_access import original_annotation
from earth_observation.validation import validate_development_sources


def validate(
    root: Path,
    manifest_path: str = "manifests/archive-data-access-v1.json",
    write_record: bool = False,
) -> dict:
    """Reproduce complete native-source and split coverage from local files only.

    Parameters
    ----------
    root : Path
        Repository with verified archives' extraction receipts, pinned catalog,
        native TIFFs and existing development caches. No downloads are started.
    manifest_path : str
        Explicit versioned access manifest; original 25-ID evidence is preserved.
    write_record : bool
        Write the evidence-based v3 blocked candidate for the full selection.

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
    access = json.loads((root / manifest_path).read_text())
    selection = root / access["selection_file"]
    if hashlib.sha256(selection.read_bytes()).hexdigest() != access["selection_sha256"]:
        raise ValueError("Predeclared selection changed")
    planned = pd.read_csv(selection)
    first, last = access["selection_rows"]
    ids = planned.iloc[first - 1 : last].patch_id.tolist()
    if ids != access["planned_patch_ids"]:
        raise ValueError("Only the unchanged explicitly selected IDs are permitted")
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
    extraction_path = (
        root
        / access.get("cache_output", "data/cache/archive-access")
        / "extraction-results.json"
    )
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
    text_cache = root / access.get("text_cache_output", "data/cache")
    actual_annotations = []
    for asset in access.get("text_assets", []):
        if not (text_cache / asset["name"]).is_file():
            raise FileNotFoundError("Pinned text snapshot is unavailable")
        page = json.loads(fetch_asset(asset, text_cache).read_text())
        item = page["rows"][0]
        actual_annotations.append(
            original_annotation(page, item["row"]["patch_id"], item["row_idx"])
        )
    if actual_annotations != annotations:
        raise ValueError("Manifest annotations differ from actual pinned responses")
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
    anchors = access.get("previous_development_ids", old_ids)
    assignments = spatial_split(footprints, anchors, design["spatial"])
    decisions = pd.concat([old_decisions, new_decisions])
    repeated_native, overlapping_envelopes = [], []
    for position, left_id in enumerate(all_ids):
        left = footprints.loc[left_id]
        for right_id in all_ids[position + 1 :]:
            right = footprints.loc[right_id]
            if (
                left.native_crs == right.native_crs
                and left.native_bounds == right.native_bounds
            ):
                repeated_native.append([left_id, right_id])
            if max(left.left, right.left) < min(left.right, right.right) and max(
                left.bottom, right.bottom
            ) < min(left.top, right.top):
                overlapping_envelopes.append([left_id, right_id])
    countries = catalog.set_index("patch_id").loc[all_ids, "country"]
    geography = pd.crosstab(countries, assignments.split).to_dict("index")
    text_status = pd.Series("verified", index=all_ids)
    text_status.loc[ids] = sources.text_status
    split_text_counts = pd.crosstab(assignments.split, text_status).to_dict("index")
    output = root / access.get("completion_output", "outputs/archive-data-access-v1")
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
    blockers.append(
        "Fine relation reference suitability is unverified: generalized CLC2018 "
        "cannot establish visually verified 60-m contact truth"
    )
    result = {
        "version": access.get("version", "archive-data-access-v1") + "-completion",
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
        "repeated_native_footprints_all_pairs": repeated_native,
        "overlapping_projected_envelopes_all_pairs": overlapping_envelopes,
        "country_split_counts": geography,
        "split_text_counts": split_text_counts,
        "previous_development_ids": anchors,
        "previous_development_preserved": bool(
            assignments.loc[anchors, "split"].eq("development").all()
        ),
        "duplicate_native_footprints_with_development": duplicate_footprints,
        "projected_envelope_overlaps_with_development": development_overlaps,
        "spatial_groups": int(assignments.group_id.nunique()),
        "split_counts": assignments.split.value_counts().to_dict(),
        "new_split_counts": assignments.loc[ids].split.value_counts().to_dict(),
        "selected_images_in_previous_development_components": int(
            assignments.loc[ids, "group_id"]
            .isin(assignments.loc[anchors, "group_id"])
            .sum()
        ),
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
    if write_record:
        if access["selection_rows"] != [1, 250]:
            raise ValueError("Candidate v3 requires the full unchanged selection")
        inputs = [
            manifest_path,
            "manifests/coverage-selection-v1.csv",
            "manifests/development-validation-v2.json",
            "config/benchmark-design-v1.json",
            "config/reference-rules-v1.json",
            "config/query-specification-v1.json",
            "config/frozen-models-v1.json",
            "uv.lock",
            "src/earth_observation/archives.py",
            "src/earth_observation/archive_validation.py",
            "src/earth_observation/text_access.py",
            "src/earth_observation/data.py",
            "src/earth_observation/raster.py",
            "src/earth_observation/reference.py",
            "src/earth_observation/benchmark.py",
            "scripts/validate_archive_access.py",
            "scripts/fetch_archives.py",
            "scripts/fetch_selected_text.py",
            "data/cache/metadata.parquet",
        ]
        inputs.extend(
            "data/raw/" + member["name"]
            for receipt in extractions
            for member in receipt["members"]
        )
        inputs.extend(
            "data/raw/" + member["name"]
            for asset in development["raster_prefixes"]
            for member in asset["members"]
        )
        inputs.extend(
            str((text_cache / a["name"]).relative_to(root))
            for a in access.get("text_source_receipts", [])
        )
        record = {
            "version": "benchmark-candidate-v3",
            "status": "blocked-not-frozen",
            "blockers": blockers,
            "data_version": "BigEarthNet-v2 2.0.0 / archive-data-access-v2",
            "design_version": design["version"],
            "reference_version": rules["version"],
            "query_version": queries["version"],
            "model_specification": "config/frozen-models-v1.json",
            "evaluation_specification": "config/benchmark-design-v1.json#evaluation",
            "previous_development_ids": anchors,
            "main_candidates": {
                split: assignments.index[assignments.split.eq(split)].tolist()
                for split in ["development", "test"]
            },
            "relation_controls": {
                split: controls[split] for split in ["development", "test"]
            },
            "unassigned_selection": [],
            "spatial_inventory": footprints.join(assignments)
            .reset_index()
            .to_dict("records"),
            "relevance": {
                "patch_ids": all_ids,
                "intent_ids": decisions.columns.tolist(),
                "states": decisions.to_numpy().tolist(),
            },
            "coverage": coverage,
            "access": {
                "planned": len(ids),
                "technical": len(sources),
                "original_text_verified": result["new_text_verified_patches"],
                "text_unknown_ids": sources.index[
                    sources.text_status.eq("unknown")
                ].tolist(),
                "additional_archive_bytes": 0,
            },
            "reference_suitability": "Unverified fine-boundary visual truth; "
            "native geometry does not improve generalized CLC2018 accuracy",
            "inputs_sha256": {name: file_digest(root / name) for name in inputs},
        }
        write_benchmark_record(root / "manifests/benchmark-candidate-v3.json", record)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="manifests/archive-data-access-v1.json")
    parser.add_argument("--write-record", action="store_true")
    arguments = parser.parse_args()
    summary = validate(
        Path(__file__).resolve().parents[1], arguments.manifest, arguments.write_record
    )
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
