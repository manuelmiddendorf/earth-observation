# Reproducing the study

The four notebooks tell the scientific story; the linked specifications retain
implementation and provenance details. Run notebooks from a fresh kernel in order.
All paths below are relative to the repository root.

## Local prerequisites

The full study requires the pinned native rasters, original model checkpoints,
and historical Development artifacts. These large files are not shipped in Git.
The acquisition history and verified source commands are in
[DATA_ACCESS](DATA_ACCESS.md) and [RETRIEVAL_PILOT](RETRIEVAL_PILOT.md).
The full archives total about 64 GB; extracting the selected rasters does not
require unpacking the entire collection. Do not interpret a successful unit test
run without local data as reproduction of the final experiment.

Install the locked environment with `uv sync --locked`. If the notebook kernel
is absent, register it in that environment:

```bash
uv run python -m ipykernel install --sys-prefix --name earth-observation
```

## Final evaluation and stored-result verification


The actual run used Apple M2 Pro, 32 GiB RAM, macOS 15.6.1 arm64 and Python
3.12.12, CPU float32/four threads. Original encode/load times were 23.914 s for
CLIP and 25.899 s for RemoteCLIP (image encoding 19.869/22.730 s), excluding
freeze validation, analysis and notebook execution. Each encoded 871 images and
24 texts once. A subsequent metadata/validation analysis reused both exact
caches; no downloads or repeated model encoding occurred.

Use the locked environment and retain all pinned local rasters/checkpoints plus
historical Development artifacts for Notebook 03. The final runner forbids
acquisition and rejects missing/changed assets. Verified commands from the root:

```bash
uv sync --locked
uv run python scripts/evaluate_final.py
uv run pytest -q tests/test_encoding.py tests/test_final_evaluation.py
uv run ruff check src tests scripts notebooks/03_retrieval_evaluation.ipynb notebooks/04_error_analysis.ipynb
uv run ruff format --check src tests scripts notebooks/03_retrieval_evaluation.ipynb notebooks/04_error_analysis.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=earth-observation notebooks/*.ipynb
uv run python scripts/render_final_figures.py
```

The local full result identifies source/configuration/lockfile hashes, ordered
inputs, checkpoint/transform/tokenizer/software identity, measured inference
state, cache bytes and 41,808 full ranking rows. Notebook readers verify those
identities and reproduce exact scores/ranks from saved vectors without inference.
Large artifacts stay ignored under `outputs/final-evaluation-v1`,
`data/cache/embeddings`, `data/raw` and `models/weights`. The
[lightweight summary](../results/final-evaluation-v1/summary.json) and figure
provenance are versioned. Missing local assets are an explicit prerequisite,
not authorization for a new download. The final integration check explicitly skips
when no local final result exists; partial or changed artifacts fail. A skip
is not evidence of a verified final run.

Reusable execution/validation, reference conditions and report figures live in
`src`; scientific tables, interpretations and the fixed visual inspection stay
in notebooks. Historical acquisition and pilot reproduction are documented in
[DATA_ACCESS](DATA_ACCESS.md) and [RETRIEVAL_PILOT](RETRIEVAL_PILOT.md).
The [implementation plan](IMPLEMENTATION_PLAN.md) records project state.


## Post-hoc random-ranking context

The random reference was added at completion, after observing Test results.
It uses the published summary's counts and exact finite-population expectations;
no images, rankings, reference rules or model results change. Regenerate its
identified artifact with `uv run python scripts/summarize_random_reference.py`.
See [the completion review](COMPLETION_REVIEW.md) for interpretation and checks.

## Complete verification

```bash
uv run pytest -q
uv run ruff check src tests scripts notebooks
uv run ruff format --check src tests scripts notebooks
```

The tests marked integration use locally available source artifacts. Report
skips explicitly. The notebooks check stored source/cache identities and fail
on incompatible inputs rather than silently regenerating final results.
