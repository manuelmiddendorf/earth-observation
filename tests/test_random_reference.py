"""Independent finite-population checks for post-hoc random expectations."""

from itertools import combinations
from math import comb

import pytest

from earth_observation.random_reference import expected_random_metrics


def test_expectations_against_all_relevant_position_sets():
    # Every two-positive position set is equally likely under a random ranking.
    n, positives = 11, 2
    ap, precision = 0.0, 0.0
    for positions in combinations(range(1, n + 1), positives):
        ap += sum(i / rank for i, rank in enumerate(positions, 1)) / positives
        precision += sum(rank <= 10 for rank in positions) / 10
    expected = expected_random_metrics(n, positives)
    assert expected["average_precision"] == pytest.approx(ap / comb(n, positives))
    assert expected["p_at_10"] == pytest.approx(precision / comb(n, positives))


def test_all_positive_and_one_positive_populations():
    assert expected_random_metrics(10, 10) == pytest.approx(
        {"p_at_10": 1, "average_precision": 1}
    )
    assert expected_random_metrics(10, 1)["average_precision"] == pytest.approx(
        sum(1 / k for k in range(1, 11)) / 10
    )


@pytest.mark.parametrize("n,r", [(9, 2), (10, 0), (10, 11), (10.0, 2), (10, True)])
def test_invalid_counts_and_undefined_metrics(n, r):
    with pytest.raises(ValueError):
        expected_random_metrics(n, r)


def test_unknown_bounds_and_control_population_remain_separate():
    from earth_observation.random_reference import random_reference_rows

    main = {
        "intent_id": "water",
        "candidate_count": 20,
        "known_positive_count": 2,
        "unknown_count": 1,
    }
    control = {**main, "candidate_count": 10, "unknown_count": 0}
    result = {
        "main": {"reference_coverage": [main]},
        "exploratory_controls": [{"analysis": {"reference_coverage": [control]}}],
    }
    rows = random_reference_rows(result)
    precision = [r for r in rows if r["metric"] == "p_at_10"]
    assert precision[0]["lower"] == 0.1 and precision[0]["upper"] == 0.15
    assert precision[1]["lower"] == precision[1]["upper"] == 0.2
    main["unknown_count"] = 19
    with pytest.raises(ValueError, match="Unknown count"):
        random_reference_rows(result)
