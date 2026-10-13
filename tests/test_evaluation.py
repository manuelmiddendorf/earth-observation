"""Independent exact arithmetic and invariance checks for frozen v3 analysis."""

import copy
import itertools
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earth_observation.analysis_protocol import PROTOCOL_CONTRACT
from earth_observation.evaluation import (
    error_category,
    evaluate_rankings,
    evaluate_relation_controls,
    family_sensitivity,
    top_k_jaccard,
    validate_benchmark_candidates,
)
from earth_observation.retrieval import completion_metrics, ranking_metrics

ROOT = Path(__file__).resolve().parents[1]
QUERIES = json.loads((ROOT / "config/query-specification-v1.json").read_text())
POLICY = json.loads((ROOT / "config/benchmark-design-v3.json").read_text())[
    "evaluation"
]["bootstrap"]


def brute_force(ids, refs):
    """Independent fractions, explicit rank loops; no production metric helper."""
    unknown = sorted(p for p, s in refs.items() if s == "unknown")
    output = []
    for bits in itertools.product((0, 1), repeat=len(unknown)):
        completion = dict(zip(unknown, bits, strict=True))
        labels = [
            completion[p] if refs[p] == "unknown" else int(refs[p] == "true")
            for p in ids
        ]
        positives, numerator = 0, Fraction(0)
        for rank, label in enumerate(labels, 1):
            positives += label
            if label:
                numerator += Fraction(positives, rank)
        output.append(
            {
                "p_at_10": Fraction(sum(labels[:10]), 10) if len(ids) >= 10 else None,
                "average_precision": numerator / positives if positives else None,
            }
        )
    return output


def toy_input(states=None, orders=None):
    states = states or ["unknown", "false", "true", "unknown"] + ["false"] * 8
    ids = [f"p{i:02}" for i in range(len(states))]
    refs = pd.DataFrame({i["intent_id"]: states for i in QUERIES["intents"]}, index=ids)
    orders = orders or {"clip": [ids] * 3, "remote": [list(reversed(ids))] * 3}
    rows = []
    for model, pp_orders in orders.items():
        for intent in QUERIES["intents"]:
            for p, order in enumerate(pp_orders, 1):
                rows.extend(
                    {
                        "model_id": model,
                        "query_id": f"{intent['intent_id']}/p{p}",
                        "rank": rank,
                        "patch_id": pid,
                    }
                    for rank, pid in enumerate(order, 1)
                )
    return pd.DataFrame(rows), refs


def analyze(rankings, references, models=None):
    return evaluate_rankings(
        rankings, references, QUERIES, models or ["clip", "remote"], PROTOCOL_CONTRACT
    )


def test_known_metrics_and_ap_mixed_assignment_extremum():
    ids = [f"p{i}" for i in range(12)]
    known = {p: "true" if i in (0, 2, 10) else "false" for i, p in enumerate(ids)}
    result = ranking_metrics(ids, known, PROTOCOL_CONTRACT)["metric_bounds"]
    assert result["p_at_10"]["value"] == 0.2
    assert result["average_precision"]["value"] == pytest.approx(
        float((1 + Fraction(2, 3) + Fraction(3, 11)) / 3)
    )
    refs = dict(
        zip(ids, ["unknown", "false", "true", "unknown"] + ["false"] * 8, strict=True)
    )
    result = ranking_metrics(ids, refs, PROTOCOL_CONTRACT)
    assert result["candidate_count"] == 12 and result["unknown_count"] == 2
    assert result["metric_bounds"]["p_at_10"]["lower"] == 0.1
    assert result["metric_bounds"]["p_at_10"]["upper"] == 0.3
    ap = completion_metrics(ids, refs, PROTOCOL_CONTRACT)["values"]["average_precision"]
    np.testing.assert_allclose(ap, [1 / 3, 5 / 12, 5 / 6, 29 / 36])
    assert ap.max() > max(ap[0], ap[-1])
    assert result["metric_bounds"]["average_precision"]["value"] is None


def test_random_small_enumerations_match_independent_brute_force():
    generator = np.random.default_rng(832)
    ids = [f"p{i}" for i in range(12)]
    for _ in range(20):
        states = generator.choice(["true", "false"], len(ids)).tolist()
        for i in generator.choice(len(ids) - 1, 3, replace=False):
            states[i] = "unknown"
        states[-1] = "true"  # Guarantees AP defined under every completion.
        refs = dict(zip(ids, states, strict=True))
        order = generator.permutation(ids).tolist()
        actual = completion_metrics(order, refs, PROTOCOL_CONTRACT)
        expected = brute_force(order, refs)
        for metric in ["p_at_10", "average_precision"]:
            np.testing.assert_allclose(
                actual["values"][metric],
                [float(r[metric]) for r in expected],
                atol=1e-14,
            )


