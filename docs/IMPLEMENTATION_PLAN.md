# Implementation Plan

## Current State

Updated: 2026-10-13.

Completion package (branch `codex/research-completion`):

- PR #11 was human-merged while the authorized completion review was in progress;
  its review improvements were carried onto a new branch from updated main.
- README now follows the scientific argument with concise results and interpretation.
  All four notebooks distinguish current findings from historical stages; repeated
  low-level explanations and per-panel caveats are reduced. Detailed commands and
  prerequisites live in `docs/REPRODUCTION.md`.
- Added analytical random P@10/AP expectations as explicitly post-hoc descriptive
  context, using the published summary only. No change to the frozen protocol,
  reference labels, model results or candidate pools; no inference or downloads.
- Fresh execution exposed historical source-drift in Notebook 02 and three brittle
  tests. Retired acquisition continuations are removed from the executable story; historical
  manifests and production source/readiness guards remain intact. Temporary
  test fixtures isolate readiness without editing historical manifests.
- All four notebooks executed fresh with zero errors; representative RGB/map and
  result panels were visually inspected. Final full suite: **132 passed, zero skips**. Ruff check and format pass for
  source, tests, scripts and all notebooks. Freeze/final-input hashes are unchanged.
- Completion findings, added context and scientific limits are in
  `docs/COMPLETION_REVIEW.md`. Next: human review/merge of the completion PR.
  A demo and stronger relation study remain optional separate projects.

Completed WP6 final evaluation (branch `codex/final-evaluation`):

- PR #10 was human-merged; Review 2 has no consequential open findings.
  Before any Test inference, all **121 tests** passed with no skips, Ruff check/
  format passed and the native/source-pinned freeze was revalidated. No freeze
  pin, query, threshold, reference, sampling or candidate rule was changed.
- The local-only final runner encoded 871 Test images/24 texts once per model,
  storing exact-identity unit-vector caches and **41,808** complete score/rank
  rows. No downloads. CLIP/RemoteCLIP original encode/load times: 23.914/25.899 s
  on Apple M2 Pro, 32 GiB, CPU float32/four threads. A later analysis-only pass
  reused both caches to record hardware and strengthen stored-input checks.
  Existing Development artifacts and cache bytes remain intact.
- All 96 formulation, 32 intent and 16 paired-intent metrics are defined.
  Main candidates remain 871 images/637 spatial groups. P@10 aggregate bounds:
  CLIP [0.3500, 0.3500], RemoteCLIP [0.2625, 0.2625]. AP conservative envelopes:
  [0.315837, 0.318982] / [0.287589, 0.289852]; paired RemoteCLIP-minus-CLIP
  [−0.030474, −0.026889]. Exact marginal intent bounds and conservative
  cross-intent envelopes remain distinct from confidence intervals.
- Single-concept AP favors RemoteCLIP slightly in aggregate, with arable/pasture
  gains but forest/water losses; conjunction/adjacency favor CLIP. Mean pairwise
  top-ten paraphrase Jaccard is 0.1931/0.2308. These are descriptive findings for
  eight intents/two dependent families, not general checkpoint superiority.
- Separate exploratory controls retain 35/2/0 forest-water and 59/7/0
  arable-pasture true/false/unknown. Control AP is 0.9936/0.9837 and
  0.9454/0.8718 (CLIP/RemoteCLIP); scarce negatives and dispersion do not isolate
  general spatial reasoning. Optional two-family sensitivity is not a CI.
- Notebook 03 separates historical Development from final Test; new Notebook 04
  shows all predeclared p1 ranks 1/5/10: **48 slots/35 unique images**, with native
  RGB/maps and conditions. The sample contains no unknown or both-present false
  relation, so that qualitative gap is reported without replacement. Observation,
  map limits, computational categories and untested explanations remain separate.
