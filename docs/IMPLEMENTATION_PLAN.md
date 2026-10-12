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
  and adjacency. Package 3 subsequently added encoding and basic metrics;
  bootstrap and the final benchmark remain unimplemented.
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
- Work package 2 and Review 1 were merged in PR #4 before starting package 3.
- Work package 3 implements the identified official CLIP/RemoteCLIP ViT-B/32
  checkpoints, explicit `model-rgb-v1` DN-to-uint8 conversion, checkpoint-specific
  transforms/QuickGELU, frozen CPU inference, provenance-aware embedding caches,
  complete deterministic cosine ranking and per-formulation P@10/AP. Maps enter
  only after ranking; no relevance candidate filtering or metadata encoding.
- Both real checkpoints ran on native arm64 Python 3.12.12, Apple M2 Pro / 32 GiB,
  CPU float32, four threads, batch five. Ten images and 24 queries per model
  produced 48 formulation results and 480 ranking rows. Measured load+encoding:
  CLIP 2.8094 s, RemoteCLIP 2.9412 s, excluding downloads. Cache reuse preserved
  artifact modification times and exactly equal result tables without encoding.
- The third notebook reports all formulations, metric assumptions and selected
  actual top-three images. First arable-land AP: CLIP 0.8095, RemoteCLIP 0.3417;
  first inland-water AP: 0.6607 / 0.8179. These are development examples, not
  aggregate model findings. P@10 equals prevalence with ten candidates. The
  illustrated map-negative adjacency top result has 4.53% water, below the
  unchanged 5% requirement; map agreement is not visual truth.
- Package 3 verification: 53 tests passed, none skipped, including real model
  artifact reuse; Ruff passed; notebook executed from a fresh kernel and real
  top-result figure visually inspected. Focused self-check only; no agents or
  additional full review. See `docs/RETRIEVAL_PILOT.md` for exact checkpoint
  identities, runtime, metric edge cases and reproduction details.
- Next: human review/merge, then work package 4 coverage analysis and benchmark
  freeze. Do not select final queries/thresholds from these pilot rankings.
  Broader coverage, spatial separation and a distinct relation-control set remain
  open; no intent aggregation, bootstrap or final performance claim is made.

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
