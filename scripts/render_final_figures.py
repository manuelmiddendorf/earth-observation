"""Render the final report figure from verified saved Test artifacts only."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

from earth_observation.encoding import file_digest
from earth_observation.final_evaluation import load_final
from earth_observation.result_figures import quality_figure

if __name__ == "__main__":
    import json

    root = Path(__file__).resolve().parents[1]
    result = load_final(root)
    output = root / "results/final-evaluation-v1"
    plt.rcParams["svg.hashsalt"] = result["version"]
    fig = quality_figure(result)
    path = output / "intent-quality.svg"
    fig.savefig(path, metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    # Canonical whitespace keeps generated SVG diffs clean without changing paths.
    path.write_text(
        "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
    )
    provenance = {
        "figure": path.name,
        "figure_sha256": file_digest(path),
        "result_content_sha256": result["content_sha256"],
        "summary_sha256": file_digest(output / "summary.json"),
        "matplotlib": matplotlib.__version__,
        "inputs_sha256": {
            name: file_digest(root / name)
            for name in [
                "src/earth_observation/result_figures.py",
                "scripts/render_final_figures.py",
            ]
        },
        "meaning": "Exact marginal intent reference bounds; not confidence intervals",
        "candidate_count": 871,
        "spatial_groups": 637,
    }
    (output / "figure-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(path.name, provenance["figure_sha256"])
