"""Run the authorized frozen Test comparison using local assets only."""

from pathlib import Path

from earth_observation.final_evaluation import evaluate_final

if __name__ == "__main__":
    result = evaluate_final(Path(__file__).resolve().parents[1])
    print(result["version"], result["ranking_rows"], "complete ranking rows")
    for row in result["main"]["descriptive_paired"]:
        if row["scope"] == "all":
            print(row["metric"], row["status"], row["lower"], row["upper"])
