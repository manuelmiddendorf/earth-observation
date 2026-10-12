# Implementation Plan

## Current State

Updated: 2026-10-12.

- Foundation PR #1 and initial data-pilot PR #2 are merged. Work package 1 is
  complete in a focused follow-up PR; no later-stage implementation exists.
- Minimal uv/Python package, lockfile, pytest and Ruff remain in place. Reusable
  source/cache/identity, bounded extraction and raster validation live in `src`;
  inspection tables, display-only code names and plots remain in the existing
  data-understanding notebook. zstandard was added for archive streaming;
  the now-yanked notebook dependency soupsieve received a targeted lock update.
- `data-pilot-v1 / archive-prefix-v1` preserves all ten selected IDs. Four pinned
  text pages and the official catalog verify S2/S1 pairing. All patches belong
  to one Austria tile with the provider's `test` split; this convenience sample
  is not the project's final test set or a representative benchmark.
- Bounded official access is verified: a 2-MiB S2 prefix and 256-KiB map prefix
  contain the required thirty RGB bands and ten reference maps. Transfer:
  2,359,296 bytes; retained TIFFs: 887,617 bytes. Original valid prefix bytes
  were reused. No full archive, model weights or alternative data were fetched.
- Manifest now records ranges, archive/member paths, sizes, SHA-256 digests and
  observed native schema. HTTP ranges must be honored exactly. Prefix/member
  hashes cannot verify the whole archive's published MD5. The unversioned text
  API remains pinned by response digests, with the observed HF SHA as context.
- All forty real rasters are uint16, 120×120, EPSG:32633, 10-m cells, NoData 0.
  RGB/map transforms and footprints match within every patch. Text/raster
  centers agree within 1e-8 degrees. Reference values are raw CLC level-3 IDs;
  source code 999 (unlabeled) and NoData 0 remain distinct unknown information.
- Validation: thirteen tests pass with no skips, including real text/catalog
  and all-ten-patch raster integration. Ruff lint/format and locked uv sync
  pass. A separate small empty cache reacquired four real files for the first
  unchanged patch with matching hashes/alignment (524,288 transferred bytes).
  The updated single notebook ran from a fresh kernel; three fixed real RGB/map
  pairs were visually inspected. Broad landscape correspondence is plausible,
  while small boundaries and forest subclasses are not visually verified truth.
- No external blocker remains for the selected ten patches. Later arbitrary
  member access, representative coverage and reference-rule validity remain
  unverified. No relevance, aggregation, adjacency or retrieval was implemented.
- Next action: human review/merge of the follow-up PR, then work package 2:
  reference rules and query specification on development data, followed by the
  planned scientific review checkpoint.

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
