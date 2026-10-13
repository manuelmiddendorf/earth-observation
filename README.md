# Robust Compositional Retrieval in Earth Observation

## Abstract

Frozen image–text retrieval can find a salient concept without satisfying every
condition in a satellite-image query. We compare identified CLIP and RemoteCLIP
ViT-B/32 checkpoints on 871 spatially held-out Sentinel-2 RGB images, eight
land-cover intents and three formulations per intent. Relevance measures
agreement with fixed generalized CLC2018 map rules, independently of scores.
CLIP achieves mean P@10 of 0.3500 versus RemoteCLIP's 0.2625; the paired
RemoteCLIP-minus-CLIP AP reference envelope is [−0.030474, −0.026889]. Quality
falls for conjunctions and adjacency, while equivalent wording changes retrieved
sets substantially. These descriptive results concern this country-balanced,
eight-intent benchmark; reference bounds are not confidence intervals and sparse
negative relation controls cannot establish general spatial reasoning.

## Research Questions

1. How does quality change from single concepts to conjunctions and relations?
2. How sensitive are rankings and quality to equivalent query formulations?
3. Does the selected checkpoint comparison depend on query type?

`Forest`, `forest and water`, and `forest adjacent to water` require progressively
more conditions. A forest-only result cannot satisfy the latter two intents.

## Data and Retrieval Task

BigEarthNet.txt supplies the source context; images and references come from
BigEarthNet-v2. The fixed expansion selects 200 images per country across ten
countries and retains earlier Development inputs: 2,013 verified RGB/map pairs.
A frozen 2 km spatial-component protocol keeps all acquisition dates together,
anchors previous Development images there, and assigns remaining groups with a
fixed hash rule. Development contains 1,142 images/643 groups; Test contains
871/637. No image was selected using a model ranking.

The main pool is all 871 Test images. The eight intents cover forest, inland
water, arable land and pasture, two conjunctions and their adjacency versions.
Three fixed English formulations each give 24 queries and two direct intent
families. Models receive only B04/B03/B02 RGB and query text. Reference maps,
labels and captions affect neither main scores nor main candidates. Original
captions are verified for 254 images, source-absent for nine earlier IDs and not
requested for 1,750; captions are optional and unused here.

Relevance is **map agreement**, not independently verified visual truth. Presence
requires ≥5% of full patch area; adjacency also requires both presences and
≥60 m summed four-neighbor shared boundary. Missing evidence stays unknown.
Native 10 m map cells do not increase CLC2018's underlying 25 ha mapping-unit /
100 m minimum linear-feature detail. See the
[reference specification](docs/REFERENCE_SPECIFICATION.md),
[data provenance and access limits](docs/DATA_ACCESS.md) and
[frozen analysis protocol](docs/ANALYSIS_PROTOCOL.md).

## Methodology

The two ViT-B/32 baselines share architecture and frozen QuickGELU inference,
allowing a focused comparison between the official general-purpose OpenAI CLIP
and remote-sensing RemoteCLIP checkpoints. Their exact bytes, RemoteCLIP revision,
RGB conversion, tokenizer and transforms are identified in
[the model specification](config/frozen-models-v1.json). Native RGB is clipped to
DN/3000 and quantized with round-to-even; checkpoint bicubic resize/center crop
produces 224×224 inputs. CPU float32, four threads, seed zero, evaluation mode,
frozen parameters and inference mode are recorded. No fine-tuning occurs.

Unit embeddings yield exact cosine scores; equal scores break by Unicode patch
ID. Full rankings retain all candidates. P@10 is the relevant fraction of the
first ten ranks. AP averages precision at positive ranks over **each completed
reference's** positive count:

$$
\mathrm{AP}(z)=\frac{1}{R(z)}\sum_{r=1}^{N} y_r(z)
\frac{\sum_{j=1}^{r}y_j(z)}{r},\qquad R(z)=\sum_r y_r(z).
$$

Here $y_r(z)$ is completed binary relevance at rank $r$, and $z$ assigns unknown
labels. Each intent enumerates all marginal assignments, sharing each assignment
across both models and all three formulations. Formulations are averaged before
extrema, and paired differences are computed before extrema. Intent bounds are
exact in this authorized completion space. Equal-intent cross-intent means are
**conservative reference envelopes**; their extremes need not be jointly
physically attainable. Unknown counts are 0 for forest, 2 for arable and 3 for
each other intent. No current metric is undefined or blocked; zero-positive or
over-cap cases fail explicitly rather than being omitted.

Paraphrase quality range and pairwise top-ten Jaccard remain separate from
reference uncertainty. Only two dependent intent families are available, so the
optional paired family resampling is a restricted sensitivity diagnostic, never
a general confidence interval. The separately filtered **known both-present**
relation controls are exploratory; they are not unfiltered retrieval.
[Pipeline contracts and completed Review 2](docs/EVALUATION_PIPELINE.md) precede
this final Test run. All freeze pins, queries, thresholds and candidates remain
unchanged.

## Results

All values average three formulations within intents, then equally weight the
intents in the indicated scope. AP entries below are conservative aggregate
reference envelopes; coincident P@10 endpoints are shown compactly, with no
reference-imputed point estimate.

