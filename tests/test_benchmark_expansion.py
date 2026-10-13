"""Stable sampling, authorized semantics, merged groups and frozen leakage guards."""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from earth_observation.benchmark import (
    select_catalog,
    spatial_split,
    write_benchmark_record,
)
from earth_observation.benchmark_expansion import (
    load_expanded_benchmark,
    spatial_transition_audit,
    verify_design_revision,
)

ROOT = Path(__file__).resolve().parents[1]


def test_design_revision_cannot_relax_gates_or_change_spatial_analysis():
    previous = json.loads((ROOT / "config/benchmark-design-v1.json").read_text())
    revised = json.loads((ROOT / "config/benchmark-design-v2.json").read_text())
    verify_design_revision(revised, previous)
    changed = copy.deepcopy(revised)
    changed["estimand"]["target"] = "verified-visible-truth"
    with pytest.raises(ValueError, match="mapped semantics"):
        verify_design_revision(changed, previous)
    changed = copy.deepcopy(revised)
    changed["estimand"]["original_captions_required"] = True
    with pytest.raises(ValueError, match="optional captions"):
        verify_design_revision(changed, previous)
    changed = copy.deepcopy(revised)
    changed["coverage"]["control_min_false"] = 1
    with pytest.raises(ValueError, match="coverage"):
        verify_design_revision(changed, previous)
    changed = copy.deepcopy(revised)
    changed["spatial"]["distance_m"] = 1
    with pytest.raises(ValueError, match="spatial"):
        verify_design_revision(changed, previous)


@pytest.mark.integration
def test_full_catalog_extension_preserves_country_prefixes_and_ignores_labels():
    path = ROOT / "data/cache/metadata.parquet"
    if not path.is_file():
        pytest.skip("Acquire the checksum-pinned catalog first")
    metadata = pd.read_parquet(path)
    design = json.loads((ROOT / "config/benchmark-design-v2.json").read_text())
    selected = select_catalog(metadata, design["selection"])
    old = pd.read_csv(ROOT / "manifests/coverage-selection-v1.csv")
    assert len(selected) == 2000 and selected.country.value_counts().eq(200).all()
    for country in old.country.unique():
        assert (
            selected.loc[selected.country.eq(country), "patch_id"].head(25).tolist()
            == old.loc[old.country.eq(country), "patch_id"].tolist()
        )
    metadata["labels"] = [[] for _ in range(len(metadata))]
    pd.testing.assert_frame_equal(
        selected, select_catalog(metadata, design["selection"])
    )


def test_new_neighbor_bridge_anchors_previously_test_group_in_development():
    footprint = pd.DataFrame(
        {
            "left": [0, 6000, 3000],
            "bottom": [0, 0, 0],
            "right": [1000, 7000, 4000],
            "top": [1000] * 3,
            "crs": ["EPSG:3035"] * 3,
            "native_crs": ["EPSG:32633"] * 3,
            "native_bounds": [
                [0, 0, 1000, 1000],
                [6000, 0, 7000, 1000],
                [3000, 0, 4000, 1000],
            ],
        },
        index=["dev", "prior-test", "bridge"],
    )
    policy = json.loads((ROOT / "config/benchmark-design-v2.json").read_text())[
        "spatial"
    ]
    previous = pd.DataFrame(
        {"group_id": ["dev", "prior-test"], "split": ["development", "test"]},
        index=["dev", "prior-test"],
    )
    assignment = spatial_split(footprint, ["dev"], policy)
    assert assignment.split.eq("development").all()
    audit = spatial_transition_audit(footprint, assignment, previous)
    assert audit["merged_previous_groups"][0]["old_groups"] == ["dev", "prior-test"]
    assert any(
        r["patch_id"] == "prior-test" and r["new_split"] == "development"
        for r in audit["prior_assignment_changes"]
    )
    corrupted = assignment.copy()
    corrupted.loc["dev", "split"] = "test"
    mixed = assignment.copy()
    mixed.loc["prior-test", "split"] = "test"
    with pytest.raises(ValueError, match="component leaks"):
        spatial_transition_audit(footprint, mixed, previous)
    with pytest.raises(ValueError, match="never enter Test"):
        spatial_transition_audit(footprint, corrupted, previous)


@pytest.mark.integration
def test_real_expansion_retains_unknown_text_and_rejects_false_freeze(tmp_path):
    path = ROOT / "manifests/benchmark-candidate-v4.json"
    if not path.is_file():
        pytest.skip("Complete the fixed local-archive expansion first")
    record = load_expanded_benchmark(path, ROOT, require_frozen=False)
    assert (
        len(
            record["main_candidates"]["development"] + record["main_candidates"]["test"]
        )
        == 2013
    )
    assert record["source_text_availability"]["not-requested"] == 1750
    assert record["source_text_availability"]["source-absent"] == 9
    if record["status"] == "blocked-not-frozen":
        with pytest.raises(ValueError, match="not frozen"):
            load_expanded_benchmark(path, ROOT)
        fake = copy.deepcopy(record)
        fake["status"], fake["blockers"] = "frozen", []
        destination = tmp_path / "false-freeze.json"
        write_benchmark_record(destination, fake)
        with pytest.raises(ValueError, match="coverage"):
            load_expanded_benchmark(destination, ROOT)
    else:
        load_expanded_benchmark(path, ROOT)
