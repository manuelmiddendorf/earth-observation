"""Connect identified pilot images, frozen encoding, exact ranking and references."""

import json
import platform
import time
from pathlib import Path

import pandas as pd

from earth_observation.data import acquire_rasters
from earth_observation.encoding import (
    cached_embeddings,
    embedding_identity,
    encode_frozen,
    file_digest,
    identity_key,
)
from earth_observation.raster import RGB_BANDS, patch_files
from earth_observation.reference import evaluate_pilot, load_specifications
from earth_observation.retrieval import cosine_rankings, ranking_metrics


def run_retrieval_pilot(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute or reuse the two-model development pilot and save local results.

    Parameters
    ----------
    root : Path
        Repository root with versioned configurations and original pilot manifest.
        Missing raw files use the existing bounded acquisition contract.

    Returns
    -------
    tuple
        Model × formulation metric table, complete scored rankings with reference
        states attached AFTER ranking, and provenance/cache/timing metadata.
        Ignored outputs/frozen-retrieval-pilot-v1 contains CSVs and run.json; local
        embeddings are content-addressed under data/cache/embeddings.
        No intent-level aggregation, candidate filtering or benchmark freeze.
    """
    start = time.perf_counter()
    manifest_path = root / "manifests/data-pilot-v1.json"
    manifest = json.loads(manifest_path.read_text())
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    acquire_rasters(manifest_path, root / "data/cache", root / "data/raw")
    patch_ids = manifest["patch_ids"]
    files = []
    for pid in patch_ids:
        paths = patch_files(
            pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        files.append({band: paths[band] for band in RGB_BANDS})
    formulations = pd.DataFrame(
        [
            {
                "query_id": f"{intent['intent_id']}/p{number}",
                "intent_id": intent["intent_id"],
                "family_id": intent["family_id"],
                "text": text,
            }
            for intent in queries["intents"]
            for number, text in enumerate(intent["paraphrases"], 1)
        ]
    )
    query_ids = formulations["query_id"].tolist()
    texts = formulations["text"].tolist()
    rankings, model_runs = [], {}
    for model in config["models"]:
        identity = embedding_identity(model, config, patch_ids, files, query_ids, texts)
        key = identity_key(identity)
        cache = root / "data/cache/embeddings" / f"{key}.npz"
        before = time.perf_counter()
        images, text_vectors, measured, hit = cached_embeddings(
            cache,
            identity,
            lambda: encode_frozen(model, config, root / "models/weights", files, texts),
        )
        lookup_seconds = time.perf_counter() - before
        rank_start = time.perf_counter()
        scores, order = cosine_rankings(images, text_vectors, patch_ids, query_ids)
        rank_seconds = time.perf_counter() - rank_start
        model_runs[model["model_id"]] = {
            "cache_key": key,
            "cache_sha256": file_digest(cache),
            "cache_hit": hit,
            "cache_lookup_or_encode_seconds": lookup_seconds,
            "ranking_seconds": rank_seconds,
            "original_encoding": measured,
            "identity": identity,
        }
        for q, formulation in formulations.iterrows():
            for rank, index in enumerate(order[q], 1):
                rankings.append(
                    {
                        "model_id": model["model_id"],
                        **formulation.to_dict(),
                        "rank": rank,
                        "patch_id": patch_ids[index],
                        "cosine_similarity": float(scores[q, index]),
                    }
                )
    # Map information first enters here, after all candidates have been scored.
    _, references = evaluate_pilot(
        manifest_path, root / "data/cache", root / "data/raw", rules, queries
    )
    ranking_table = pd.DataFrame(rankings)
    ranking_table["reference_state"] = [
        references.loc[row.patch_id, row.intent_id]
        for row in ranking_table.itertuples()
    ]
    metrics = []
    for (model_id, query_id), group in ranking_table.groupby(
        ["model_id", "query_id"], sort=False
    ):
        intent = group.iloc[0]["intent_id"]
        metrics.append(
            {
                "model_id": model_id,
                "query_id": query_id,
                "intent_id": intent,
                "family_id": group.iloc[0]["family_id"],
                "text": group.iloc[0]["text"],
                **ranking_metrics(
                    group["patch_id"].tolist(), references[intent].to_dict()
                ),
            }
        )
    metric_table = pd.DataFrame(metrics)
    provenance = {
        "experiment_version": config["version"],
        "status": "technical development pilot; not final evaluation",
        "platform": {
            "machine": platform.machine(),
            "python": platform.python_version(),
            "system": platform.system(),
        },
        "inputs": {
            str(path): file_digest(root / path)
            for path in (
                "manifests/data-pilot-v1.json",
                "config/frozen-models-v1.json",
                "config/query-specification-v1.json",
                "config/reference-rules-v1.json",
            )
        },
        "models": model_runs,
        "run_seconds": time.perf_counter() - start,
    }
    output = root / "outputs" / config["version"]
    output.mkdir(parents=True, exist_ok=True)
    metric_table.to_csv(output / "metrics.csv", index=False)
    ranking_table.to_csv(output / "rankings.csv", index=False)
    provenance["outputs"] = {
        name: file_digest(output / name) for name in ("metrics.csv", "rankings.csv")
    }
    (output / "run.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return metric_table, ranking_table, provenance
