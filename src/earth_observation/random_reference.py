"""Analytical random-ranking context, added after the frozen Test evaluation.

A uniformly random permutation has expected precision equal to prevalence.
Expected AP also depends on the finite candidate count. These expectations
provide descriptive context, not new benchmark rules or significance tests.
"""

from math import fsum


def expected_random_metrics(
    candidate_count: int, positive_count: int
) -> dict[str, float]:
    """Return expected P@10 and AP for a uniform random permutation.

    Parameters
    ----------
    candidate_count : int
        Number of distinct candidates, at least ten.
    positive_count : int
        Number of relevant candidates, between one and candidate_count.

    Returns
    -------
    dict[str, float]
        Analytical expectations of p_at_10 and average_precision. With
        harmonic sum H_N, expected AP is H_N/N +
        (R-1)(N-H_N)/(N(N-1)). These are means, not uncertainty intervals.

    Raises
    ------
    ValueError
        Counts are not integers, P@10 is undefined, or AP has no positives.
    """
    if (
        type(candidate_count) is not int
        or type(positive_count) is not int
        or candidate_count < 10
        or not 1 <= positive_count <= candidate_count
    ):
        raise ValueError("Require integer N >= 10 and 1 <= R <= N")
    harmonic = fsum(1 / rank for rank in range(1, candidate_count + 1))
    return {
        "p_at_10": positive_count / candidate_count,
        "average_precision": harmonic / candidate_count
        + (positive_count - 1)
        * (candidate_count - harmonic)
        / (candidate_count * (candidate_count - 1)),
    }


def random_reference_rows(result: dict) -> list[dict]:
    """Summarize random expectations for main intents and separate controls.

    Parameters
    ----------
    result : dict
        Stored final evaluation with reference_coverage in main and each
        exploratory control. No images, scores or model execution are used.

    Returns
    -------
    list[dict]
        One row per scope, intent and metric. Endpoints reflect the possible
        positive counts from known and unknown references; they are not
        confidence intervals. Original candidate populations remain intact.
    """
    pools = [("main", result["main"])]
    pools.extend(
        ("exploratory-control", control["analysis"])
        for control in result["exploratory_controls"]
    )
    rows = []
    for scope, pool in pools:
        for coverage in pool["reference_coverage"]:
            n = coverage["candidate_count"]
            positives = coverage["known_positive_count"]
            unknowns = coverage["unknown_count"]
            if type(unknowns) is not int or not 0 <= unknowns <= n - positives:
                raise ValueError("Unknown count exceeds the candidate population")
            lower = expected_random_metrics(n, positives)
            upper = expected_random_metrics(n, positives + unknowns)
            for metric in lower:
                rows.append(
                    {
                        "scope": scope,
                        "intent_id": coverage["intent_id"],
                        "metric": metric,
                        "candidate_count": n,
                        "known_positive_count": positives,
                        "unknown_count": unknowns,
                        "lower": lower[metric],
                        "upper": upper[metric],
                        "quantity": "expected-uniform-random-ranking",
                        "interpretation": "post-hoc descriptive context; not a CI",
                    }
                )
    return rows
