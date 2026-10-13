# Robust Compositional Retrieval in Earth Observation

**Status:** in development. A ten-patch technical pilot verifies frozen CLIP and
RemoteCLIP retrieval, embedding reuse and per-formulation map-agreement metrics.
The final model comparison remains planned. The validated
`benchmark-freeze-v1` contains 871 spatially held-out Test images under the
explicit partial-reference protocol; relation controls are exploratory.

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
with paired per-intent results and descriptive aggregation. Incomplete map
judgments will yield reference-uncertainty bounds, distinct from sampling error.
The implemented development pilot shows that both identified checkpoints run
reproducibly and that ranking quality differs across individual formulations.
Its small, spatially concentrated sample cannot establish model superiority.

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

The data source is BigEarthNet.txt with underlying BigEarthNet-v2 Sentinel-2
images and generalized CLC2018 reference maps. One fixed deterministic expansion
selects 2,000 images, 200 per country across ten countries and 53 tiles, retaining
all previously planned 250 IDs. Including earlier Development gives 2,013
technically verified RGB/map pairs. Actual original text is verified for 254;
nine earlier selected IDs are source-absent and 1,750 new IDs were not queried.
Original captions are optional for image/query main retrieval and their absence
is separate from missing map evidence. Any caption analysis uses actual texts only.
The original ten-image model pilot remains a separate Development experiment.

The models receive RGB images and query text. Land-cover labels, reference
maps, and evaluation metadata are kept separate from the main ranking.
The authorized `benchmark-design-v3` outcome remains map-reference agreement:
10-m cells do not improve CLC2018 mapping accuracy (25-ha mapping units,
100-m minimum linear feature width). These are mapping conventions, not
per-pixel positional accuracy guarantees. Adjacency means mapped contact under the
documented rule. RGB disagreement is a separate qualitative diagnosis.

## Methodology

Reference construction and frozen development retrieval are implemented.
The analysis follows four principles; final evaluation remains planned:

**Explicit relevance.** Implemented development rules aggregate raw CLC codes
into forest, inland water, arable land and pasture. Presence requires a
frozen 5% of full patch area. Adjacency requires both presences and at least
60 m of summed four-neighbor shared boundary; corner contact does not count.
Unknown map area yields evidence bounds and true/false/unknown conditions.
These are our derived definitions, not a confirmed reconstruction of the
original text-annotation generator. See the
[reference specification](docs/REFERENCE_SPECIFICATION.md) and
[benchmark-construction notebook](notebooks/02_benchmark_construction.ipynb).

**Controlled comparisons.** Both models use the same queries and candidate
images. The implemented pilot uses the complete unfiltered ten-image candidate
set. Separate exploratory relation controls contain both known-present queried
classes in every candidate while the mapped relation varies. Their few negative
cases cannot establish confirmatory relation capability.

**Frozen evaluation.** Class mappings, thresholds, paraphrases, candidate sets,
and analysis rules are fixed before the final test. Development and test data
are separated with attention to spatial overlap.

**Parsimony and uncertainty.** The initial comparison uses two frozen ViT-B/32
models without fine-tuning. Precision@10 is the primary metric; average
precision, paraphrase quality variation, and error categories provide context.
The main presentation will pair models within each intent and aggregate
descriptively. With only two direct intent families, a family bootstrap may
serve only as a restricted sensitivity diagnostic. The pilot reports each
formulation separately.

## Development Results and Error Inspection

The official OpenAI CLIP and RemoteCLIP ViT-B/32 checkpoints each encoded ten
images and 24 texts in CPU float32, without training. Both use checkpoint
preprocessing and explicitly versioned Sentinel-2 RGB conversion. Complete cosine
rankings use deterministic patch-ID ties; embedding caches identify model,
software, preprocessing and ordered input bytes/texts. See
[model provenance, metric contracts and measured runtime](docs/RETRIEVAL_PILOT.md).

