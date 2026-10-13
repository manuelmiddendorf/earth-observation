"""Explicit RGB conversion and cache provenance/corruption contracts."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from earth_observation.encoding import (
    cached_embeddings,
    embedding_identity,
    identity_key,
    model_rgb,
)


def test_rgb_quantization_and_rejection():
    raw = np.array([[[0, 1500, 3000], [-1, 4000, 750]]])
    original = raw.copy()
    image = model_rgb(raw, 3000)
    assert image.mode == "RGB"
    np.testing.assert_array_equal(np.asarray(image), [[[0, 128, 255], [0, 255, 64]]])
    np.testing.assert_array_equal(raw, original)
    for values, upper in [
        (np.ma.array(raw, mask=raw == 0), 3000),
        (np.array([[[np.nan, 1, 2]]]), 3000),
        (raw, 0),
        (raw[:, :, 0], 3000),
    ]:
        with pytest.raises(ValueError):
            model_rgb(values, upper)


def test_cache_reuse_identity_changes_and_corruption(tmp_path):
    identity = {
        "images": [{"patch_id": "p"}],
        "queries": [{"query_id": "q"}],
        "embedding_dimension": 2,
        "model": "checkpoint-v1",
    }
    calls = []

    def encode():
        calls.append(1)
        return (
            np.array([[1, 0]], dtype="float32"),
            np.array([[0, 1]], dtype="float32"),
            {},
        )

    path = tmp_path / "cache.npz"
    first = cached_embeddings(path, identity, encode)
    mtime = path.stat().st_mtime_ns
    second = cached_embeddings(path, identity, encode)
    assert first[3] is False and second[3] is True
    assert len(calls) == 1 and path.stat().st_mtime_ns == mtime
    np.testing.assert_array_equal(first[0], second[0])
    changed = {**identity, "model": "checkpoint-v2"}
    assert identity_key(changed) != identity_key(identity)
    with pytest.raises(ValueError, match="identity"):
        cached_embeddings(path, changed, encode)
    with np.load(path, allow_pickle=False) as cache:
        metadata = cache["metadata"].copy()
        texts = cache["texts"].copy()
    # Another valid unit vector is still corruption of the stored embedding.
    np.savez(
        path, images=np.array([[0, 1]], dtype="float32"), texts=texts, metadata=metadata
    )
    with pytest.raises(ValueError, match="Corrupt"):
        cached_embeddings(path, identity, encode)
    assert len(calls) == 1


def test_identity_tracks_exact_bytes_text_order_and_software(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    files = {}
    for band in ("B04", "B03", "B02"):
        files[band] = tmp_path / f"{band}.tif"
        files[band].write_bytes(b"original")

    def identity(model=None, queries=None, texts=None, settings=None):
        return embedding_identity(
            model or config["models"][0],
            settings or config,
            ["p"],
            [files],
            queries or ["q1", "q2"],
            texts or ["first", "second"],
        )

    original = identity()
    for changed in [
        identity(queries=["q2", "q1"], texts=["second", "first"]),
        identity(texts=["first changed", "second"]),
        identity(model=config["models"][1]),
    ]:
        assert identity_key(changed) != identity_key(original)
    settings = copy.deepcopy(config)
    settings["rgb"]["upper_dn"] = 4000
    assert identity_key(identity(settings=settings)) != identity_key(original)
    files["B02"].write_bytes(b"changed")
    assert identity_key(identity()) != identity_key(original)
    changed = copy.deepcopy(original)
    changed["software"]["torch"] = "different"
    assert identity_key(changed) != identity_key(original)
    with pytest.raises(ValueError, match="rows"):
        identity(queries=["q1"])


@pytest.mark.integration
def test_real_model_artifacts_reused_without_encoding():
    from earth_observation.encoding import file_digest

    root = Path(__file__).resolve().parents[1]
    path = root / "outputs/frozen-retrieval-pilot-v1/run.json"
    if not path.exists():
        pytest.skip("BLOCKED: original real model provenance unavailable")
    provenance = json.loads(path.read_text())

    def no_encoding():
        raise AssertionError("Integration must reuse existing historical encoding")

    for run in provenance["models"].values():
        cache = root / "data/cache/embeddings" / f"{run['cache_key']}.npz"
        assert file_digest(cache) == run["cache_sha256"]
        _, _, measured, hit = cached_embeddings(cache, run["identity"], no_encoding)
        assert hit and measured == run["original_encoding"]
        assert measured["evaluation_mode"] and measured["all_parameters_frozen"]
        assert measured["dtype"] == "torch.float32" and measured["device"] == "cpu"


def test_text_context_limit_and_frozen_state_are_enforced():
    import open_clip
    import torch

    from earth_observation.encoding import encode_texts

    # No encoder invocation is permitted for either rejected input contract.
    model = torch.nn.Linear(2, 2).eval().requires_grad_(False)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    with pytest.raises(ValueError, match="77-token"):
        encode_texts(model, tokenizer, ["forest " * 80], batch_size=5)
    model.requires_grad_(True)
    with pytest.raises(ValueError, match="frozen"):
        encode_texts(model, tokenizer, ["forest"], batch_size=5)