def test_undefined_zero_positive_over_limit_and_collapsed_unknown_bounds():
    ids = [f"p{i}" for i in range(14)]
    refs = dict.fromkeys(ids, "false")
    refs[ids[-1]] = "unknown"
    result = ranking_metrics(ids, refs, PROTOCOL_CONTRACT)["metric_bounds"]
    assert result["average_precision"]["status"] == "blocked"
    assert "zero-positive" in result["average_precision"]["reason"]
    assert result["p_at_10"]["status"] == "reference-uncertainty-interval"
    assert result["p_at_10"]["lower"] == result["p_at_10"]["upper"] == 0
    assert result["p_at_10"]["value"] is None
    refs = dict.fromkeys(ids, "unknown")
    refs[ids[0]] = "true"
    result = ranking_metrics(ids, refs, PROTOCOL_CONTRACT)["metric_bounds"]
    assert all(r["status"] == "blocked" and r["lower"] is None for r in result.values())
    result = ranking_metrics(["a"], {"a": "true"}, PROTOCOL_CONTRACT)["metric_bounds"]
    assert result["p_at_10"]["status"] == "undefined"
    assert result["average_precision"]["value"] == 1


def test_shared_assignments_across_models_paraphrases_and_variation():
    rankings, refs = toy_input()
    ids = refs.index.tolist()
    orders = {
        "clip": [ids, list(reversed(ids)), ids[2:] + ids[:2]],
        "remote": [list(reversed(ids)), ids[2:] + ids[:2], ids],
    }
    rankings, refs = toy_input(orders=orders)
    result = analyze(rankings, refs)

    def expected(model):
        return np.array(
            [
                [
                    float(row["average_precision"])
                    for row in brute_force(order, refs.iloc[:, 0].to_dict())
                ]
                for order in orders[model]
            ]
        )

    for model in orders:
        scores = expected(model)
        row = next(
            r
            for r in result["intents"]
            if r["model_id"] == model
            and r["intent_id"] == "single-forest"
            and r["metric"] == "average_precision"
        )
        assert row["lower"] == pytest.approx(scores.mean(axis=0).min())
        assert row["upper"] == pytest.approx(scores.mean(axis=0).max())
        assert row["upper"] < scores.max(axis=1).mean()
        variation = next(
            r
            for r in result["quality_variation"]
            if r["model_id"] == model
            and r["intent_id"] == "single-forest"
            and r["metric"] == "average_precision"
        )
        assert variation["lower"] == pytest.approx(np.ptp(scores, axis=0).min())
        assert variation["upper"] == pytest.approx(np.ptp(scores, axis=0).max())
    # Different ordering of the same three formulations: identical intent mean
    # for every assignment, despite broad individual-model uncertainty intervals.
    paired = next(
        r
        for r in result["paired_intents"]
        if r["intent_id"] == "single-forest" and r["metric"] == "average_precision"
    )
    assert paired["lower"] == pytest.approx(0, abs=1e-15)
    assert paired["upper"] == pytest.approx(0, abs=1e-15)
    assert paired["status"] == "reference-uncertainty-interval"
    aggregate = next(
        r
        for r in result["descriptive_paired"]
        if r["scope"] == "all" and r["metric"] == "average_precision"
    )
    assert aggregate["status"] == "conservative-aggregate-reference-envelope"
    assert not aggregate["joint_physical_attainability_claimed"]


def test_paired_swap_zero_difference_and_input_reordering():
    rankings, refs = toy_input()
    result = analyze(rankings, refs)
    swapped = analyze(rankings, refs, ["remote", "clip"])
    for a, b in zip(result["paired_intents"], swapped["paired_intents"], strict=True):
        assert b["lower"] == pytest.approx(-a["upper"])
        assert b["upper"] == pytest.approx(-a["lower"])
    shuffled = analyze(rankings.sample(frac=1, random_state=61), refs.iloc[::-1])
    assert shuffled == result
    same = rankings.loc[rankings.model_id.eq("clip")].copy()
    remote_copy = same.copy()
    remote_copy["model_id"] = "remote"
    same = pd.concat([same, remote_copy], ignore_index=True)
    assert all(
        r["lower"] == r["upper"] == 0 for r in analyze(same, refs)["paired_intents"]
    )


