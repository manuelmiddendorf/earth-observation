"""Ignored ranges, cumulative budgets and original row/schema identity."""

import copy
import io
import json
from pathlib import Path

import pytest

from earth_observation.text_access import acquire_text_asset, original_annotation

URL = "https://huggingface.co/datasets/example/resolve/revision/file.parquet"


def test_range_rejected_before_payload_and_budget_retains_failed_allocation(
    monkeypatch, tmp_path
):
    class Response(io.BytesIO):
        status = 200
        headers = {}

        def read(self, *args):
            pytest.fail("Ignored range must not read a complete source")

    monkeypatch.setattr(
        "earth_observation.text_access.urllib.request.urlopen",
        lambda *_a, **_k: Response(b"whole parquet"),
    )
    budget = {"limit_bytes": 10, "transferred_bytes": 0, "reserved_bytes": 0}
    with pytest.raises(ValueError, match="not honored"):
        acquire_text_asset(
            URL,
            tmp_path,
            "column.bin",
            budget,
            expected_size=4,
            byte_range=(2, 5),
            total_size=20,
        )
    assert budget == {"limit_bytes": 10, "transferred_bytes": 0, "reserved_bytes": 5}
    with pytest.raises(ValueError, match="budget"):
        acquire_text_asset(
            URL,
            tmp_path,
            "column.bin",
            budget,
            expected_size=5,
            byte_range=(2, 6),
            total_size=20,
        )
    assert not list(tmp_path.iterdir())


def test_pinned_cache_reuse_rejects_corruption_and_changed_range(monkeypatch, tmp_path):
    class Response(io.BytesIO):
        status = 206
        headers = {"Content-Range": "bytes 2-5/20", "Content-Length": "4"}

    monkeypatch.setattr(
        "earth_observation.text_access.urllib.request.urlopen",
        lambda *_a, **_k: Response(b"data"),
    )
    budget = {"limit_bytes": 10, "transferred_bytes": 0, "reserved_bytes": 0}
    kwargs = {"expected_size": 4, "byte_range": (2, 5), "total_size": 20}
    acquire_text_asset(URL, tmp_path, "column.bin", budget, **kwargs)
    monkeypatch.setattr(
        "earth_observation.text_access.urllib.request.urlopen",
        lambda *_a, **_k: pytest.fail("Valid cache must be reused"),
    )
    assert (
        acquire_text_asset(URL, tmp_path, "column.bin", budget, **kwargs)[0] == b"data"
    )
    assert budget["transferred_bytes"] == budget["reserved_bytes"] == 4
    with pytest.raises(ValueError, match="range identity"):
        acquire_text_asset(
            URL,
            tmp_path,
            "column.bin",
            budget,
            expected_size=4,
            byte_range=(3, 6),
            total_size=20,
        )
    (tmp_path / "column.bin").write_bytes(b"oops")
    with pytest.raises(ValueError, match="identity mismatch"):
        acquire_text_asset(URL, tmp_path, "column.bin", budget, **kwargs)


@pytest.mark.integration
def test_actual_annotation_rejects_wrong_position_truncation_and_schema():
    path = Path(__file__).resolve().parents[1] / "data/cache/text-rows-0.json"
    if not path.is_file():
        pytest.skip("Acquire the original pilot text cache first")
    page = json.loads(path.read_text())
    page["rows"] = page["rows"][:1]
    item = page["rows"][0]
    pid, offset = item["row"]["patch_id"], item["row_idx"]
    assert original_annotation(page, pid, offset)["ID"] == item["row"]["ID"]
    with pytest.raises(ValueError, match="position/ID"):
        original_annotation(page, pid, offset + 1)
    changed = copy.deepcopy(page)
    changed["rows"][0]["truncated_cells"] = ["input"]
    with pytest.raises(ValueError, match="position/ID"):
        original_annotation(changed, pid, offset)
    changed = copy.deepcopy(page)
    changed["features"][0]["type"]["dtype"] = "string"
    with pytest.raises(ValueError, match="schema"):
        original_annotation(changed, pid, offset)
