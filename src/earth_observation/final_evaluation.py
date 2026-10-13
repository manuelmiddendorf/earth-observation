"""Local-only frozen Test execution and verified stored-result consumption.

Model inputs contain RGB and query text only. Map references enter exclusively
AFTER complete scores/rankings are constructed. Large artifacts remain ignored.
"""

import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from earth_observation.analysis_protocol import load_frozen_benchmark
from earth_observation.encoding import (
    cached_embeddings,
    checkpoint_path,
    embedding_identity,
    encode_frozen,
    file_digest,
    identity_key,
)
from earth_observation.evaluation import (
    evaluate_rankings,
    evaluate_relation_controls,
    family_sensitivity,
    validate_benchmark_candidates,
)
from earth_observation.raster import RGB_BANDS, patch_files
from earth_observation.retrieval import cosine_rankings

VERSION = "final-evaluation-v1"
INPUTS = [
    "manifests/benchmark-freeze-v1.json",
    "config/benchmark-design-v3.json",
    "config/analysis-protocol-v1.json",
    "config/query-specification-v1.json",
    "config/frozen-models-v1.json",
    "docs/EVALUATION_PIPELINE.md",
    "uv.lock",
    "src/earth_observation/encoding.py",
    "src/earth_observation/retrieval.py",
    "src/earth_observation/evaluation.py",
    "src/earth_observation/final_evaluation.py",
    "scripts/evaluate_final.py",
]


def _hardware_details():
    details = {}
    if platform.system() == "Darwin":
        for name, key in [
            ("machdep.cpu.brand_string", "cpu_model"),
            ("hw.memsize", "memory_bytes"),
        ]:
            value = subprocess.run(
                ["sysctl", "-n", name], check=True, capture_output=True, text=True
            ).stdout.strip()
            details[key] = int(value) if key == "memory_bytes" else value
    return details


