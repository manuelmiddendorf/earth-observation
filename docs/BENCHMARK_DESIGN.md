# Coverage and benchmark readiness

**Latest evidence:** the complete planned 250-ID inventory is technically
validated; original text has 241 exact matches and nine source-absent IDs.
See the full-inventory section below. Earlier numbered checkpoints retain
their historical scope and do not describe the latest availability.


Work package 4, checked 2026-10-12. **No final benchmark is frozen.**
The reference-only coverage, acquisition design, spatial grouping and evaluation
specification are implemented. The broader raster access prerequisite remains
blocked; no final model evaluation was performed.

## What was actually assessed?

The unchanged development pilot has ten complete checksum-identified RGB/map
pairs, all from Austria, MGRS tile 33UUP and acquisition 20170613T101031. Native
footprints transform to European EPSG:3035 bounding envelopes with densified edges.
Envelopes overlapping or separated by at most 2,000 m form connected components,
including transitive chains and repeated acquisitions across dates. All ten
images belong to **one component and remain development**. Pairwise native
checks find zero identical footprints and zero positive-area overlaps; there are
no repeat dates in this pilot. Neighboring observations still share landscape
context and are kept together. Synthetic tests include repeated acquisitions.

| Intent | Positive | Negative | Unknown | Judged | Positive spatial groups |
|---|---:|---:|---:|---:|---:|
| Forest | 10 | 0 | 0 | 100% | 1 |
| Inland water | 6 | 4 | 0 | 100% | 1 |
| Arable land | 3 | 7 | 0 | 100% | 1 |
| Pasture | 5 | 5 | 0 | 100% | 1 |
| Forest and water | 6 | 4 | 0 | 100% | 1 |
| Forest adjacent to water | 6 | 4 | 0 | 100% | 1 |
| Arable and pasture | 2 | 8 | 0 | 100% | 1 |
| Arable adjacent to pasture | 2 | 8 | 0 | 100% | 1 |

The forest/water family has 28 positive, 12 negative and zero unknown **patch ×
intent decisions**; arable/pasture has 12/28/0. Both family denominators are 40
with 100% judged coverage, but each covers only ten unique images in one country,
one tile and one spatial component. These counts are not independent samples or
paraphrase counts. Removing the largest positive component leaves zero positives
for every intent. All source masks, configured unknown codes and unexpected codes
count zero on these maps; unknown source causes are separately tested using known
masked/999/unrecognized examples. Unknown area and unknown intent state are
separate quantities, since an interval can still yield a definite decision.

| Separate filtered control | Both present | Relation true | Relation false | Relation unknown | Excluded missing class | Excluded unknown presence |
|---|---:|---:|---:|---:|---:|---:|
| Forest/water | 6 | 6 | 0 | 0 | 4 | 0 |
| Arable/pasture | 2 | 2 | 0 | 0 | 8 | 0 |

Both presences must be true for control eligibility. Unknown relation states
remain unknown inside the eligible control. Missing/insufficient classes are
not false relations. Main retrieval keeps the entire shared split candidate
collection, independent of query relevance; controls are explicitly filtered
additional experiments and are never pooled with main results.

## Spatial design and its limits

The 2-km envelope-distance criterion exceeds a 1.2-km patch edge and conservatively
keeps immediate neighbors together. It was chosen without model scores; it is not
an empirically established independence radius. EPSG:3035 distances are projected
metres, not exact geodesic distances. Envelopes may overgroup rotated footprints;
this conservatism helps prevent leakage. No raster is resampled. Filename indices,
country names and source-provided train/test labels are not coordinate evidence.

Any spatial component containing an already developed ID stays development. Other
verified components use the fixed seed and SHA-256 hash fraction to assign whole
components, with test fraction 0.5. There is no label-driven balancing or manual
movement after coverage inspection. Exact repeats, overlaps, inclusive-distance
neighbors and transitive chains are tested. New cross-zone/cross-date observations
must first have verified complete native geometry; unavailable inputs remain
**unassigned**, not presumed spatially separate or put into test.

## Predeclared acquisition selection and bounded access

