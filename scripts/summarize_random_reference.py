"""Write post-hoc random expectations without changing frozen results."""

import hashlib
import json
from pathlib import Path

from earth_observation.random_reference import random_reference_rows


def main() -> None:
    """Read the published summary and save identified analytical expectations."""
    root = Path(__file__).resolve().parents[1]
    source = root / "results/final-evaluation-v1/summary.json"
    result = json.loads(source.read_text())
    artifact = {
        "role": "post-hoc descriptive context, not frozen primary analysis",
        "source_summary_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "formula": "E[P@10]=R/N; E[AP]=H_N/N+(R-1)(N-H_N)/(N(N-1))",
        "rows": random_reference_rows(result),
    }
    (source.parent / "random-reference.json").write_text(
        json.dumps(artifact, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
