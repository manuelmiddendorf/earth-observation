"""Exact image/text cosine retrieval and map-agreement metrics, without filtering."""

from itertools import product

import numpy as np


def validate_ids(ids: list[str]) -> None:
    """Validate a nonempty ordered list of unique, nonempty string IDs.

    Parameters
    ----------
    ids : list of str
        Stable IDs in array row order; never coerced or reordered.

    Raises
    ------
    ValueError
        Empty, duplicate or non-string identities are supplied.
    """
    if not ids or any(type(i) is not str or not i for i in ids):
        raise ValueError("Require nonempty string IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate IDs")


def normalize_embeddings(values: np.ndarray) -> np.ndarray:
    """Return finite float32 unit vectors without mutating caller-owned arrays.

    Parameters
    ----------
    values : numpy.ndarray
        Nonempty N x D real-valued embeddings, ordered by caller IDs.

    Returns
    -------
    numpy.ndarray
        N x D float32 embeddings with Euclidean norm one per row.

    Raises
    ------
    ValueError
        Invalid shape, non-real/nonfinite values, or zero/overflowed norms.
    """
    values = np.asarray(values)
    if values.ndim != 2 or 0 in values.shape or values.dtype.kind not in "fiu":
        raise ValueError("Expected a nonempty real N x D array")
    converted = values.astype(np.float64)
    norms = np.linalg.norm(converted, axis=1, keepdims=True)
    if not np.isfinite(converted).all() or not np.isfinite(norms).all():
        raise ValueError("Nonfinite embeddings or norms")
    if np.any(norms == 0):
        raise ValueError("Zero embedding norm")
    return (converted / norms).astype(np.float32)


