"""Paired complete-ranking analysis with explicit reference and wording bounds.

No image encoding, acquisition or ranking optimization occurs here. Completion
order is shared across models/formulations within an intent. Across intents,
only the conservative envelopes authorized by the freeze are reported.
"""

from itertools import combinations

import numpy as np
import pandas as pd

from earth_observation.analysis_protocol import PROTOCOL_CONTRACT
from earth_observation.reference import conjunction
from earth_observation.retrieval import completion_metrics, metric_bounds, validate_ids

METRICS = ("p_at_10", "average_precision")


def validate_benchmark_candidates(
    rankings: pd.DataFrame, benchmark: dict, stage: str
) -> None:
    """Check frozen split membership without ranking or removing any candidates.

    Parameters
    ----------
    rankings : pandas.DataFrame
        Supplied stored ranking rows with patch_id; no scoring occurs here.
    benchmark : dict
        Fully validated freeze from load_frozen_benchmark.
    stage : str
        Development permits an explicitly reported subset of Development IDs;
        test requires the entire frozen Test pool. Neither permits split mixing.

    Raises
    ------
    ValueError
        Wrong/blocked stage, unknown IDs, Development/Test leakage or incomplete
        Test pool. This guard does not authorize executing a final model run.
    """
    if stage not in {"development", "test"} or benchmark.get("status") != "frozen":
        raise ValueError(
            "Validated freeze and explicit Development/Test stage required"
        )
    ids = set(rankings.patch_id)
    expected = set(benchmark["main_candidates"][stage])
    if not ids or not ids.issubset(expected) or (stage == "test" and ids != expected):
        raise ValueError(
            "Incomplete/foreign candidate pool or Development/Test leakage"
        )


def top_k_jaccard(first: list[str], second: list[str], k: int = 10) -> float:
    """Compare available top-k ID sets, independently of reference quality.

    Parameters
    ----------
    first, second : list of str
        Complete unique-ID rankings of the identical candidate pool.
    k : int
        Positive cutoff. If N < k the available prefix is the entire pool;
        callers must report N and the available cutoff, not call this quality.

    Returns
    -------
    float
        Intersection size / union size, in [0,1]. Unknown labels have no effect.

    Raises
    ------
    ValueError
        Duplicate/empty IDs, differing pools or invalid cutoff.
    """
    validate_ids(first)
    validate_ids(second)
    if set(first) != set(second) or type(k) is not int or k < 1:
        raise ValueError("Jaccard requires identical pools and a positive integer k")
    a, b = set(first[:k]), set(second[:k])
    return len(a & b) / len(a | b)


def error_category(states: dict[str, str], intent: dict, queries: dict) -> dict:
    """Classify frozen three-state relevance without inventing visual truth.

    Parameters
    ----------
    states : dict
        One patch's complete declared-intent three-state judgments.
    intent, queries : dict
        Fixed intent and query specification. Composite class order is preserved.

    Returns
    -------
    dict
        Relevance, category, diagnostic status and reason. Unknown relevance is
        unknown-reference. Known false with an uncertain constituent presence
        has no identified class-pattern category and is explicitly unresolved,
        as documented before implementation in EVALUATION_PIPELINE.md.

    Raises
    ------
    ValueError
        Invalid states or contradictory known composite/single evidence.
    """
    if set(states) != {i["intent_id"] for i in queries["intents"]} or not set(
        states.values()
    ).issubset({"true", "false", "unknown"}):
        raise ValueError(
            "Error diagnosis requires complete three-state intent evidence"
        )
    relevance = states[intent["intent_id"]]
    category, status, reason = None, "classified", None
    if relevance == "unknown":
        category = "unknown-reference"
    elif relevance == "true":
        category = "satisfied"
    elif intent["kind"] == "single":
        category = "single-presence-failure"
    else:
        singles = [
            next(
                i["intent_id"]
                for i in queries["intents"]
                if i["kind"] == "single" and i["classes"] == [name]
            )
            for name in intent["classes"]
        ]
        a, b = (states[s] for s in singles)
        if "unknown" in (a, b):
            status = "unresolved-class-pattern"
            reason = (
                "Known negative relevance; uncertain class pattern "
                "has no frozen category"
            )
        elif a == b == "false":
            category = "neither"
        elif a == "true" and b == "false":
            category = "class-a-only"
        elif a == "false" and b == "true":
            category = "class-b-only"
        elif intent["kind"] == "adjacency":
            category = "both-present-relation-failure"
        else:
            raise ValueError("False conjunction contradicts both known true presences")
    return {
        "relevance": relevance,
        "category": category,
        "status": status,
        "reason": reason,
    }