def _digest(result: dict) -> str:
    return hashlib.sha256(
        json.dumps(result, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def _rankings(images, texts, ids, queries, model_id):
    qids = [q["query_id"] for q in queries]
    scores, orders = cosine_rankings(images, texts, ids, qids)
    return pd.DataFrame(
        [
            {
                "model_id": model_id,
                **query,
                "patch_id": ids[index],
                "rank": rank,
                "cosine_similarity": float(scores[q, index]),
            }
            for q, query in enumerate(queries)
            for rank, index in enumerate(orders[q], 1)
        ]
    )


def _forbid_encoding():
    raise FileNotFoundError("Saved final cache missing; notebook encoding prohibited")


def evaluate_final(root: Path) -> dict:
    """Encode missing exact-identity Test caches and run the frozen analysis.

    Parameters
    ----------
    root : Path
        Repository with all pinned rasters and locally verified checkpoints.

    Returns
    -------
    dict
        Hash-identified analysis and actual encoding provenance. Full rankings
        and embeddings remain local; the lightweight summary is versionable.

    Raises
    ------
    ValueError, FileNotFoundError
        Freeze/input/checkpoint/cache identity or complete pairing fails. No
        download fallback or candidate replacement is permitted.
    """
    benchmark = load_frozen_benchmark(root / INPUTS[0], root)
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    queries = json.loads((root / "config/query-specification-v1.json").read_text())
    protocol = json.loads((root / "config/analysis-protocol-v1.json").read_text())
    design = json.loads((root / "config/benchmark-design-v3.json").read_text())
    ids = benchmark["main_candidates"]["test"]
    if len(ids) != 871 or len(queries["intents"]) != 8:
        raise ValueError("Require the authorized 871-image/eight-intent freeze")
    ordered_queries = [
        {"query_id": f"{i['intent_id']}/p{p}", "text": text}
        for i in queries["intents"]
        for p, text in enumerate(i["paraphrases"], 1)
    ]
    if len(ordered_queries) != 24:
        raise ValueError("Require all 24 frozen formulations")
    files = [
        {
            b: path
            for b, path in patch_files(
                pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
            ).items()
            if b in RGB_BANDS
        }
        for pid in ids
    ]
    # Fail before either model runs if any required local weight is unavailable.
    for model in config["models"]:
        checkpoint_path(model, root / "models/weights", allow_download=False)
    qids = [q["query_id"] for q in ordered_queries]
    texts = [q["text"] for q in ordered_queries]
    rankings, runs = [], {}
    for model in config["models"]:
        mid = model["model_id"]
        identity = embedding_identity(model, config, ids, files, qids, texts)
        key = identity_key(identity)
        cache = root / "data/cache/embeddings" / f"{key}.npz"
        print(
            mid,
            "cache hit" if cache.is_file() else "encoding 871 Test images",
            flush=True,
        )
        images, text_vectors, measured, hit = cached_embeddings(
            cache,
            identity,
            lambda model=model: encode_frozen(
                model,
                config,
                root / "models/weights",
                files,
                texts,
                allow_download=False,
            ),
        )
        rankings.append(_rankings(images, text_vectors, ids, ordered_queries, mid))
        runs[mid] = {
            "identity": identity,
            "cache_key": key,
            "cache_sha256": file_digest(cache),
            "cache_hit": hit,
            "original_encoding": measured,
            "image_shape": list(images.shape),
            "text_shape": list(text_vectors.shape),
        }
        print(mid, "complete", measured["total_seconds"], "seconds", flush=True)
    ranks = pd.concat(rankings, ignore_index=True)
    validate_benchmark_candidates(ranks, benchmark, "test")
    matrix = benchmark["relevance"]
    refs = pd.DataFrame(
        matrix["states"], index=matrix["patch_ids"], columns=matrix["intent_ids"]
    ).loc[ids]
    models = [m["model_id"] for m in config["models"]]
    main = evaluate_rankings(ranks, refs, queries, models, protocol)
    controls = evaluate_relation_controls(ranks, refs, queries, models, protocol)
    spatial = pd.DataFrame(benchmark["spatial_inventory"]).set_index("patch_id")
    for control in controls:
        if set(control["candidate_ids"]) != set(
            benchmark["relation_controls"]["test"][control["intent_id"]]
        ):
            raise ValueError("Control membership differs from frozen Test set")
        control["spatial_groups"] = int(
            spatial.loc[control["candidate_ids"], "group_id"].nunique()
        )
    output = root / "outputs" / VERSION
    output.mkdir(parents=True, exist_ok=True)
    ranks.to_csv(output / "rankings.csv", index=False)
    result = {
        "version": VERSION,
        "stage": "final-test",
        "benchmark_version": benchmark["version"],
        "benchmark_content_sha256": benchmark["content_sha256"],
        "candidate_ids": ids,
        "query_ids": qids,
        "spatial_groups": int(spatial.loc[ids, "group_id"].nunique()),
        "models": runs,
        "main": main,
        "exploratory_controls": controls,
        "family_sensitivity": family_sensitivity(
            main["paired_intents"], queries, design["evaluation"]["bootstrap"]
        ),
        "hardware": {
            **_hardware_details(),
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "platform": platform.platform(),
        },
        "analysis_runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs_sha256": {name: file_digest(root / name) for name in INPUTS},
        "rankings_sha256": file_digest(output / "rankings.csv"),
        "ranking_rows": len(ranks),
        "new_downloads": False,
    }
    result["content_sha256"] = _digest(result)
    (output / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    summary = {k: v for k, v in result.items() if k != "models"}
    summary["models"] = {
        mid: {k: v for k, v in run.items() if k != "identity"}
        for mid, run in runs.items()
    }
    summary["full_result_sha256"] = file_digest(output / "results.json")
    summary.pop("content_sha256")
    summary["content_sha256"] = _digest(summary)
    small = root / "results" / VERSION
    small.mkdir(parents=True, exist_ok=True)
    (small / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    return result


def load_final(root: Path) -> dict:
    """Verify saved final inputs, caches and complete ranks without encoding.

    Parameters
    ----------
    root : Path
        Repository containing the ignored full final artifact and its caches.

    Returns
    -------
    dict
        Verified saved final result suitable for notebooks/error analysis.

    Raises
    ------
    ValueError, FileNotFoundError
        Artifact tampering, missing cache, changed freeze or encoding inputs.
        No model inference or acquisition can occur in this read path.
    """
    output = root / "outputs" / VERSION
    result = json.loads((output / "results.json").read_text())
    expected = result.pop("content_sha256")
    if _digest(result) != expected:
        raise ValueError("Final result content changed")
    result["content_sha256"] = expected
    if result["version"] != VERSION or result["stage"] != "final-test":
        raise ValueError("Require final Test artifact")
    for name in INPUTS:
        if file_digest(root / name) != result["inputs_sha256"][name]:
            raise ValueError(f"Final analysis dependency changed: {name}")
    benchmark = load_frozen_benchmark(root / INPUTS[0], root)
    if (
        result["candidate_ids"] != benchmark["main_candidates"]["test"]
        or result["benchmark_content_sha256"] != benchmark["content_sha256"]
    ):
        raise ValueError("Final pool/order differs from frozen Test")
    if file_digest(output / "rankings.csv") != result["rankings_sha256"]:
        raise ValueError("Saved final rankings changed")
    ranks = pd.read_csv(output / "rankings.csv", float_precision="round_trip")
    validate_benchmark_candidates(ranks, benchmark, "test")
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    specification = json.loads(
        (root / "config/query-specification-v1.json").read_text()
    )
    ordered_queries = [
        {"query_id": f"{i['intent_id']}/p{p}", "text": text}
        for i in specification["intents"]
        for p, text in enumerate(i["paraphrases"], 1)
    ]
    models = {m["model_id"]: m for m in config["models"]}
    if set(result["models"]) != set(models):
        raise ValueError("Final model pairing differs from specification")
    files = [
        {
            b: path
            for b, path in patch_files(
                pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
            ).items()
            if b in RGB_BANDS
        }
        for pid in result["candidate_ids"]
    ]
    for mid, run in result["models"].items():
        identity = embedding_identity(
            models[mid],
            config,
            result["candidate_ids"],
            files,
            [q["query_id"] for q in ordered_queries],
            [q["text"] for q in ordered_queries],
        )
        if identity != run["identity"]:
            raise ValueError("Current encoding inputs differ from final cache")
        key = identity_key(identity)
        cache = root / "data/cache/embeddings" / f"{key}.npz"
        if key != run["cache_key"] or file_digest(cache) != run["cache_sha256"]:
            raise ValueError("Final embedding cache bytes changed")
        images, texts, measured, hit = cached_embeddings(
            cache, identity, _forbid_encoding
        )
        if (
            not hit
            or measured != run["original_encoding"]
            or [x["patch_id"] for x in identity["images"]] != result["candidate_ids"]
            or [x["query_id"] for x in identity["queries"]] != result["query_ids"]
        ):
            raise ValueError("Final cache order/provenance changed")
        recomputed = _rankings(
            images, texts, result["candidate_ids"], identity["queries"], mid
        )
        pd.testing.assert_frame_equal(
            recomputed.reset_index(drop=True),
            ranks[ranks.model_id.eq(mid)].reset_index(drop=True),
            check_exact=True,
        )
    return result
