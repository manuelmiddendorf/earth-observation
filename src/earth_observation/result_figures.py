"""Scientific figures for saved final quality and the fixed error sample.

Native maps are displayed without resampling or label correction. Their colors
represent generalized map classes, not independently verified image truth.
"""

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from earth_observation.encoding import model_rgb
from earth_observation.raster import RGB_BANDS, patch_files, read_rgb_bands
from earth_observation.reference import (
    evaluate_intents,
    load_specifications,
    summarize_reference,
)

MODEL_NAMES = {"clip-openai-vit-b32": "CLIP", "remoteclip-vit-b32": "RemoteCLIP"}
MODEL_COLORS = {"clip-openai-vit-b32": "#2166ac", "remoteclip-vit-b32": "#d6604d"}
CLASS_COLORS = ["#d0d0d0", "#228833", "#4477aa", "#ccbb44", "#ee6677", "#aa4499"]
CLASS_NAMES = [
    "Known other",
    "Forest",
    "Inland water",
    "Arable land",
    "Pasture",
    "Unknown",
]


def quality_figure(result: dict) -> Figure:
    """Plot intent-mean P@10/AP exact reference bounds for two paired models.

    Parameters
    ----------
    result : dict
        Verified final result, with eight intents and both identified models.

    Returns
    -------
    matplotlib.figure.Figure
        Two metric panels; bars are reference bounds, never sampling intervals.
    """
    frame = pd.DataFrame(result["main"]["intents"])
    intents = list(dict.fromkeys(frame.intent_id))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    for ax, metric, label in zip(
        axes, ["p_at_10", "average_precision"], ["P@10", "AP"], strict=True
    ):
        for offset, (model, color) in zip(
            [-0.12, 0.12], MODEL_COLORS.items(), strict=True
        ):
            rows = (
                frame[frame.model_id.eq(model) & frame.metric.eq(metric)]
                .set_index("intent_id")
                .loc[intents]
            )
            y = np.arange(len(intents)) + offset
            lower, upper = rows.lower.to_numpy(float), rows.upper.to_numpy(float)
            ax.hlines(y, lower, upper, color=color, linewidth=3)
            ax.scatter(lower, y, s=25, color=color, label=MODEL_NAMES[model])
            ax.scatter(upper, y, s=25, color=color)
        ax.set(
            yticks=np.arange(len(intents)),
            yticklabels=intents,
            xlim=(0, 1),
            xlabel=f"Intent mean {label} (three formulations)",
        )
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)
        ax.legend(loc="lower right")
    fig.suptitle(
        "Frozen Test: 871 images / 637 groups; exact marginal reference bounds"
    )
    return fig


def sample_conditions(root: Path, result: dict) -> pd.DataFrame:
    """Recompute native reference conditions for the unchanged fixed 48 slots.

    Parameters
    ----------
    root : Path
        Repository containing the locally pinned RGB and reference TIFFs.
    result : dict
        Verified final result with protocol-selected p1 ranks 1, 5 and 10.

    Returns
    -------
    pandas.DataFrame
        One row per slot: repeated-image count, class fractions/presences,
        contact bounds (metres), computational category and frozen relevance.
    """
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    intents = {i["intent_id"]: i for i in queries["intents"]}
    samples = result["main"]["error_samples"]
    repetitions = Counter(s["patch_id"] for s in samples)
    rows = []
    for sample in samples:
        intent = intents[sample["intent_id"]]
        files = patch_files(
            sample["patch_id"],
            root / "data/raw/BigEarthNet-S2",
            root / "data/raw/Reference_Maps",
        )
        pairs = [tuple(intent["classes"])] if intent["kind"] == "adjacency" else []
        with rasterio.open(files["reference"]) as ds:
            summary = summarize_reference(
                ds.read(1, masked=True), ds.transform, ds.crs, rules, pairs
            )
        if (
            evaluate_intents(summary, {**queries, "intents": [intent]})[
                intent["intent_id"]
            ]
            != sample["relevance"]
        ):
            raise ValueError("Sample native map differs from frozen relevance")
        descriptions = []
        for name in intent["classes"]:
            cls = summary["classes"][name]
            descriptions.append(
                f"{name}: {100 * cls['fraction_lower']:.2f}–"
                f"{100 * cls['fraction_upper']:.2f}% ({cls['state']})"
            )
        row = {
            **sample,
            "image_occurrences_in_48_slots": repetitions[sample["patch_id"]],
            "presence_conditions": "; ".join(descriptions),
            "unknown_area_percent": 100
            * summary["unknown_area_m2"]
            / summary["total_area_m2"],
            "contact_lower_m": None,
            "contact_upper_m": None,
        }
        if pairs:
            boundary = summary["pairs"][tuple(sorted(intent["classes"]))]
            row.update(
                contact_lower_m=boundary["boundary_lower_m"],
                contact_upper_m=boundary["boundary_upper_m"],
            )
        rows.append(row)
    return pd.DataFrame(rows)