def _validated_rankings(
    rankings: pd.DataFrame,
    references: pd.DataFrame,
    queries: dict,
    models: list[str],
    active_intents: list[dict],
) -> dict[tuple[str, str], list[str]]:
    validate_ids(models)
    if len(models) != 2:
        raise ValueError("Exactly two ordered models (CLIP, RemoteCLIP) required")
    validate_ids(references.index.tolist())
    intents = [i["intent_id"] for i in queries["intents"]]
    validate_ids(intents)
    if any(
        len(i["paraphrases"]) != 3 or i["family_id"] not in queries["families"]
        for i in queries["intents"]
    ):
        raise ValueError("Require three frozen formulations and declared families")
    if references.columns.tolist() != intents or not set(
        references.to_numpy().ravel()
    ).issubset({"true", "false", "unknown"}):
        raise ValueError(
            "References require declared intent order and three-state labels"
        )
    for intent in queries["intents"]:
        if intent["kind"] == "single":
            continue
        singles = [
            next(
                i["intent_id"]
                for i in queries["intents"]
                if i["kind"] == "single" and i["classes"] == [c]
            )
            for c in intent["classes"]
        ]
        presence = references[singles].apply(
            lambda row: conjunction(row.tolist()), axis=1
        )
        actual = references[intent["intent_id"]]
        if intent["kind"] == "conjunction":
            invalid = actual.ne(presence)
        else:
            invalid = (presence.eq("false") & actual.ne("false")) | (
                actual.eq("true") & presence.ne("true")
            )
        if invalid.any():
            raise ValueError(
                "Composite references contradict canonical presence states"
            )
    needed = {"model_id", "query_id", "patch_id", "rank"}
    if not needed.issubset(rankings) or rankings[list(needed)].isna().any().any():
        raise ValueError("Missing complete-ranking columns/values")
    expected_queries = {
        f"{i['intent_id']}/p{p}": (i, text)
        for i in active_intents
        for p, text in enumerate(i["paraphrases"], 1)
    }
    expected_pairs = {(m, q) for m in models for q in expected_queries}
    groups = dict(tuple(rankings.groupby(["model_id", "query_id"], sort=False)))
    if set(groups) != expected_pairs:
        raise ValueError("Incomplete or extra model/formulation pairing")
    result = {}
    for (model, query), group in groups.items():
        rank = group["rank"].to_numpy()
        if rank.dtype.kind not in "iu" or sorted(rank.tolist()) != list(
            range(1, len(references) + 1)
        ):
            raise ValueError("Ranks must be integer 1..N, complete without duplication")
        ordered = group.sort_values("rank")
        ids = ordered.patch_id.tolist()
        validate_ids(ids)
        if set(ids) != set(references.index):
            raise ValueError(
                "Every ranking must contain the exact reference candidate pool"
            )
        intent, text = expected_queries[query]
        for column, expected in [
            ("intent_id", intent["intent_id"]),
            ("family_id", intent["family_id"]),
            ("text", text),
        ]:
            if column in group and not group[column].eq(expected).all():
                raise ValueError(
                    "Ranking intent/family/text mapping differs from specification"
                )
        if "cosine_similarity" in ordered:
            scores = ordered.cosine_similarity.to_numpy()
            if (
                scores.dtype.kind not in "fiu"
                or not np.isfinite(scores).all()
                or np.any(np.abs(scores) > 1 + 1e-6)
            ):
                raise ValueError(
                    "Require finite real cosine scores in [-1,1] within tolerance"
                )
            expected_order = np.lexsort((ids, -scores))
            if not np.array_equal(expected_order, np.arange(len(ids))):
                raise ValueError(
                    "Ranking differs from descending cosine/Unicode-ID ties"
                )
        result[(model, query)] = ids
    return result


