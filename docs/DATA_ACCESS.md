> **Current access:** both official archives are downloaded and verified locally;
> the 2,000-ID selection plus the earlier pilot provides 2,013 native RGB/map
> pairs. Original captions are optional for the final image/query retrieval.
> This document preserves acquisition stages and source commands. The
> [reproduction guide](REPRODUCTION.md) distinguishes local prerequisites from
> the current final evaluation.

# Data pilot: sources and access evidence

**Latest evidence:** the fixed 2,000-ID expansion is technically validated.
`benchmark-design-v2` targets generalized map agreement and makes original
captions optional for main retrieval. Unknown map judgments and sparse hard
relation negatives still block candidate v4. Earlier checkpoints below retain
their historical scope; see the latest expansion section for current evidence.


Checked 2026-10-12; experiment `data-pilot-v1`, raster access `archive-prefix-v1`.
The unchanged ten-patch pilot now has verified text/catalog pairs, **thirty real
RGB band files and ten real reference maps**. Real raster integration and visual
inspection of three fixed examples complete work package 1.

## Sources and identity

| Component | Official source | Pinned identity | Available download |
|---|---|---|---:|
| Text annotations | [BIFOLD dataset](https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt) | revision `72d865f2146f0a85b720f7f3ca1cdbaeafc3d316` observed at acquisition | Parquet: 466,819,745 bytes |
| S2 images | [BigEarthNet site](https://bigearth.net/) → [Zenodo record 10891137](https://zenodo.org/records/10891137) | v2.0.0; archive MD5 in manifest | 63,251,710,377 bytes |
| Reference maps | Same Zenodo record | v2.0.0; CLC2018 v2020_u1 origin reported by provider | 282,391,301 bytes |
| Patch catalog | `metadata.parquet` in same record | MD5 `55687065e77b6d0b0f1ff604a6e7b49c`, additionally SHA-256 pinned | 3,616,349 bytes |

The provider credits the RSiM and DIMA groups at TU Berlin/BIFOLD for v2;
the text dataset credits Herzog, Adler, Hackel, Shu, Zavras, Papoutsis, Rota,
and Demir. Both sources declare
[CDLA-Permissive-1.0](https://cdla.dev/permissive-1-0/).
Redistributing source data requires retaining provider attribution and providing
the license text/name or link; modified data needs a prominent change notice.
The cached responses here remain local. Cite the providers' BigEarthNet.txt
preprint and reBEN publication when reporting research based on these data.

The [official text card](https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt/blob/72d865f2146f0a85b720f7f3ca1cdbaeafc3d316/README.md)
points to the v2 images separately. Its example confirms B04/B03/B02 ordering.
The [v2 description](https://bigearth.net/static/documents/Description_BigEarthNet_v2.pdf)
documents tile/patch directories and the `_reference_map.tif` suffix. This layout
was verified against actual tar members and local GeoTIFFs.

## Bounded acquisition and selection

The Hugging Face dataset-server `rows` API returned four pages of 100 rows at
ascending offsets 0, 100, 200, 300 (`default`, `all_data`). From these 400 rows,
select the first ten distinct `patch_id` values by `row_idx`, preserving the
first annotation per patch. The 400 rows contain 16 distinct patch IDs.
The exact responses and catalog are SHA-256 pinned in
[`data-pilot-v1.json`](../manifests/data-pilot-v1.json). Text/catalog assets total 3,842,879 bytes. Repeated runs reuse validated files.

The rows endpoint does not accept a pinned repository revision. The recorded
repository SHA provides acquisition context; it is **not proof that the server
responses came from that revision**. Response digests identify the actual
snapshot. If the service changes serialization/content, reproduction fails
explicitly; recover the matching original cache or create a new named pilot
rather than bypassing verification. The manifest retains no machine paths.

The catalog checksum matches Zenodo's published MD5. All ten exact S2 IDs exist
in its `patch_id` column, with matching S1 names, country, and split. All belong
to one Austria tile and carry the provider's `test` split. This convenience
sample establishes bounded data access; it is not representative,
not the project's final test set, and must not guide benchmark parameter choices.
Missing catalog entries remain unknown; contradictory pairs fail validation.

## Observed schema

Observed through the real rows API (not a full Parquet download): `ID` is int64;
`patch_id`, `s1_name`, `input`, `output`, `type`, `category`, `split`, `country`,
`season`, and `climate_zone` are strings; `latitude`/`longitude` are float64.
The provider describes the coordinates as patch-center latitude/longitude;
the API does not encode a CRS for them. They are not used to assert raster
alignment. Annotation IDs differ from patch IDs: multiple instructions share
a patch. Truncated records are rejected.

The downloaded v2 catalog has 480,038 rows and eight fields: `patch_id`,
`s1_name`, `s2v1_name`, `split`, `country`, `labels` (list-valued in Parquet),
`contains_seasonal_snow`, and `contains_cloud_or_shadow` (Boolean). The two
quality flags are reported metadata; no extra filtering is applied here.
The separate snow/cloud/shadow catalog is not needed for this sample and was
not downloaded. Catalog absence in other samples would not imply false labels.

## Verified bounded raster access

The earlier 1-KiB HTTP 206 probes established range support, but were too small
to inspect archive members. This continuation inspected 256-KiB prefixes of the
same official archives: both begin with the unchanged pilot IDs, in the same
order. The S2 prefix was extended by the adjacent range 262144–2097151, reusing
the original bytes. A finite **2,097,152-byte S2 prefix** and a **262,144-byte map
prefix** contain all required complete members. The total raster acquisition is
**2,359,296 bytes (2.25 MiB)**. Only the selected thirty bands (875,880 bytes) and
ten maps (11,737 bytes) are persisted: **887,617 bytes**, forty TIFFs.

This is a verified prefix-streaming route for these ten early members, not
arbitrary indexed access to later patches. The provider's
[pinned compression script](https://github.com/rsim-tu-berlin/bigearthnet-pipeline/blob/78551a68525fc26b15257b676f46c3c254be70cc/nu-scripts/zstd-compressor.nu)
uses zstd. It does not promise a random-access member index. Archive ordering
was established by inspecting the actual official tar stream, not assumed from
filenames or that script. No credentials were needed; the same dataset license
applies. No full image or map archive was downloaded.

The public manifest records each exact archive member name, size and SHA-256,
and each prefix's URL, byte interval, archive total size and SHA-256. Network
acquisition requires an exact HTTP 206 `Content-Range`; an ignored range is
rejected before reading the body. Prefix SHA-256 and each extracted member's
SHA-256 detect drift. These hashes were measured on received bytes; **the full
archive's provider MD5 cannot be verified without the whole archive**.
The decompressed stream stops once all requested complete members are checked.
A partial trailing tar/zstd frame is expected, never used as a complete archive;
missing or incomplete selected members fail. An 8-MB uncompressed scan budget
prevents expanding the task if a requested member is absent.

Extraction writes only selected regular TIFF members. No archive links or path
traversal are accepted. A valid existing raster is reused; a mismatched existing
file raises an error without replacement. Compatible source prefixes remain in
`data/cache/`. Extracted local roots are unchanged:

- `data/raw/BigEarthNet-S2/<tile>/<patch_id>/<patch_id>_B04.tif`
  (also B03 and B02).
- `data/raw/Reference_Maps/<tile>/<patch_id>/<patch_id>_reference_map.tif`.

`scripts/fetch_pilot.py` acquires the complete pilot with these finite prefixes.
`scripts/check_subset_reproduction.py` reacquired only the first pilot patch in
a separate empty temporary cache: two 256-KiB prefixes, **524,288 transferred
bytes**, four complete TIFFs with matching member hashes and native alignment.
This checks reproducibility without downloading the complete pilot again.
The full ten-patch prefixes remain fixed; the smaller reproduction prefix is
explicitly identified separately in the manifest.

## Observed raster contracts and map semantics

All forty actual TIFFs have one uint16 band, shape 120×120, CRS EPSG:32633 (UTM
zone 33N, metre units), native cell size 10×10 m and declared NoData 0. Each
patch covers 1,200×1,200 m. Within every patch the three RGB grids and reference
map have identical transforms and bounds; no resolution difference occurs here.
North-up grids have positive x scale and negative y scale. The real integration
test checks all member digests, native grid/footprint agreement and transformed
raster-center agreement with the original text latitude/longitude at 1e-8-degree
absolute tolerance. Observed differences are at most 1.43e-14 degrees.
These checks complement exact S2 ID and independent S1 catalog-pair verification.
The individual TIFFs have no descriptive band tag; band identity comes from the
exact official member suffix and provider-documented B04/B03/B02 convention,
not an invented internal tag or spectral inference.

The map values are **raw CLC level-3 IDs**, not indices into the recommended
19-class aggregation. Nine occur here: 112 (discontinuous urban fabric),
211 (non-irrigated arable land), 231 (pastures), 242 (complex cultivation
patterns), 243 (agriculture with significant natural vegetation), 311
(broad-leaved forest), 312 (coniferous forest), 313 (mixed forest) and 511
(water courses). Meanings follow Table 1 of the official v2 description, whose
PDF SHA-256 is recorded in the manifest. Code 999 means unlabeled information,
separate from declared NoData 0; 999 does not occur in these ten maps. Neither
is interpreted as a negative label. No class aggregation, relevance threshold
or adjacency rule is implemented.

RGB display uses fixed `clip(DN / 3000, 0, 1)` in B04/B03/B02 order. Declared
masked/NoData or nonfinite values make the entire RGB pixel NaN; undeclared
zero would be retained. This is a display choice, not calibrated reflectance
or future model preprocessing. The notebook assigns discrete display colors to
raw map IDs, preserving the mask. It renders both native grids with nearest
interpolation and axes in projected metres; no raster is resampled or repaired.

Three examples, fixed at pilot positions 1, 5 and 9, were visually inspected.
Broad field/woodland divisions and the western or southern river corridors
correspond plausibly between RGB and reference. Fine field boundaries, small
structures, and forest subclass distinctions remain uncertain. Technical
alignment does not make the CORINE-derived map independently verified visual
truth; its 10-m storage grid does not improve the original mapping accuracy.

## Remaining limits

No external access blocker remains for these ten patches. Prefix extraction is
specific to early members in this version; later/representative sampling still
needs its own bounded-access assessment. The sample remains one geographically
concentrated Austria tile, unsuitable as a frozen evaluation benchmark. Retrieval
performance and reference-rule validity have not been evaluated.

## Authorized full-archive continuation

The earlier bounded-download restriction was explicitly lifted on 2026-10-12
for exactly these two official files. No S1 archive, full text parquet or new
model weights are part of this continuation. A fresh response from the
[official Zenodo record](https://zenodo.org/records/10891137), version 2.0.0,
matches the previous inventory SHA-256
`96261dd63ba881d2114db64c27f31399924a1f8b90d3e3705809f25a6ecd6fef`.

| Archive | Exact bytes | Published MD5 | Current validation |
| --- | ---: | --- | --- |
| BigEarthNet-S2.tar.zst | 63,251,710,377 | `2245ed2d1a93f6ce637d839bc856396e` | Complete; MD5 passed |
| Reference_Maps.tar.zst | 282,391,301 | `95d85a222fa983faddcac51a19f28917` | Complete; MD5 passed |

The map archive's measured SHA-256 is
`d87bda4759d6b209fad71cd8e95968abedd7eda8b63838d2b5a6462bdc788756`.
All 282,391,301 map bytes were actually acquired. After a premature EOF at
263,179,956 bytes, an exact HTTP 206 continuation transferred only the remainder;
the complete MD5 passed. The S2 transfer initially retained 1,448,083,456 bytes
before a deliberate switch to 64-MiB requests. Subsequent requests demonstrably
resume from that nonzero offset rather than downloading the beginning again.
The subsequent download completed and the published S2 MD5 passed. Its measured
SHA-256 is `fa3464f732865b3caeafe905390fb889dce2705fa87cd6bc626c0bd426dff58f`.
The download process is finished; the final resume used download mode only.

At preflight the disk had about 1.1 TiB free, versus 63,534,101,678 archive bytes
plus at most 64 MiB of selected TIFFs and small logs/buffers. Partial-to-final
archive rename does not make a second archive copy. No complete decompressed
tar or image tree is created. Existing pilot caches and 52 source TIFFs are
preserved. The two archive prefixes remain separate historical pilot assets,
not mislabeled complete archives.

### Reproduction, progress and resume behavior

```bash
uv run python scripts/fetch_archives.py --stage all
```

This sequential command validates the unchanged selection CSV checksum and
recomputes its catalog-based deterministic ordering before selecting **rows
1–25 only**. The [acquisition manifest](../manifests/archive-data-access-v1.json)
lists their 100 exact B04/B03/B02/reference paths. A local lock prevents concurrent
writers. Downloads retain `.part` files with exact source identity, reject an
ignored or incorrect Range before reading/appending any response body, and use
60-second socket inactivity timeouts with at most three consecutive failures.
Completed chunks reset the failure count; retries never reset the byte offset.
A wrong complete checksum is an error, not permission to overwrite/restart it.
Archive store: ignored `data/cache/archives/`.

Progress/error snapshots are `data/cache/archives/*.progress.json`. The
one-time macOS background job also writes ignored
`data/cache/archive-access/transfer.log` and `transfer-errors.log`. It has no
login/startup file or repeating schedule. Its local label is
`org.codex.earth-observation.archive-data-access`; `launchctl list` with that
label shows its PID/exit status. Its ignored `background-job.plist` explicitly
sets `RunAtLoad=true`, `KeepAlive=false` and contains no interval or restart rule.
The initial `launchctl submit` job unexpectedly restarted failed processes;
it was removed and replaced with this explicitly non-restarting configuration.
Do not launch another writer while it runs.
After a stopped/failed job, the reproduction command resumes identified partial
files. Explicit `--stage download` or `--stage extract` isolates the same stages.

After **both** complete archive checks the extraction command scans the tar
streams sequentially, holding only selected payloads. It rejects missing or
duplicate selected names, links, path traversal, output symlinks, excessive
selected payload and incompatible existing bytes. Nonselected members are
never written. The full scan checks selected-name uniqueness without retaining
millions of tar header objects. Outputs use the existing native raw-data layout.
The extraction command ends after extraction; it does not assign splits,
calculate embeddings, run models or freeze the benchmark.

### Completed native extraction and validation (2026-10-13)

```bash
uv run python scripts/fetch_archives.py --stage extract
uv run python scripts/validate_archive_access.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_benchmark_construction.ipynb
```

This completion started **zero downloads**. Exact archive names/sizes and existing
verified MD5/SHA-256 receipts were checked. Receipt reuse additionally requires
matching asset identity and archive modification/change times no newer than the
trusted local receipt. Changed/stale files trigger a new checksum pass or fail;
complete validation is not bypassed. Both streams were then sequentially scanned
for exact member uniqueness, without extra complete checksum passes beforehand.

Exactly **100 original TIFFs** for the same first 25 IDs are present: 75 new
B04/B03/B02 files and 25 reused original maps, totaling **2,214,854 bytes**.
The original 52 TIFFs remain unchanged. Member sizes/SHA-256 and both verified
archive identities are recorded in the acquisition manifest.

All 25 new pairs passed actual byte/catalog/band/grid/extent/dtype/NoData/value
checks. Native RGB/map geometry is identical: EPSG:32633, 120×120 single bands,
uint16, 10×10-m cells, NoData 0 and zero masked RGB values. Valid RGB DNs span
1–17,824. RGB order is explicitly B04/B03/B02; the original member suffix and
provider convention establish band identity, not absent descriptive TIFF tags.
No resampling, silent repair or reference-rule change occurred.

The combined inventory has **38 unique pairs in 25 components**. No new ID,
identical native footprint, projected-envelope overlap or 2-km component connects
to the existing 13 Development images. The existing seeded protocol assigns nine
new images to Development and 16 to the Test side: totals **22 / 16**, in **10 /
15 components**. These are measured source-stage assignments, not a frozen test
benchmark, visual ground truth or an independence guarantee.

| Reference intent | All 38 true/false/unknown | Test-side 16 true/false/unknown |
| --- | --- | --- |
| Forest | 29 / 9 / 0 | 11 / 5 / 0 |
| Inland water | 7 / 31 / 0 | 0 / 16 / 0 |
| Arable land | 22 / 16 / 0 | 12 / 4 / 0 |
| Pasture | 8 / 30 / 0 | 1 / 15 / 0 |
| Forest/water conjunction or adjacency | 6 / 32 / 0 | 0 / 16 / 0 |
| Arable/pasture conjunction or adjacency | 4 / 34 / 0 | 1 / 15 / 0 |

All-collection both-present controls have six and four true relations, zero
false/unknown; test-side controls have zero and one true, still zero false.
Main candidates retain all spatially assigned images. Controls are separate
both-present subsets. Family totals are patch × intent counts (152 per family),
not independent samples. The new batch still supplies nine forest negatives but
no hard relation negatives. Test-side water/pasture and minimum-count/dispersion
requirements remain inadequate. The other 225 planned IDs were not acquired.

The local text snapshot contains only earlier Development IDs; all 25 new text
pairings remain **unknown**, separately from complete technical raster checks.
The previous bounded filter returned HTTP 502 and a first-ID retry timed out.
No new text request or full text parquet was fetched under this completion's
no-download constraint. Matching local rows or clarification allowing targeted
small text requests are needed to close this source-validation item.

Notebook sections 12–13 now display three fixed-position actual RGB/map pairs,
spatial assignments and separate all/Development/Test intent/family/control
coverage. RGB display uses fixed `clip(DN / 3000, 0, 1)` and masked pixels become
NaN. Visual inspection found broad woodland/field correspondence, merged field
strips and unresolved small clearings/structures. Gray known-other CLC regions
are not missing labels. Technical alignment and visual plausibility do not
improve generalized CLC2018 accuracy or redefine small-scale relation truth.

Verification: **82 tests passed, none skipped**; Ruff check/format passed for
`src tests scripts`; the notebook executed from a fresh kernel. Changed notebook
cells have zero Ruff findings. There are 22 pre-existing style findings in
untouched cells (20 long lines, two multiple-statement lines); no whole-notebook
reformat was performed. Actual RGB/map and spatial figures were visually checked.
Both original candidate input digests and default final-evaluation refusals
remain valid. `benchmark-candidate-v2` stays `blocked-not-frozen`; no new benchmark
candidate, model embeddings/rankings, statistics or final evaluation are created.
PR #8 remains Draft while original text pairing is unresolved.

## Full planned selection and original text access

The latest explicit continuation authorizes extraction of the entire unchanged
250-ID plan and at most 50,000,000 new text bytes. Earlier 25-ID manifests,
extraction receipts and completion artifacts are preserved as provenance.
`archive-data-access-v2` uses separate local receipts/output paths. No archive
request was made: each already verified archive was scanned once sequentially.
Exactly 900 missing TIFFs were written and 100 valid TIFFs reused, with
22,150,304 selected bytes (21,897,000 RGB and 253,304 map bytes).

All 250 selected pairs pass exact member SHA-256/catalog/S1 identity, B04/B03/B02
ordering, uint16 120×120 grids, CRS/bounds/transform, native 10-m resolution,
NoData 0 and RGB/map alignment checks. Seven native UTM zones occur
(EPSG:32629/31/32/33/34/35/36). RGB has zero masked values; valid DN spans
1–17,824. No geometry repair or resampling occurred. Catalog country metadata
and original-text center coordinates are checked separately against native data.

### Proven bounded original-text route

The existing 400-row text cache contains zero exact planned IDs. Official
`filter` and `search` probes again returned timeouts/HTTP 500. The official
[Parquet inventory endpoint](https://huggingface.co/docs/dataset-viewer/parquet)
lists one 466,819,745-byte file. Exact HTTP 206 range responses were verified
before any body read: status, inclusive Content-Range/parent size, identity
encoding and bounded length. Ignored ranges cannot trigger a full download.

The 185,271-byte footer describes 9,553,962 rows in 78 groups and the original
13-field schema. Complete patch-ID min/max metadata identifies 70 potentially
relevant groups. Their patch-ID column chunks total only **9,182,428 bytes**.
These chunks locate the first exact row position per selected patch; complete
metadata excludes the other groups. A local explicitly partial sparse Parquet
contains only these chunks/footer, never the complete dataset. No input/output
text columns or full row groups were downloaded from Parquet.

Repository revision `72d865f2146f0a85b720f7f3ca1cdbaeafc3d316` remains the observed
source context. Converted Parquet revision
`d1d566c27e7b7d888316d89801013b70ec68bf2e` pins the range source, with a matching
footer verified at that immutable URL. The independently fetched
[official rows endpoint](https://huggingface.co/docs/dataset-viewer/rows) uses
`default/all_data`, exact indexed offset and length one. It does not accept a
revision; therefore its SHA-256 response snapshots, not the observed repository
SHA alone, identify actual annotation bytes. Schema, row index, patch identity,
S1 pair, country and raster-center residual <=1e-8 degree are required.

241 planned IDs have original rows; nine exact IDs are absent from the pinned
Parquet ID inventory and are explicitly listed in the access manifest. The
first 25 contain 24 matches and one absent entry. No adjacent IDs or synthetic
annotations substitute for them. These original instruction/answer examples
are source provenance only; captions and answers never create relevance labels.
The earlier 13 pairs retain their original text proofs: total 263 technical /
254 fully available pairs. Unknown text and unknown map evidence are different.

Transient connection failures and HTTP 429 rate limits were handled with
bounded retries, official waiting intervals and cache reuse. The transfer ledger
retains allocations for failed requests and enforces the cumulative 50-MB cap
before opening another request. Individual responses have URL/size/SHA-256
receipts; changed or unidentified caches fail explicitly. The final measured
response bytes and conservative failed-request upper bound are in v2's text
receipt, separately from the 22.15-MB local raster extraction and zero new
archive bytes. The concrete external source gap is nine absent text IDs;
request those exact original annotations from BIFOLD before revising requirements.

See [full inventory feasibility](BENCHMARK_DESIGN.md#full-planned-inventory-feasibility)
for actual spatial/intent/control coverage and the independently blocked freeze.

Final successful response payload including preliminary probes: **9,942,373
bytes**; pinned response caches total 9,754,768 bytes, with 187,605 additional
successful preliminary bytes. The conservative received-byte upper bound is
9,954,432 bytes; failed-request allocations raise the cumulative transfer upper
bound to **10,954,442 bytes**, below 50 MB. No full text Parquet was transferred.
Exact text-center residual maximum is 1.42e-14 degree. Fully available split
counts are 122 Development / 132 Test-side, with six / three unknown texts.

## Fixed 2,000-ID local expansion

The explicitly authorized `archive-data-access-v3` / `benchmark-design-v2`
continuation preserves all earlier source artifacts. The fixed expansion retains
each country's old 25-ID prefix and raises the quota to 200, before new reference
labels are examined. The catalog population, seed, 53 tiles, Development-tile
exclusion and label/model-independent ordering are unchanged.

Only already verified local archives were used, once sequentially per archive.
Exact required schema is three RGB bands B04/B03/B02 and one original reference
map per ID: 8,000 TIFFs for 2,000 IDs. Maps: 1,750 newly extracted / 250 reused,
2,020,674 selected bytes. RGB: 5,250 new / 750 reused, 175,176,000 selected bytes.
Total: 7,000 new / 1,000 reused, 177,196,674 selected bytes; subtracting the
previous 22,150,304 gives **155,046,370 additional native bytes**, below 256 MiB.
The original measured extraction receipts remain local; replay can change reuse
counts without changing verified source identities or the candidate manifest.

All 2,000 pairs pass exact source byte identity, catalog association, band order,
CRS/transform/extent, uint16 120×120 shape, 10-m resolution, NoData and aligned
native grids. Seven UTM zones occur; zero RGB values are masked, valid DN spans
1–17,888. No repair or resampling. Native geometry supplies the enlarged split;
image IDs at coincident footprints across dates remain distinct images within the
same spatial group. Earlier caches and the 13 original Development pairs remain.

No further original texts were requested. All 241 available selected annotations
and 13 earlier annotations keep their independent source proofs. Nine old selected
IDs remain proven source-absent; the 1,750 added IDs are **not requested**, not
claimed source-absent. Under the authorized map-agreement estimand, these missing
captions do not block main image/query retrieval. Actual unknown map judgments
remain separate and still trigger unchanged coverage gates.

The fixed inventory has 2,013 technical pairs, Development 1,142 / Test-side 871,
in 1,280 groups. New neighbors merge 11 prior groups; 32 previous Test-side images
become Development, while all 128 earlier Development images stay Development.
See [the measured coverage decision](BENCHMARK_DESIGN.md#measured-2000-id-outcome):
unknown main judgments and sparse false controls block candidate v4. No archive,
text or weight transfer, full extraction, repeated draw, model or statistical run
occurred during this expansion.
