"""Acquire only the five checksum-pinned text/catalog assets (under 5 MB total)."""

from pathlib import Path

from earth_observation.data import load_pilot

root = Path(__file__).resolve().parents[1]
patches, catalog = load_pilot(
    root / "manifests/data-pilot-v1.json", root / "data/cache"
)
print(f"Selected patches: {len(patches)}")
print(catalog["catalog_status"].value_counts().to_string())
print("Image/reference access is incomplete; no archive download is attempted.")