@pytest.mark.parametrize(
    "failure",
    [
        "missing-model",
        "duplicate-id",
        "missing-reference",
        "duplicate-rank",
        "wrong-text",
        "wrong-score-order",
    ],
)
def test_inconsistent_candidate_and_model_pairing_rejected(failure):
    rankings, refs = toy_input()
    if failure == "missing-model":
        rankings = rankings[rankings.model_id.eq("clip")]
    elif failure == "duplicate-id":
        rankings.loc[1, "patch_id"] = rankings.loc[0, "patch_id"]
    elif failure == "missing-reference":
        refs = refs.iloc[:-1]
    elif failure == "duplicate-rank":
        rankings.loc[1, "rank"] = 1
    elif failure == "wrong-text":
        rankings["text"] = "unfrozen query"
    else:
        rankings["cosine_similarity"] = rankings["rank"].astype(float)
    with pytest.raises(ValueError):
        analyze(rankings, refs)


def test_jaccard_distinguishes_ranking_stability_from_quality():
    first = [f"p{i}" for i in range(12)]
    assert top_k_jaccard(first, first) == 1
    assert top_k_jaccard(first, first[2:] + first[:2]) == pytest.approx(8 / 12)
    assert top_k_jaccard(["a", "b"], ["b", "a"], 10) == 1
    with pytest.raises(ValueError):
        top_k_jaccard(first, first[:-1])


def test_disjoint_error_categories_and_explicit_unresolved_pattern():
    q = QUERIES
    singles = {
        i["classes"][0]: i["intent_id"] for i in q["intents"] if i["kind"] == "single"
    }
    intent = next(i for i in q["intents"] if i["intent_id"] == "adjacent-forest-water")
    for a, b, expected in [
        ("true", "false", "class-a-only"),
        ("false", "true", "class-b-only"),
        ("false", "false", "neither"),
        ("true", "true", "both-present-relation-failure"),
    ]:
        states = {i["intent_id"]: "false" for i in q["intents"]}
        states[singles["forest"]] = a
        states[singles["inland_water"]] = b
        assert error_category(states, intent, q)["category"] == expected
    states[intent["intent_id"]] = "unknown"
    assert error_category(states, intent, q)["category"] == "unknown-reference"
    states[intent["intent_id"]] = "true"
    assert error_category(states, intent, q)["category"] == "satisfied"
    states[intent["intent_id"]] = "false"
    states[singles["forest"]] = "unknown"
    states[singles["inland_water"]] = "false"
    result = error_category(states, intent, q)
    assert result["relevance"] == "false" and result["category"] is None
    assert result["status"] == "unresolved-class-pattern"


def test_controls_separate_small_undefined_metrics_and_unknown_presence():
    rankings, refs = toy_input()
    controls = evaluate_relation_controls(
        rankings, refs, QUERIES, ["clip", "remote"], PROTOCOL_CONTRACT
    )
    assert all(
        c["reference_counts"] == {"true": 1, "false": 0, "unknown": 0} for c in controls
    )
    assert all(c["excluded_unknown_presence"] == 2 for c in controls)
    assert all(
        c["analysis"]["candidate_scope"] == "exploratory-relation-control"
        for c in controls
    )
    assert all(
        r["status"] == "undefined"
        for c in controls
        for r in c["analysis"]["intents"]
        if r["metric"] == "p_at_10"
    )
    assert any(
        r["status"] == "unavailable-rank"
        for r in controls[0]["analysis"]["error_samples"]
    )
    with pytest.raises(ValueError, match="both known true"):
        evaluate_rankings(
            rankings,
            refs,
            QUERIES,
            ["clip", "remote"],
            PROTOCOL_CONTRACT,
            control_intent="adjacent-forest-water",
        )


def test_family_sensitivity_weighting_multiplicity_and_undefined_retention():
    # Unequal family sizes verify intent weighting rather than a family mean.
    queries = {
        "families": {"a": "A", "b": "B"},
        "intents": [
            {"intent_id": "a1", "family_id": "a"},
            {"intent_id": "a2", "family_id": "a"},
            {"intent_id": "b1", "family_id": "b"},
        ],
    }
    paired = [
        {
            "intent_id": i["intent_id"],
            "metric": m,
            "lower": 0 if i["family_id"] == "a" else 1,
            "upper": 0.2 if i["family_id"] == "a" else 1,
        }
        for i in queries["intents"]
        for m in ["p_at_10", "average_precision"]
    ]
    result = family_sensitivity(paired, queries, POLICY)
    assert result == family_sensitivity(list(reversed(paired)), queries, POLICY)
    assert (
        result["distinct_family_multiplicities"] == 3
        and not result["confidence_interval"]
    )
    # Independently reconstruct the PCG64 family draws and weighted estimator.
    draws = np.random.Generator(np.random.PCG64(POLICY["seed"])).integers(
        0, 2, size=(10000, 2)
    )
    values = [
        sum(x == 1 for x in row) / sum(2 if x == 0 else 1 for x in row) for row in draws
    ]
    assert set(values) == {0, 1 / 3, 1}
    middle = result["results"][0]["multiplicity_estimates"][1]
    assert middle["family_counts"] == {"a": 1, "b": 1}
    assert middle["intent_occurrences"] == 3
    assert middle["lower_reference_envelope"] == pytest.approx(1 / 3)
    assert middle["upper_reference_envelope"] == pytest.approx(1.4 / 3)
    np.testing.assert_allclose(
        result["results"][0]["lower_reference_envelope_percentiles"],
        np.quantile(values, [0.025, 0.975], method="linear"),
    )
    paired[0]["lower"] = None
    blocked = family_sensitivity(paired, queries, POLICY)
    assert blocked["results"][0]["status"] == "undefined"
    assert blocked["results"][0]["blocked_intents"] == ["a1"]


