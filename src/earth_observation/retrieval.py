"""Exact image/text cosine retrieval and map-agreement metrics, without filtering."""

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


def ranking_metrics(ranked_ids: list[str], reference: dict[str, str]) -> dict:
    """Measure P@10 and AP against three-state map references after ranking.

    Parameters
    ----------
    ranked_ids : list of str
        Complete ordered candidate IDs. Scores and order are already fixed.
    reference : dict
        Exactly the same candidate IDs mapped to true, false or unknown.

    Returns
    -------
    dict
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
    ap = (
        float((np.cumsum(relevant) / np.arange(1, judged + 1))[relevant].sum())
        / positives
        if positives
        else float("nan")
    )
    precision = float(relevant[:10].mean()) if judged else float("nan")
    return {
        "candidate_count": len(states),
        "judged_count": judged,
        "unknown_count": unknown,
        "known_positive_count": positives,
        "judged_fraction": judged / len(states),
        "p_at_10": precision if not unknown and len(states) >= 10 else float("nan"),
        "average_precision": ap if not unknown else float("nan"),
        "judged_only_p_at_available": precision,
        "judged_only_average_precision": ap,
    }
