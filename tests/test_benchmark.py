"""Known expectations for model-independent coverage, spatial splits and integrity."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earth_observation.benchmark import (
    coverage_tables,
    freeze_blockers,
    load_benchmark_record,
    reference_unknown_sources,
    select_catalog,
    spatial_split,
    verified_footprints,
    write_benchmark_record,
)
from earth_observation.encoding import file_digest
from earth_observation.reference import load_specifications

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "config/benchmark-design-v1.json").read_text())
RULES, QUERIES = load_specifications(
    ROOT / "config/reference-rules-v1.json", ROOT / "config/query-specification-v1.json"
)


def test_catalog_sampling_is_order_independent_and_never_uses_labels():
    rows = []
    for country in ["A", "B"]:
        for tile in ["33UUP", "33UVP", "33UWQ"]:
            for index in range(5):
                rows.append(
                    {
                        "patch_id": (
                            "S2A_MSIL2A_20170613T101031_N9999_R022_"
                            f"T{tile}_{index}_{ord(country)}"
                        ),
                        "country": country,
                        "labels": ["forest"],
                    }
                )
    frame = pd.DataFrame(rows)
    policy = {**DESIGN["selection"], "target_count": 6, "per_country": 3}
    first = select_catalog(frame, policy)
    shuffled = frame.sample(frac=1, random_state=19)
    shuffled["labels"] = "different labels"
    pd.testing.assert_frame_equal(first, select_catalog(shuffled, policy))
    assert first.groupby("country").size().tolist() == [3, 3]
    assert not first.tile.eq("33UUP").any()
    assert first.groupby("country").tile.nunique().eq(2).all()
    with pytest.raises(ValueError, match="Duplicate"):
        select_catalog(pd.concat([frame, frame.iloc[:1]]), policy)
    with pytest.raises(ValueError, match="Quota"):
        select_catalog(frame, {**policy, "target_count": 7})
    with pytest.raises(ValueError, match="Insufficient"):
        select_catalog(frame, {**policy, "per_country": 15, "target_count": 30})


def test_spatial_components_include_ties_chains_repeated_dates_and_anchors():
    frame = pd.DataFrame(
        [
            [4000000, 3000000, 4001000, 3001000],
            [4003000, 3000000, 4004000, 3001000],  # Exactly 2000 m apart.
            [4006000, 3000000, 4007000, 3001000],  # Transitive chain, not near first.
            [4000000, 3000000, 4001000, 3001000],  # Repeated acquisition footprint.
            [4010001, 3000000, 4011001, 3001000],
        ],
        columns=["left", "bottom", "right", "top"],
        index=pd.Index(
            ["old", "neighbor", "chain", "repeat-date", "far"], name="patch_id"
        ),
    )
    frame["crs"] = "EPSG:3035"
    policy = {**DESIGN["spatial"], "test_fraction": 0.999999}
    result = spatial_split(frame, ["old"], policy)
    assert result.group_id.nunique() == 2
    assert (
        result.loc[["old", "neighbor", "chain", "repeat-date"], "split"]
        .eq("development")
        .all()
    )
    assert result.loc["far", "split"] == "test"
    assert result.groupby("group_id").split.nunique().eq(1).all()
    pd.testing.assert_frame_equal(
        result.sort_index(),
        spatial_split(frame.iloc[::-1], ["old"], policy).sort_index(),
    )
    with pytest.raises(ValueError, match="anchors"):
        spatial_split(frame, ["missing"], policy)
    with pytest.raises(ValueError, match="metric"):
        spatial_split(frame.assign(crs="EPSG:4326"), [], policy)
    broken = frame.copy()
    broken.loc["far", "right"] = np.nan
    with pytest.raises(ValueError, match="metric"):
        spatial_split(broken, [], policy)


def test_three_state_coverage_and_filtered_relation_controls():
    intents = [i["intent_id"] for i in QUERIES["intents"]]
    decisions = pd.DataFrame("false", index=["a", "b", "c", "d"], columns=intents)
    for single in ["single-forest", "single-inland-water"]:
        decisions.loc[["a", "b", "c"], single] = "true"
    decisions.loc[["a", "b", "c"], "both-forest-water"] = "true"
    decisions.loc[["a", "b", "c"], "adjacent-forest-water"] = [
        "true",
        "false",
        "unknown",
    ]
    decisions.loc["d", "single-forest"] = "unknown"
    decisions.loc["d", "single-inland-water"] = "true"
    decisions.loc["d", ["both-forest-water", "adjacent-forest-water"]] = "unknown"
    groups = pd.Series(["g1", "g2", "g2", "g3"], index=decisions.index)
    intent, family, relation, controls = coverage_tables(decisions, QUERIES, groups)
    row = intent.loc["adjacent-forest-water"]
    assert row["true"] == 1 and row["false"] == 1 and row["unknown"] == 2
    assert row.judged_fraction == 0.5
    assert controls["adjacent-forest-water"] == ["a", "b", "c"]
    row = relation.loc["adjacent-forest-water"]
    assert (
        row.both_present == 3 and row.unknown_presence == 1 and row.missing_class == 0
    )
    assert row["true"] == row["false"] == row["unknown"] == 1
    assert row.judged_fraction == pytest.approx(2 / 3)
    assert relation.loc["adjacent-arable-pasture", "missing_class"] == 4
    assert family.loc["forest-water", "patch_intent_count"] == 16
    assert family.loc["forest-water", ["true", "false", "unknown"]].sum() == 16
    assert intent.loc["single-forest", "positive_outside_largest_group"] == 1
    with pytest.raises(ValueError, match="order"):
        coverage_tables(decisions, QUERIES, groups.iloc[::-1])
    broken = decisions.copy()
    broken.loc["a", intents[0]] = "missing"
    with pytest.raises(ValueError, match="three-state"):
        coverage_tables(broken, QUERIES, groups)


def test_unknown_source_causes_are_disjoint_and_missing_is_not_zero():
    labels = np.ma.array([[0, 999, 777, 311]], mask=[[True, False, False, False]])
    sources = reference_unknown_sources(labels, RULES)
    assert sources == {
        "missing_map": False,
        "masked_nodata_pixels": 1,
        "configured_unknown_pixels": 1,
        "unexpected_code_pixels": 1,
    }
    assert reference_unknown_sources(None, RULES)["masked_nodata_pixels"] is None
    with pytest.raises(ValueError, match="integer"):
        reference_unknown_sources(np.array([[311.0]]), RULES)


def test_freeze_gates_require_all_intents_controls_and_spatial_dispersion():
    main = pd.DataFrame(
        [
            {
                "true": 20,
                "false": 20,
                "unknown": 0,
                "judged_fraction": 1.0,
                "spatial_groups": 3,
                "positive_outside_largest_group": 10,
            }
            for _ in QUERIES["intents"]
        ],
        index=[i["intent_id"] for i in QUERIES["intents"]],
    )
    relations = pd.DataFrame(
        [
            {
                "true": 10,
                "false": 10,
                "unknown": 0,
                "judged_fraction": 1.0,
                "spatial_groups": 3,
                "true_outside_largest_group": 5,
                "false_outside_largest_group": 5,
            }
            for _ in range(2)
        ],
        index=["adjacent-forest-water", "adjacent-arable-pasture"],
    )
    assert freeze_blockers(main, relations, DESIGN["coverage"], 0, QUERIES) == []
    broken = main.copy()
    broken.iloc[0, broken.columns.get_loc("positive_outside_largest_group")] = 9
    assert any(
        "dispersion" in b
        for b in freeze_blockers(broken, relations, DESIGN["coverage"], 0, QUERIES)
    )
    assert any(
        "every fixed" in b
        for b in freeze_blockers(
            main, relations.iloc[:1], DESIGN["coverage"], 0, QUERIES
        )
    )
    assert freeze_blockers(
        pd.DataFrame(), pd.DataFrame(), DESIGN["coverage"], 250, QUERIES
    )


def test_record_integrity_changed_inputs_and_blocked_status(tmp_path):
    input_path = tmp_path / "rules.json"
    input_path.write_text("original")
    record = {
        "version": "candidate-v1",
        "status": "blocked-not-frozen",
        "blockers": ["coverage missing"],
        "inputs_sha256": {"rules.json": file_digest(input_path)},
    }
    path = tmp_path / "record.json"
    write_benchmark_record(path, record)
    assert (
        load_benchmark_record(path, tmp_path, require_frozen=False)["version"]
        == "candidate-v1"
    )
    with pytest.raises(ValueError, match="not frozen"):
        load_benchmark_record(path, tmp_path)
    with pytest.raises(ValueError, match="new version"):
        write_benchmark_record(path, {**record, "blockers": ["different reason"]})
    input_path.write_text("changed")
    with pytest.raises(ValueError, match="Changed benchmark input"):
        load_benchmark_record(path, tmp_path, require_frozen=False)
    tampered = json.loads(path.read_text())
    tampered["status"] = "frozen"
    path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="digest"):
        load_benchmark_record(path, tmp_path)


@pytest.mark.integration
def test_real_catalog_selection_and_native_spatial_separation():
    catalog_path = ROOT / "data/cache/metadata.parquet"
    if not catalog_path.exists():
        pytest.skip("BLOCKED: real official catalog unavailable")
    selection = select_catalog(pd.read_parquet(catalog_path), DESIGN["selection"])
    pd.testing.assert_frame_equal(
        selection, pd.read_csv(ROOT / "manifests/coverage-selection-v1.csv")
    )
    assert len(selection) == 250 and selection.country.nunique() == 10
    assert selection.tile.nunique() == 53
    pilot = json.loads((ROOT / "manifests/data-pilot-v1.json").read_text())
    from earth_observation.raster import patch_files

    files = [
        patch_files(
            pid, ROOT / "data/raw/BigEarthNet-S2", ROOT / "data/raw/Reference_Maps"
        )
        for pid in pilot["patch_ids"]
    ]
    if not all(path.is_file() for paths in files for path in paths.values()):
        pytest.skip("BLOCKED: real complete native rasters unavailable")
    footprints = verified_footprints(pilot["patch_ids"], ROOT / "data/raw")
    split = spatial_split(footprints, pilot["patch_ids"], DESIGN["spatial"])
    assert split.group_id.nunique() == 1 and split.split.eq("development").all()
    assert not set(selection.patch_id).intersection(pilot["patch_ids"])


@pytest.mark.integration
def test_real_candidate_record_refuses_final_evaluation():
    path = ROOT / "manifests/benchmark-candidate-v1.json"
    if not path.exists() or not (ROOT / "data/cache/metadata.parquet").exists():
        pytest.skip("BLOCKED: actual coverage record or local sources unavailable")
    record = json.loads(path.read_text())
    changed_inputs = [
        name
        for name, expected in record["inputs_sha256"].items()
        if file_digest(ROOT / name) != expected
    ]
    if changed_inputs:
        with pytest.raises(ValueError, match="Changed benchmark input") as error:
            load_benchmark_record(path, ROOT, require_frozen=False)
        assert str(error.value) == f"Changed benchmark input: {changed_inputs[0]}"
    else:
        load_benchmark_record(path, ROOT, require_frozen=False)
    assert record["access"]["test_count"] == 0
    assert len(record["unassigned_selection"]) == 250
    assert record["main_candidates"]["test"] == []
    reason = "Changed benchmark input" if changed_inputs else "not frozen"
    with pytest.raises(ValueError, match=reason):
        load_benchmark_record(path, ROOT)


@pytest.mark.integration
def test_false_freeze_status_cannot_bypass_readiness(tmp_path):
    path = ROOT / "manifests/benchmark-candidate-v1.json"
    if not path.exists() or not (ROOT / "data/cache/metadata.parquet").exists():
        pytest.skip("BLOCKED: real candidate record unavailable")
    record = json.loads(path.read_text())
    # Isolate readiness in a temporary fixture with current source code.
    # The historical manifest/source pin is never edited or accepted as current.
    for name in record["inputs_sha256"]:
        if name.startswith("src/"):
            record["inputs_sha256"][name] = file_digest(ROOT / name)
    record.update(version="invalid-freeze-v1", status="frozen", blockers=[])
    forged = tmp_path / "invalid-freeze.json"
    write_benchmark_record(forged, record)
    with pytest.raises(ValueError, match="Incomplete verified test"):
        load_benchmark_record(forged, ROOT)
