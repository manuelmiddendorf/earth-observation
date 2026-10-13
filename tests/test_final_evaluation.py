"""Real saved Test integration: no hidden inference, identity/order and sample."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earth_observation import encoding, final_evaluation
from earth_observation.result_figures import error_sample_figure, sample_conditions

ROOT = Path(__file__).resolve().parents[1]


def test_changed_result_fails_before_any_model_or_raster_read(tmp_path, monkeypatch):
    result = {"stage": "final-test", "content_sha256": "invalid"}
    output = tmp_path / "outputs/final-evaluation-v1"
    output.mkdir(parents=True)
    (output / "results.json").write_text(json.dumps(result))

    def prohibited(*args, **kwargs):
        pytest.fail("Changed artifact reached freeze/model loading")

    monkeypatch.setattr(final_evaluation, "load_frozen_benchmark", prohibited)
    with pytest.raises(ValueError, match="content changed"):
        final_evaluation.load_final(tmp_path)


@pytest.mark.integration
def test_real_final_artifacts_and_fixed_native_sample_without_reencoding(monkeypatch):
    if not (ROOT / "outputs/final-evaluation-v1/results.json").is_file():
        pytest.skip("Requires locally produced frozen Test artifacts; no acquisition")

    def prohibited(*args, **kwargs):
        pytest.fail("Stored final read attempted inference/acquisition")

    monkeypatch.setattr(encoding, "fetch_asset", prohibited)
    monkeypatch.setattr(final_evaluation, "encode_frozen", prohibited)
    caches = list((ROOT / "data/cache/embeddings").glob("*.npz"))
    before = {p: p.stat().st_mtime_ns for p in caches}
    result = final_evaluation.load_final(ROOT)
    assert result["ranking_rows"] == 2 * 24 * 871
    assert result["spatial_groups"] == 637
    assert len(result["candidate_ids"]) == len(set(result["candidate_ids"])) == 871
    assert len(result["query_ids"]) == 24
    assert result["new_downloads"] is False
    samples = sample_conditions(ROOT, result)
    assert len(samples) == 48
    assert set(samples["rank"]) == {1, 5, 10}
    assert samples.query_id.str.endswith("/p1").all()
    assert not samples.duplicated(["model_id", "intent_id", "rank"]).any()
    ranks = pd.read_csv(ROOT / "outputs/final-evaluation-v1/rankings.csv")
    joined = samples.merge(ranks, on=["model_id", "query_id", "rank", "patch_id"])
    assert len(joined) == 48
    # Exercise actual RGB-only loading beside reference maps: reference paths
    # must never be passed into the strict three-band image reader.
    import matplotlib.pyplot as plt

    fig = error_sample_figure(ROOT, samples, "adjacent-arable-pasture")
    assert len(fig.axes) == 12
    plt.close(fig)
    for model in result["models"].values():
        assert model["image_shape"] == [871, 512]
        assert model["text_shape"] == [24, 512]
        assert model["original_encoding"]["all_parameters_frozen"]
        cache = ROOT / "data/cache/embeddings" / f"{model['cache_key']}.npz"
        with np.load(cache, allow_pickle=False) as data:
            np.testing.assert_allclose(
                np.linalg.norm(data["images"], axis=1), 1, atol=1e-5, rtol=0
            )
    assert {p: p.stat().st_mtime_ns for p in caches} == before
    assert not any(row["reason"] for row in result["main"]["intents"])
