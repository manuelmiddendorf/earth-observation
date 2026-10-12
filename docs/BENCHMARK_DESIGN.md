# Coverage and benchmark readiness

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