- Reusable local execution/artifact validation and final figures live in `src`;
  narrative tables/visual interpretation stay in notebooks. Lightweight summaries,
  fixed-slot observations/conditions and an identified report SVG are versioned;
  embeddings/full ranks/weights/native rasters remain local and ignored.
- Validation: eight affected checks pass, including exact reconstruction of all
  saved Test scores/ranks, cache modification-time preservation, local-only
  checkpoint failures and real native-map/sample rendering. Both notebooks ran
  from fresh kernels without errors; all eight fixed-image grids and the main
  quality figure were visually inspected. Ruff check/format pass for all current
  src/tests/scripts and both notebooks. No final analysis implementation bug was
  found and no scientific rule was reopened.
- Next: human review/merge of this focused PR, then separately authorize WP7's
  completion review. This task performs no full-repository review or demo.

Historical authorized analysis revision and WP4 freeze:

- PR #8 was human-merged before this work; branch starts from current main.
  `benchmark-design-v3` / `analysis-protocol-v1` retain eight intents / 24
  formulations, map-agreement estimand, all images, thresholds and spatial rules.
  Historical designs/candidates and pinned source modules remain unchanged.
- Complete main Test inventory: 871 images / 637 spatial groups; Development
  1,142 / 643. All unchanged main known-positive/negative/dispersion minima pass.
  Unknown counts by ordered intent: 0, 3, 2, 3, 3, 3, 3, 3. No exclusions/recoding.
- Explicit full-judgeability replacement: exact marginal binary-completion
  P@10/AP bounds, cap 12 unknowns (4,096 assignments); current maximum eight.
  AP's denominator varies and any zero-positive completion blocks analysis.
  Share each intent completion across models/paraphrases, average formulations
  before extrema and compute paired differences before extrema. Cross-intent
  averages are conservative reference envelopes, not physically joint extrema.
- Relations remain separately filtered, now exploratory: Test forest-water
  true/false/unknown 35/2/0 (false dispersion one); arable-pasture 59/7/0 (six).
  Old targets remain documented; these do not provide confirmatory relation proof.
  Primary statistics are paired per-intent/descriptive; two direct families make
  bootstrap at most restricted sensitivity, never broad superiority confidence.
- `benchmark-freeze-v1` is **frozen** after source hashes, native footprints,
  complete spatial components, Development anchoring, native-map recomputation,
  candidate/control identities and explicit uncertainty-readiness validation.
  A manually changed status cannot bypass these gates. Existing v4 stays blocked
  under its historical rules. No new transfers, data, embeddings or model runs.
- Reusable specification/readiness/freeze validation lives in new
  `src/earth_observation/analysis_protocol.py`; notebook section 16 retains the
  narrative and compact real coverage, plus a hand-computed AP counterexample.
  Final metric/statistics computation is deliberately reserved for WP5.
- Verification: 102 tests passed with no skips, including actual native raster
  integration and new unknown/zero-positive/invalid-protocol contracts. Ruff
  check and format pass for all 35 src/tests/scripts files. Changed notebook
  cells are clean (22 historical findings remain). All 32 code cells ran from
  a fresh kernel with zero errors; three Development RGB/map pairs and spatial
  distribution were visually inspected. No final ranking metrics were computed.
- Next step: human review/merge of the freeze PR, then explicitly begin WP5.
  Reference uncertainty, conservative aggregate envelopes, generalized CLC
  accuracy and sparse exploratory controls remain scientific limitations.

