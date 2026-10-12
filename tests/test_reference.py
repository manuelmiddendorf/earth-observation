"""Hand-computed area/contact contracts and real pilot reference integration."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin

from earth_observation.reference import (
    conjunction,
    evaluate_intents,
    evaluate_pilot,
    load_specifications,
    summarize_reference,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def specifications():
    return load_specifications(
        ROOT / "config/reference-rules-v1.json",
        ROOT / "config/query-specification-v1.json",
    )


def summarize(labels, rules, dx=10, dy=10):
    return summarize_reference(
        None if labels is None else np.ma.asarray(labels),
        from_origin(500000, 5300000, dx, dy),
        CRS.from_epsg(32633),
        rules,
        [("forest", "inland_water"), ("arable_land", "pasture")],
    )


def test_aggregation_area_full_denominator_and_input_unchanged(specifications):
    rules, _ = specifications
    labels = np.array([[311, 312, 313, 211], [511, 512, 231, 112]])
    original = labels.copy()
    result = summarize(labels, rules, dx=20, dy=10)
    assert result["total_area_m2"] == 1600
    assert result["classes"]["forest"]["area_lower_m2"] == 600
    assert result["classes"]["forest"]["fraction_lower"] == 3 / 8
    assert result["classes"]["inland_water"]["area_lower_m2"] == 400
    np.testing.assert_array_equal(labels, original)


def test_threshold_inclusive_and_just_below(specifications):
    rules, _ = specifications
    rules = copy.deepcopy(rules)
    rules["classes"]["forest"]["presence_fraction"] = 0.25
    at = summarize(np.array([[311, 211], [211, 211]]), rules)
    assert at["classes"]["forest"]["state"] == "true"
    rules["classes"]["forest"]["presence_fraction"] = 0.25000001
    below = summarize(np.array([[311, 211], [211, 211]]), rules)
    assert below["classes"]["forest"]["state"] == "false"


def test_unknown_area_bounds_and_declared_masks(specifications):
    rules, _ = specifications
    rules = copy.deepcopy(rules)
    rules["classes"]["forest"]["presence_fraction"] = 0.5
    labels = np.ma.array([[311, 999], [777, 211]], mask=[[0, 0], [0, 1]])
    result = summarize(labels, rules)
    forest = result["classes"]["forest"]
    assert result["total_area_m2"] == 400
    assert result["unknown_area_m2"] == 300
    assert forest["area_lower_m2"] == 100
    assert forest["area_upper_m2"] == 400
    assert forest["state"] == "unknown"
    assert result["unexpected_codes"] == [777]
    # Known evidence can resolve an incomplete map, but the missing area is retained.
    rules["classes"]["forest"]["presence_fraction"] = 0.25
    assert summarize(labels, rules)["classes"]["forest"]["state"] == "true"


def test_nodata_does_not_disappear_from_denominator(specifications):
    rules, _ = specifications
    result = summarize(np.array([[311, 0], [211, 211]]), rules)
    assert result["classes"]["forest"]["fraction_lower"] == 0.25
    assert result["classes"]["forest"]["fraction_upper"] == 0.5
    assert result["unknown_area_m2"] == 100


def test_missing_map_is_unknown_not_zero(specifications):
    rules, queries = specifications
    result = summarize(None, rules)
    assert result["total_area_m2"] is None
    assert set(evaluate_intents(result, queries).values()) == {"unknown"}


def test_partial_map_can_prove_absence(specifications):
    rules, _ = specifications
    rules = copy.deepcopy(rules)
    rules["classes"]["forest"]["presence_fraction"] = 0.5
    result = summarize(np.array([[211, 211], [211, 999]]), rules)
    assert result["classes"]["forest"]["state"] == "false"
    assert result["classes"]["forest"]["fraction_upper"] == 0.25


def test_corner_touch_is_not_shared_boundary(specifications):
    rules, _ = specifications
    result = summarize(np.array([[311, 211], [211, 511]]), rules)
    pair = result["pairs"][("forest", "inland_water")]
    assert pair == {"boundary_lower_m": 0, "boundary_upper_m": 0, "state": "false"}


def test_rectangular_cells_count_each_edge_once(specifications):
    rules, _ = specifications
    # One east-west transition has a 10-m edge; one north-south transition
    # has a 20-m edge: total 30 m.
    result = summarize(np.array([[311, 511], [511, 511]]), rules, dx=20, dy=10)
    pair = result["pairs"][("forest", "inland_water")]
    assert pair["boundary_lower_m"] == 30  # One horizontal + one vertical contact.
    assert pair["boundary_upper_m"] == 30


def test_boundary_threshold_and_presence_are_both_required(specifications):
    rules, queries = specifications
    labels = np.array([[311, 511]] * 6)
    result = summarize(labels, rules)
    assert result["pairs"][("forest", "inland_water")]["boundary_lower_m"] == 60
    assert evaluate_intents(result, queries)["adjacent-forest-water"] == "true"
    changed = copy.deepcopy(rules)
    changed["adjacency"]["min_shared_boundary_m"] = 60.00001
    assert (
        evaluate_intents(summarize(labels, changed), queries)["adjacent-forest-water"]
        == "false"
    )
    changed = copy.deepcopy(rules)
    changed["classes"]["forest"]["presence_fraction"] = 0.6
    assert (
        evaluate_intents(summarize(labels, changed), queries)["adjacent-forest-water"]
        == "false"
    )


def test_unknown_contact_bounds_do_not_bridge_known_other_classes(specifications):
    rules, queries = specifications
    result = summarize(np.array([[311, 999, 511]] * 6), rules)
    pair = result["pairs"][("forest", "inland_water")]
    assert pair["boundary_lower_m"] == 0
    # Twelve possible horizontal contacts (120 m) plus five vertical
    # unknown/unknown contacts (50 m); conservative bounds need not be attainable.
    assert pair["boundary_upper_m"] == 170
    assert evaluate_intents(result, queries)["adjacent-forest-water"] == "unknown"
    result = summarize(np.array([[311, 211, 511]] * 6), rules)
    assert result["pairs"][("forest", "inland_water")]["boundary_upper_m"] == 0


@pytest.mark.parametrize(
    "states,expected",
    [
        (["true", "unknown"], "unknown"),
        (["false", "unknown"], "false"),
        (["true", "true"], "true"),
        (["unknown", "unknown"], "unknown"),
    ],
)
def test_three_state_conjunction(states, expected):
    assert conjunction(states) == expected


def test_reject_geographic_rotated_and_noninteger_rasters(specifications):
    from affine import Affine

    rules, _ = specifications
    with pytest.raises(ValueError, match="metre grid"):
        summarize_reference(
            np.array([[311]]),
            from_origin(1, 1, 0.1, 0.1),
            CRS.from_epsg(4326),
            rules,
            [],
        )
    with pytest.raises(ValueError, match="metre grid"):
        summarize_reference(
            np.array([[311]]),
            Affine(10, 1, 0, 0, -10, 0),
            CRS.from_epsg(32633),
            rules,
            [],
        )
    with pytest.raises(ValueError, match="metre grid"):
        summarize_reference(
            np.array([[311]]), from_origin(1, 1, 10, 10), CRS.from_epsg(2277), rules, []
        )
    with pytest.raises(ValueError, match="integer"):
        summarize(np.array([[311.0]]), rules)


def test_specification_rejects_overlapping_mapping_and_duplicate_ids(
    specifications, tmp_path
):
    rules, queries = specifications
    rules_path, query_path = tmp_path / "rules.json", tmp_path / "queries.json"
    bad = copy.deepcopy(rules)
    bad["classes"]["pasture"]["codes"].append(311)
    rules_path.write_text(json.dumps(bad))
    query_path.write_text(json.dumps(queries))
    with pytest.raises(ValueError, match="disjoint"):
        load_specifications(rules_path, query_path)
    rules_path.write_text(json.dumps(rules))
    bad_queries = copy.deepcopy(queries)
    bad_queries["intents"].append(bad_queries["intents"][0])
    query_path.write_text(json.dumps(bad_queries))
    with pytest.raises(ValueError, match="intent"):
        load_specifications(rules_path, query_path)


@pytest.mark.integration
def test_real_pilot_reference_integration(specifications):
    rules, queries = specifications
    manifest = ROOT / "manifests/data-pilot-v1.json"
    source = json.loads(manifest.read_text())
    if not all(
        (ROOT / "data/raw" / m["name"]).is_file()
        for a in source["raster_prefixes"]
        for m in a["members"]
    ):
        pytest.skip("Acquire real pilot with scripts/fetch_pilot.py first")
    summaries, table = evaluate_pilot(
        manifest, ROOT / "data/cache", ROOT / "data/raw", rules, queries
    )
    assert table.index.tolist() == source["patch_ids"]
    assert table.shape == (10, 8)
    assert set(table.to_numpy().ravel()) <= {"true", "false", "unknown"}
    for summary in summaries.values():
        assert summary["total_area_m2"] == 1_440_000
        assert summary["unknown_area_m2"] == 0
        assert summary["unexpected_codes"] == []
        for result in summary["classes"].values():
            assert result["area_lower_m2"] == result["area_upper_m2"]
        for result in summary["pairs"].values():
            assert result["boundary_lower_m"] == result["boundary_upper_m"]


def test_fully_unknown_map_and_known_contact_with_partial_evidence(specifications):
    rules, queries = specifications
    result = summarize(np.full((3, 3), 999), rules)
    assert result["unknown_area_m2"] == 900
    assert set(evaluate_intents(result, queries).values()) == {"unknown"}
    assert result["unexpected_codes"] == []
    partial = np.array([[311, 511]] * 6 + [[0, 0]])
    result = summarize(partial, rules)
    assert result["unknown_area_m2"] == 200
    assert result["pairs"][("forest", "inland_water")]["boundary_lower_m"] == 60
    assert evaluate_intents(result, queries)["adjacent-forest-water"] == "true"


def test_query_cannot_silently_reuse_different_reference_version(specifications):
    rules, queries = specifications
    evidence = summarize(np.array([[311, 511]] * 6), rules)
    changed_queries = copy.deepcopy(queries)
    changed_queries["reference_version"] = "reference-rules-v2"
    with pytest.raises(ValueError, match="versions differ"):
        evaluate_intents(evidence, changed_queries)
