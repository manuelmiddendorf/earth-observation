"""Evaluate existing Development rankings; never acquire/encode Test inputs."""

import argparse
from pathlib import Path

from earth_observation.evaluation_run import evaluate_development

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-sensitivity", action="store_true")
    args = parser.parse_args()
    result = evaluate_development(
        Path(__file__).resolve().parents[1], bootstrap=args.family_sensitivity
    )
    print(result["version"], result["stage"], len(result["candidate_ids"]), "images")
    for row in result["main"]["descriptive_paired"]:
        if row["scope"] == "all":
            print(row["metric"], row["status"], row["lower"], row["upper"])
