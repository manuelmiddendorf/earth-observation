# Implementation Plan

## Current State

Updated: 2026-10-12.

- Work packages 1–3 are merged (PRs #3–#5); Review 1 is complete. The unchanged
  `data-pilot-v1` has ten verified RGB/map pairs, all from one Austria tile.
  Versioned provisional rules use 5% class presence and 60 m four-neighbor
  contact, including both presences and three-state unknown evidence bounds.
  Eight intents / 24 formulations have two direct families.
- Official CLIP/RemoteCLIP ViT-B/32 checkpoints ran frozen with explicit RGB
  conversion and checkpoint transforms on native arm64 Python 3.12.12, Apple
  M2 Pro / 32 GiB, CPU float32/four threads. Exact deterministic rankings,
  P@10/AP and identity-checked embedding reuse are verified. Development model
  results are documented separately in `docs/RETRIEVAL_PILOT.md`; none informed
  package 4's selection, split, thresholds or queries.
- Package 4 implements country-balanced deterministic selection, verified native
  spatial grouping, three-state intent/family coverage, separate both-present
  controls, feasibility gates and candidate integrity validation in `src/benchmark.py`.
  The existing benchmark-construction notebook is extended; no extra notebook.
- All ten available patches form one EPSG:3035 envelope component at inclusive
  2-km distance; all remain development, including any connected repeats/neighbors.
  No verified held-out test images exist. Main true/false/unknown counts remain
  forest 10/0/0, water 6/4/0, arable 3/7/0, pasture 5/5/0; conjunction/adjacency
  each 6/4/0 and 2/8/0. Both-present controls have 6/0/0 and 2/0/0 relation states:
  neither has a both-present false relation. Every intent has zero positives
  outside its largest spatial component.
- `coverage-selection-v1` plans 250 IDs, 25 per country, across 53 tiles from the
  pinned 480,038-row clean catalog, excluding the previous development tile.
  No class/model-driven selection. Equal-country enrichment is not representative
  population sampling. Native geometry for planned IDs remains unverified.
- Bounded-access assessment: official inventory has no listed patch index;
  neither archive-end probe has a seekable-zstd footer; existing prefixes reach
  zero selected IDs. Added 2,048 archive bytes and 13,711 source-inventory/recipe
  bytes, zero new image/map patches and zero encoding runs. No full archives.
- **Freeze blocked:** `benchmark-candidate-v1` is explicitly `blocked-not-frozen`.
  It pins source/code/config/raw-input identities, available geometry/splits,
  main/control IDs and reference states. Default loading refuses final evaluation;
  false frozen status cannot bypass missing test inventory. No 250-image dataset,
  adequate final coverage or completed final freeze is claimed.
- `benchmark-design-v1` predeclares reference/spatial minimum coverage, unknown
  handling, equal-intent aggregation, paired direct-family bootstrap, diagnostics
  and rank-based error sampling for package 5. No statistics pipeline is added.
  All eight intents and provisional semantic thresholds remain unchanged.
- Verification: 62 tests passed, none skipped; Ruff passes; extended notebook ran
  from a fresh kernel and real RGB/map/geographic examples were visually checked.
  No agents, full-repository review or final model evaluation.
- Next: provide an official indexed subset route or local subset with verifiable
  provenance for the selected IDs. Then validate broader development plausibility,
  native spatial separation and held-out main/control coverage under a new
  candidate version before a real freeze. Package 5's final-evaluation prerequisite
  remains unmet. See `docs/BENCHMARK_DESIGN.md` for exact rules and access evidence.

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