Illustrative **first formulations**, not intent averages:

| Query intent | Positives / candidates | CLIP AP | RemoteCLIP AP |
|---|---:|---:|---:|
| Inland water | 6 / 10 | 0.6607 | 0.8179 |
| Arable land | 3 / 10 | 0.8095 | 0.3417 |

Average precision (AP) rewards earlier relevant ranks. With ten candidates,
precision at ten (P@10) equals reference prevalence and is independent of order.
All forest candidates are positive, so forest AP = 1 is likewise uninformative.
Under the historical pilot protocol, unknown references make main metrics
undefined and judged-only diagnostics are separate. The new final protocol
retains unknowns and specifies completion bounds; no final metrics exist yet.

The [retrieval-evaluation notebook](notebooks/03_retrieval_evaluation.ipynb)
reports all formulations and shows actual top images. Both models rank a visibly
water-containing patch first for the illustrated forest/water adjacency query;
the map counts only 4.53% water, below the provisional 5% requirement. This
map-negative result illustrates a threshold-driven reference disagreement,
not independently verified visual failure. No overall model winner or isolated
relation capability can be inferred from this pilot.

The model-independent assessment validates the fixed 2,000-ID expansion and
13 earlier Development images. The unchanged spatial protocol gives 1,280 groups,
1,142 Development and 871 Test-side images. All 128 previous Development images
stay there; new neighbors merge 11 earlier groups and move 32 provisional Test
images into Development. Thirteen groups contain coincident native footprints
at different dates, kept in complete components rather than silently pruned.

Every Test intent meets the unchanged known-positive/negative and geographic
minimums. Forest is fully judged (549 true / 322 false); arable has two unknown
judgments and each other intent three. `benchmark-design-v3` explicitly replaces
full judgeability with exact marginal label-completion bounds for P@10 and AP,
with at most twelve unknowns per intent. Known labels stay fixed; rankings retain
all 871 candidates. AP uses each assignment's positive denominator and can have
mixed-assignment extrema. A possible zero-positive assignment blocks AP; the
current known-positive minimum prevents it. Within each intent, both models and
all paraphrases share the same completion. Cross-intent means report conservative
reference envelopes because marginal assignments need not be jointly realizable.
These are reference-uncertainty bounds, not statistical confidence intervals.

Separate both-present controls have 35 true / 2 false forest-water relations
(false dispersion one) and 59 true / 7 false arable-pasture relations
(false dispersion six). Both fail the former ten-false target and are explicitly
**exploratory**. The primary results will be paired per intent with descriptive
aggregation; two direct families cannot support general model-superiority claims.
Reference uncertainty, paraphrase variation and statistical uncertainty remain
distinct. See the [analysis protocol](docs/ANALYSIS_PROTOCOL.md) for equations,
shared-completion aggregation and all limits.

`benchmark-freeze-v1` is **frozen** under this authorized protocol after native
map, spatial, source-integrity and main-coverage validation. The historical
`benchmark-candidate-v4` remains blocked under its original rules. No thresholds,
queries, images or spatial rules changed, and no final models were evaluated.

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
The second notebook constructs provisional references; the third runs frozen
development retrieval and verifies cache reuse. Final evaluation and error
analysis remain planned. Reusable loading, reference, encoding, cache, ranking
and metric calculations live in `src`; exploratory tables and plots remain
in the notebooks.

## Reproduction and Project Documents

