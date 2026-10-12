"""Real development evidence and a positive controlled freeze-contract fixture."""

import json
from pathlib import Path

import pandas as pd
import pytest

from earth_observation.benchmark import (
    coverage_tables,
    load_benchmark_record,
    spatial_split,
    verified_footprints,
    write_benchmark_record,
)
from earth_observation.encoding import file_digest
from earth_observation.validation import validate_development_sources

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_real_development_extension_text_grid_and_masks():
    manifest = ROOT / "manifests/development-validation-v2.json"
    if not (ROOT / "data/cache/metadata.parquet").exists():
        pytest.skip("BLOCKED: official local sources unavailable")
    result = validate_development_sources(
        manifest, ROOT / "data/cache", ROOT / "data/raw", 3000
    )
    assert len(result) == 13
    assert result.catalog_status.eq("verified").all()
    assert result.identical_rgb_map_grid.all()
    assert result.text_center_error_deg.max() <= 1e-8
    assert result.crs.eq("EPSG:32633").all()
    assert result[["height", "width"]].eq(120).all().all()
    assert result[["pixel_width_m", "pixel_height_m"]].eq(10).all().all()
    assert result[["rgb_masked_values", "map_masked_pixels"]].eq(0).all().all()
    policy = json.loads((ROOT / "config/benchmark-design-v1.json").read_text())
    geometry = verified_footprints(result.index.tolist(), ROOT / "data/raw")
    split = spatial_split(geometry, result.index.tolist(), policy["spatial"])
    assert split.split.eq("development").all() and split.group_id.nunique() == 1


@pytest.mark.integration
def test_text_raster_coordinate_mismatch_fails(monkeypatch):
    import earth_observation.validation as validation
    from earth_observation.data import load_pilot

    manifest = ROOT / "manifests/development-validation-v2.json"
    if not (ROOT / "data/cache/metadata.parquet").exists():
        pytest.skip("BLOCKED: official local sources unavailable")
    annotations, catalog = load_pilot(manifest, ROOT / "data/cache")
    modified = [dict(row) for row in annotations]
    modified[0]["latitude"] += 0.1
    monkeypatch.setattr(validation, "load_pilot", lambda *args: (modified, catalog))
    with pytest.raises(ValueError, match="coordinate"):
        validate_development_sources(
            manifest, ROOT / "data/cache", ROOT / "data/raw", 3000
        )


def test_complete_controlled_protocol_fixture_passes_freeze_checks(tmp_path):
    # This synthetic fixture proves validator reachability, not real data access,
    # scientific reference suitability, or a frozen project benchmark.
    queries = json.loads((ROOT / "config/query-specification-v1.json").read_text())
    design = json.loads((ROOT / "config/benchmark-design-v1.json").read_text())
    (tmp_path / "config").mkdir()
    for name in ["query-specification-v1.json", "benchmark-design-v1.json"]:
        (tmp_path / "config" / name).write_bytes((ROOT / "config" / name).read_bytes())
    ids = [
        f"controlled-{group}-{number:02d}" for group in range(4) for number in range(24)
    ]
    columns = [i["intent_id"] for i in queries["intents"]]
    rows = []
    for index in range(96):
        pattern = index % 4
        a, b = pattern != 3, pattern != 2
        both, adjacent = a and b, pattern == 0
        rows.append(
            [
                "true" if state else "false"
                for state in [a, b, a, b, both, adjacent, both, adjacent]
            ]
        )
    decisions = pd.DataFrame(rows, index=ids, columns=columns)
    groups = pd.Series([f"g{index // 24}" for index in range(96)], index=ids)
    _, _, _, controls = coverage_tables(decisions, queries, groups)
    record = {
        "version": "controlled-fixture-only",
        "status": "frozen",
        "blockers": [],
        "inputs_sha256": {
            f"config/{name}": file_digest(tmp_path / "config" / name)
            for name in ["query-specification-v1.json", "benchmark-design-v1.json"]
        },
        "main_candidates": {"development": [], "test": ids},
        "unassigned_selection": [],
        "previous_development_ids": [],
        "spatial_inventory": [
            {"patch_id": pid, "group_id": groups[pid], "split": "test"} for pid in ids
        ],
        "relevance": {"patch_ids": ids, "intent_ids": columns, "states": rows},
        "relation_controls": {"test": controls},
    }
    path = tmp_path / "fixture.json"
    write_benchmark_record(path, record)
    assert load_benchmark_record(path, tmp_path)["version"] == "controlled-fixture-only"
    # Successful loading still depends on unchanged protocol inputs.
    altered = dict(design)
    altered["coverage"] = {**design["coverage"], "main_min_positive": 100}
    (tmp_path / "config/benchmark-design-v1.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="Changed benchmark input"):
        load_benchmark_record(path, tmp_path)


@pytest.mark.integration
def test_both_candidate_versions_remain_blocked():
    if not (ROOT / "data/cache/metadata.parquet").exists():
        pytest.skip("BLOCKED: official local sources unavailable")
    for version, count in [("v1", 10), ("v2", 13)]:
        path = ROOT / f"manifests/benchmark-candidate-{version}.json"
        record = load_benchmark_record(path, ROOT, require_frozen=False)
        assert len(record["main_candidates"]["development"]) == count
        assert record["main_candidates"]["test"] == []
        with pytest.raises(ValueError, match="not frozen"):
            load_benchmark_record(path, ROOT)