The pinned official `metadata.parquet` has 480,038 clean-catalog rows across ten
countries and 54 MGRS tiles. The provider already excludes snow/cloud/shadow
patches from this catalog; this defines the population, not a new class filter.
The selection reads patch IDs and countries only. It excludes the entire
previously developed 33UUP tile, selects 25 patches per country, and round-robins
across seeded tile order and seeded patch order within each tile. Ordering uses
SHA-256 of `seed|identity`, then identity ties; seed `coverage-v1-20261012`.

The immutable [250-row acquisition plan](../manifests/coverage-selection-v1.csv)
spans all ten countries and 53 distinct tiles. Equal-country quotas and tile
spreading deliberately enrich geography relative to the population distribution;
it is not a representative random sample of a global archive. Catalog row
permutations and changed class labels leave selection unchanged. No query,
reference relevance, caption or retrieval ranking influences selection.

The design limits acquisition to 250 IDs in batches of 25 and **64 MiB of
additional raster bytes**. It prohibits full archives, replacement by accessible
early IDs and unbounded growth. The verified route cannot currently reach this
selection:

- The [official Zenodo inventory](https://zenodo.org/records/10891137) provides a
  63,251,710,377-byte S2 archive and a 282,391,301-byte map archive, without a listed
  member index or individual-patch endpoints. The official Hugging Face group
  lists the text dataset, not an individual-raster mirror.
- Existing pinned prefix headers declare first-frame uncompressed sizes
  102,406,983,680 bytes (S2) and 1,534,300,160 bytes (maps), with 2-MiB windows.
  The [pinned provider compression recipe](https://github.com/rsim-tu-berlin/bigearthnet-pipeline/blob/78551a68525fc26b15257b676f46c3c254be70cc/nu-scripts/zstd-compressor.nu)
  uses ordinary zstd and does not provide a seek table.
- Exact HTTP 206 end probes acquired 1,024 bytes per archive. Neither ends in
  seekable-format magic `0x8F92EAB1`, required by the
  [official Zstandard seekable format](https://github.com/facebook/zstd/blob/dev/contrib/seekable_format/zstd_seekable_compression_format.md).
  Probe intervals, sizes and measured digests are pinned in
  [coverage-access-v1](../manifests/coverage-access-v1.json).
- A bounded rescan of the existing cached prefixes reaches zero selected IDs.
  More early neighboring members do not fulfill the predeclared broader rule.

Exactly **2,048 additional archive bytes**, zero new image/map patches and zero
new model runs were acquired. Existing catalog and pilot caches were reused.
Official inventory/compression-source responses added 13,711 bytes
(9,196-byte Zenodo inventory, 1,417-byte Hugging Face inventory and 3,098-byte
compression source); they are separate from the raster budget. This is a documented limitation of the
verified route, not a claim that a future indexed subset service is impossible.
No full image or map archive was downloaded.

The 250 planned patches have no verified reference states or native coordinates
in this assessment. They are not counted as measured positives/negatives, and
missing evidence does not become false. They remain outside assigned main/control
collections until source bytes and geometry can be verified under a new candidate
version. Already developed images cannot be reclassified as final test.

## Feasibility gates, not a power claim

The machine-readable [benchmark design](../config/benchmark-design-v1.json) fixes:

- Main collection: at least 20 candidates, ten positives and ten negatives per
  fixed intent, three components, and ten positives outside the largest positive
  component. Ten positives prevent a structural P@10 ceiling below one; negatives
  and N>10 avoid trivial all-positive and prevalence-only comparisons.
- Both-present relation controls: ten true and ten false relations, three
  components, and five true/five false cases outside the respective largest
  component. Presence negatives cannot stand in for relation negatives.
- Complete known judgments for the intended main metric comparison. Unknowns
  remain in full rankings; any unknown makes main metrics undefined, with counts
  and coverage retained. Judged-only diagnostics are explicitly separate, using
  compressed fixed rankings and precision denominator min(10, judged count).
  No reference-based candidate exclusion repairs the main collection.

These are reference-based development feasibility requirements, not optimized
model thresholds or a statistical-power guarantee. The unchanged eight intents,
24 texts, 5% presence and 60-m adjacency rules remain provisional. Broader
reference and RGB/preprocessing plausibility must be checked on development
before freeze. Final test references may receive only predefined structural and
coverage checks; semantic iteration on test cases is prohibited.

## Evaluation contract for work package 5

The design specifies, but does not implement, the statistics pipeline:

1. Score the full common test collection using the two pinned model specifications
   and checkpoint preprocessing. Rank by exact cosine, descending, with full
   Unicode patch ID ties. Main/control collections remain distinct.
2. Compute P@10/AP under the existing edge-case contract: P@10 undefined for N<10;
   AP undefined for zero positives; no unknown-as-negative conversion.
3. Arithmetic mean across all formulations within each fixed intent, then equal
   weight across intents, not formulations or families. Overall: eight fixed
   intent means; report single/conjunction/adjacency blocks separately. No NaN
   skipping or performance-driven intent removal. Undefined inputs make their
   prespecified aggregate undefined and require a coverage explanation.
4. Preserve both models and formulations together. Difference is RemoteCLIP minus
   CLIP. Resample G direct families uniformly with replacement, retaining every
   intent and repeated family occurrence. Each estimate is the sum of sampled
   intent differences divided by sampled intent count, matching equal-intent
   point-estimate weighting even if family sizes differ.
5. Use 10,000 draws, NumPy Generator(PCG64), seed 20261012; percentile 0.025/0.975
   using `numpy.quantile(method='linear')`. Do not discard undefined replicates.
   With only two families, intervals are conditional robustness descriptions,
   not broad model/geographic uncertainty or a power demonstration.
6. Separately report each formulation, max-minus-min quality range, and all
   unordered paraphrase top-10 Jaccard pairs per intent/model.
7. Later qualitative sampling: p1 of each fixed intent, ranks 1/5/10 for both
   models, with no score-driven replacement. Record repeated images and classify
   satisfied, presence failures, both-present relation failure and unresolved
   reference using disjoint three-state rules. Manual RGB/map conflicts remain
   separate annotations, never silent reference overwrites.

## Candidate artifact, verification and next action

[benchmark-candidate-v1](../manifests/benchmark-candidate-v1.json) is expressly
`blocked-not-frozen`. Its canonical content digest covers source/specification/
code hashes, selection, native geometry/groups, development-only main candidates,
separate controls, reference states, model/preprocessing and evaluation references.
Input digests include the actual catalog and forty verified TIFFs. The default
loader rejects this candidate for final evaluation; a fabricated `frozen` status
cannot bypass missing verified test inventory. Future frozen records must also
pass exact candidate/relevance/control identity, split leakage and coverage checks.

Reproduce from the native locked environment:

```bash
uv run python scripts/prepare_benchmark.py
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
```

The script reuses checksum-verified catalog/pilot/probe caches; missing probes
require exactly 2 KiB of range downloads. It validates the versioned selection
and saves ignored coverage/spatial/unknown-source tables and assessment provenance.
`--write-record` verifies or creates the same named candidate without overwriting
a changed version. Evaluation/specification changes after a future freeze require
a new version and explanation; test-result-motivated changes are exploratory.

62 tests passed, none skipped, including real catalog selection, native spatial
integration, input/record drift detection and blocked/false-freeze rejection.
Ruff passed. The extended existing notebook executed from a fresh kernel; its
three RGB/map examples and geographic envelopes were visually inspected. No
new notebook, subagents, full repository review, bootstrap pipeline or final
model evaluation was introduced.

Next: establish an official indexed/checksum-identified subset route, or a local
subset with matching verifiable provenance, for this selected inventory. Then
assess development plausibility and held-out main/control coverage under a new
candidate version. A final freeze and work package 5's evaluation prerequisite
remain blocked until that evidence exists.


## Continuation: candidate v2 (2026-10-12)

The original candidate and its 58 input checksums remain unchanged and verifiable.
The continuation uses a separate [development manifest](../manifests/development-validation-v2.json)
and [candidate v2](../manifests/benchmark-candidate-v2.json), both distinct from the
unchanged 250-ID acquisition plan. No method or minimum criterion was relaxed.

| Collection | Planned | Complete files present | Actually loaded and technically validated | Development | Test | Independently validated fine-boundary truth |
|---|---:|---:|---:|---:|---:|---:|
| Broader acquisition plan | 250 | 0 | 0 | 0 | 0 | 0 |
| Available development | 13 | 13 | 13 | 13 | 0 | 0 |

Before inspecting access, the small supplemental batch was defined as the next
three distinct patch IDs after the original ten in the same pinned 400-row text
snapshot. The complete required TIFFs were already present in verified finite
archive caches. Twelve additional source files were extracted and loaded,
bringing the total to 39 RGB bands and 13 original provider reference maps.
**Additional archive transfer: zero bytes.** This does not replace three planned
IDs or imply acquisition of any of the 250 geographically broader candidates.

`validate_development_sources` reuses canonical source selection, catalog pairing,
checksum acquisition, RGB loading and conversion. It verifies actual native CRS,
metre units, affine grid/footprint agreement, image/map resolutions, NoData and
original annotation-to-raster center agreement (tolerance 1e-8 degree). All 13
pairs have 120 × 120 uint16 RGB/maps, EPSG:32633, 10-m cells, NoData 0, identical
RGB/map grids and zero masked pixels. They form one component under the unchanged
2-km rule, one country/tile and one acquisition date. Every explored image remains
development. No test geometry, embedding or ranking is invented.

Updated true/false/unknown coverage: forest 13/0/0; water 6/7/0; arable 5/8/0;
pasture 6/7/0; forest/water conjunction and adjacency each 6/7/0; arable/pasture
each 3/10/0. Family counts are 31/21/0 and 17/35/0 patch-intent decisions (52 per
family, only 13 unique images). Both-present controls have six and three true
relations, **zero false relations**, and zero unknowns. Every intent has zero
positives outside its largest group. The original coverage gates still fail.

### What source scale permits us to conclude

We use the provider's original published reference TIFFs. Our colored panels
aggregate raw CLC codes for display; they are not new surveyed labels or finer
reference data. The underlying CLC2018 status product has a 25-ha minimum mapping
unit and 100-m minimum linear-feature width, documented by
[Copernicus](https://www.copernicus.eu/en/access-data/copernicus-services-catalogue/corine-land-cover-2018-vector-europe-6-yearly-version).
Its generalized source semantics remain despite the TIFFs' 10-m storage grid.

Five percent of a 144-ha patch is 7.2 ha. This is not automatically invalid:
clipping a larger original polygon can leave a smaller area within a patch.
Likewise minimum feature width is not summed boundary length; 100-m width does
not directly prescribe a substitute contact threshold. No parameter was retuned.
The current computations are well-defined **stored-map agreement**, but these
facts do not validate exact visible cover or a surveyed 60-m boundary. Small
structures, generalization and the 2017-image/2018-reference temporal difference
remain limitations.

The three additional RGB/map pairs were visually inspected: broad woodland/field
correspondence is plausible, while small clearings, roads and field boundaries
are generalized. Gray means known other cover, not missing evidence. RGB color
alone cannot independently validate pasture/arable labels. This is qualitative
plausibility, not a thematic-accuracy estimate or fine-boundary ground truth.

Reviewable proposal: either explicitly scope subsequent results to map-defined
agreement, or obtain independent relation/boundary evidence before claiming
visual relational performance. This is an open scientific interpretation decision,
not an implemented replacement of the queries, source or thresholds. Broader
geographic development and adequate held-out coverage remain separate blockers.

### Previous bounded-access handover and verification

At that checkpoint, the official complete S2/map archives totaled 63,534,101,678
bytes and were outside the authorized bounded-download scope. This restriction
is superseded for these two archives by the authorization documented below.
The verified prefix route still cannot
reach the unchanged planned selection. Provide an official indexed endpoint or
a provenance-verified local subset for the **first 25 rows** of
`coverage-selection-v1.csv`: B04/B03/B02 plus the original reference map for each
ID (100 TIFFs), with source version and identifiable original members. File
sizes/checksums and native identity must be verified before any later batch.
No credentials or substitute dataset were assumed at that checkpoint.

```bash
uv run python scripts/validate_development.py
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
```

The command reproduces the same candidate v2 without overwriting a different
version. Source and coverage diagnostics/figures remain in ignored
`outputs/development-validation-v2/`. Existing original-pilot embeddings remain
untouched; no new encoding or statistical pipeline is run.

66 tests passed, none skipped, including real 13-image source/spatial integration,
text-coordinate mismatch rejection, unchanged/blocked candidate versions, and a
positive **controlled protocol fixture** passing the complete existing structural
and coverage checks. That temporary synthetic fixture is a validator test, not
research evidence or an alternative frozen dataset. The loader was not changed
or weakened. Ruff passed, and the extended notebook ran from a fresh kernel with
actual visual inspection. Candidate v2 remains `blocked-not-frozen`; work package
5 is not authorized by these improvements until a valid freeze and human merge.

## Completed native archive access; benchmark freeze remains blocked

Both official archives are complete and have passed their published MD5 checks.
The [acquisition manifest](../manifests/archive-data-access-v1.json) records the
unchanged first 25 IDs, exact 100 members and measured extraction/coverage.
All 25 native pairs are technically validated. New text annotation pairing is
unknown because matching rows are not cached and this completion starts no
new downloads. This is a separate source-validation limitation.

Together with the preserved Development inventory, 38 distinct pairs form 25
native spatial components. No new image overlaps/connects to the previous
Development component. The unchanged protocol assigns 22 images to Development
and 16 to the Test side (nine / 16 new images; ten / 15 components overall).
Main collections are unfiltered by relevance; both-present relation controls
remain separate. No image was selected using model rankings or relabeled to
improve coverage. Visual checks did not motivate rule/query adjustments.

| Intent | All 38 true/false/unknown | Test-side true/false/unknown |
| --- | --- | --- |
| Forest | 29/9/0 | 11/5/0 |
| Inland water | 7/31/0 | 0/16/0 |
| Arable land | 22/16/0 | 12/4/0 |
| Pasture | 8/30/0 | 1/15/0 |
| Forest/water conjunction or adjacency | 6/32/0 | 0/16/0 |
| Arable/pasture conjunction or adjacency | 4/34/0 | 1/15/0 |

The all-collection family counts are forest/water 48/104/0 and arable/pasture
38/114/0, each over 152 patch × intent states (not 152 independent images).
All-collection controls contain six true forest/water and four true
arable/pasture relations, zero false relations. Test-side controls have zero and
one true respectively; neither has a both-present false counterexample.

Thus native geography improves substantially, and forest negatives become
available, but a 16-image test-side collection fails the existing 20-candidate
minimum, has no water positive and only one pasture positive, and lacks hard
relation controls. Dispersion/positive-count gates also fail. The remaining
225 planned IDs and source-scale suitability are unresolved; no criteria are
weakened or additional extraction batch launched.

The notebook freshly executes real RGB/map examples at the first three fixed
acquisition positions, geographic grouping and compact split-specific coverage.
Raster geometry, map-derived labels and visually verified truth remain distinct.
Existing candidate v2 stays unchanged and `blocked-not-frozen`; default loading
continues to refuse final evaluation. No test embeddings, ranks or statistics
are generated. PR #8 stays Draft until the remaining original-text pairing
item is resolved, despite complete native raster extraction/validation.

## Full planned inventory feasibility

This measured assessment supersedes the historical 13-/38-image checkpoints
above. `coverage-selection-v1` is unchanged: 250 IDs, 25 per country, 53 tiles.
The new access scope preserves `archive-data-access-v1`; it does not silently
reinterpret its first-25 authorization. Exactly 1,000 original TIFFs are loaded
and technically verified, with 900 newly extracted and 100 reused. Together
with earlier Development, there are 263 unique native RGB/map pairs.

The unchanged 2-km component/hash protocol now yields 235 components,
128 Development images in 110 groups and 135 Test-side images in 125 groups.
All 22 previously assigned Development IDs remain Development anchors. Every
acquisition date participates; duplicate/overlapping footprints stay in the same
component. Test-side membership is a feasibility allocation, not a final freeze.
No Test RGB inspection, embedding, ranking or query/rule adjustment occurred.

| Intent | All true/false/unknown (n=263) | Test-side true/false/unknown (n=135) | Test positives outside largest group |
|---|---:|---:|---:|
| Forest | 164/99/0 | 89/46/0 | 87 |
| Inland water | 16/247/0 | 6/129/0 | 5 |
| Arable land | 106/157/0 | 50/85/0 | 48 |
| Pasture | 76/187/0 | 40/95/0 | 38 |
| Forest and water | 11/252/0 | 3/132/0 | 2 |
| Forest adjacent to water | 9/254/0 | 2/133/0 | 1 |
| Arable and pasture | 28/235/0 | 10/125/0 | 8 |
| Arable adjacent to pasture | 26/237/0 | 9/126/0 | 7 |

Both-present controls are separate from main retrieval. Across all 263 images,
forest/water has 9 true / 2 false / 0 unknown in six groups; arable/pasture has
26/2/0 in 24 groups. Test-side controls are respectively 2/1/0 in three groups
and 9/1/0 in nine groups. Each family has only one Test false relation, leaving
zero after removing its largest negative group. Thus the zero-hard-negative gap
is closed, but the ten-false and five-dispersed-false gates still fail. The
forest/water true-count and dispersion gates also fail; arable/pasture true count
is nine, below ten. Full exact failed gates are recorded in candidate v3.

### Scientific suitability and the next decision

All map states are judged; zero unknown map states does not establish fine
visual truth. Original text evidence is independently verified for 241 selected
IDs and absent for nine exact IDs in the pinned text source. Missing original
text is explicitly unknown and never converted into a false relevance label.
No missing-text IDs were pruned from the unfiltered main candidate collection.

The three predeclared Development comparisons use the first Development ID in
Austria, Belgium and Finland, without class/ranking selection. Their native
geometry checks cannot resolve generalized CLC2018 boundary accuracy. The
25-ha mapping unit and 100-m minimum linear width remain source limitations;
10-m rasterization does not create independent fine-scale truth. The 5% presence
threshold (7.2 ha) is not invalid merely because clipped mapped polygons can
be smaller than 25 ha. Conversely, 60 m of summed mapped contact does not
prove the corresponding visible relation. Fine-reference suitability remains
unverified and is an independent freeze prerequisite.

**Proposed, not implemented:** explicitly decide whether the scientific target is
agreement with generalized mapped boundaries, or independently verified visible
relations. The former needs a documented narrow interpretation and broader
Development suitability validation; the latter needs an appropriate independent
reference. After that decision, preregister additional deterministic country/tile
batches and budgets, preserving spatial Development anchors and the complete
unfiltered main pool until the existing coverage gates are met. Do not lower
minima, change query meanings from Test references, or choose by model ranking.
Ask the source provider about the nine exact absent text IDs before changing
source-completeness requirements. No such adaptation is implemented here.

`benchmark-candidate-v3` captures actual new raster/text/geographic evidence,
not a formal progress revision. It preserves v1/v2, pins original inputs,
separates main/control IDs and remains **blocked-not-frozen**. Default loading
refuses final evaluation. A fully checked access/feasibility PR may be ready for
review even though its scientific outcome is a demonstrated freeze blocker.

All 19 projected-envelope overlap pairs remain within complete components
(16 older Development pairs, three planned neighboring pairs). There are no
identical native footprints or selected overlaps/connections with the original
13-image Development component. Envelope overlap is conservative spatial
screening and does not prove native pixel-area overlap. The 22 Development
anchors are preserved. Text-complete allocation is 122 Development / 132 Test,
with six / three source-absent text annotations respectively.

Visual inspection of the three predeclared Development examples found an almost
textureless water-only Austria image (CLC 512), individual Belgian fields and
settlement structure generalized into arable/pasture/known-other regions, and a
Finnish mixed field/vegetation region largely assigned to known-other CLC 243/324.
Gray is known other cover, not NoData. These observations support the stated
reference limitation; they do not verify fine adjacency or motivate rule changes.
