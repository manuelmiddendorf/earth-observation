"""Hand-computed retrieval contracts, including incomplete map judgments."""

import numpy as np
import pytest

from earth_observation.retrieval import (
    cosine_rankings,
    normalize_embeddings,
    ranking_metrics,
)


def test_unit_vectors_and_exact_cosines_do_not_mutate():
    images = np.array([[3, 4], [0, 2], [-3, -4]])
    original = images.copy()
    unit = normalize_embeddings(images)
    assert unit.dtype == np.float32
    np.testing.assert_allclose(unit[0], [0.6, 0.8])
    scores, order = cosine_rankings(images, np.array([[0, 1]]), ["b", "c", "a"], ["q"])
    np.testing.assert_allclose(scores, [[0.8, 1, -0.8]], atol=1e-7)
    assert order.tolist() == [[1, 0, 2]]
    np.testing.assert_array_equal(images, original)


@pytest.mark.parametrize(
    "values",
    [
        [[0, 0]],
        [[np.nan, 1]],
        [[np.inf, 1]],
        [],
        [1, 2],
        [[1 + 2j, 3]],
    ],
)
def test_invalid_embeddings_fail(values):
    with pytest.raises(ValueError):
        normalize_embeddings(np.asarray(values))


def test_ties_use_patch_ids_and_preserve_query_order():
    images = np.array([[1, 0], [1, 0], [0, 1]])
    scores, order = cosine_rankings(images, np.eye(2), ["z", "a", "b"], ["q2", "q1"])
    assert order.tolist() == [[1, 0, 2], [2, 1, 0]]
    np.testing.assert_array_equal(scores, [[1, 1, 0], [0, 0, 1]])
    for patch_ids, query_ids in [
        (["a", "a", "b"], ["q", "r"]),
        (["a", "b"], ["q", "r"]),
        (["a", "b", 3], ["q", "r"]),
        (["a", "b", "c"], ["q"]),
    ]:
        with pytest.raises(ValueError):
            cosine_rankings(images, np.eye(2), patch_ids, query_ids)
    with pytest.raises(ValueError, match="dimensions"):
        cosine_rankings(images, np.ones((1, 3)), ["a", "b", "c"], ["q"])


def test_metrics_hand_computed_and_no_positives():
    ids = [f"p{i}" for i in range(12)]
    refs = dict.fromkeys(ids, "false")
    refs["p0"] = refs["p2"] = refs["p10"] = "true"
    result = ranking_metrics(ids, refs)
    assert result["p_at_10"] == 0.2
    assert result["average_precision"] == pytest.approx((1 + 2 / 3 + 3 / 11) / 3)
    empty = ranking_metrics(ids, dict.fromkeys(ids, "false"))
    assert empty["p_at_10"] == 0
    assert np.isnan(empty["average_precision"])


def test_fewer_than_ten_unknown_and_all_unknown():
    result = ranking_metrics(["a", "b", "c"], {"a": "true", "b": "false", "c": "true"})
    assert np.isnan(result["p_at_10"])
    assert result["average_precision"] == pytest.approx(5 / 6)
    assert result["judged_only_p_at_available"] == pytest.approx(2 / 3)
    result = ranking_metrics(
        ["a", "b", "c"], {"a": "unknown", "b": "false", "c": "true"}
    )
    assert result["unknown_count"] == 1
    assert result["judged_fraction"] == pytest.approx(2 / 3)
    assert np.isnan(result["average_precision"])
    assert result["judged_only_average_precision"] == 0.5
    result = ranking_metrics(["a"], {"a": "unknown"})
    assert result["judged_count"] == 0
    assert np.isnan(result["judged_only_p_at_available"])
    assert np.isnan(result["judged_only_average_precision"])


@pytest.mark.parametrize(
    "ids,refs",
    [
        (["a", "a"], {"a": "true"}),
        (["a"], {}),
        (["a"], {"a": "true", "b": "false"}),
        (["a"], {"a": False}),
        ([], {}),
    ],
)
def test_reference_identity_or_state_mismatches_fail(ids, refs):
    with pytest.raises(ValueError):
        ranking_metrics(ids, refs)
