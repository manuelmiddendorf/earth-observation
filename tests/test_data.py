"""Identity and cache failure cases, plus a real official-catalog integration."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from earth_observation.data import (
    fetch_asset,
    load_pilot,
    match_metadata,
    select_patches,
)


def page(rows):
    return {
        "rows": [
            {"row_idx": i, "row": row, "truncated_cells": []}
            for i, row in enumerate(rows)
        ]
    }


def test_selection_preserves_identity_and_rejects_duplicates():
    rows = [
        {"ID": 1, "patch_id": "b", "s1_name": "s1b"},
        {"ID": 2, "patch_id": "b", "s1_name": "s1b"},
        {"ID": 3, "patch_id": "a", "s1_name": "s1a"},
    ]
    assert [p["patch_id"] for p in select_patches([page(rows)], 2)] == ["b", "a"]
    with pytest.raises(ValueError, match="Duplicate annotation"):
        select_patches([page([rows[0], rows[0]])], 1)
    with pytest.raises(ValueError, match="Not enough"):
        select_patches([page(rows)], 3)


def test_catalog_absence_is_unknown_and_contradiction_fails():
    patches = [{"patch_id": "a", "s1_name": "s1a"}, {"patch_id": "b", "s1_name": "s1b"}]
    metadata = pd.DataFrame([patches[0]])
    assert match_metadata(patches, metadata)["catalog_status"].tolist() == [
        "verified",
        "unknown",
    ]
    with pytest.raises(ValueError, match="Contradictory"):
        match_metadata(patches, pd.DataFrame([{"patch_id": "a", "s1_name": "wrong"}]))
    with pytest.raises(ValueError, match="unique"):
        match_metadata([patches[0], patches[0]], metadata)


def test_cache_reuse_and_stale_identity(tmp_path):
    content = b"known source"
    asset = {
        "name": "sample",
        "url": "https://invalid.example",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    (tmp_path / "sample").write_bytes(content)
    assert fetch_asset(asset, tmp_path).read_bytes() == content
    (tmp_path / "sample").write_bytes(b"stale")
    with pytest.raises(ValueError, match="identity mismatch"):
        fetch_asset(asset, tmp_path)
    with pytest.raises(ValueError, match="budget"):
        fetch_asset(asset, tmp_path, max_bytes=1)


@pytest.mark.integration
def test_official_text_catalog_pilot():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifests/data-pilot-v1.json").read_text())
    if not all((root / "data/cache" / a["name"]).is_file() for a in manifest["assets"]):
        pytest.skip("Run scripts/fetch_pilot.py to acquire official source snapshots")
    patches, joined = load_pilot(
        root / "manifests/data-pilot-v1.json", root / "data/cache"
    )
    assert len(patches) == 10
    assert joined["catalog_status"].tolist() == ["verified"] * 10
    assert joined["split"].equals(joined["split_metadata"])
    assert joined["country"].equals(joined["country_metadata"])


def test_annotation_pair_disagreement_fails():
    rows = [
        {"ID": 1, "patch_id": "a", "s1_name": "s1a"},
        {"ID": 2, "patch_id": "a", "s1_name": "other"},
    ]
    with pytest.raises(ValueError, match="Contradictory pair"):
        select_patches([page(rows)], 1)
