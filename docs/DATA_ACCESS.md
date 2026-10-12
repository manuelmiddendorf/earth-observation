# Data pilot: sources and access evidence

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
