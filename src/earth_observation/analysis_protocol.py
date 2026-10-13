"""Validate the authorized partial-reference protocol and freeze existing data.

This module implements readiness and provenance contracts, never final ranking
metrics. Historical candidate validators and their pinned source bytes remain
unchanged. Native map states and spatial assignments are checked independently.
"""

import copy
import json
from pathlib import Path

import pandas as pd
import rasterio

from earth_observation.benchmark import (
    coverage_tables,
    load_benchmark_record,
    spatial_split,
    verified_footprints,
    write_benchmark_record,
)
from earth_observation.benchmark_expansion import load_expanded_benchmark
from earth_observation.encoding import file_digest
from earth_observation.raster import patch_files
from earth_observation.reference import (
    evaluate_intents,
    load_specifications,
    summarize_reference,
)

# Supported semantics are explicit rather than inferred from a "frozen" label.
PROTOCOL_CONTRACT = {
    "version": "analysis-protocol-v1",
    "candidate_policy": "complete-unfiltered-test-including-unknown",
    "completion_space": "per-intent-all-binary-unknown-assignments",
    "max_unknown_per_intent": 12,
    "precision_at_10": "exact-known-top10-plus-unknown-top10-bounds",
    "average_precision": "exact-enumeration-with-assignment-dependent-denominator",
    "zero_positive_assignment": "block-ap-analysis-if-any-completion-has-zero",
    "fully_known_output": "exact-value",
    "partially_known_output": "reference-uncertainty-interval-even-if-collapsed",
    "paraphrase_aggregation": "mean-before-extrema-with-shared-intent-assignment",
    "intent_aggregation": "equal-intent-mean-of-marginal-bounds-conservative-envelope",
    "paired_difference": "remoteclip-minus-clip-under-identical-assignment",
    "relation_controls": "exploratory-separate-both-known-present",
    "primary_statistics": "paired-per-intent-and-descriptive-equal-intent-mean",
    "family_bootstrap": "optional-restricted-sensitivity-not-confidence-evidence",
    "uncertainty_types": ["reference", "paraphrase-variation", "statistical"],
    "specification_document": "docs/ANALYSIS_PROTOCOL.md",
}


def validate_analysis_revision(design: dict, previous: dict, protocol: dict) -> None:
    """Require only the authorized uncertainty/control/statistics revision.

    Parameters
    ----------
    design, previous : dict
        New v3 and historical v2 designs. Sampling, spatial rules, estimand,
        metric/tie/query policies and all main count/dispersion minima stay fixed.
    protocol : dict
        Supported machine-readable completion and aggregation contract; unknown
        limit is exactly twelve (4,096 assignments), not a permission to sample.

    Raises
    ------
    ValueError
        Unsupported protocol, relaxed count gates or any unauthorized change.
    """
    if (
        protocol != PROTOCOL_CONTRACT
        or type(protocol.get("max_unknown_per_intent")) is not int
    ):
        raise ValueError("Unsupported analysis protocol or unknown enumeration limit")
    if (
        design.get("version") != "benchmark-design-v3"
        or design.get("previous_version") != previous["version"]
        or previous["version"] != "benchmark-design-v2"
    ):
        raise ValueError("Explicit design-v3 revision of design-v2 required")
    for key in ["selection", "spatial", "estimand", "changes"]:
        if design[key] != previous[key]:
            raise ValueError(f"Unchanged {key} required")
    expected = previous["coverage"].copy()
    del expected["main_required_judged_fraction"]
    expected.update(
        main_reference_policy=protocol["version"],
        control_role="exploratory",
        rationale=design["coverage"]["rationale"],
    )
    if design["coverage"] != expected:
        raise ValueError(
            "Main coverage minima and historical control targets must stay"
        )
    expected = copy.deepcopy(previous["evaluation"])
    expected.update(
        analysis_protocol="config/analysis-protocol-v1.json",
        unknown=protocol["completion_space"],
        controls=protocol["relation_controls"],
    )
    expected["bootstrap"].update(
        role=protocol["family_bootstrap"],
        interpretation=(
            "Two direct families: sensitivity only; no general superiority CI"
        ),
    )
    if design["evaluation"] != expected:
        raise ValueError("Only authorized analysis/control/statistical changes allowed")


