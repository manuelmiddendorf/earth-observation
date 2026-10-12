"""Interrupted transfers, source integrity and safe exact tar-member selection."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest
import zstandard

from earth_observation.archives import (
    download_archive,
    extract_archive_selection,
    selected_raster_members,
    verify_archive,
)

PATCH = "S2B_MSIL2A_20170801T095029_N9999_R079_T33TXN_01_53"


def asset_for(content, name="Reference_Maps.tar.zst"):
    return {
        "name": name,
        "url": f"https://zenodo.org/api/records/10891137/files/{name}/content",
        "size_bytes": len(content),
        "md5": hashlib.md5(content, usedforsecurity=False).hexdigest(),
    }


class Response(io.BytesIO):
    def __init__(self, content, start, end, total, status=206):
        super().__init__(content)
        self.status = status
        self.headers = {
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(end - start + 1),
        }


def test_interrupted_transfer_resumes_without_retransmitting(monkeypatch, tmp_path):
    payload = b"abcdefghij"
    requests = []

    def open_response(request, timeout):
        start, end = map(int, request.get_header("Range")[6:].split("-"))
        requests.append((start, end))
        content = payload[start : end + 1]
        if len(requests) == 1:
            content = content[:3]  # A real premature EOF, not a complete first chunk.
        return Response(content, start, end, len(payload))

    monkeypatch.setattr(
        "earth_observation.archives.urllib.request.urlopen", open_response
    )
    monkeypatch.setattr("earth_observation.archives.time.sleep", lambda _: None)
    result = download_archive(asset_for(payload), tmp_path, chunk_size_bytes=4)
    assert (tmp_path / "Reference_Maps.tar.zst").read_bytes() == payload
    assert requests == [(0, 3), (3, 6), (7, 9)]
    assert result["downloaded_bytes"] == 10
    assert result["md5"] == asset_for(payload)["md5"]
    # Complete verified archives are reused without any network call.
    monkeypatch.setattr(
        "earth_observation.archives.urllib.request.urlopen",
        lambda *_args, **_kwargs: pytest.fail("Complete archive must be reused"),
    )
    assert download_archive(asset_for(payload), tmp_path)["downloaded_bytes"] == 0


def test_ignored_resume_is_rejected_before_read_or_append(monkeypatch, tmp_path):
    payload = b"abcdefghij"
    asset = asset_for(payload)
    partial = tmp_path / f"{asset['name']}.part"
    partial.write_bytes(payload[:3])
    (tmp_path / f"{asset['name']}.part.json").write_text(json.dumps(asset))

    class Ignored(Response):
        def read(self, *args):
            pytest.fail("Ignored range must be rejected before reading payload")

    monkeypatch.setattr(
        "earth_observation.archives.urllib.request.urlopen",
        lambda *_args, **_kwargs: Ignored(payload, 0, 9, 10, status=200),
    )
    with pytest.raises(ValueError, match="exact resume range"):
        download_archive(asset, tmp_path)
    assert partial.read_bytes() == payload[:3]
    assert not (tmp_path / asset["name"]).exists()


def test_partial_identity_and_complete_checksum_fail_closed(tmp_path):
    asset = asset_for(b"abc")
    path = tmp_path / asset["name"]
    path.write_bytes(b"abd")
    with pytest.raises(ValueError, match="published MD5 mismatch"):
        verify_archive(path, asset)
    path.rename(tmp_path / f"{asset['name']}.part")
    with pytest.raises(ValueError, match="partial archive"):
        download_archive(asset, tmp_path)
    assert (tmp_path / f"{asset['name']}.part").read_bytes() == b"abd"


def test_failed_connections_have_a_bounded_retry_count(monkeypatch, tmp_path):
    attempted = []

    def fail(request, timeout):
        attempted.append(request.get_header("Range"))
        raise TimeoutError("No source response")

    monkeypatch.setattr("earth_observation.archives.urllib.request.urlopen", fail)
    monkeypatch.setattr("earth_observation.archives.time.sleep", lambda _: None)
    with pytest.raises(OSError, match="2 consecutive attempts"):
        download_archive(asset_for(b"abc"), tmp_path, attempts=2)
    assert attempted == ["bytes=0-2", "bytes=0-2"]
    assert not (tmp_path / "Reference_Maps.tar.zst").exists()


def test_bad_download_checksum_does_not_publish_or_restart(monkeypatch, tmp_path):
    asset = asset_for(b"abc")
    calls = []

    def source(request, timeout):
        calls.append(request.get_header("Range"))
        return Response(b"abd", 0, 2, 3)

    monkeypatch.setattr("earth_observation.archives.urllib.request.urlopen", source)
    with pytest.raises(ValueError, match="published MD5 mismatch"):
        download_archive(asset, tmp_path)
    assert calls == ["bytes=0-2"]
    assert (tmp_path / f"{asset['name']}.part").read_bytes() == b"abd"
    assert not (tmp_path / asset["name"]).exists()


def test_verified_receipt_reuse_and_modified_archive_rejection(monkeypatch, tmp_path):
    asset = asset_for(b"abc")
    path = tmp_path / asset["name"]
    path.write_bytes(b"abc")
    verified = verify_archive(path, asset)
    receipt = tmp_path / "verified.json"
    receipt.write_text(json.dumps({**verified, "status": "verified"}))
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if self == path:
            pytest.fail("Unchanged verified archive must not be hashed again")
        return original_open(self, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "open", guarded_open)
        assert verify_archive(path, asset, receipt) == verified
    path.write_bytes(b"abd")
    with pytest.raises(ValueError, match="MD5 mismatch"):
        verify_archive(path, asset, receipt)


def make_archive(tmp_path, members):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, content in members:
            info = tarfile.TarInfo(name)
            if content is None:
                info.type = tarfile.SYMTYPE
                info.linkname = "../../outside"
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    content = zstandard.ZstdCompressor().compress(stream.getvalue())
    asset = asset_for(content)
    path = tmp_path / asset["name"]
    path.write_bytes(content)
    return path, asset


def test_only_exact_requested_member_is_extracted_and_cache_checked(tmp_path):
    name = selected_raster_members([PATCH])[-1]
    path, asset = make_archive(
        tmp_path,
        [
            ("../../outside", b"unsafe"),
            (name + ".extra", b"decoy"),
            (name, b"native map"),
        ],
    )
    raw = tmp_path / "raw"
    result = extract_archive_selection(path, asset, [name], raw)
    assert result["created_files"] == 1
    assert len(list(raw.rglob("*.tif"))) == 1
    assert not (tmp_path / "outside").exists()
    assert extract_archive_selection(path, asset, [name], raw)["reused_files"] == 1
    (raw / name).write_bytes(b"user bytes")
    with pytest.raises(ValueError, match="Existing raster identity"):
        extract_archive_selection(path, asset, [name], raw)
    assert (raw / name).read_bytes() == b"user bytes"


@pytest.mark.parametrize("failure", ["duplicate", "link", "missing", "budget"])
def test_bad_selected_members_publish_no_tiffs(tmp_path, failure):
    name = selected_raster_members([PATCH])[-1]
    members = [(name, b"map")]
    if failure == "duplicate":
        members += members
    elif failure == "link":
        members = [(name, None)]
    elif failure == "missing":
        members = [(name + ".extra", b"map")]
    path, asset = make_archive(tmp_path, members)
    raw = tmp_path / "raw"
    with pytest.raises(ValueError):
        extract_archive_selection(
            path,
            asset,
            [name],
            raw,
            selected_budget_bytes=2 if failure == "budget" else 67108864,
        )
    assert not list(raw.rglob("*.tif"))


def test_output_symlink_cannot_escape_raw_root(tmp_path):
    name = selected_raster_members([PATCH])[-1]
    path, asset = make_archive(tmp_path, [(name, b"map")])
    raw = tmp_path / "raw"
    raw.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (raw / "Reference_Maps").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        extract_archive_selection(path, asset, [name], raw)
    assert not list(outside.rglob("*"))


@pytest.mark.integration
def test_real_checksum_verified_25_reference_members():
    root = Path(__file__).resolve().parents[1]
    output = root / "data/cache/archive-access/maps-extraction.json"
    if not output.is_file():
        pytest.skip("Acquire and extract the official reference archive first")
    result = json.loads(output.read_text())
    assert len(result["members"]) == 25
    for member in result["members"]:
        content = (root / "data/raw" / member["name"]).read_bytes()
        assert len(content) == member["size_bytes"]
        assert hashlib.sha256(content).hexdigest() == member["sha256"]


@pytest.mark.integration
def test_reference_preview_preserves_unknown_contract_and_exact_selection(tmp_path):
    import pandas as pd

    from earth_observation.archive_validation import inspect_reference_selection
    from earth_observation.reference import load_specifications

    root = Path(__file__).resolve().parents[1]
    output = root / "data/cache/archive-access/maps-extraction.json"
    if not output.is_file():
        pytest.skip("Acquire and extract the official reference archive first")
    receipt = json.loads(output.read_text())
    ids = pd.read_csv(root / "manifests/coverage-selection-v1.csv").head(25)
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    sources, states, _ = inspect_reference_selection(
        receipt, ids.patch_id.tolist(), root / "data/raw", rules, queries
    )
    assert len(sources) == 25
    assert sources.index.tolist() == ids.patch_id.tolist()
    assert states["single-forest"].value_counts().to_dict() == {"true": 16, "false": 9}
    assert sources.crs.eq("EPSG:32633").all()
    with pytest.raises(ValueError, match="exact selected maps"):
        inspect_reference_selection(
            receipt, ids.patch_id.tolist()[:1], root / "data/raw", rules, queries
        )
    member = receipt["members"][0]
    destination = tmp_path / member["name"]
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source identity mismatch"):
        inspect_reference_selection(
            {"members": [member]},
            ids.patch_id.tolist()[:1],
            tmp_path,
            rules,
            queries,
        )


@pytest.mark.integration
def test_complete_native_selection_and_unknown_text_are_separate():
    import pandas as pd

    from earth_observation.archive_validation import validate_raster_selection

    root = Path(__file__).resolve().parents[1]
    path = root / "data/cache/archive-access/extraction-results.json"
    if not path.is_file():
        pytest.skip("Extract the fixed 100 TIFFs first")
    extractions = json.loads(path.read_text())
    manifest = json.loads((root / "manifests/archive-data-access-v1.json").read_text())
    catalog = pd.read_parquet(root / "data/cache/metadata.parquet")
    checked = validate_raster_selection(
        extractions, manifest["planned_patch_ids"], root / "data/raw", catalog
    )
    assert len(checked) == 25
    assert checked.technical_status.eq("verified").all()
    assert checked.text_status.eq("unknown").all()
    assert checked.identical_rgb_map_grid.all()
    assert checked.rgb_dtype.eq("uint16").all()
    assert checked.rgb_valid_min_dn.ge(0).all()
    assert checked.rgb_valid_max_dn.le(65535).all()


@pytest.mark.integration
def test_supplied_text_cannot_contradict_native_center():
    import pandas as pd

    from earth_observation.archive_validation import validate_raster_selection

    root = Path(__file__).resolve().parents[1]
    path = root / "data/cache/archive-access/extraction-results.json"
    if not path.is_file():
        pytest.skip("Extract the fixed 100 TIFFs first")
    extractions = json.loads(path.read_text())
    manifest = json.loads((root / "manifests/archive-data-access-v1.json").read_text())
    ids = manifest["planned_patch_ids"]
    catalog = pd.read_parquet(root / "data/cache/metadata.parquet")
    source = catalog.set_index("patch_id").loc[ids[0]]
    # This contradictory validator fixture is not a fabricated research annotation.
    wrong = {
        "patch_id": ids[0],
        "s1_name": source.s1_name,
        "country": source.country,
        "ID": -1,
        "latitude": 0.0,
        "longitude": 0.0,
    }
    with pytest.raises(ValueError, match="native raster center"):
        validate_raster_selection(extractions, ids, root / "data/raw", catalog, [wrong])
