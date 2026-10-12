# Implementation Plan

## Current State

Updated: 2026-10-12.

- Work package 1 is complete and PR #3 merged. Its unchanged ten-patch real
  pilot remains available: thirty RGB bands, ten maps, verified source digests,
  native alignment and visual inspection. No additional data were downloaded.
- Work package 2 implements versioned raw CLC mapping for forest, inland water,
  arable land and pasture; native projected areas and four-neighbor shared
  boundary; three-state presence/conjunction/adjacency. Unknown pixels remain
  in the full-area denominator with conservative area/contact evidence bounds.
  Reusable calculations and specification validation live in `src/reference.py`.
- `reference-rules-v1` and `query-specification-v1` are provisional development
  specifications. Presence is inclusively 5% of full patch area; contact is
  inclusively 60 m, also requiring both presences. These illustrative choices
  require broader development validation before freeze. Equivalence to the
  original BigEarthNet.txt adjacency generator is unconfirmed; our derived
  definition is explicit. See `docs/REFERENCE_SPECIFICATION.md`.
- Eight stable intents (24 English formulations) have two predeclared direct
  families: forest/water and arable/pasture, each with two singles, conjunction
  and adjacency. No encoder, metric, bootstrap or final benchmark was added.
- Observed pilot coverage (true/false/unknown): forest 10/0/0; inland water 6/4/0;
  arable land 3/7/0; pasture 5/5/0. Forest/water conjunction and adjacency are
  each 6/4/0; arable/pasture each 2/8/0. There is no forest-negative or
  both-present/nonadjacent case for either pair. Coverage is insufficient for
  an isolated relation test or a final benchmark claim; thresholds were not
  retuned to create distinctions. The inspected source `test` patches serve
  development inspection, not untouched final project evaluation.
- The benchmark-construction notebook calculates evidence/coverage, shows three
  fixed real RGB/map examples, and saves provisional decisions, coverage, figure
  and input/output digests under ignored `outputs/`. No bulky arrays or raw data
  are versioned. Axis units/display mapping and threshold-driven negatives are
  distinguished from independent visual truth; no raster was resampled.
- Validation: 32 tests passed, none skipped, including actual source/raster and
  reference integration. Ruff lint/format pass. The second notebook ran from a
  fresh kernel and its representative figure was visually inspected.
- Review 1: separate final-diff audit of changed reference/specification/notebook
  components is recorded in the reference specification. A version-provenance
  gap was fixed: summaries carry their rule version and reject incompatible
  query versions, with a regression test. No consequential finding remains open;
  the scientific limitations above remain explicit.
- Next: human review/merge, then work package 3 (frozen model development pilot).
  Larger coverage analysis and final parameter/query freeze remain later work.

Research reports and agent instructions are local working documents, excluded
from the public repository. The public methodology is summarized in the README.

## GitHub Delivery Workflow

Each file-changing Codex task produces a focused PR on a separate branch.
The user reviews and merges it; Codex does not merge or enable auto-merge.
Review fixes stay in the same PR. Start the next independent work package from
updated `main` after its predecessor has been merged. Report a concrete blocker
if GitHub access prevents PR creation.

`main` is protected: PRs are required, including for administrators; force
pushes and branch deletion are disabled. A second person's approval is not
required, so the repository owner can inspect and merge their own PRs.

The larger scientific/code reviews below complement the user's review of every
PR. They do not require repeating an expensive full review at each work package.

Update this section after a completed package with verified artifacts, checks,
consequential decisions, and unresolved issues. Keep it a compact handover,
not a chronological transcript of every tool call.

## Work Packages

### 1. Project foundation and verified data access

Inspect existing files, establish a minimal Python environment, and verify
official access to text annotations, Sentinel-2 images, and reference maps.
Start with approximately 10-30 patches; grow toward a 200-300-image technical
pilot only when download size and reproducibility are understood.