def _aggregate(rows: list[dict], intents: list[dict]) -> list[dict]:
    """Equal-intent conservative envelopes; never optimize formulations apart."""
    result = []
    subsets = {"all": intents} | {
        kind: [i for i in intents if i["kind"] == kind]
        for kind in ["single", "conjunction", "adjacency"]
    }
    for scope, subset in subsets.items():
        if not subset:
            continue
        ids = {i["intent_id"] for i in subset}
        for model in dict.fromkeys(r["model_id"] for r in rows):
            for metric in METRICS:
                selected = [
                    r
                    for r in rows
                    if r["intent_id"] in ids
                    and r["model_id"] == model
                    and r["metric"] == metric
                ]
                reasons = [
                    f"{r['intent_id']}: {r['reason']}"
                    for r in selected
                    if r["lower"] is None
                ]
                if len(selected) != len(ids):
                    reasons.append("Missing intent result; no skipped aggregate")
                unknown = any(r["unknown_count"] for r in selected)
                lower = (
                    None if reasons else float(np.mean([r["lower"] for r in selected]))
                )
                upper = (
                    None if reasons else float(np.mean([r["upper"] for r in selected]))
                )
                result.append(
                    {
                        "scope": scope,
                        "model_id": model,
                        "metric": metric,
                        "intent_count": len(ids),
                        "status": "undefined"
                        if reasons
                        else "conservative-aggregate-reference-envelope"
                        if unknown
                        else "exact",
                        "value": lower if not reasons and not unknown else None,
                        "lower": lower,
                        "upper": upper,
                        "reasons": reasons,
                        "uncertainty_type": "reference" if unknown else "none",
                        "joint_physical_attainability_claimed": False,
                    }
                )
    return result