Verified environment: native arm64 Python 3.12.12 on Apple M2 Pro, 32 GiB RAM,
CPU float32 with four threads. Use [uv](https://docs.astral.sh/uv/) and a native
interpreter; a Rosetta Intel Python cannot use the locked current macOS PyTorch
wheels. For a fresh Apple Silicon setup:

```bash
uv python install cpython-3.12.12-macos-aarch64-none
uv sync --locked --python "$(uv python dir)/cpython-3.12.12-macos-aarch64-none/bin/python3.12"
```

From the repository root with that environment:

```bash
uv sync --locked
uv run python scripts/fetch_pilot.py
uv run python scripts/prepare_benchmark.py
uv run python scripts/validate_development.py
uv run python scripts/check_subset_reproduction.py
uv run python scripts/run_retrieval_pilot.py
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run python -m ipykernel install --sys-prefix --name earth-observation
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_understanding.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/03_retrieval_evaluation.ipynb
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
provenance under `outputs/`; its final section validates the new frozen benchmark.
Its eight intents have
three equivalent English formulations each, assigned to two direct families.

See [source versions, observed schema, license, display policy and access limits](docs/DATA_ACCESS.md)
and the [pilot manifest](manifests/data-pilot-v1.json). The retrieval command
downloads only the two checksum-pinned weights (959,184,943 bytes total) when
missing; valid local caches are reused. Weight and embedding files remain ignored.
The coverage command additionally reuses existing data and checks two pinned
1-KiB archive-end probes (2,048 bytes if missing). It reproduces coverage and
validates the original explicitly blocked candidate record. The continuation
command verifies the 13-image development manifest and candidate v2 using the
existing pilot caches; both candidates remain non-frozen. These commands perform
no model evaluation. Selection, design and integrity specifications are versioned;
raw data and local diagnostic outputs remain ignored.

Both official archives already exist locally (63,534,101,678 bytes, published
checksums verified). The fixed expansion scans each once, writes 7,000 missing
TIFFs and reuses 1,000: 177,196,674 selected bytes, including 155,046,370 new bytes,
below the 256-MiB budget. No additional archive, caption or model transfer occurs.
Earlier access/design/candidate versions and valid caches remain intact.

Reproduce from these verified local sources and prior caption caches:

```bash
uv run python scripts/expand_benchmark.py --stage all
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
```

Use `--stage validate` to reproduce source/coverage checks without another archive
scan. Source disagreement, changed historical inputs or an incompatible record
fails explicitly. New `benchmark_expansion` reuses canonical raster/reference/
spatial/coverage implementations; the historical expanded loader refuses a
blocked benchmark. The new `analysis_protocol.load_frozen_benchmark` validates
the authorized partial-reference freeze, including native map states and spatial
components. With existing local data, reproduce it without downloads or models:

```bash
uv run python scripts/freeze_benchmark.py
```

WP5 begins after human merge of the freeze PR. See
[actual local access](docs/DATA_ACCESS.md) and
[the scoped access manifest](manifests/archive-data-access-v3.json).

The retrieval command saves complete formulation metrics, rankings and measured
provenance locally.
The third notebook checks exact cache reuse and displays representative real
top results; it runs independently from a fresh kernel.

- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): work packages, reviews,
  and current implementation state.

## Limitations and Future Work

In the original ten-image retrieval pilot, all patches satisfy forest presence;
there is no forest-negative case. Forest/water and arable/pasture conjunctions
have six and two positives respectively, all also satisfying adjacency. Neither
pair has a both-present/nonadjacent case. This pilot cannot isolate relation
errors or establish final coverage. The larger frozen collection supports mapped
reference agreement, retains unknown labels and offers only exploratory hard
relation controls. Its reference intervals quantify marginal label ambiguity,
not independently verified visual truth. Cross-intent aggregate envelopes can be
loose; final scoring must implement the documented shared-completion contracts.
Only two direct intent families restrict statistical generalization.

The proposed study is limited to selected queries and a controlled Sentinel-2
RGB subset. Map uncertainty, spatial redundancy, rare relevant scenes, and
possible pretraining overlap may constrain interpretation. Results will not
automatically generalize to global imagery archives, additional sensors, or
arbitrary user language.

An agentic query-decomposition comparison is a possible second project stage,
after the direct retrieval baseline is complete. Building/roof segmentation,
large-scale training, and additional models are outside the initial scope.