Deliver a data index/loader, source and patch manifest, spatial/identity checks,
RGB previews, and working reproduction instructions. A text-only download is
not complete image/reference access. Do not download model weights or full
image archives in this package.

### 2. Reference rules and query specification

Implement class aggregation, presence, and documented adjacency. Preserve
unknown reference states. Specify intents, families, and equivalent paraphrases
in machine-readable configuration. Inspect map/image agreement on selected
pilot cases and test reference calculations with known examples.

Deliver reproducible relevance calculations and explicit unresolved parameter
choices. Do not silently claim that a proposed adjacency rule is the original
BigEarthNet.txt rule.

**Review 1:** image-map identity, spatial alignment, class mapping, area/units,
relation definitions, unknown values, and reference independence.

### 3. Frozen models and retrieval pilot

Identify concrete CLIP/RemoteCLIP ViT-B/32 checkpoints. Implement documented
preprocessing, embedding caches, exact cosine ranking, deterministic ties,
and basic P@10/AP calculations. Run development queries and validate metrics
against hand-computed rankings.

Deliver reusable artifacts and an understandable development notebook.
Reference information must not influence main retrieval.

### 4. Coverage analysis and benchmark freeze

Measure positive/negative/unknown coverage, geographical concentration, and
true/false relation cases with both classes present. Extend the candidate
archive only when reference coverage justifies it, using a fixed sampling rule.
Prepare spatial development/test separation and separate relation-control sets.

Freeze data manifests, intents/paraphrases, mappings, thresholds, relations,
relevance matrices, checkpoints/preprocessing, and the analysis specification.
Do not use final model rankings to select the test benchmark.

### 5. Complete evaluation and statistical analysis

Implement intent-level aggregation, paraphrase quality range and Jaccard
diagnostics, error categories, and paired intent-family bootstrap intervals.
Keep the point estimate's weighting consistent with the resampling procedure.
Test calculations and component integration using small controlled cases.

**Review 2, before the final test:** metric definitions, denominators, candidate
sets, unknown reference handling, paraphrase aggregation, family grouping,
resampling, leakage, and the actual freeze artifacts.

### 6. Final evaluation and scientific interpretation

Run both models under the frozen protocol. Report per-intent and aggregate
results, uncertainty, coverage, and the separate relation-control experiment.
Inspect successes and failures using a predefined sampling rule.

Treat post-test changes to queries/reference rules as exploratory. Document
actual implementation bugs and rerun affected comparisons for both models.
Use stored valid artifacts instead of repeating encoding.

### 7. Research report, small demo, and completion

Update the README with measured results and a concise scientific argument.
Complete the notebook narrative, reproducible figures, limitations, and working
setup/experiment instructions. Add a small comparison demo only after the
evaluation is reliable.

**Completion review:** reproducibility, agreement between artifacts and claims,
outstanding defects, readable notebooks, and consistency of README/demo/report.
Do not reopen unchanged components without a concrete reason.

## Planned Notebook Storyline

Use four substantive notebooks rather than one notebook per engineering task:

| Notebook | Question | Work packages |
|---|---|---|
| Data Understanding | What do the images and references contain, and can they be matched reliably? | 1 |
| Benchmark Construction | What counts as relevant, and which queries can we evaluate fairly? | 2, 4 |
| Retrieval Evaluation | How do the frozen models perform across conditions and formulations? | 3, 5, 6 |
| Error Analysis | Where do the systems fail, and what can the evidence actually explain? | 6, 7 |

Development exploration and final results must be clearly separated within the
evaluation narrative. Create each notebook when its content exists.

## Efficient Completion Criteria

Each package should leave usable code/artifacts, relevant checks, and a short
handover. Read targeted files; preserve resolved decisions. Add dependencies
and modules when needed. Cache expensive results with explicit provenance.
Reviews focus on the stated risks rather than redoing broad planning.

This plan sets no automatic permission gates. Follow the user's authorized
scope; clarify only genuinely unresolved information or consequential changes
that cannot be resolved from the existing design and data evidence.
