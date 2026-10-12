"""Controlled raster contracts; these are not evidence of real image access."""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from earth_observation.raster import inspect_patch, load_rgb, patch_files


def write_raster(path, value, size=4, resolution=10, x=500000, crs="EPSG:32633"):
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.full((size, size), value, dtype="uint16")
    values[0, 0] = 65535
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="uint16",
        crs=crs,
        nodata=65535,
        transform=from_origin(x, 5300000, resolution, resolution),
    ) as ds:
        ds.write(values, 1)


@pytest.fixture
def files(tmp_path):
    files = patch_files("S2A_example_1_2", tmp_path / "s2", tmp_path / "maps")
    for band, value in [("B04", 3000), ("B03", 1500), ("B02", 750), ("reference", 1)]:
        write_raster(files[band], value)
    return files


def test_rgb_order_scale_nodata_and_no_mutation(files):
    rgb = load_rgb(files)
    np.testing.assert_allclose(rgb[1, 1], [1, 0.5, 0.25])
    assert np.isnan(rgb[0, 0]).all()
    with rasterio.open(files["B04"]) as ds:
        assert ds.read(1)[1, 1] == 3000


def test_missing_reference_is_not_negative(files):
    files["reference"].unlink()
    assert inspect_patch(files)["missing"] == ["reference"]
    with pytest.raises(FileNotFoundError):
        load_rgb(files)


def test_reference_resolution_can_differ_but_extent_cannot(files):
    write_raster(files["reference"], 1, size=2, resolution=20)
    assert inspect_patch(files)["status"] == "aligned"
    write_raster(files["reference"], 1, x=500010)
    with pytest.raises(ValueError, match="footprint"):
        inspect_patch(files)


def test_rgb_shift_and_reference_crs_mismatch_fail(files):
    write_raster(files["B03"], 1, x=500010)
    with pytest.raises(ValueError, match="same grid"):
        inspect_patch(files)
    write_raster(files["B03"], 1)
    write_raster(files["reference"], 1, crs="EPSG:32632")
    with pytest.raises(ValueError, match="CRS/footprint"):
        inspect_patch(files)


@pytest.mark.integration
def test_real_raster_pilot():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifests/data-pilot-v1.json").read_text())
    files = [
        patch_files(
            p, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        for p in manifest["patch_ids"]
    ]
    if not all(path.is_file() for item in files for path in item.values()):
        pytest.skip("BLOCKED: complete official RGB/reference subset is unavailable")
    for item in files:
        assert inspect_patch(item)["status"] == "aligned"
        assert load_rgb(item).shape[-1] == 3
