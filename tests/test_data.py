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


def test_ignored_archive_range_fails_before_read(monkeypatch, tmp_path):
    from earth_observation.data import fetch_asset

    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            pytest.fail("A full-archive response must never be read")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    asset = {
        "name": "prefix.zst",
        "url": "https://example.org/archive",
        "size_bytes": 1024,
        "sha256": "unused",
        "byte_range": [0, 1023],
        "archive_size_bytes": 1_000_000,
    }
    with pytest.raises(ValueError, match="exact archive range"):
        fetch_asset(asset, tmp_path)


@pytest.fixture
def archive_prefix(tmp_path):
    import io
    import tarfile

    import zstandard

    content = b"known member bytes"
    name = "BigEarthNet-S2/tile/patch/patch_B04.tif"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for member_name, data in [(name, content), ("unrelated.tif", b"excluded")]:
            entry = tarfile.TarInfo(member_name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    prefix = tmp_path / "prefix.zst"
    prefix.write_bytes(zstandard.ZstdCompressor().compress(output.getvalue()))
    members = [
        {
            "name": name,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    ]
    return prefix, members


def test_selected_extraction_preserves_existing_data(archive_prefix, tmp_path):
    from earth_observation.data import extract_rasters

    prefix, members = archive_prefix
    raw = tmp_path / "raw"
    paths = extract_rasters(prefix, members, raw)
    assert paths[0].read_bytes() == b"known member bytes"
    assert len(list(raw.rglob("*.tif"))) == 1
    paths[0].write_bytes(b"incompatible user file")
    with pytest.raises(ValueError, match="Existing raster identity mismatch"):
        extract_rasters(prefix, members, raw)
    assert paths[0].read_bytes() == b"incompatible user file"


def test_incomplete_or_changed_members_fail(archive_prefix, tmp_path):
    from earth_observation.data import extract_rasters

    prefix, members = archive_prefix
    changed = [{**members[0], "sha256": "incorrect"}]
    with pytest.raises(ValueError, match="checksum mismatch"):
        extract_rasters(prefix, changed, tmp_path / "bad-digest")
    missing = [{**members[0], "name": "BigEarthNet-S2/tile/patch/absent_B02.tif"}]
    with pytest.raises(ValueError, match="all requested rasters"):
        extract_rasters(prefix, missing, tmp_path / "missing-member")
    assert not list(tmp_path.rglob("*.tif"))