def evaluate_rankings(
    rankings: pd.DataFrame,
    references: pd.DataFrame,
    queries: dict,
    models: list[str],
    protocol: dict,
    *,
    control_intent: str | None = None,
) -> dict:
    """Evaluate paired complete rankings with one completion per intent.

    Parameters
    ----------
    rankings : pandas.DataFrame
        Rows model_id/query_id/patch_id/integer rank. Optional cosine, intent,
        family and text columns are validated when present. Input row order is
        immaterial; explicit ranks are authoritative and never optimized.
    references : pandas.DataFrame
        Exact candidate-by-declared-intent true/false/unknown table. Every model
        and formulation must rank this complete pool; unknowns are retained.
    queries : dict
        Validated query specification including ordered paraphrases and families.
    models : list of str
        Exactly [CLIP identity, RemoteCLIP identity]; differences are second-first.
    protocol : dict
        Frozen analysis-protocol-v1. There is no historical judged-only fallback.
    control_intent : str or None
        Explicit exploratory adjacency control; all candidates must have both
        known true presences. None requires the complete unfiltered main pool.

    Returns
    -------
    dict
        JSON-compatible coverage, formulation/intent/paired bounds, wording
        ranges, reference-independent Jaccard diagnostics, prescribed rank-based
        error samples and descriptive conservative aggregate envelopes. All
        undefined results carry reasons; no individual imputed score exists.

    Raises
    ------
    ValueError
        Unsupported protocol, identities, incomplete pairing, order or references.
    """
    if protocol != PROTOCOL_CONTRACT:
        raise ValueError("Explicit frozen analysis protocol required")
    active = queries["intents"]
    if control_intent is not None:
        active = [
            i
            for i in active
            if i["intent_id"] == control_intent and i["kind"] == "adjacency"
        ]
        if len(active) != 1:
            raise ValueError("Only a declared adjacency control can filter candidates")
        for name in active[0]["classes"]:
            single = next(
                i["intent_id"]
                for i in queries["intents"]
                if i["kind"] == "single" and i["classes"] == [name]
            )
            if not references[single].eq("true").all():
                raise ValueError("Control candidates require both known true presences")
    ordered = _validated_rankings(rankings, references, queries, models, active)
    formulation_rows, intent_rows, paired_rows, variation, jaccard, errors, coverage = (
        [] for _ in range(7)
    )
    for intent in active:
        iid = intent["intent_id"]
        qids = [f"{iid}/p{p}" for p in range(1, len(intent["paraphrases"]) + 1)]
        ref = references[iid].to_dict()
        model_means = {}
        intent_coverage = None
        for model in models:
            completions = [
                completion_metrics(ordered[model, q], ref, protocol) for q in qids
            ]
            first = completions[0]
            unknown = first["coverage"]["unknown_count"]
            intent_coverage = {
                "intent_id": iid,
                "family_id": intent["family_id"],
                **first["coverage"],
                "assignment_count": first["assignment_count"],
            }
            model_means[model] = {}
            for metric in METRICS:
                values = np.array([c["values"][metric] for c in completions])
                reason = first["reasons"][metric]
                for q, scores in zip(qids, values, strict=True):
                    formulation_rows.append(
                        {
                            "model_id": model,
                            "intent_id": iid,
                            "query_id": q,
                            "metric": metric,
                            "unknown_count": unknown,
                            **metric_bounds(scores, unknown, reason),
                        }
                    )
                mean = values.mean(axis=0) if values.shape[1] else np.array([])
                model_means[model][metric] = (mean, reason)
                intent_rows.append(
                    {
                        "model_id": model,
                        "intent_id": iid,
                        "family_id": intent["family_id"],
                        "metric": metric,
                        "unknown_count": unknown,
                        **metric_bounds(mean, unknown, reason),
                    }
                )
                ranges = np.ptp(values, axis=0) if values.shape[1] else np.array([])
                variation.append(
                    {
                        "model_id": model,
                        "intent_id": iid,
                        "metric": metric,
                        "quantity": "paraphrase-quality-range",
                        **metric_bounds(ranges, unknown, reason),
                    }
                )
            for a, b in combinations(qids, 2):
                jaccard.append(
                    {
                        "model_id": model,
                        "intent_id": iid,
                        "first_query": a,
                        "second_query": b,
                        "k": 10,
                        "available_k": min(10, len(ref)),
                        "jaccard": top_k_jaccard(ordered[model, a], ordered[model, b]),
                        "quantity": "ranking-stability",
                        "uncertainty_type": "none",
                    }
                )
            for rank in [1, 5, 10]:
                if rank > len(ref):
                    errors.append(
                        {
                            "model_id": model,
                            "intent_id": iid,
                            "query_id": qids[0],
                            "rank": rank,
                            "patch_id": None,
                            "relevance": None,
                            "category": None,
                            "status": "unavailable-rank",
                            "reason": "N < requested rank",
                        }
                    )
                else:
                    pid = ordered[model, qids[0]][rank - 1]
                    errors.append(
                        {
                            "model_id": model,
                            "intent_id": iid,
                            "query_id": qids[0],
                            "rank": rank,
                            "patch_id": pid,
                            **error_category(
                                references.loc[pid].to_dict(), intent, queries
                            ),
                        }
                    )
        coverage.append(intent_coverage)
        for metric in METRICS:
            left, lr = model_means[models[0]][metric]
            right, rr = model_means[models[1]][metric]
            paired_rows.append(
                {
                    "model_id": "second-minus-first",
                    "intent_id": iid,
                    "family_id": intent["family_id"],
                    "metric": metric,
                    "unknown_count": intent_coverage["unknown_count"],
                    **metric_bounds(
                        right - left, intent_coverage["unknown_count"], lr or rr
                    ),
                }
            )
    return {
        "reference_coverage": coverage,
        "formulations": formulation_rows,
        "intents": intent_rows,
        "paired_intents": paired_rows,
        "quality_variation": variation,
        "top_k_jaccard": jaccard,
        "error_samples": errors,
        "candidate_scope": "exploratory-relation-control"
        if control_intent
        else "unfiltered-main",
        "descriptive_models": _aggregate(intent_rows, active),
        "descriptive_paired": _aggregate(paired_rows, active),
        "difference_direction": {
            "positive_model": models[1],
            "negative_model": models[0],
        },
        "statistical_uncertainty": "No confidence interval; two direct intent families",
    }


