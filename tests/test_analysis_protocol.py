"""Contracts for partial references; toy arithmetic does not implement WP5."""

import copy
import itertools
import json
from fractions import Fraction
from pathlib import Path

import pandas as pd
import pytest

from earth_observation.analysis_protocol import (
    PROTOCOL_CONTRACT,
    analysis_readiness,
    load_frozen_benchmark,
    validate_analysis_revision,
)
from earth_observation.benchmark import write_benchmark_record

ROOT = Path(__file__).resolve().parents[1]


def specifications():
    paths = [
        "config/benchmark-design-v3.json",
        "config/benchmark-design-v2.json",
        "config/query-specification-v1.json",
    ]
    return [json.loads((ROOT / p).read_text()) for p in paths]


def evidence(unknown=3):
    _, _, queries = specifications()
    states = ["true"] * 11 + ["false"] * 10 + ["unknown"] * unknown
    ids = [f"patch-{i}" for i in range(len(states))]
    return (
        pd.DataFrame({i["intent_id"]: states for i in queries["intents"]}, index=ids),
        pd.Series([f"group-{i}" for i in range(len(states))], index=ids),
    )


def test_known_unknown_counts_and_exact_enumeration_limit():
    design, previous, queries = specifications()
    validate_analysis_revision(design, previous, PROTOCOL_CONTRACT)
    for unknown in [0, 3, 12, 13]:
        decisions, groups = evidence(unknown)
        result = analysis_readiness(
            decisions, queries, groups, design, PROTOCOL_CONTRACT
        )
        row = result["reference_coverage"][0]
        assert row["known_true"] == 11 and row["known_false"] == 10
        assert row["unknown"] == unknown and row["candidates"] == 21 + unknown
        assert row["assignments"] == (2**unknown if unknown <= 12 else None)
        assert row["output"] == (
            "exact-value" if unknown == 0 else "reference-uncertainty-interval"
        )
        assert bool(result["blockers"]) == (unknown > 12)
    decisions.iloc[0, 0] = "missing"
    with pytest.raises(ValueError, match="three-state"):
        analysis_readiness(decisions, queries, groups, design, PROTOCOL_CONTRACT)


def test_zero_positive_completion_blocks_ap_and_known_count_gates_remain():
    design, _, queries = specifications()
    decisions, groups = evidence()
    decisions.iloc[:11, 0] = "false"
    result = analysis_readiness(decisions, queries, groups, design, PROTOCOL_CONTRACT)
    assert not result["reference_coverage"][0]["ap_defined_for_all_completions"]
    assert any("zero-positive" in b for b in result["blockers"])
    assert any("main_min_positive" in b for b in result["blockers"])
    assert result["reference_coverage"][0]["assignments"] == 8


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_unknown_per_intent", 13),
        ("completion_space", "unknown-is-false"),
        ("paired_difference", "independent-model-extrema"),
        ("paraphrase_aggregation", "independent-paraphrase-extrema"),
        ("family_bootstrap", "general-superiority-confidence-interval"),
    ],
)
def test_reject_unapproved_uncertainty_specifications(key, value):
    design, previous, _ = specifications()
    protocol = copy.deepcopy(PROTOCOL_CONTRACT)
    protocol[key] = value
    with pytest.raises(ValueError, match="Unsupported analysis protocol"):
        validate_analysis_revision(design, previous, protocol)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("coverage", "main_min_positive", 1),
        ("spatial", "distance_m", 1),
        ("evaluation", "ties", "random"),
    ],
)
def test_reject_unapproved_design_relaxations(section, key, value):
    design, previous, _ = specifications()
    design[section][key] = value
    with pytest.raises(ValueError):
        validate_analysis_revision(design, previous, PROTOCOL_CONTRACT)


def test_hand_computed_ap_extremum_is_mixed_and_pairing_changes_bounds():
    # Only four toy assignments: independently audit the specification's example.
    def toy_ap(labels):
        count, numerator = 0, Fraction(0)
        for rank, positive in enumerate(labels, 1):
            count += positive
            if positive:
                numerator += Fraction(count, rank)
        return numerator / count

    clip, remote = [], []
    for first, last in itertools.product((0, 1), repeat=2):
        clip.append(toy_ap([first, 0, 1, last]))
        remote.append(toy_ap([last, 1, 0, first]))
    assert clip == [Fraction(1, 3), Fraction(5, 12), Fraction(5, 6), Fraction(29, 36)]
    assert max(clip) == clip[2] > max(clip[0], clip[-1])
    paired = [r - c for r, c in zip(remote, clip, strict=True)]
    assert (min(paired), max(paired)) != (
        min(remote) - max(clip),
        max(remote) - min(clip),
    )


@pytest.mark.integration
def test_real_freeze_revalidates_maps_spatial_groups_and_partial_reference(tmp_path):
    if not (ROOT / "data/raw/BigEarthNet-S2").is_dir():
        pytest.skip("Acquire the pinned local native inventory before integration")
    record = load_frozen_benchmark(ROOT / "manifests/benchmark-freeze-v1.json", ROOT)
    assert record["status"] == "frozen" and not record["blockers"]
    assert len(record["main_candidates"]["test"]) == 871
    rows = record["analysis_readiness"]["reference_coverage"]
    assert [r["unknown"] for r in rows] == [0, 3, 2, 3, 3, 3, 3, 3]
    assert [
        r["false"] for r in record["analysis_readiness"]["exploratory_relations"]
    ] == [2, 7]
    assert all(r["ap_defined_for_all_completions"] for r in rows)
    for mutation in ["missing-pin", "changed-reference", "removed-unknown"]:
        bad = copy.deepcopy(record)
        if mutation == "missing-pin":
            del bad["inputs_sha256"]["config/analysis-protocol-v1.json"]
        elif mutation == "changed-reference":
            bad["relevance"]["states"][0][0] = "unknown"
        else:
            bad["main_candidates"]["test"].pop()
        path = tmp_path / f"{mutation}.json"
        write_benchmark_record(path, bad)
        with pytest.raises(ValueError):
            load_frozen_benchmark(path, ROOT)
