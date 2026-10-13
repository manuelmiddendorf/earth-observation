"""Read verified historical Development rankings and save v3 evaluation artifacts.

This executable path is deliberately Development-only. Existing embedding
identities remain historical evidence; metric-code changes do not trigger new
encoding or migrate caches silently. No downloader or model encoder is called.
"""

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from earth_observation.analysis_protocol import load_frozen_benchmark
from earth_observation.encoding import cached_embeddings, file_digest, identity_key
from earth_observation.evaluation import (
    evaluate_rankings,
    evaluate_relation_controls,
    family_sensitivity,
    validate_benchmark_candidates,
)
from earth_observation.raster import RGB_BANDS, patch_files


def _no_encoding():
    raise ValueError(
        "Missing historical Development cache; encoding is prohibited here"
    )


def load_development_pilot(
    root: Path, benchmark: dict
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load hash-verified stored pilot rankings and their historical caches.

    Parameters
    ----------
    root : Path
        Repository with original outputs/frozen-retrieval-pilot-v1/run.json,
        rankings.csv, metrics.csv and immutable historical embedding caches.
    benchmark : dict
        Fully validated frozen benchmark from load_frozen_benchmark. Every
        stored input image must belong to its Development collection.

    Returns
    -------
    tuple
        Historical formulation metrics, stored complete ranking table, and
        original run provenance. Main analysis uses frozen relevance instead
        of the historical CSV's attached labels. Nothing is encoded/reranked.

    Raises
    ------
    ValueError
        Changed source/caches/model/input IDs, query mapping, or any Test image.
    FileNotFoundError
        Required historical artifact/cache is missing; no download fallback.
    """
    output = root / "outputs/frozen-retrieval-pilot-v1"
    provenance = json.loads((output / "run.json").read_text())
    if set(provenance["outputs"]) != {"metrics.csv", "rankings.csv"}:
        raise ValueError("Unexpected historical output inventory")
    for name, expected in provenance["outputs"].items():
        if file_digest(output / name) != expected:
            raise ValueError("Stored Development results changed")
    for name, expected in provenance["inputs"].items():
        if file_digest(root / name) != expected:
            raise ValueError("Historical Development input specification changed")
    rankings = pd.read_csv(output / "rankings.csv", float_precision="round_trip")
    ids = set(rankings.patch_id)
    validate_benchmark_candidates(rankings, benchmark, "development")
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    queries = json.loads((root / "config/query-specification-v1.json").read_text())
    expected_queries = [
        {"query_id": f"{i['intent_id']}/p{p}", "text": text}
        for i in queries["intents"]
        for p, text in enumerate(i["paraphrases"], 1)
    ]
    if set(provenance["models"]) != {m["model_id"] for m in config["models"]}:
        raise ValueError("Incomplete original model pairing")
    for model in config["models"]:
        run = provenance["models"][model["model_id"]]
        identity = run["identity"]
        if (
            identity["model"] != model
            or identity["queries"] != expected_queries
            or {p["patch_id"] for p in identity["images"]} != ids
        ):
            raise ValueError("Historical model/image/text identities changed")
        for field in [
            "architecture",
            "embedding_dimension",
            "activation",
            "rgb",
            "preprocessing",
            "runtime",
        ]:
            if identity[field] != config[field]:
                raise ValueError(
                    "Historical representation settings differ from freeze"
                )
        for image in identity["images"]:
            files = patch_files(
                image["patch_id"],
                root / "data/raw/BigEarthNet-S2",
                root / "data/raw/Reference_Maps",
            )
            if any(
                file_digest(files[band]) != image["bands"][band] for band in RGB_BANDS
            ):
                raise ValueError("Historical cached image bytes changed")
        if identity_key(identity) != run["cache_key"]:
            raise ValueError("Historical embedding identity key changed")
        cache = root / "data/cache/embeddings" / f"{run['cache_key']}.npz"
        if file_digest(cache) != run["cache_sha256"]:
            raise ValueError("Historical embedding cache bytes changed")
        _, _, measured, hit = cached_embeddings(cache, identity, _no_encoding)
        if not hit or measured != run["original_encoding"]:
            raise ValueError("Historical cache provenance differs")
    return pd.read_csv(output / "metrics.csv"), rankings, provenance


def evaluate_development(root: Path, *, bootstrap: bool = False) -> dict:
    """Integrate saved Development rankings into a provenance-rich v3 result.

    Parameters
    ----------
    root : Path
        Repository with a valid freeze and existing Development artifacts.
    bootstrap : bool
        Explicit opt-in to the permitted restricted two-family sensitivity.
        Default False; primary analysis is paired per-intent/descriptive.

    Returns
    -------
    dict
        Deterministic JSON-compatible analysis/provenance, saved locally under
        outputs/evaluation-development-v3/results.json. No NaN serialization,
        encoding, acquisition, Test rankings or statistical CI claims.
    """
    benchmark = load_frozen_benchmark(root / "manifests/benchmark-freeze-v1.json", root)
    if benchmark["version"] != "benchmark-freeze-v1" or benchmark["status"] != "frozen":
        raise ValueError("Valid frozen benchmark required")
    _, rankings, original = load_development_pilot(root, benchmark)
    queries = json.loads((root / "config/query-specification-v1.json").read_text())
    protocol = json.loads((root / "config/analysis-protocol-v1.json").read_text())
    design = json.loads((root / "config/benchmark-design-v3.json").read_text())
    config = json.loads((root / "config/frozen-models-v1.json").read_text())
    matrix = benchmark["relevance"]
    states = pd.DataFrame(
        matrix["states"], index=matrix["patch_ids"], columns=matrix["intent_ids"]
    )
    candidate_ids = sorted(set(rankings.patch_id))
    references = states.loc[candidate_ids]
    models = [m["model_id"] for m in config["models"]]
    main = evaluate_rankings(rankings, references, queries, models, protocol)
    controls = evaluate_relation_controls(
        rankings, references, queries, models, protocol
    )
    for control in controls:
        expected = set(
            benchmark["relation_controls"]["development"][control["intent_id"]]
        ) & set(candidate_ids)
        if set(control["candidate_ids"]) != expected:
            raise ValueError(
                "Exploratory Development control differs from frozen membership"
            )
    spatial = pd.DataFrame(benchmark["spatial_inventory"]).set_index("patch_id")
    for control in controls:
        groups = spatial.loc[control["candidate_ids"], "group_id"]
        counts = references.loc[control["candidate_ids"], control["intent_id"]]
        control["spatial_groups"] = int(groups.nunique())
        control["state_dispersion"] = {}
        for state in ["true", "false"]:
            per_group = groups[counts.eq(state)].value_counts()
            control["state_dispersion"][state + "_outside_largest_group"] = (
                int(per_group.sum() - per_group.max()) if len(per_group) else 0
            )
    sensitivity = (
        family_sensitivity(
            main["paired_intents"], queries, design["evaluation"]["bootstrap"]
        )
        if bootstrap
        else {"status": "not-requested", "confidence_interval": False}
    )
    inputs = [
        "manifests/benchmark-freeze-v1.json",
        "config/benchmark-design-v3.json",
        "config/analysis-protocol-v1.json",
        "config/query-specification-v1.json",
        "config/frozen-models-v1.json",
        "docs/EVALUATION_PIPELINE.md",
        "uv.lock",
        "src/earth_observation/retrieval.py",
        "src/earth_observation/evaluation.py",
        "src/earth_observation/evaluation_run.py",
        "scripts/evaluate_development.py",
        "outputs/frozen-retrieval-pilot-v1/run.json",
        "outputs/frozen-retrieval-pilot-v1/rankings.csv",
    ]
    result = {
        "version": "evaluation-development-v3",
        "analysis_runtime": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "python": platform.python_version(),
        },
        "stage": "development-integration-only",
        "benchmark_version": benchmark["version"],
        "benchmark_content_sha256": benchmark["content_sha256"],
        "design_version": design["version"],
        "analysis_protocol": protocol["version"],
        "candidate_ids": candidate_ids,
        "spatial_groups": int(spatial.loc[candidate_ids, "group_id"].nunique()),
        "models": config["models"],
        "source_embedding_caches": {
            m: {k: r[k] for k in ["cache_key", "cache_sha256"]}
            for m, r in original["models"].items()
        },
        "historical_encoding_implementation": {
            m: r["identity"]["implementation"] for m, r in original["models"].items()
        },
        "inputs_sha256": {name: file_digest(root / name) for name in inputs},
        "main": main,
        "exploratory_controls": controls,
        "family_sensitivity": sensitivity,
        "new_encoding": False,
        "new_downloads": False,
        "test_model_evaluation": False,
    }
    result["content_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    output = root / "outputs/evaluation-development-v3"
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result