def analysis_readiness(
    decisions: pd.DataFrame,
    queries: dict,
    groups: pd.Series,
    design: dict,
    protocol: dict,
) -> dict:
    """Check main feasibility and exact-enumeration readiness without rankings.

    Parameters
    ----------
    decisions : pandas.DataFrame
        Complete candidate-by-intent true/false/unknown matrix, unchanged order.
    queries : dict
        Validated fixed intent/formulation specification.
    groups : pandas.Series
        Verified spatial group IDs in exact candidate order.
    design, protocol : dict
        Revision-validated v3 design and supported analysis contract.

    Returns
    -------
    dict
        Main blockers, per-intent reference coverage/assignment counts and
        separate exploratory relation coverage and candidate IDs. Zero known
        positives admits an all-zero completion and blocks AP; no unknown is
        recoded or removed. Controls do not satisfy confirmatory relation gates.

    Raises
    ------
    ValueError
        Unsupported protocol or malformed three-state coverage input.
    """
    if (
        protocol != PROTOCOL_CONTRACT
        or type(protocol.get("max_unknown_per_intent")) is not int
    ):
        raise ValueError("Unsupported analysis protocol")
    intent, _, relations, controls = coverage_tables(decisions, queries, groups)
    policy = design["coverage"]
    blockers, uncertainty = [], []
    for intent_id, row in intent.iterrows():
        positive, negative, unknown = (
            int(row[k]) for k in ["true", "false", "unknown"]
        )
        total = positive + negative + unknown
        for value, key in [
            (total, "main_min_candidates"),
            (positive, "main_min_positive"),
            (negative, "main_min_negative"),
            (row.spatial_groups, "main_min_groups"),
            (
                row.positive_outside_largest_group,
                "main_min_positive_outside_largest_group",
            ),
        ]:
            if value < policy[key]:
                blockers.append(f"{intent_id}: {key} {value} < {policy[key]}")
        if unknown > protocol["max_unknown_per_intent"]:
            blockers.append(f"{intent_id}: unknown enumeration limit exceeded")
        if positive == 0:
            blockers.append(
                f"{intent_id}: possible zero-positive completion; AP blocked"
            )
        uncertainty.append(
            {
                "intent_id": intent_id,
                "known_true": positive,
                "known_false": negative,
                "unknown": unknown,
                "candidates": total,
                "judged_fraction": row.judged_fraction,
                "assignments": (
                    2**unknown
                    if unknown <= protocol["max_unknown_per_intent"]
                    else None
                ),
                "ap_defined_for_all_completions": positive > 0,
                "output": "reference-uncertainty-interval"
                if unknown
                else "exact-value",
            }
        )
    return {
        "blockers": blockers,
        "reference_coverage": uncertainty,
        "exploratory_relations": relations.reset_index().to_dict("records"),
        "relation_candidates": controls,
    }


