"""Acquire the bounded official text/catalog and ten-patch RGB/map pilot."""

from pathlib import Path

from earth_observation.data import acquire_rasters, load_pilot

root = Path(__file__).resolve().parents[1]
patches, catalog = load_pilot(
    root / "manifests/data-pilot-v1.json", root / "data/cache"
)
print(f"Selected patches: {len(patches)}")
print(catalog["catalog_status"].value_counts().to_string())
files = acquire_rasters(
    root / "manifests/data-pilot-v1.json", root / "data/cache", root / "data/raw"
)
print(f"Checksum-verified RGB/reference files: {len(files)}")
