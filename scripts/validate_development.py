"""Verify the small development extension and reproduce candidate v2, not a freeze."""

import json
from pathlib import Path

import pandas as pd
import rasterio

from earth_observation.benchmark import (
    coverage_tables,
    freeze_blockers,
    load_benchmark_record,
    reference_unknown_sources,
    spatial_split,
    verified_footprints,
    write_benchmark_record,
)
from earth_observation.encoding import file_digest
from earth_observation.reference import evaluate_pilot, load_specifications
from earth_observation.validation import validate_development_sources


def validate(root: Path) -> dict:
    """Reproduce technical development evidence and the versioned blocked revision.

    Parameters
    ----------
    root : Path
        Repository containing pinned development-v2 and unchanged design/configs.

    Returns
    -------
    dict
        Candidate v2 with 13 development images, zero test images and unchanged
        250-ID acquisition plan. Saves measured source/coverage diagnostics locally.
        No model, final test, parameter selection or statistics is executed.
    """
    old = load_benchmark_record(
        root / "manifests/benchmark-candidate-v1.json", root, False
    )
    manifest_path = root / "manifests/development-validation-v2.json"
    manifest = json.loads(manifest_path.read_text())
    design = json.loads((root / "config/benchmark-design-v1.json").read_text())
    models = json.loads((root / "config/frozen-models-v1.json").read_text())
    inventory = validate_development_sources(
        manifest_path, root / "data/cache", root / "data/raw", models["rgb"]["upper_dn"]
    )
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    _, decisions = evaluate_pilot(
        manifest_path, root / "data/cache", root / "data/raw", rules, queries
    )
    ids = decisions.index.tolist()
    footprints = verified_footprints(ids, root / "data/raw")
    assignments = spatial_split(footprints, ids, design["spatial"])
    intent, family, relations, controls = coverage_tables(
        decisions, queries, assignments.group_id
    )
    planned = pd.read_csv(root / "manifests/coverage-selection-v1.csv")
    if set(ids).intersection(planned.patch_id):
        raise ValueError("Supplemental development must not replace planned candidates")
    planned_present = 0
    from earth_observation.raster import patch_files

    for pid in planned.patch_id:
        paths = patch_files(
            pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        planned_present += int(all(path.is_file() for path in paths.values()))
    record = {k: v for k, v in old.items() if k != "content_sha256"}
    record.update(
        {
            "version": "benchmark-candidate-v2",
            "status": "blocked-not-frozen",
            "parent_version": old["version"],
            "parent_content_sha256": old["content_sha256"],
            "revision_reason": (
                "Three predeclared additional development images are "
                "genuinely loaded from existing official caches; source- "
                "scale suitability remains open. No threshold, query, "
                "sampling criterion or final test changed."
            ),
            "data_version": "BigEarthNet-v2 2.0.0 / development-validation-v2",
            "previous_development_ids": ids,
            "main_candidates": {"development": ids, "test": []},
            "relation_controls": {
                "development": controls,
                "test": {key: [] for key in controls},
            },
            "spatial_inventory": footprints.join(assignments)
            .reset_index()
            .to_dict("records"),
            "relevance": {
                "patch_ids": ids,
                "intent_ids": decisions.columns.tolist(),
                "states": decisions.to_numpy().tolist(),
            },
            "available_coverage": {
                "intent": intent.reset_index().to_dict("records"),
                "family": family.reset_index().to_dict("records"),
                "relations": relations.reset_index().to_dict("records"),
            },
            "source_validation": inventory.reset_index().to_dict("records"),
            "reference_suitability": {
                "status": (
                    "valid map-derived computations; visual adjacency accuracy "
                    "unverified"
                ),
                "storage_resolution_m": 10,
                "source_min_mapping_unit_ha": 25,
                "source_min_linear_width_m": 100,
                "patch_area_ha": 144,
                "presence_threshold_area_ha": 7.2,
                "decision": (
                    "Retain existing rules provisionally; no visual-boundary "
                    "truth or 60-m accuracy claim. MMU describes original "
                    "polygons, not clipped patch areas; minimum width is not "
                    "shared-boundary length."
                ),
                "source": "https://www.copernicus.eu/en/access-data/copernicus-services-catalogue/corine-land-cover-2018-vector-europe-6-yearly-version",
                "proposal": (
                    "Review an explicit map-agreement interpretation or "
                    "independent boundary reference before any visual relation- "
                    "performance claim; do not silently change query semantics."
                ),
            },
            "access": {
                **old["access"],
                "verified_development_patches": len(inventory),
                "additional_development_patches": len(
                    set(ids) - set(old["previous_development_ids"])
                ),
                "new_archive_bytes_this_revision": 0,
                "verified_new_planned_patches": 0,
                "validated_source_files": sum(
                    len(asset["members"]) for asset in manifest["raster_prefixes"]
                ),
                "planned_complete_files_present": planned_present,
                "independent_visual_boundary_truth_count": 0,
            },
            "development_gate_failures": freeze_blockers(
                intent, relations, design["coverage"], 0, queries
            ),
            "blockers": [
                (
                    "250 planned images still lack a verified bounded raster "
                    "route and native geometry"
                ),
                (
                    "All 13 available images are development in one spatial "
                    "component; no held-out test"
                ),
                "Both-present relation negatives are absent; fixed coverage gates fail",
                (
                    "Broader geographic development and visual-reference "
                    "suitability remain unverified"
                ),
            ],
        }
    )
    inputs = list(old["inputs_sha256"])
    inputs += [
        "manifests/development-validation-v2.json",
        "scripts/validate_development.py",
        "src/earth_observation/validation.py",
    ]
    inputs += [
        "data/raw/" + member["name"]
        for asset in manifest["raster_prefixes"]
        for member in asset["members"]
    ]
    record["inputs_sha256"] = {
        name: file_digest(root / name) for name in dict.fromkeys(inputs)
    }
    output = root / "outputs/development-validation-v2"
    output.mkdir(parents=True, exist_ok=True)
    for name, table in [
        ("sources", inventory),
        ("intent", intent),
        ("family", family),
        ("relations", relations),
        ("spatial", footprints.join(assignments)),
    ]:
        table.to_csv(output / f"{name}.csv")
    record["unknown_pixel_sources"] = []
    for pid in ids:
        files = patch_files(
            pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        with rasterio.open(files["reference"]) as raster:
            sources = reference_unknown_sources(raster.read(1, masked=True), rules)
        record["unknown_pixel_sources"].append({"patch_id": pid, **sources})
    write_benchmark_record(root / "manifests/benchmark-candidate-v2.json", record)
    print("Loaded and technically validated:", len(inventory), "development images")
    print("New archive bytes: 0; planned IDs acquired: 0; held-out test: 0")
    print(intent[["true", "false", "unknown"]].to_string())
    print(relations[["both_present", "true", "false", "unknown"]].to_string())
    return record


if __name__ == "__main__":
    validate(Path(__file__).resolve().parents[1])
