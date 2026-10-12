# Robust Compositional Retrieval in Earth Observation

**Status:** in development. A ten-patch pilot has verified text/catalog,
Sentinel-2 RGB and reference-map access. No retrieval experiments or performance
findings are available.

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
will be selected after verifying relevance coverage and spatial structure.
The final subset size is not fixed yet. A technical pilot currently loads ten
unchanged patch IDs from one Austria tile: thirty RGB band files and ten native
reference maps. Exact catalog identities, file checksums and native grids agree.
Only 2.25 MiB of official raster archives were transferred; extraction retains
887,617 bytes. This access result does not establish representative coverage
or independent visual truth of the reference maps.

The models receive RGB images and query text. Land-cover labels, reference
maps, and evaluation metadata are kept separate from the main ranking.
Reference-map agreement will be distinguished from visually verified content:
rasterizing a coarse map does not make its boundaries more accurate.

## Methodology

The analysis follows four principles; reference construction is implemented
provisionally, while model comparison and final evaluation remain planned:

**Explicit relevance.** Implemented development rules aggregate raw CLC codes
into forest, inland water, arable land and pasture. Presence requires a
provisional 5% of full patch area. Adjacency requires both presences and at least
60 m of summed four-neighbor shared boundary; corner contact does not count.
Unknown map area yields evidence bounds and true/false/unknown conditions.
These are our derived definitions, not a confirmed reconstruction of the
original text-annotation generator. See the
[reference specification](docs/REFERENCE_SPECIFICATION.md) and
[benchmark-construction notebook](notebooks/02_benchmark_construction.ipynb).

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
records the real ten-patch pilot, spatial checks and three RGB/map examples.
Later stages remain planned. Reusable loading and validation live in `src`;
one-off inspection tables and plots remain in the notebook.

## Reproduction and Project Documents

Use Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/). From the repository
root:

```bash
uv sync --locked
uv run python scripts/fetch_pilot.py
uv run python scripts/check_subset_reproduction.py
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run python -m ipykernel install --sys-prefix --name earth-observation
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_understanding.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
```

The acquisition command downloads checksum-pinned text pages and the 3.6-MB
patch catalog (3,842,879 bytes total), plus fixed S2/map archive prefixes
(2,359,296 bytes total). It extracts only the forty required TIFFs. No complete
archive is requested. Valid caches and files are reused; ignored HTTP ranges,
changed source bytes or incompatible local files fail explicitly. The separate
reproduction command acquires four real files for the first unchanged patch
in an empty temporary cache using only 524,288 bytes.

After acquisition, `pytest` includes both official text/catalog and real raster
integration checks. Without the required local data the corresponding tests
explicitly skip; a skip is not evidence of data access. The notebook executes
from a fresh kernel and shows actual native RGB/map pairs. Source prefixes,
rasters and diagnostic figures remain outside version control. The second
notebook saves provisional reference decisions, coverage and digest-based
provenance under `outputs/`; no benchmark is frozen. Its eight intents have
three equivalent English formulations each, assigned to two direct families.

See [source versions, observed schema, license, display policy and access limits](docs/DATA_ACCESS.md)
and the [pilot manifest](manifests/data-pilot-v1.json). No model is loaded.

- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): work packages, reviews,
  and current implementation state.

## Limitations and Future Work

With the provisional rules, all ten pilot patches satisfy forest presence;
there is no forest-negative case. Forest/water and arable/pasture conjunctions
have six and two positives respectively, all also satisfying adjacency. Neither
pair has a both-present/nonadjacent case. This sample cannot isolate relation
errors or establish final coverage. Presence thresholds, contact thresholds and
family coverage require broader development verification before benchmark freeze.

The proposed study is limited to selected queries and a controlled Sentinel-2
RGB subset. Map uncertainty, spatial redundancy, rare relevant scenes, and
possible pretraining overlap may constrain interpretation. Results will not
automatically generalize to global imagery archives, additional sensors, or
arbitrary user language.

An agentic query-decomposition comparison is a possible second project stage,
after the direct retrieval baseline is complete. Building/roof segmentation,
large-scale training, and additional models are outside the initial scope.
