"""Validate development source identity and geometry without encoding any model."""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform

from earth_observation.data import acquire_rasters, load_pilot
from earth_observation.encoding import model_rgb
from earth_observation.raster import (
    RGB_BANDS,
    inspect_patch,
    patch_files,
    read_rgb_bands,
)


def validate_development_sources(
    manifest_path: Path, cache: Path, raw_root: Path, upper_dn: float
) -> pd.DataFrame:
    """Check real RGB/map measurements against pinned text and catalog identities.

    Parameters
    ----------
    manifest_path : Path
        Pinned development manifest selecting original annotation rows and members.
    cache, raw_root : Path
        Source cache and native extracted raster roots; valid files are reused.
    upper_dn : float
        Explicit model RGB saturation DN from the existing model specification.
        Conversion is checked without generating embeddings or loading weights.

    Returns
    -------
    pandas.DataFrame
        One row per manifest patch, in its order. Records catalog verification,
        annotation ID, native CRS/shape/resolution/NoData, map alignment and
        pixel-mask counts, WGS84 center residual in degrees, country and tile.
        These are technical checks, not independent visual reference truth.

    Raises
    ------
    ValueError
        Source identity, geometry, text-center alignment (absolute tolerance
        1e-8 degree), incomplete catalog pairing or model RGB contract fails.
    """
    annotations, catalog = load_pilot(manifest_path, cache)
    acquire_rasters(manifest_path, cache, raw_root)
    if not catalog.catalog_status.eq("verified").all():
        raise ValueError("Complete official catalog pairing required")
    rows = []
    for annotation in annotations:
        pid = annotation["patch_id"]
        files = patch_files(
            pid, raw_root / "BigEarthNet-S2", raw_root / "Reference_Maps"
        )
        inspected = inspect_patch(files)
        if inspected["status"] != "aligned":
            raise ValueError("Complete aligned RGB/map pair required")
        rgb = read_rgb_bands({band: files[band] for band in RGB_BANDS})
        model_rgb(rgb, upper_dn)
        red = inspected["rasters"]["B04"]
        reference = inspected["rasters"]["reference"]
        crs = rasterio.crs.CRS.from_string(red["crs"])
        if not crs.is_projected or crs.linear_units_factor[1] != 1:
            raise ValueError("Development measurements require a projected metre CRS")
        left, bottom, right, top = red["bounds"]
        longitude, latitude = transform(
            red["crs"], "EPSG:4326", [(left + right) / 2], [(bottom + top) / 2]
        )
        residual = max(
            abs(longitude[0] - annotation["longitude"]),
            abs(latitude[0] - annotation["latitude"]),
        )
        if not np.isfinite(residual) or residual > 1e-8:
            raise ValueError("Text coordinate does not match native raster center")
        with rasterio.open(files["reference"]) as raster:
            masked = int(np.ma.getmaskarray(raster.read(1, masked=True)).sum())
        rows.append(
            {
                "patch_id": pid,
                "annotation_id": annotation["ID"],
                "catalog_status": "verified",
                "country": annotation["country"],
                "tile": pid.rsplit("_", 2)[0].rsplit("_", 1)[1],
                "crs": red["crs"],
                "height": red["shape"][0],
                "width": red["shape"][1],
                "dtype": red["dtype"],
                "pixel_width_m": red["resolution"][0],
                "pixel_height_m": red["resolution"][1],
                "map_height": reference["shape"][0],
                "map_width": reference["shape"][1],
                "map_dtype": reference["dtype"],
                "map_pixel_width_m": reference["resolution"][0],
                "map_pixel_height_m": reference["resolution"][1],
                "rgb_nodata": red["nodata"],
                "map_nodata": reference["nodata"],
                "rgb_masked_values": int(np.ma.getmaskarray(rgb).sum()),
                "map_masked_pixels": masked,
                "identical_rgb_map_grid": red["transform"] == reference["transform"]
                and red["shape"] == reference["shape"],
                "text_center_error_deg": residual,
            }
        )
    return pd.DataFrame(rows).set_index("patch_id")
