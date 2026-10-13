"""Validate and freeze the existing inventory without downloads or model runs."""

from pathlib import Path

from earth_observation.analysis_protocol import freeze_existing_benchmark

if __name__ == "__main__":
    record = freeze_existing_benchmark(Path(__file__).resolve().parents[1])
    print(record["version"], record["status"])
    print(record["analysis_readiness"]["reference_coverage"])
