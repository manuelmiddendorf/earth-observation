"""Inspect local RGB/reference rasters without resampling or reference derivation."""

from pathlib import Path

import numpy as np
import rasterio

RGB_BANDS = ("B04", "B03", "B02")


def patch_files(patch_id: str, image_root: Path, map_root: Path) -> dict[str, Path]:
    """Resolve the documented v2 tile/patch layout under caller-owned roots.

    Parameters
    ----------
    patch_id : str
        Full S2 patch ID, ending in two numeric grid indices.
    image_root, map_root : Path
        Extracted BigEarthNet-S2 and Reference_Maps roots, respectively.

    Returns
    -------
    dict
        RGB band and reference paths. Existence is checked separately.

    Raises
    ------
    ValueError
        Unsafe or malformed patch ID.
    """
    parts = patch_id.rsplit("_", 2)
    if (
        len(parts) != 3
        or not parts[0].startswith("S2")
        or not all(p.isdigit() for p in parts[1:])
        or "/" in patch_id
        or "\\" in patch_id
    ):
        raise ValueError("Expected an S2 patch ID with two numeric grid indices")
    relative = Path(parts[0]) / patch_id
    files = {b: image_root / relative / f"{patch_id}_{b}.tif" for b in RGB_BANDS}
    files["reference"] = map_root / relative / f"{patch_id}_reference_map.tif"
    return files


def inspect_patch(files: dict[str, Path]) -> dict:
    """Check RGB grids and reference footprints in native coordinates.

    Parameters
    ----------
    files : dict
        B04/B03/B02/reference paths for one explicitly identified patch.

    Returns
    -------
    dict
        Missing components, raster shape, dtype, CRS, affine transform, bounds,
        resolution (CRS units), and NoData. Different map resolution is accepted
        only with identical CRS/extent and north-up, unrotated grids.

    Raises
    ------
    ValueError
        Non-single-band raster, undefined CRS, RGB misalignment, or map mismatch.
        No spatial claims are returned for an incomplete patch.
    """
    if set(files) != {*RGB_BANDS, "reference"}:
        raise ValueError("Expected exactly three RGB bands and a reference")
    missing = [k for k, path in files.items() if not path.is_file()]
    if missing:
        return {"status": "incomplete", "missing": missing, "rasters": {}}
    rasters = {}
    for key, path in files.items():
        with rasterio.open(path) as ds:
            if ds.count != 1 or ds.crs is None:
                raise ValueError("Expected a single band and explicit CRS")
            if ds.transform.b != 0 or ds.transform.d != 0:
                raise ValueError("Rotated grids require explicit review")
            if ds.transform.a <= 0 or ds.transform.e >= 0:
                raise ValueError("Expected a north-up grid")
            rasters[key] = {
                "shape": (ds.height, ds.width),
                "dtype": ds.dtypes[0],
                "crs": ds.crs.to_string(),
                "transform": tuple(ds.transform),
                "bounds": tuple(ds.bounds),
                "resolution": ds.res,
                "nodata": ds.nodata,
            }
    red = rasters["B04"]
    for band in RGB_BANDS[1:]:
        other = rasters[band]
        if any(other[k] != red[k] for k in ("shape", "crs", "transform")):
            raise ValueError("RGB bands are not on the same grid")
    reference = rasters["reference"]
    if reference["crs"] != red["crs"] or not np.allclose(
        reference["bounds"], red["bounds"], rtol=0, atol=1e-6
    ):
        raise ValueError("Reference CRS/footprint does not match the image")
    return {"status": "aligned", "missing": [], "rasters": rasters}


def load_rgb(files: dict[str, Path], upper: float = 3000) -> np.ndarray:
    """Create a fixed-scale RGB display, independently of model preprocessing.

    Parameters
    ----------
    files : dict
        Complete, spatially checked band/reference paths.
    upper : float
        Positive raw-DN display saturation threshold. Default 3000 is a display
        choice, not a calibrated reflectance claim or learned model transform.

    Returns
    -------
    numpy.ndarray
        Float32 H x W x 3 display in [0, 1], ordered red/green/blue. Any masked
        or nonfinite band value makes the entire pixel NaN (unknown/transparent).
        Undeclared zero values are retained; no undocumented NoData assumption.

    Raises
    ------
    FileNotFoundError
        A required component is absent.
    ValueError
        Invalid scale or incompatible raster geometry.
    """
    if not np.isfinite(upper) or upper <= 0:
        raise ValueError("upper must be finite and positive")
    if inspect_patch(files)["status"] != "aligned":
        raise FileNotFoundError("Complete RGB and reference rasters are required")
    bands = []
    for band in RGB_BANDS:
        with rasterio.open(files[band]) as ds:
            bands.append(ds.read(1, masked=True).astype("float32").filled(np.nan))
    rgb = np.stack(bands, axis=-1)
    invalid = ~np.isfinite(rgb).all(axis=-1)
    rgb = np.clip(rgb / upper, 0, 1)
    rgb[invalid] = np.nan
    return rgb