def family_sensitivity(paired: list[dict], queries: dict, policy: dict) -> dict:
    """Optional paired family-resampling diagnostic, never a superiority CI.

    Parameters
    ----------
    paired : list of dict
        Complete per-intent/per-metric paired bounds from evaluate_rankings.
        Whole intent bounds remain conservative across related references.
    queries : dict
        Exactly two direct families with their fixed dependent intents.
    policy : dict
        Frozen v3 bootstrap policy: PCG64, seed, multiplicity-preserving draws,
        intent-weighted estimator, linear percentile summaries and restricted role.

    Returns
    -------
    dict
        Separate percentile distributions of lower/upper conservative reference
        envelopes under family resampling. Exact reference endpoints coincide
        for fully judged data. No reference imputation or discarded replicates.
        Undefined intent metrics explicitly block the affected diagnostic.

    Raises
    ------
    ValueError
        Unsupported role, family structure or incomplete/extra intent pairing.
    """
    if (
        policy.get("role") != PROTOCOL_CONTRACT["family_bootstrap"]
        or len(queries["families"]) != 2
    ):
        raise ValueError("Only restricted two-family sensitivity is supported")
    if (
        policy.get("generator") != "NumPy Generator(PCG64)"
        or type(policy.get("seed")) is not int
        or type(policy.get("replicates")) is not int
        or policy["replicates"] < 1
    ):
        raise ValueError("Require explicit PCG64 seed and positive replicate count")
    families = sorted(queries["families"])
    groups = [
        [i["intent_id"] for i in queries["intents"] if i["family_id"] == f]
        for f in families
    ]
    if any(not g for g in groups):
        raise ValueError("Each direct family requires at least one intent")
    generator = np.random.Generator(np.random.PCG64(policy["seed"]))
    draws = generator.integers(0, len(groups), size=(policy["replicates"], len(groups)))
    multiplicities = np.column_stack([(draws == f).sum(axis=1) for f in range(2)])
    configurations = np.array([[2, 0], [1, 1], [0, 2]])
    output = []
    for metric in METRICS:
        rows = [r for r in paired if r["metric"] == metric]
        expected = {i["intent_id"] for i in queries["intents"]}
        if len(rows) != len(expected) or {r["intent_id"] for r in rows} != expected:
            raise ValueError(
                "Incomplete paired intent collection for family sensitivity"
            )
        by_id = {r["intent_id"]: r for r in rows}
        reasons = [
            r["intent_id"] for r in rows if r["lower"] is None or r["upper"] is None
        ]
        if reasons:
            output.append(
                {"metric": metric, "status": "undefined", "blocked_intents": reasons}
            )
            continue
        sizes = np.array([len(g) for g in groups])
        denominators = multiplicities @ sizes
        bounds = {}
        examples = {}
        for endpoint in ["lower", "upper"]:
            totals = np.array([sum(by_id[i][endpoint] for i in g) for g in groups])
            estimates = (multiplicities @ totals) / denominators
            examples[endpoint] = (
                (configurations @ totals) / (configurations @ sizes)
            ).tolist()
            bounds[endpoint + "_reference_envelope_percentiles"] = np.quantile(
                estimates, [0.025, 0.975], method="linear"
            ).tolist()
        output.append(
            {
                "metric": metric,
                "status": "restricted-sensitivity-diagnostic",
                **bounds,
                "multiplicity_estimates": [
                    {
                        "family_counts": dict(
                            zip(families, counts.tolist(), strict=True)
                        ),
                        "intent_occurrences": int(counts @ sizes),
                        "lower_reference_envelope": examples["lower"][j],
                        "upper_reference_envelope": examples["upper"][j],
                    }
                    for j, counts in enumerate(configurations)
                ],
            }
        )
    return {
        "role": policy["role"],
        "family_count": len(groups),
        "replicates": policy["replicates"],
        "seed": policy["seed"],
        "generator": policy["generator"],
        "percentiles": [0.025, 0.975],
        "quantile_method": "linear",
        "estimate_weighting": "equal-intent with drawn family multiplicity",
        "distinct_family_multiplicities": 3,
        "confidence_interval": False,
        "reference_aggregation": (
            "conservative envelopes, no joint physical attainment claim"
        ),
        "results": output,
    }