@pytest.mark.integration
def test_saved_development_ranking_to_result_without_encoding_or_download(monkeypatch):
    from earth_observation.evaluation_run import evaluate_development

    root = ROOT
    if not (root / "outputs/frozen-retrieval-pilot-v1/run.json").exists():
        pytest.skip("Acquire original Development cache/rankings first")

    def prohibited(*args, **kwargs):
        raise AssertionError("No encoding/download allowed")

    monkeypatch.setattr("earth_observation.encoding.encode_frozen", prohibited)
    monkeypatch.setattr("earth_observation.data.fetch_asset", prohibited)
    originals = [
        root / "outputs/frozen-retrieval-pilot-v1/rankings.csv",
        root / "outputs/frozen-retrieval-pilot-v1/run.json",
    ]
    originals += list((root / "data/cache/embeddings").glob("*.npz"))
    mtimes = {p: p.stat().st_mtime_ns for p in originals}
    result = evaluate_development(root, bootstrap=True)
    assert (
        not result["new_encoding"]
        and not result["new_downloads"]
        and not result["test_model_evaluation"]
    )
    assert (
        result["benchmark_version"] == "benchmark-freeze-v1"
        and len(result["candidate_ids"]) == 10
    )
    assert len(result["main"]["formulations"]) == 96
    assert (
        next(
            r
            for r in result["main"]["descriptive_paired"]
            if r["scope"] == "all" and r["metric"] == "p_at_10"
        )["value"]
        == 0
    )
    assert all(p.stat().st_mtime_ns == mtime for p, mtime in mtimes.items())
    saved = json.loads(
        (root / "outputs/evaluation-development-v3/results.json").read_text()
    )
    assert saved == result


def test_review_rejects_contradictory_reference_states_and_empty_protocol():
    rankings, refs = toy_input()
    refs.loc["p02", "both-forest-water"] = "false"
    with pytest.raises(ValueError, match="contradict canonical presence"):
        analyze(rankings, refs)
    rankings, refs = toy_input()
    with pytest.raises(ValueError, match="Explicit frozen"):
        evaluate_relation_controls(rankings, refs, QUERIES, ["clip", "remote"], {})
    bad = copy.deepcopy(POLICY)
    bad["generator"] = "unspecified generator"
    result = analyze(rankings, refs)
    with pytest.raises(ValueError, match="PCG64"):
        family_sensitivity(result["paired_intents"], QUERIES, bad)


def test_over_limit_blocks_all_affected_aggregates_without_hiding_rows():
    states = ["true"] + ["unknown"] * 13
    rankings, refs = toy_input(states=states)
    result = analyze(rankings, refs)
    assert len(result["paired_intents"]) == 16
    assert all(r["status"] == "blocked" for r in result["paired_intents"])
    assert all(
        r["status"] == "undefined" and r["reasons"]
        for r in result["descriptive_paired"]
    )
    assert len(result["top_k_jaccard"]) == 48


def test_frozen_membership_requires_complete_test_and_never_mixes_splits():
    # Synthetic identity contract only, no actual Test ranks or embeddings.
    benchmark = {
        "status": "frozen",
        "main_candidates": {"development": ["d0", "d1"], "test": ["t0", "t1"]},
    }
    validate_benchmark_candidates(
        pd.DataFrame({"patch_id": ["d1"]}), benchmark, "development"
    )
    validate_benchmark_candidates(
        pd.DataFrame({"patch_id": ["t1", "t0"]}), benchmark, "test"
    )
    for ids, stage in [
        (["t0"], "test"),
        (["d0", "t0"], "development"),
        (["d0", "t0", "t1"], "test"),
    ]:
        with pytest.raises(ValueError, match="candidate pool|leakage"):
            validate_benchmark_candidates(
                pd.DataFrame({"patch_id": ids}), benchmark, stage
            )
