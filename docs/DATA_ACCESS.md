# Data pilot: sources and access evidence

Checked 2026-10-12; experiment `data-pilot-v1`. This package is incomplete.
Ten text/catalog patch pairs are verified; **no real image or reference raster
has been loaded**. Controlled raster fixtures are not dataset-access evidence.

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
is an expected contract, **not an observed local raster schema**.

## Bounded acquisition and selection

The Hugging Face dataset-server `rows` API returned four pages of 100 rows at
ascending offsets 0, 100, 200, 300 (`default`, `all_data`). From these 400 rows,
select the first ten distinct `patch_id` values by `row_idx`, preserving the
first annotation per patch. The 400 rows contain 16 distinct patch IDs.
The exact responses and catalog are SHA-256 pinned in
[`data-pilot-v1.json`](../manifests/data-pilot-v1.json). Total downloaded pilot
assets are under 5 MB. Repeated runs reuse validated files.

The rows endpoint does not accept a pinned repository revision. The recorded
repository SHA provides acquisition context; it is **not proof that the server
responses came from that revision**. Response digests identify the actual
snapshot. If the service changes serialization/content, reproduction fails
explicitly; recover the matching original cache or create a new named pilot
rather than bypassing verification. The manifest retains no machine paths.

The catalog checksum matches Zenodo's published MD5. All ten exact S2 IDs exist
in its `patch_id` column, with matching S1 names, country, and split. All belong
to one Austria tile and carry the provider's `test` split. This convenience
sample establishes technical catalog access only; it is not representative,
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

## Image/reference access blocker

For each archive, an explicit 1,024-byte range probe returned HTTP 206,
`Accept-Ranges: bytes`, and `Content-Range` with the sizes above. These probes
are not image/map downloads. The official record publishes compressed tar
archives and catalogs, with no separately listed patch files or member-offset
index. HTTP range support alone does not establish selective extraction from
compressed tar; no indexed, bounded route to these selected members was verified.
No complete archive, weights, or substitute imagery was downloaded.

To complete work package 1, supply a provenance-preserving extracted v2 subset
for the selected IDs, or establish an official indexed member-access route.
The local roots must directly contain `<tile>/<patch_id>/`:

- `data/raw/BigEarthNet-S2/<tile>/<patch_id>/<patch_id>_B04.tif`
  (also B03 and B02).
- `data/raw/Reference_Maps/<tile>/<patch_id>/<patch_id>_reference_map.tif`.

The raster checks then record dimensions, dtype, CRS, affine transform, native
resolution/extent, and declared NoData. RGB grids must be identical. References
may have different resolution, but must have matching CRS/extent and a north-up
unrotated grid. No implicit resampling or repair occurs. Matching geometry is
necessary, but still needs provenance and visual inspection to establish the
correct image/map pairing; unrelated rasters can share a footprint.

RGB display uses a fixed `clip(DN / 3000, 0, 1)` in B04/B03/B02 order.
Declared masked/NoData or nonfinite values make the whole RGB pixel NaN;
undeclared zero values are retained. This display scale is not calibrated
reflectance, model preprocessing, or a claim about reference accuracy.
No real raster dimensions, CRS, transformations, resolutions, NoData settings,
or visual map/image agreement have yet been observed.
