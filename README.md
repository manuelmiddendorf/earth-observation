# Robust Compositional Retrieval in Earth Observation

**Status:** research design completed; implementation and experiments have not
started. Dataset access, benchmark coverage, and model performance remain to
be verified.

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

These are planned stages, not existing notebooks. Reusable implementation will
live in `src`; one-off analytical observations will remain visible in notebooks.

## Reproduction and Project Documents

There is no runnable experiment pipeline or dependency environment yet.
Verified installation and execution instructions will be added with the first
implementation package.

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