| Query scope | Intents | CLIP P@10 bounds | RemoteCLIP P@10 bounds | CLIP AP envelope | RemoteCLIP AP envelope |
|---|---:|---:|---:|---:|---:|
| All | 8 | [0.3500, 0.3500] | [0.2625, 0.2625] | [0.3158, 0.3190] | [0.2876, 0.2899] |
| Single concept | 4 | [0.5000, 0.5000] | [0.4917, 0.4917] | [0.4778, 0.4791] | [0.4866, 0.4887] |
| Conjunction | 2 | [0.2167, 0.2167] | [0.0500, 0.0500] | [0.1541, 0.1586] | [0.0878, 0.0900] |
| Adjacency | 2 | [0.1833, 0.1833] | [0.0167, 0.0167] | [0.1537, 0.1591] | [0.0893, 0.0920] |

![Exact per-intent marginal reference bounds, not confidence intervals](results/final-evaluation-v1/intent-quality.svg)

The paired all-intent AP envelope favors CLIP for every allowed marginal
completion. The comparison is heterogeneous: RemoteCLIP's single-concept paired
AP envelope is positive [0.008407, 0.010038], with gains for arable/pasture but
losses for forest/water. Conjunction/adjacency differences favor CLIP. Smaller
positive sets also make the composite tasks harder; the scope comparison alone
does not isolate compositional reasoning.

Mean top-ten Jaccard over the three unordered formulation pairs and eight
intents is 0.1931 for CLIP and 0.2308 for RemoteCLIP. Higher set overlap does not
imply higher quality. Within-intent P@10 ranges reach 0.6 for both models; three
formulations provide evidence of wording sensitivity, not arbitrary-language
robustness. [Notebook 03](notebooks/03_retrieval_evaluation.ipynb) separates the
historical ten-image Development pilot from the complete final Test and reports
all formulations, paired intent bounds, controls and restricted sensitivity.

Conditional forest/water controls contain 35 true/2 false cases in 35 groups:
P@10 is 1 for both models, AP 0.9936/0.9837 (CLIP/RemoteCLIP). Arable/pasture
controls contain 59 true/7 false in 48 groups: P@10 0.9667/0.8000 and AP
0.9454/0.8718. High values in strongly positive pools, few negatives and weak
negative dispersion cannot demonstrate general relation capability. These
results are kept out of the main aggregate.

## Error Analysis

[Notebook 04](notebooks/04_error_analysis.ipynb) shows exactly the predeclared p1
ranks 1, 5 and 10 for both models and all eight intents: 48 slots/35 unique
images. No case was replaced. CLIP has 9 satisfied slots and RemoteCLIP 5 among
24 slots each. Both have nine partial-class failures; RemoteCLIP also has three
neither-class cases. These counts describe a fixed diagnostic sample, not an
unbiased failure rate.

Visible parcel mosaics do not establish arable versus pasture use, and broad
mapped regions merge finer image detail. Some selected scenes contain bright
winter features; snow/shadow effects are possible explanations without an
ablation. The fixed sample contains no unknown or both-present-but-false
relation slot; most sampled relation failures already miss a presence condition.
We report that limitation rather than replacing cases. Computed map categories,
map limitations, observed RGB content and untested explanations are recorded
separately in [the qualitative evidence](results/final-evaluation-v1/qualitative-observations.json).
No reference label changed after inspection.

## Main Findings

- Quality decreases for the selected multi-condition and relation tasks.
- Equivalent wording changes both quality and the retrieved top-ten sets.
- CLIP has the higher descriptive aggregate here; the checkpoint gap varies by
  intent type and does not establish general superiority.
- Reference ambiguity does not reverse the aggregate AP sign, but is distinct
  from sampling uncertainty and independent visual truth.
- Sparse hard-negative controls and the fixed image sample do not isolate
  general spatial reasoning.

## Reproduction

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
uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=earth-observation notebooks/03_retrieval_evaluation.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=earth-observation notebooks/04_error_analysis.ipynb
uv run python scripts/render_final_figures.py
```

The local full result identifies source/configuration/lockfile hashes, ordered
inputs, checkpoint/transform/tokenizer/software identity, measured inference
state, cache bytes and 41,808 full ranking rows. Notebook readers verify those
identities and reproduce exact scores/ranks from saved vectors without inference.
Large artifacts stay ignored under `outputs/final-evaluation-v1`,
`data/cache/embeddings`, `data/raw` and `models/weights`. The
[lightweight summary](results/final-evaluation-v1/summary.json) and figure
provenance are versioned. Missing local assets are an explicit prerequisite,
not authorization for a new download. The final integration check explicitly skips
when no local final result exists; partial or changed artifacts fail. A skip
is not evidence of a verified final run.

Reusable execution/validation, reference conditions and report figures live in
`src`; scientific tables, interpretations and the fixed visual inspection stay
in notebooks. Historical acquisition and pilot reproduction are documented in
[DATA_ACCESS](docs/DATA_ACCESS.md) and [RETRIEVAL_PILOT](docs/RETRIEVAL_PILOT.md).
The [implementation plan](docs/IMPLEMENTATION_PLAN.md) records project state.

## Limitations

This country-balanced subset is not weighted to operational archive prevalence.
Eight intents in two families, rare positives, generalized map reference,
spatial redundancy within groups and possible pretraining overlap constrain
transfer to other sensors, countries, vocabularies or image archives. Reference
envelopes describe marginal label ambiguity and may be conservative across
intents; they are not statistical confidence intervals. Few negative relation
controls and single-date RGB inspection do not establish causal explanations
or independent land-use truth. The final evaluation is complete; the separately
authorized completion review follows in WP7.