def error_sample_figure(root: Path, samples: pd.DataFrame, intent_id: str) -> Figure:
    """Display all six predeclared slots for an intent, RGB beside native map.

    Parameters
    ----------
    root : Path
        Repository with native raster assets.
    samples : pandas.DataFrame
        Conditions from sample_conditions; no score-based replacement allowed.
    intent_id : str
        One frozen intent, p1 for both models at ranks 1, 5 and 10.

    Returns
    -------
    matplotlib.figure.Figure
        Two model rows by three RGB/map pairs, with categories and map legend.
    """
    rules, _ = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    fig, axes = plt.subplots(2, 6, figsize=(15, 5.8))
    fig.subplots_adjust(bottom=0.16, top=0.86, hspace=0.4, wspace=0.1)
    rows = samples[samples.intent_id.eq(intent_id)]
    for model_index, model in enumerate(MODEL_NAMES):
        for rank_index, rank in enumerate([1, 5, 10]):
            row = rows[rows.model_id.eq(model) & rows["rank"].eq(rank)].iloc[0]
            files = patch_files(
                row.patch_id,
                root / "data/raw/BigEarthNet-S2",
                root / "data/raw/Reference_Maps",
            )
            with rasterio.open(files["reference"]) as ds:
                labels = ds.read(1, masked=True)
            classes = np.zeros(labels.shape, dtype=np.uint8)
            for index, definition in enumerate(rules["classes"].values(), 1):
                classes[np.isin(labels.data, definition["codes"])] = index
            classes[
                np.ma.getmaskarray(labels)
                | ~np.isin(labels.data, rules["known_clc_codes"])
            ] = 5
            a, b = axes[model_index, 2 * rank_index : 2 * rank_index + 2]
            a.imshow(
                model_rgb(read_rgb_bands({b: files[b] for b in RGB_BANDS}), 3000),
                interpolation="nearest",
                extent=(0, 1.2, 1.2, 0),
            )
            b.imshow(
                classes,
                cmap=ListedColormap(CLASS_COLORS),
                vmin=0,
                vmax=5,
                interpolation="nearest",
                extent=(0, 1.2, 1.2, 0),
            )
            suffix = "_".join(row.patch_id.split("_")[-3:])
            a.set_title(f"{MODEL_NAMES[model]} rank {rank}\n{suffix}", fontsize=8)
            b.set_title(
                f"{row.category}\n"
                f"{row.image_occurrences_in_48_slots} sample occurrences",
                fontsize=7,
            )
            for ax in (a, b):
                ax.set_xticks([0, 1.2], ["0", "1.2 km"])
                ax.set_yticks([])
                ax.tick_params(labelsize=7)
    fig.legend(
        handles=[
            Patch(color=c, label=n)
            for c, n in zip(CLASS_COLORS, CLASS_NAMES, strict=True)
        ],
        loc="lower center",
        ncol=6,
        fontsize=8,
    )
    fig.suptitle(
        f"{intent_id} / p1 — fixed ranks 1, 5, 10; native 10 m CLC2018 storage\n"
        "5% presence; ≥60 m four-neighbor contact; generalized map, no label edits",
        fontsize=11,
    )
    return fig