def load_frozen_benchmark(path: Path, root: Path) -> dict:
    """Revalidate the new freeze, its immutable predecessor and native evidence.

    Parameters
    ----------
    path, root : Path
        Freeze record and repository containing the pinned native files/specs.
        No download, extraction, model execution or ranking occurs.

    Returns
    -------
    dict
        Integrity-verified frozen benchmark under analysis-protocol-v1.

    Raises
    ------
    ValueError
        Status-only freeze, stale/missing provenance, changed candidate/state/
        control inventory, unsupported protocol, native geometry or main gates.
    """
    record = load_benchmark_record(path, root, require_frozen=False)
    predecessor_path = "manifests/benchmark-candidate-v4.json"
    design_path = "config/benchmark-design-v3.json"
    protocol_path = "config/analysis-protocol-v1.json"
    required = {
        predecessor_path,
        design_path,
        protocol_path,
        "src/earth_observation/analysis_protocol.py",
        "scripts/freeze_benchmark.py",
        "docs/ANALYSIS_PROTOCOL.md",
    }
    if not required.issubset(record["inputs_sha256"]):
        raise ValueError("Missing required freeze input pins")
    if (
        record["version"] != "benchmark-freeze-v1"
        or record["design_file"] != design_path
        or record.get("analysis_protocol_file") != protocol_path
        or record.get("predecessor_file") != predecessor_path
    ):
        raise ValueError("Explicit analysis-protocol freeze required")
    predecessor = load_expanded_benchmark(root / predecessor_path, root, False)
    design = json.loads((root / design_path).read_text())
    protocol = json.loads((root / protocol_path).read_text())
    previous = json.loads((root / predecessor["design_file"]).read_text())
    validate_analysis_revision(design, previous, protocol)
    if not predecessor["inputs_sha256"].items() <= record["inputs_sha256"].items():
        raise ValueError("Historical source pins were omitted or changed")
    revised_keys = {
        "version",
        "status",
        "blockers",
        "content_sha256",
        "inputs_sha256",
        "design_version",
        "design_file",
        "evaluation_specification",
    }
    for key in predecessor.keys() - revised_keys:
        if record.get(key) != predecessor[key]:
            raise ValueError(f"Historical verified {key} changed")
    if (
        record["design_version"] != design["version"]
        or record["evaluation_specification"] != design_path + "#evaluation"
        or record["reference_validation"]["status"] != "verified-for-mapped-semantics"
        or record["unassigned_selection"]
    ):
        raise ValueError("Incomplete identity/design/reference evidence")
    main = record["main_candidates"]
    ids = main["development"] + main["test"]
    if (
        not main["test"]
        or len(ids) != len(set(ids))
        or not set(record["previous_development_ids"]).issubset(main["development"])
    ):
        raise ValueError("Invalid or leaking Development/Test identity inventory")
    spatial = pd.DataFrame(record["spatial_inventory"]).set_index("patch_id")
    footprints = verified_footprints(spatial.index.tolist(), root / "data/raw")
    expected = spatial_split(
        footprints, record["previous_development_ids"], design["spatial"]
    )
    if (
        not expected.equals(spatial[expected.columns])
        or not footprints.equals(spatial[footprints.columns])
        or set(spatial.index[spatial.split.eq("test")]) != set(main["test"])
        or set(spatial.index) != set(ids)
    ):
        raise ValueError("Native spatial inventory or complete component split changed")
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    pairs = [
        tuple(i["classes"]) for i in queries["intents"] if i["kind"] == "adjacency"
    ]
    native_states = []
    for pid in record["relevance"]["patch_ids"]:
        files = patch_files(
            pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        with rasterio.open(files["reference"]) as raster:
            summary = summarize_reference(
                raster.read(1, masked=True), raster.transform, raster.crs, rules, pairs
            )
        native_states.append(list(evaluate_intents(summary, queries).values()))
    if native_states != record["relevance"]["states"]:
        raise ValueError("Reference states differ from native maps")
    matrix = record["relevance"]
    decisions = pd.DataFrame(
        matrix["states"], index=matrix["patch_ids"], columns=matrix["intent_ids"]
    )
    readiness = analysis_readiness(
        decisions.loc[main["test"]],
        queries,
        spatial.loc[main["test"], "group_id"],
        design,
        protocol,
    )
    if readiness["relation_candidates"] != record["relation_controls"]["test"]:
        raise ValueError(
            "Exploratory control membership differs from both-presence states"
        )
    if readiness != record.get("analysis_readiness"):
        raise ValueError("Reference uncertainty readiness evidence changed")
    if readiness["blockers"] or record["blockers"] or record["status"] != "frozen":
        raise ValueError("Benchmark fails validated freeze prerequisites")
    return record


def freeze_existing_benchmark(root: Path) -> dict:
    """Write and independently validate a freeze using only existing evidence.

    Parameters
    ----------
    root : Path
        Repository with immutable v4 candidate and authorized v3/protocol files.

    Returns
    -------
    dict
        Newly written, fully validated freeze. An incompatible existing version
        is never overwritten. No final metrics are calculated.
    """
    predecessor = load_expanded_benchmark(
        root / "manifests/benchmark-candidate-v4.json", root, False
    )
    design_file = "config/benchmark-design-v3.json"
    protocol_file = "config/analysis-protocol-v1.json"
    design = json.loads((root / design_file).read_text())
    protocol = json.loads((root / protocol_file).read_text())
    validate_analysis_revision(
        design, json.loads((root / predecessor["design_file"]).read_text()), protocol
    )
    record = copy.deepcopy(predecessor)
    matrix = record["relevance"]
    decisions = pd.DataFrame(
        matrix["states"], index=matrix["patch_ids"], columns=matrix["intent_ids"]
    )
    spatial = pd.DataFrame(record["spatial_inventory"]).set_index("patch_id")
    test = record["main_candidates"]["test"]
    readiness = analysis_readiness(
        decisions.loc[test],
        queries=json.loads((root / "config/query-specification-v1.json").read_text()),
        groups=spatial.loc[test, "group_id"],
        design=design,
        protocol=protocol,
    )
    if readiness["blockers"]:
        raise ValueError(f"Freeze blocked: {readiness['blockers']}")
    record.update(
        version="benchmark-freeze-v1",
        status="frozen",
        blockers=[],
        design_version=design["version"],
        design_file=design_file,
        evaluation_specification=design_file + "#evaluation",
        analysis_protocol_file=protocol_file,
        predecessor_file="manifests/benchmark-candidate-v4.json",
        analysis_readiness=readiness,
    )
    for name in [
        design_file,
        protocol_file,
        "docs/ANALYSIS_PROTOCOL.md",
        "src/earth_observation/analysis_protocol.py",
        "scripts/freeze_benchmark.py",
        record["predecessor_file"],
    ]:
        record["inputs_sha256"][name] = file_digest(root / name)
    # Validate before publication: stage an ignored record then write the final
    # immutable version only after native provenance and all gates pass.
    staging = root / "outputs/freeze-validation/benchmark-freeze-v1.json"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.unlink(missing_ok=True)
    write_benchmark_record(staging, record)
    verified = load_frozen_benchmark(staging, root)
    write_benchmark_record(root / "manifests/benchmark-freeze-v1.json", verified)
    return verified