def cosine_rankings(
    images: np.ndarray, texts: np.ndarray, patch_ids: list[str], query_ids: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate every cosine score and deterministic complete query ranking.

    Parameters
    ----------
    images, texts : numpy.ndarray
        N x D image and Q x D text vectors in supplied ID order. Normalization
        is explicit inside this function; no metadata or references enter it.
    patch_ids, query_ids : list of str
        Unique identities in embedding row order.

    Returns
    -------
    tuple of numpy.ndarray
        Float64 Q x N cosine scores (not probabilities), and Q x N integer
        image row indices, descending score then ascending Unicode patch ID.
        A direct matrix product is used, without approximate search.

    Raises
    ------
    ValueError
        Identity counts or embedding dimensions disagree.
    """
    validate_ids(patch_ids)
    validate_ids(query_ids)
    image_unit = normalize_embeddings(images)
    text_unit = normalize_embeddings(texts)
    if image_unit.shape[0] != len(patch_ids) or text_unit.shape[0] != len(query_ids):
        raise ValueError("Embedding rows do not match IDs")
    if image_unit.shape[1] != text_unit.shape[1]:
        raise ValueError("Embedding dimensions differ")
    scores = text_unit.astype(np.float64) @ image_unit.astype(np.float64).T
    order = np.array([np.lexsort((patch_ids, -row)) for row in scores])
    return scores, order


def ranking_metrics(
    ranked_ids: list[str],
    reference: dict[str, str],
    protocol: dict | None = None,
) -> dict:
    """Measure P@10 and AP against three-state map references after ranking.

    Parameters
    ----------
    ranked_ids : list of str
        Complete ordered candidate IDs. Scores and order are already fixed.
    reference : dict
        Exactly the same candidate IDs mapped to true, false or unknown.

    protocol : dict or None
        Explicit frozen analysis-protocol-v1 enables completion bounds. None
        retains the historical pilot contract, including judged-only diagnostics.

    Returns
    -------
    dict
        With the protocol, coverage and structured metric_bounds (no imputed
        scalar scores): exact values or marginal reference intervals; explicit
        blocked/undefined reasons. Otherwise the historical return contract:
        Candidate, judged, unknown and known-positive counts and coverage;
        main p_at_10 and average_precision. Main metrics require complete
        judgments; P@10 additionally requires at least ten candidates; AP
        additionally requires positives. Undefined values are NaN. With all
        negative complete judgments P@10 is zero and AP undefined.
        Separate judged_only_p_at_available and judged_only_average_precision
        remove unknowns from this fixed ranking and are diagnostics ONLY.
        Diagnostic precision divides by min(10, judged count), not ten.

    Raises
    ------
    ValueError
        Invalid/duplicate IDs, absent/extra references or invalid states.
    """
    if protocol is not None:
        completion = completion_metrics(ranked_ids, reference, protocol)
        return {
            **completion["coverage"],
            "metric_bounds": {
                name: metric_bounds(
                    values,
                    completion["coverage"]["unknown_count"],
                    completion["reasons"][name],
                )
                for name, values in completion["values"].items()
            },
        }
    validate_ids(ranked_ids)
    if set(reference) != set(ranked_ids):
        raise ValueError("Reference IDs must exactly equal candidate IDs")
    if not set(reference.values()).issubset({"true", "false", "unknown"}):
        raise ValueError("Require true/false/unknown references")
    states = [reference[i] for i in ranked_ids]
    relevant = np.array([s == "true" for s in states if s != "unknown"])
    judged = len(relevant)
    positives = int(relevant.sum())
    unknown = len(states) - judged
    binary_metrics = _binary_metrics(relevant[None, :])
    ap = float(binary_metrics["average_precision"][0])
    precision = float(relevant[:10].mean()) if judged else float("nan")
    return {
        "candidate_count": len(states),
        "judged_count": judged,
        "unknown_count": unknown,
        "known_positive_count": positives,
        "judged_fraction": judged / len(states),
        "p_at_10": float(binary_metrics["p_at_10"][0]) if not unknown else float("nan"),
        "average_precision": ap if not unknown else float("nan"),
        "judged_only_p_at_available": precision,
        "judged_only_average_precision": ap,
    }


def _binary_metrics(relevance: np.ndarray) -> dict[str, np.ndarray]:
    """One canonical P@10/AP calculation for rows of complete binary relevance."""
    counts = relevance.sum(axis=1)
    precision_at_rank = np.cumsum(relevance, axis=1) / np.arange(
        1, relevance.shape[1] + 1
    )
    numerator = (precision_at_rank * relevance).sum(axis=1)
    ap = np.divide(
        numerator, counts, out=np.full(len(counts), np.nan), where=counts > 0
    )
    return {
        "p_at_10": relevance[:, :10].sum(axis=1) / 10
        if relevance.shape[1] >= 10
        else np.full(len(counts), np.nan),
        "average_precision": ap,
    }


def metric_bounds(
    values: np.ndarray, unknown_count: int, reason: str | None = None
) -> dict:
    """Summarize values over shared completions without inventing point scores.

    Parameters
    ----------
    values : numpy.ndarray
        One-dimensional score for each permitted reference completion.
    unknown_count : int
        Number of unresolved labels; collapsed bounds still retain uncertainty.
    reason : str or None
        Explicit blocked/undefined reason; no NaN skipping is permitted.

    Returns
    -------
    dict
        Status, exact value (only fully judged), lower/upper, reason and distinct
        uncertainty_type. Nonfinite or empty inputs are explicitly undefined.
    """
    values = np.asarray(values)
    if values.ndim != 1 or type(unknown_count) is not int or unknown_count < 0:
        raise ValueError("Require one-dimensional completion scores and unknown count")
    if not unknown_count and values.size > 1:
        raise ValueError("Fully known references have exactly one completion")
    if reason is not None or values.size == 0 or not np.isfinite(values).all():
        return {
            "status": "blocked"
            if reason and reason.startswith("blocked:")
            else "undefined",
            "value": None,
            "lower": None,
            "upper": None,
            "reason": reason or "Undefined completion; no partial aggregation",
            "uncertainty_type": "reference" if unknown_count else "none",
        }
    lower, upper = float(values.min()), float(values.max())
    return {
        "status": "reference-uncertainty-interval" if unknown_count else "exact",
        "value": None if unknown_count else lower,
        "lower": lower,
        "upper": upper,
        "reason": None,
        "uncertainty_type": "reference" if unknown_count else "none",
    }


def completion_metrics(
    ranked_ids: list[str], reference: dict[str, str], protocol: dict
) -> dict:
    """Enumerate exact P@10/AP scores under a fixed complete ranking.

    Parameters
    ----------
    ranked_ids : list of str
        All unique candidate IDs in fixed ranking order, including unknowns.
    reference : dict of str to str
        Exactly the candidates with true/false/unknown labels. Sorted unknown
        IDs define the lexicographic binary assignment order shared by every
        model and formulation. Labels and caller ranking are never mutated.
    protocol : dict
        The explicit supported frozen completion contract (limit twelve).

    Returns
    -------
    dict
        Coverage, sorted unknown IDs, assignment count, per-completion metric
        arrays and reasons. Beyond the cap both analyses are blocked. If a
        zero-positive completion is possible, every AP value is undefined.
        P@10 is undefined for fewer than ten candidates. No judged compression.

    Raises
    ------
    ValueError
        Unsupported protocol, invalid IDs, missing/extra labels or invalid states.
    """
    from earth_observation.analysis_protocol import PROTOCOL_CONTRACT

    if (
        protocol != PROTOCOL_CONTRACT
        or type(protocol.get("max_unknown_per_intent")) is not int
    ):
        raise ValueError("Unsupported frozen completion protocol")
    validate_ids(ranked_ids)
    if set(reference) != set(ranked_ids):
        raise ValueError("Reference IDs must exactly equal candidate IDs")
    if not set(reference.values()).issubset({"true", "false", "unknown"}):
        raise ValueError("Require true/false/unknown references")
    unknown_ids = sorted(p for p, state in reference.items() if state == "unknown")
    positives = sum(state == "true" for state in reference.values())
    coverage = {
        "candidate_count": len(ranked_ids),
        "judged_count": len(ranked_ids) - len(unknown_ids),
        "unknown_count": len(unknown_ids),
        "known_positive_count": positives,
        "judged_fraction": (len(ranked_ids) - len(unknown_ids)) / len(ranked_ids),
        "unknown_ids": unknown_ids,
    }
    if len(unknown_ids) > protocol["max_unknown_per_intent"]:
        return {
            "coverage": coverage,
            "assignment_count": None,
            "values": {k: np.array([]) for k in ["p_at_10", "average_precision"]},
            "reasons": {
                k: "blocked: unknown enumeration limit exceeded"
                for k in ["p_at_10", "average_precision"]
            },
        }
    assignments = np.array(
        list(product((False, True), repeat=len(unknown_ids))), dtype=bool
    )
    completed = np.tile(
        [reference[p] == "true" for p in ranked_ids], (len(assignments), 1)
    )
    positions = {p: i for i, p in enumerate(ranked_ids)}
    for column, pid in enumerate(unknown_ids):
        completed[:, positions[pid]] = assignments[:, column]
    values = _binary_metrics(completed)
    reasons = {
        "p_at_10": None if len(ranked_ids) >= 10 else "Fewer than ten candidates",
        "average_precision": None
        if positives
        else "blocked: possible zero-positive completion",
    }
    if not positives:
        values["average_precision"][:] = np.nan
    return {
        "coverage": coverage,
        "assignment_count": len(assignments),
        "values": values,
        "reasons": reasons,
    }
