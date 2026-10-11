# Robust Compositional Retrieval in Earth Observation

**Status:** in development. A ten-patch text/catalog pilot is implemented;
real Sentinel-2 image and reference-map access remains blocked. No retrieval
experiments or performance findings are available.

## Abstract

This project investigates whether pretrained image-text models can retrieve
Sentinel-2 satellite scenes that satisfy all conditions of a natural-language
query. The planned study compares frozen CLIP and RemoteCLIP representations
across single land-cover concepts, conjunctions, and spatial relations, and
examines sensitivity to semantically equivalent paraphrases. Relevance is
determined independently from documented land-cover reference rules rather
than embedding similarity. A separate relation-control experiment restricts
candidates to scenes containing both queried concepts. The aim is a small,
reproducible evaluation that explains partial-condition and relational failures,
with paired uncertainty estimates over search intents and their families.
No experimental findings are available yet.

## Research Questions

The central question is:

> How reliably do frozen general-purpose and remote-sensing vision-language
> models satisfy compositional Earth-observation queries, and how robust are
> they to linguistic variation?

The study asks:

1. How does retrieval quality change from a single concept to multiple
   conditions or a spatial relation?
2. How does quality vary across equivalent formulations of the same intent?
3. As an exploratory comparison, does the gap between the selected CLIP and
   RemoteCLIP checkpoints vary with query type?

For example, `forest`, `forest and water`, and `forest adjacent to water`
require progressively more specific conditions. Finding a scene with forest
alone does not satisfy the latter two requests.

## Data and Retrieval Task

The preferred starting point is BigEarthNet.txt with the underlying
BigEarthNet-v2 Sentinel-2 images and land-cover reference maps. A bounded subset
will be selected after verifying data access, relevance coverage, and spatial
structure. The final subset size is not fixed yet.

The models receive RGB images and query text. Land-cover labels, reference
maps, and evaluation metadata are kept separate from the main ranking.
Reference-map agreement will be distinguished from visually verified content:
rasterizing a coarse map does not make its boundaries more accurate.

## Methodology

The planned analysis follows four principles:

**Explicit relevance.** A retrieved image is relevant only if all specified
conditions hold under the documented reference rules. Unknown annotations are
not treated as negative labels.

**Controlled comparisons.** Both models use the same queries and candidate
images. A separate relation-control experiment contains both queried classes
in every candidate while the relation varies.

**Frozen evaluation.** Class mappings, thresholds, paraphrases, candidate sets,
and analysis rules are fixed before the final test. Development and test data
are separated with attention to spatial overlap.

**Parsimony and uncertainty.** The initial comparison uses two frozen ViT-B/32
models without fine-tuning. Precision@10 is the primary metric; average
precision, paraphrase quality variation, and error categories provide context.
Paired bootstrap intervals preserve intent-family structure.

## Planned Analytical Narrative

The notebooks will follow the same research-oriented style as the
yoga-attendance project:

1. **Data Understanding:** establish source structure, image/reference
   identity, spatial properties, and available information.
2. **Benchmark Construction:** define intents, reference rules, coverage,
   development/test separation, and the benchmark freeze.
3. **Retrieval Evaluation:** compare models and query types, then examine
   paraphrases and statistical uncertainty.
4. **Error Analysis:** explain where the frozen systems succeed and fail,
   including reference disagreements and limitations.

The first [data-understanding notebook](notebooks/01_data_understanding.ipynb)
records the bounded text/catalog pilot and its missing raster components.
Later stages remain planned. Reusable loading and validation live in `src`;
one-off inspection tables and plots remain in the notebook.

## Reproduction and Project Documents

Use Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/). From the repository
root:

```bash
uv sync --locked
uv run python scripts/fetch_pilot.py
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run python -m ipykernel install --sys-prefix --name earth-observation
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_understanding.ipynb
```

The acquisition command downloads only checksum-pinned text pages and the
3.6-MB official patch catalog, under 5 MB total. It never downloads image/map
archives. A changed source response or invalid cache fails explicitly.
`pytest` includes an official text/catalog integration test when those assets
are cached; without them that test is skipped. Controlled raster tests are
separate from real data access. The notebook executes from a fresh kernel and
reports absent RGB/map examples explicitly. Supply an independently verified
local v2 subset before claiming complete raster integration.

See [source versions, schema, license, display policy and access blocker](docs/DATA_ACCESS.md)
and the [pilot manifest](manifests/data-pilot-v1.json). Local caches, raster
files and generated diagnostic PNGs are ignored by Git. No model is loaded.

- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): work packages, reviews,
  and current implementation state.

## Limitations and Future Work

The proposed study is limited to selected queries and a controlled Sentinel-2
RGB subset. Map uncertainty, spatial redundancy, rare relevant scenes, and
possible pretraining overlap may constrain interpretation. Results will not
automatically generalize to global imagery archives, additional sensors, or
arbitrary user language.

An agentic query-decomposition comparison is a possible second project stage,
after the direct retrieval baseline is complete. Building/roof segmentation,
large-scale training, and additional models are outside the initial scope.
