"""Assess the authorized map-agreement design on one fixed expanded inventory.

Historical specifications and their code pins remain unchanged. All numerical
coverage and spatial calculations reuse the existing canonical implementations.
Original source annotations are optional evidence, never relevance labels.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

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
from earth_observation.encoding import file_digest
from earth_observation.raster import patch_files
from earth_observation.reference import (
    evaluate_pilot,
    load_specifications,
    summarize_reference,
)
from earth_observation.validation import validate_development_sources


def verify_design_revision(design: dict, previous: dict) -> None:
    """Require explicitly authorized semantics without numerical gate changes.

    Parameters
    ----------
    design, previous : dict
        New map-agreement design and unchanged original design. Coverage, spatial
        protocol and analysis must be identical; the fixed quota becomes 200.

    Raises
    ------
    ValueError
        Changed numerical criteria, spatial/analysis policy or unapproved scope.
    """
    estimand = design.get("estimand", {})
    if (
        estimand.get("target") != "generalized-clc-map-agreement"
        or estimand.get("adjacency_target") != "mapped-four-neighbor-contact"
        or estimand.get("original_captions_required") is not False
    ):
        raise ValueError("Authorized mapped semantics and optional captions required")
    for key in ["coverage", "spatial", "evaluation"]:
        if design[key] != previous[key]:
            raise ValueError(f"Unchanged {key} protocol required")
    for key in ["seed", "population", "ordering", "exclude_development_tiles"]:
        if design["selection"][key] != previous["selection"][key]:
            raise ValueError("Original model-independent sampling frame changed")
    if (
        design["selection"]["target_count"] != 2000
        or design["selection"]["per_country"] != 200
        or design["selection"]["additional_raster_budget_bytes"] != 256 * 1024**2
        or design["version"] != "benchmark-design-v2"
    ):
        raise ValueError("Only the authorized fixed 2000-ID / 256-MiB scope is valid")


def spatial_transition_audit(
    footprints: pd.DataFrame, assignments: pd.DataFrame, previous: pd.DataFrame
) -> dict:
    """Check conservative overlap separation and retain previous Development.

    Parameters
    ----------
    footprints : pandas.DataFrame
        Verified native identities and EPSG:3035 envelope coordinates.
    assignments, previous : pandas.DataFrame
        New and earlier patch-indexed component/split tables. Earlier Test-side
        allocation is provisional; every previous Development ID must stay there.

    Returns
    -------
    dict
        Exact prior reassignments, merged groups, duplicate native footprints and
        conservative envelope-overlap pairs. Overlap is not native pixel overlap.

    Raises
    ------
    ValueError
        Missing historical identities, Development moved to Test or cross-split
        envelope overlap (spatial leakage).
    """
    if not set(previous.index).issubset(assignments.index):
        raise ValueError("Historical identities missing")
    dev = previous.index[previous.split.eq("development")]
    if not assignments.loc[dev, "split"].eq("development").all():
        raise ValueError("Previous Development must never enter Test")
    if assignments.groupby("group_id").split.nunique().gt(1).any():
        raise ValueError("Spatial component leaks across splits")
    ids = footprints.index.tolist()
    boxes = footprints[["left", "bottom", "right", "top"]].to_numpy()
    overlaps = []
    for i, pid in enumerate(ids):
        other = boxes[i + 1 :]
        mask = (
            np.maximum(boxes[i, 0], other[:, 0]) < np.minimum(boxes[i, 2], other[:, 2])
        ) & (
            np.maximum(boxes[i, 1], other[:, 1]) < np.minimum(boxes[i, 3], other[:, 3])
        )
        for j in np.flatnonzero(mask) + i + 1:
            pair = [pid, ids[j]]
            if assignments.loc[pair, "split"].nunique() != 1:
                raise ValueError("Overlapping envelopes leak across splits")
            overlaps.append(pair)
    native = {}
    for pid, row in footprints.iterrows():
        native.setdefault((row.native_crs, tuple(row.native_bounds)), []).append(pid)
    changed, merged = [], []
    for pid, row in previous.iterrows():
        current = assignments.loc[pid]
        if row.group_id != current.group_id or row.split != current.split:
            changed.append(
                {
                    "patch_id": pid,
                    "old_group": row.group_id,
                    "new_group": current.group_id,
                    "old_split": row.split,
                    "new_split": current.split,
                }
            )
    for group, frame in assignments.loc[previous.index].groupby("group_id"):
        old_groups = sorted(previous.loc[frame.index, "group_id"].unique())
        if len(old_groups) > 1:
            merged.append({"new_group": group, "old_groups": old_groups})
    return {
        "prior_assignment_changes": changed,
        "merged_previous_groups": merged,
        "duplicate_native_footprints": [v for v in native.values() if len(v) > 1],
        "projected_envelope_overlaps": overlaps,
        "previous_development_preserved": True,
    }


def assess_expansion(root: Path) -> dict:
    """Validate all real sources and write an evidence-based candidate v4.

    Parameters
    ----------
    root : Path
        Repository with the fixed selection, local extraction receipts and data.
        No network, original-text requests, models or rankings are used.

    Returns
    -------
    dict
        Actual source/split/coverage measurements and explicit freeze decision.
        Text status distinguishes verified, source-absent and unrequested.

    Raises
    ------
    ValueError
        Changed source/config/selection, raster identity or spatial leakage.
    """
    access_path = root / "manifests/archive-data-access-v3.json"
    access = json.loads(access_path.read_text())
    design = json.loads((root / access["design_file"]).read_text())
    verify_design_revision(
        design, json.loads((root / "config/benchmark-design-v1.json").read_text())
    )
    old_record = load_benchmark_record(
        root / "manifests/benchmark-candidate-v3.json", root, require_frozen=False
    )
    previous = pd.DataFrame(old_record["spatial_inventory"]).set_index("patch_id")
    ids = access["planned_patch_ids"]
    selection = pd.read_csv(root / access["selection_file"])
    if (
        ids != selection.patch_id.tolist()
        or file_digest(root / access["selection_file"]) != access["selection_sha256"]
    ):
        raise ValueError("Predeclared expanded selection changed")
    old_access = json.loads((root / access["text_provenance"]).read_text())
    # Historical record v3 verifies every pinned original text response too.
    annotations = old_access["text_annotations"]
    extraction_path = root / "data/cache/archive-access-v3/extraction-results.json"
    extractions = json.loads(extraction_path.read_text())
    if len(extractions) != 2:
        raise ValueError("Both complete selected archive receipts required")
    for receipt in extractions:
        expected = next(
            a for a in access["archives"] if a["name"] == receipt["archive"]["name"]
        )
        for key in ["md5", "size_bytes"]:
            if receipt["archive"][key] != expected[key]:
                raise ValueError("Archive provenance changed")
    raw = root / "data/raw"
    catalog = pd.read_parquet(root / "data/cache/metadata.parquet")
    sources = validate_raster_selection(extractions, ids, raw, catalog, annotations)
    absent = set(old_access["text_evidence"]["missing_patch_ids"])
    sources["original_text_availability"] = [
        "verified"
        if pid in {a["patch_id"] for a in annotations}
        else "source-absent"
        if pid in absent
        else "not-requested"
        for pid in ids
    ]
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    maps = next(
        r for r in extractions if r["archive"]["name"] == "Reference_Maps.tar.zst"
    )
    map_sources, new_states, map_summaries = inspect_reference_selection(
        maps, ids, raw, rules, queries
    )
    development = root / "manifests/development-validation-v2.json"
    old_sources = validate_development_sources(
        development, root / "data/cache", raw, 3000
    )
    _, old_states = evaluate_pilot(
        development, root / "data/cache", raw, rules, queries
    )
    if set(ids) & set(old_states.index):
        raise ValueError("Expanded inventory duplicates initial Development IDs")
    states = pd.concat([old_states, new_states])
    footprints = verified_footprints(states.index.tolist(), raw)
    assignments = spatial_split(
        footprints, access["previous_development_ids"], design["spatial"]
    )
    audit = spatial_transition_audit(footprints, assignments, previous)
    # Country/Development selection precedes this diagnostic and uses no labels.
    semantic_examples = []
    pairs = [
        tuple(i["classes"]) for i in queries["intents"] if i["kind"] == "adjacency"
    ]
    for country in ["Austria", "Belgium", "Finland"]:
        pid = next(
            p
            for p in ids
            if sources.loc[p, "country"] == country
            and assignments.loc[p, "split"] == "development"
        )
        files = patch_files(pid, raw / "BigEarthNet-S2", raw / "Reference_Maps")
        with rasterio.open(files["reference"]) as raster:
            labels = raster.read(1, masked=True)
            summary = summarize_reference(
                labels, raster.transform, raster.crs, rules, pairs
            )
            pixel_area = abs(raster.transform.a * raster.transform.e)
            raw_counts = {
                int(code): int(count)
                for code, count in zip(
                    *np.unique(labels.compressed(), return_counts=True), strict=True
                )
            }
            for name, definition in rules["classes"].items():
                mapped_count = sum(
                    raw_counts.get(code, 0) for code in definition["codes"]
                )
                if (
                    summary["classes"][name]["area_lower_m2"]
                    != mapped_count * pixel_area
                ):
                    raise ValueError("CLC aggregation differs from raw category counts")
            if summary["total_area_m2"] != labels.size * pixel_area:
                raise ValueError(
                    "Presence denominator must remain the entire native patch"
                )
            for a, b in pairs:
                encoded = np.zeros(labels.shape, dtype=np.uint8)
                for value, name in [(1, a), (2, b)]:
                    encoded[
                        np.isin(labels.data, rules["classes"][name]["codes"])
                        & ~np.ma.getmaskarray(labels)
                    ] = value
                # Products equal two only for category 1 next to category 2.
                # This independent raw-category check counts no diagonal edges.
                contact = (
                    np.count_nonzero(encoded[:, :-1] * encoded[:, 1:] == 2)
                    * abs(raster.transform.e)
                    + np.count_nonzero(encoded[:-1, :] * encoded[1:, :] == 2)
                    * raster.transform.a
                )
                if (
                    contact
                    != summary["pairs"][tuple(sorted((a, b)))]["boundary_lower_m"]
                ):
                    raise ValueError(
                        "Mapped contact differs from raw categorical edges"
                    )
            semantic_examples.append(
                {
                    "patch_id": pid,
                    "country": country,
                    "raw_clc_pixel_counts": raw_counts,
                    "full_patch_area_m2": summary["total_area_m2"],
                    "mapped_fractions": {
                        k: v["fraction_lower"] for k, v in summary["classes"].items()
                    },
                    "mapped_contact_m": {
                        "|".join(k): v["boundary_lower_m"]
                        for k, v in summary["pairs"].items()
                    },
                }
            )
    output = root / "outputs/archive-data-access-v3"
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in [
        ("source-checks", sources),
        ("intent-states", states),
        ("spatial-footprints", footprints),
        ("spatial-assignments", assignments),
    ]:
        frame.to_csv(output / f"{name}.csv")
    coverage, controls, blockers = {}, {}, []
    for split in ["all", "development", "test"]:
        subset = (
            states.index
            if split == "all"
            else assignments.index[assignments.split.eq(split)]
        )
        intent, family, relation, control = coverage_tables(
            states.loc[subset], queries, assignments.loc[subset, "group_id"]
        )
        coverage[split] = {
            "intent": intent.reset_index().to_dict("records"),
            "family": family.reset_index().to_dict("records"),
            "relations": relation.reset_index().to_dict("records"),
        }
        controls[split] = control
        for name, frame in [
            ("intent", intent),
            ("family", family),
            ("relations", relation),
        ]:
            frame.to_csv(output / f"{split}-{name}.csv")
        if split == "test":
            blockers = freeze_blockers(intent, relation, design["coverage"], 0, queries)
    unknown_references = [
        {
            "patch_id": pid,
            "split": assignments.loc[pid, "split"],
            "unknown_area_m2": map_summaries[pid]["unknown_area_m2"],
            "unknown_fraction": map_summaries[pid]["unknown_area_m2"]
            / map_summaries[pid]["total_area_m2"],
            "unexpected_codes": map_summaries[pid]["unexpected_codes"],
            "masked_pixels": int(map_sources.loc[pid, "masked_pixels"]),
        }
        for pid in ids
        if new_states.loc[pid].eq("unknown").any()
    ]
    map_sources.to_csv(output / "map-source-checks.csv")
    status = "blocked-not-frozen" if blockers else "frozen"
    countries = catalog.set_index("patch_id").loc[states.index, "country"]
    availability = pd.Series("verified", index=states.index)
    availability.loc[ids] = sources.original_text_availability
    result = {
        "version": "archive-data-access-v3-completion",
        "design_version": design["version"],
        "status": status,
        "technical_patches": len(states),
        "planned_validated": len(sources),
        "old_development_validated": len(old_sources),
        "text_availability": availability.value_counts().to_dict(),
        "unknown_reference_decisions": unknown_references,
        "split_counts": assignments.split.value_counts().to_dict(),
        "spatial_groups": int(assignments.group_id.nunique()),
        "country_split_counts": pd.crosstab(countries, assignments.split).to_dict(
            "index"
        ),
        "extraction": {
            "created_files": sum(r["created_files"] for r in extractions),
            "reused_files": sum(r["reused_files"] for r in extractions),
            "selected_bytes": sum(r["selected_bytes"] for r in extractions),
        },
        "spatial_audit": audit,
        "coverage": coverage,
        "relation_controls": controls,
        "blockers": blockers,
        "no_model_execution": True,
        "reference_validation": {
            "status": "verified-for-mapped-semantics",
            "development_examples": semantic_examples,
            "interpretation": "Native categorical CLC aggregation/full-area counts; "
            "four-neighbor mapped edge metres, not visible-object boundaries",
        },
        "reference_target": (
            "Generalized CLC map agreement; not independent visible truth"
        ),
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    inputs = [
        str(access_path.relative_to(root)),
        access["design_file"],
        access["selection_file"],
        "src/earth_observation/benchmark_expansion.py",
        "scripts/expand_benchmark.py",
        "config/reference-rules-v1.json",
        "config/query-specification-v1.json",
        "config/frozen-models-v1.json",
        "uv.lock",
        "manifests/benchmark-candidate-v3.json",
    ]
    pins = old_record["inputs_sha256"] | {
        name: file_digest(root / name) for name in inputs
    }
    pins.update(
        {
            "data/raw/" + m["name"]: m["sha256"]
            for r in extractions
            for m in r["members"]
        }
    )
    record = {
        "version": "benchmark-candidate-v4",
        "status": status,
        "blockers": blockers,
        "design_version": design["version"],
        "design_file": access["design_file"],
        "reference_version": rules["version"],
        "query_version": queries["version"],
        "previous_development_ids": access["previous_development_ids"],
        "main_candidates": {
            s: assignments.index[assignments.split.eq(s)].tolist()
            for s in ["development", "test"]
        },
        "relation_controls": {s: controls[s] for s in ["development", "test"]},
        "unassigned_selection": [],
        "spatial_inventory": footprints.join(assignments)
        .reset_index()
        .to_dict("records"),
        "relevance": {
            "patch_ids": states.index.tolist(),
            "intent_ids": states.columns.tolist(),
            "states": states.to_numpy().tolist(),
        },
        "coverage": coverage,
        "source_text_availability": result["text_availability"],
        "estimand": design["estimand"],
        "reference_validation": result["reference_validation"],
        "model_specification": "config/frozen-models-v1.json",
        "evaluation_specification": access["design_file"] + "#evaluation",
        "inputs_sha256": pins,
    }
    write_benchmark_record(root / "manifests/benchmark-candidate-v4.json", record)
    return result


def load_expanded_benchmark(
    path: Path, root: Path, require_frozen: bool = True
) -> dict:
    """Check revised semantics and retain canonical freeze/leakage protection.

    Parameters
    ----------
    path, root : Path
        Expanded v4 record and repository holding its pinned inputs.
    require_frozen : bool
        Default refuses blocked records. A frozen record additionally requires
        mapped-semantics validation and an independently reconstructed native
        spatial split. Missing captions do not filter main candidates.

    Returns
    -------
    dict
        Integrity-checked expanded record with explicit map-agreement estimand.

    Raises
    ------
    ValueError
        Changed criteria/estimand, unsupported revision, invalid reference
        suitability, missing inventory, coverage failure or spatial leakage.
    """
    record = load_benchmark_record(path, root, require_frozen=False)
    if (
        record["version"] != "benchmark-candidate-v4"
        or record["design_file"] != "config/benchmark-design-v2.json"
    ):
        raise ValueError("Explicit expanded design revision required")
    design = json.loads((root / record["design_file"]).read_text())
    verify_design_revision(
        design, json.loads((root / "config/benchmark-design-v1.json").read_text())
    )
    if record["estimand"] != design["estimand"]:
        raise ValueError("Map-agreement estimand changed")
    if require_frozen:
        if record["reference_validation"]["status"] != "verified-for-mapped-semantics":
            raise ValueError("Mapped reference semantics are unverified")
        # The numerical policies are exactly v1's: reuse its guarded loader.
        load_benchmark_record(path, root, require_frozen=True)
        inventory = pd.DataFrame(record["spatial_inventory"]).set_index("patch_id")
        footprints = verified_footprints(inventory.index.tolist(), root / "data/raw")
        expected = spatial_split(
            footprints, record["previous_development_ids"], design["spatial"]
        )
        if not expected[["group_id", "split"]].equals(inventory[["group_id", "split"]]):
            raise ValueError("Recorded spatial split differs from native geometry")
    return record