Historical authorized design revision and fixed expansion (PR #8, merged):

- `benchmark-design-v2` explicitly targets generalized CLC map agreement.
  Adjacency is mapped four-neighbor contact, not independently visible truth.
  Captions are optional for main retrieval. All numerical coverage, spatial,
  query/reference and analysis rules remain unchanged; raw Development CLC
  counts/full-area fractions and categorical edge counts verify map semantics.
- Stable `coverage-selection-v2`: 2,000 IDs / 200 per country / 53 tiles,
  same catalog/seed/exclusions/tile round-robin. Each country's first 25 IDs
  exactly preserves v1. Selection was pinned before inspecting new labels.
- One local scan per archive: 8,000 exact TIFFs, 7,000 new / 1,000 reused;
  177,196,674 selected bytes, 155,046,370 new bytes below 256 MiB. All 2,000
  pairs pass native identity/grid/dtype/NoData/reference checks. No archive,
  original-text or model downloads; no full unpacking or repeated sampling.
- Total 2,013 unique image IDs in 1,280 groups: Development 1,142, Test 871.
  All 128 prior Development images remain there. Eleven merged earlier groups,
  86 previous group/split changes, including 32 Test→Development; zero reverse.
  Thirteen coincident native-footprint groups and 218 envelope overlap pairs
  remain in complete components. No silent duplicate pruning or spatial leakage.
- Original text availability: 254 verified, nine proven source-absent, 1,750
  not requested. These are distinct from unknown map judgments and do not
  filter or block the unfiltered image/query main collection.
- Test positive/negative/dispersion minima now pass for every intent. Main map
  judgments are unknown in three water/pasture/composite and two arable cases,
  so seven intents fail required judged_fraction=1.0. Both-present controls:
  forest-water 35/2/0; arable-pasture 59/7/0. False deficits are eight and three;
  forest-water false dispersion is one (<5). No criteria were changed.
- `benchmark-candidate-v4` is **blocked-not-frozen**. Default expanded loading
  retains frozen-status/numeric coverage protection and native spatial checks.
  Earlier candidates/designs and their code pins remain unchanged. No final
  evaluation, embeddings, rankings or statistics implementation.
- Concrete proposal only: smaller mapped forest-presence/paraphrase study
  (549 positive / 322 negative fully judged Test cases, 537 positives outside
  largest group), requiring explicit new scope/analysis; or a separately
  preregistered reference-enriched relation control with fresh spatial groups.
  No further images are drawn and neither proposal is implemented.
- Verification: 90 tests passed without skips, including stable real-catalog
  expansion, changed-label invariance, transitive neighbor bridges, Development
  anchoring, optional captions and rejection of a false frozen record. Final
  revised-design/source guards were rechecked (4 tests). Ruff check/format pass
  for src/tests/scripts; changed notebook cells have no findings (22 historical
  findings remain). Notebook freshly executed without errors; three fixed
  Development RGB/maps and the expanded spatial figure visually inspected.
  Reusable design/transition/freeze/source assessment is in the new
  `benchmark_expansion` module; extraction reuses existing canonical logic.
  Existing candidate code pins are preserved by leaving historical modules and
  acquisition scripts unchanged. PR #8 was subsequently human-merged; the revised
  freeze above supersedes this
  historical decision without changing its artifacts.

Historical full-selection access and feasibility evidence (PR #8):

- The unchanged 250-ID selection is fully extracted from the two already
  verified official archives. One sequential scan per archive writes 900 missing
  TIFFs and reuses 100 valid files: 1,000 original files / 22,150,304 selected
  bytes, zero new archive transfer. Original 25-ID selection/access evidence
  remains intact; `archive-data-access-v2` explicitly authorizes the full scope.
- All 250 native RGB/map pairs pass exact member/catalog/band/grid/CRS/extent/
  resolution/dtype/NoData/value checks. B04/B03/B02, uint16 120×120, seven UTM
  zones, 10 m, NoData 0, no masked RGB values; DN 1–17,824. No resampling.
- Official filter/search failures are bypassed through verified exact Parquet
  ranges: 185,271-byte footer, 9,182,428 patch-ID column bytes in 70/78 groups,
  then one original row per exact indexed ID. Converted source commit and
  response SHA-256 snapshots are pinned. Rows API revision limitation is explicit.
  241 selected text records pass S1/country/native-center checks (maximum center
  residual 1.42e-14 degree); nine exact IDs are absent from the pinned source.
  The first 25 contain 24 matches / one absent entry. No invented replacements.
- Successful new text responses including preliminary probes total 9,942,373
  bytes; conservative cumulative ceiling including failed allocations is
  10,954,442 bytes, below the authorized 50 MB. Valid caches are identity checked.
- Total 263 distinct technical pairs / 254 complete original-text pairs.
  Unchanged spatial protocol: 235 groups, Development 128 (110 groups), Test-side
  135 (125 groups). All 22 previous Development IDs stay Development. Text-complete
  allocation: 122 Development / 132 Test; missing text 6/3. No duplicate native
  footprints; 19 projected-envelope overlaps (16 earlier Development pairs and
  three selected neighbor pairs), all contained within complete split groups.
  No planned image overlaps/connects to the original 13-image Development group.
- Main Test true/false/unknown: forest 89/46/0, water 6/129/0, arable 50/85/0,
  pasture 40/95/0, forest/water conjunction 3/132/0 and adjacency 2/133/0,
  arable/pasture conjunction 10/125/0 and adjacency 9/126/0. Controls are separate:
  all forest/water 9/2/0, arable/pasture 26/2/0; Test 2/1/0 and 9/1/0.
  Both-present false cases now exist, but unchanged counts/dispersion still fail.
- `benchmark-candidate-v3` pins actual new 263-image evidence; v1/v2 remain
  unchanged. Status stays `blocked-not-frozen`: sparse water/composite/control
  coverage, nine missing original texts and unverified fine-reference suitability.
  No thresholds, queries, gates, statistics or final model/embedding runs changed.
- Next decision: explicitly choose mapped-boundary agreement versus independently
  verified visible relations; then preregister further deterministic sampling and
  budget to satisfy unchanged gates. Ask BIFOLD for the nine exact absent texts
  before altering completeness requirements. These are proposals, not changes.

- Verification: 86 tests passed without skips, including the full 250-patch real
  raster/text integration and failed-range/budget/cache/schema tests. Ruff check
  and format pass for src/tests/scripts; changed notebook cells have zero findings
  (22 older findings remain unchanged). Notebook executed in a fresh kernel with
  zero errors; three predeclared Development RGB/maps and full spatial figure
  visually inspected. A text-cache reproduction added zero transfer and preserved
  exact annotations. Reusable transfer/schema validation is in `src/text_access.py`;
  source orchestration stays in scripts and compact exploration/plots in notebook.
- The scoped data/access/feasibility implementation is complete. PR #8 can be
  ready for review with an explicitly blocked freeze and concrete next decisions.

Historical implementation checkpoints follow.

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
- Continuation: `development-validation-v2` selects the next three distinct
  IDs from the original pinned text snapshot before access inspection. Existing
  official prefixes contain the twelve required additional files. All 13 pairs
  (52 source TIFFs) were actually loaded; source/country/S1/text-center identities,
  EPSG:32633 metre grids, 120×120 uint16 shape, 10-m RGB/map resolution, NoData 0
  and alignment are verified. Additional archive transfer: zero bytes.
- Planned broader inventory: 250, complete files present 0, verified 0, assigned
  development/test 0/0. Available development: 13, loaded/technically validated
  13, development/test 13/0, independently verified fine-boundary truth 0. All
  remain one component/date/tile. No planned ID was substituted with accessible
  early development members.
- Current coverage (true/false/unknown): forest 13/0/0, water 6/7/0, arable 5/8/0,
  pasture 6/7/0, forest/water conjunction/adjacency 6/7/0, arable/pasture 3/10/0.
  Controls contain six and three true relations, still no false relations.
  Fixed coverage/dispersion requirements were applied without relaxation.
- Reference suitability: provider-native 10-m TIFF storage inherits generalized
  CLC2018 semantics (25-ha mapping unit, 100-m minimum linear width). Clipped
  patch areas and summed boundaries are different quantities; no numerical
  parameter replacement follows automatically. Current rules remain provisional
  map-defined computations, not verified visual-boundary truth. Explicit
  interpretation or independent reference evidence remains an open proposal.
- `benchmark-candidate-v2` preserves v1 and records the source/development revision
  with fresh input hashes; both remain blocked. Freeze-loader code/criteria are
  unchanged. 66 tests passed, including real source integration and a positive
  controlled protocol fixture; Ruff passes; notebook freshly executed and new
  RGB/map examples visually inspected. No new model encoding or statistics.
- Previous next action (superseded by the full-archive authorization below):
  provide an official indexed subset route or local subset with verifiable
  provenance initially for the first 25 selected IDs (100 TIFFs). Then validate
  broader development plausibility,
  native spatial separation and held-out main/control coverage under a new
  candidate version before a real freeze. Package 5's final-evaluation prerequisite
  remains unmet. See `docs/BENCHMARK_DESIGN.md` for exact rules and access evidence.
- Archive-access continuation: full acquisition of **only** BigEarthNet-S2 and
  Reference_Maps from Zenodo 10891137 is explicitly authorized (63,534,101,678
  bytes). Fresh official inventory confirms v2.0.0, sizes and published MD5s.
  The local disk has about 1.1 TiB free; archives stay in ignored
  `data/cache/archives/`, with no full uncompressed dataset written.
- Reference archive: all 282,391,301 bytes downloaded and published MD5 verified;
  measured SHA-256 and 25 exact original map-member hashes are recorded in
  `archive-data-access-v1`. An interrupted transfer resumed at byte 263,179,956
  with exact HTTP 206. The 25 maps total 25,154 bytes and were actually read:
  EPSG:32633, 120×120 uint16, native 10-m cells, NoData 0, zero masked pixels.
- At the previous partial-stage checkpoint, S2 acquisition was in progress and
  unverified. A one-time local macOS job
  resumes retained partial bytes in exact 64-MiB HTTP ranges; three consecutive
  network failures stop it. After both complete MD5 checks it automatically
  scans the archives sequentially and extracts only the fixed 100 TIFFs.
  Runtime byte counts/errors are local progress files, not frozen research inputs.
- The unchanged first 25 IDs cover seven Austria tiles and nine acquisitions.
  Planned 25; original maps present/loaded/member-verified 25; RGB TIFFs present 0;
  complete RGB/map patches validated 0; new Development/Test assignments 0/0.
  Existing complete validation remains 13 Development, one group, zero Test.
  Text-filter access returned HTTP 502; a first-patch retry timed out. No full
  text parquet, S1 archive or additional model weights were downloaded.
- Reference-only preview (true/false/unknown): forest 16/9/0, water 1/24/0,
  arable 17/8/0, pasture 2/23/0; forest/water conjunction/adjacency 0/25/0;
  arable/pasture 1/24/0. Both-present controls have 0/0/0 and 1/0/0 states.
  Forest negatives are newly evidenced in maps, but hard relation negatives
  remain absent. These are provisional map counts, not retrieval/test coverage.
- No candidate revision, criteria change, model encoding or statistics.
  `benchmark-candidate-v2` remains `blocked-not-frozen`. The acquisition PR is
  Draft while the S2 download, complete raster/text validation, native spatial
  grouping and new RGB/map visual examples remain unfinished. Next: finish the
  retained download, validate the exact 25 complete pairs and their text/source
  identities, then apply the unchanged spatial protocol and coverage gates.
- Partial-stage verification: 79 tests passed without skips; Ruff check/format
  passed; the notebook executed from a fresh kernel and actual map previews were
  visually inspected. Original v1/v2 input digests and default loader rejections
  still pass. HTTP 504 interrupted S2 acquisition; saved bytes are preserved.
  An initial background manager's unintended restarts were stopped; the local
  replacement explicitly disables automatic restart (`KeepAlive=false`).

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
