"""Run the development retrieval pilot; retain complete results locally."""

from pathlib import Path

from earth_observation.pilot import run_retrieval_pilot

if __name__ == "__main__":
    metrics, _, provenance = run_retrieval_pilot(Path(__file__).resolve().parents[1])
    print(
        metrics.loc[
            metrics.query_id.str.endswith("/p1"),
            ["model_id", "intent_id", "p_at_10", "average_precision"],
        ].to_string(index=False)
    )
    for model_id, run in provenance["models"].items():
        print(
            model_id,
            "cache_hit:",
            run["cache_hit"],
            "original encoding seconds:",
            run["original_encoding"]["total_seconds"],
        )