def evaluate_relation_controls(
    rankings: pd.DataFrame,
    references: pd.DataFrame,
    queries: dict,
    models: list[str],
    protocol: dict,
) -> list[dict]:
    """Analyze separate both-present controls without pooling main results.

    Parameters
    ----------
    rankings, references, queries, models, protocol
        Same complete main inputs as evaluate_rankings. Filtering is explicit:
        both canonical single presence states must be true; unknown relation
        states stay inside each predefined control. No score-based selection.

    Returns
    -------
    list of dict
        Exploratory per-adjacency counts/exclusions and separate analysis.
        Empty pools are explicitly undefined; small pools retain unavailable
        P@10/error-rank flags. These are not confirmatory relation results.
    """
    if protocol != PROTOCOL_CONTRACT:
        raise ValueError("Explicit frozen analysis protocol required")
    _validated_rankings(rankings, references, queries, models, queries["intents"])
    results = []
    for intent in queries["intents"]:
        if intent["kind"] != "adjacency":
            continue
        singles = [
            next(
                i["intent_id"]
                for i in queries["intents"]
                if i["kind"] == "single" and i["classes"] == [name]
            )
            for name in intent["classes"]
        ]
        presence = references[singles]
        both = presence.eq("true").all(axis=1)
        missing = presence.eq("false").any(axis=1)
        ids = sorted(references.index[both])
        row = {
            "intent_id": intent["intent_id"],
            "role": "exploratory",
            "candidate_ids": ids,
            "excluded_false_presence": int(missing.sum()),
            "excluded_unknown_presence": int((~both & ~missing).sum()),
            "reference_counts": {
                s: int(references.loc[ids, intent["intent_id"]].eq(s).sum())
                for s in ["true", "false", "unknown"]
            },
        }
        if not ids:
            row.update(
                status="undefined",
                reason="No both-known-present candidates",
                analysis=None,
            )
        else:
            qids = [
                f"{intent['intent_id']}/p{p}"
                for p in range(1, len(intent["paraphrases"]) + 1)
            ]
            subset = rankings.loc[
                rankings.query_id.isin(qids) & rankings.patch_id.isin(ids)
            ].copy()
            subset = subset.sort_values(["model_id", "query_id", "rank"])
            subset["rank"] = subset.groupby(["model_id", "query_id"]).cumcount() + 1
            row.update(
                status="exploratory-only",
                reason="Sparse negatives; no confirmatory claim",
                analysis=evaluate_rankings(
                    subset,
                    references.loc[ids],
                    queries,
                    models,
                    protocol,
                    control_intent=intent["intent_id"],
                ),
            )
        results.append(row)
    return results
