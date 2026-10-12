"""Reproduce model-independent coverage and the explicitly blocked candidate record.

No model is instantiated. The selected broader inventory is never replaced by
convenient early archive members when bounded access cannot reach its IDs.
"""

import argparse
import json
import tarfile
from pathlib import Path

import pandas as pd
import rasterio
import zstandard

from earth_observation.benchmark import (
    coverage_tables,
    freeze_blockers,
    reference_unknown_sources,
    select_catalog,
    spatial_split,
    verified_footprints,
    write_benchmark_record,
)
from earth_observation.data import acquire_rasters, fetch_asset, load_pilot
from earth_observation.encoding import file_digest
from earth_observation.raster import patch_files
from earth_observation.reference import evaluate_pilot, load_specifications


def _prefix_inventory(path: Path, budget: int = 8_000_000) -> set[str]:
    # Reading each body distinguishes complete members from a partial last header.
    ids = set()
    with path.open("rb") as compressed:
        with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
            try:
                with tarfile.open(fileobj=stream, mode="r|") as archive:
                    for member in archive:
                        if archive.offset > budget:
                            break
                        if not member.isfile():
                            continue
                        if member.size > 1_000_000:
                            raise ValueError(
                                "Unexpectedly large member in bounded probe"
                            )
                        body = archive.extractfile(member).read(member.size + 1)
                        if len(body) != member.size:
                            break
                        parts = Path(member.name).parts
                        if len(parts) == 4:
                            ids.add(parts[2])
            except (tarfile.ReadError, zstandard.ZstdError):
                pass  # A finite prefix ends mid-stream; only completed bodies count.
    return ids


def prepare(root: Path, write_record: bool = False) -> dict:
    """Reproduce bounded-access evidence and all available reference coverage.

    Parameters
    ----------
    root : Path
        Repository root with the versioned pilot, selection and design.
    write_record : bool
        Save the content-identified candidate record after all checks. Existing
        different versions fail closed; no final evaluation is performed.

    Returns
    -------
    dict
        Record with verified geometry/coverage, candidate collections, unassigned
        planned acquisition IDs, input digests, freeze status and concrete blockers.
    """
    pilot_path = root / "manifests/data-pilot-v1.json"
    design_path = root / "config/benchmark-design-v1.json"
    access_path = root / "manifests/coverage-access-v1.json"
    pilot = json.loads(pilot_path.read_text())
    design = json.loads(design_path.read_text())
    access = json.loads(access_path.read_text())
    load_pilot(pilot_path, root / "data/cache")
    acquire_rasters(pilot_path, root / "data/cache", root / "data/raw")
    catalog = pd.read_parquet(root / "data/cache/metadata.parquet")
    selected = select_catalog(catalog, design["selection"])
    selected_path = root / "manifests/coverage-selection-v1.csv"
    pd.testing.assert_frame_equal(selected, pd.read_csv(selected_path))
    for asset in access["tail_probes"]:
        tail = fetch_asset(asset, root / "data/cache", max_bytes=1024)
        if tail.read_bytes()[-4:].hex() != asset["last_four_bytes_hex"]:
            raise ValueError("Archive tail changed")
    observed_prefix_ids = {}
    for asset in pilot["raster_prefixes"]:
        path = fetch_asset(asset, root / "data/cache")
        parameters = zstandard.get_frame_parameters(path.read_bytes()[:64])
        expected_size = access["zstd_frames"][asset["name"]]["content_size_bytes"]
        if parameters.content_size != expected_size:
            raise ValueError("Archive frame provenance changed")
        observed_prefix_ids[asset["name"]] = _prefix_inventory(path)
    # IDs remain an acquisition plan. No coordinate or relevance is invented.
    reached = set.intersection(*observed_prefix_ids.values()) & set(selected.patch_id)
    if reached:
        raise ValueError(
            "Access evidence changed; revise the candidate version explicitly"
        )
    available_ids = pilot["patch_ids"]
    footprints = verified_footprints(available_ids, root / "data/raw")
    assignment = spatial_split(footprints, available_ids, design["spatial"])
    rules, queries = load_specifications(
        root / "config/reference-rules-v1.json",
        root / "config/query-specification-v1.json",
    )
    summaries, decisions = evaluate_pilot(
        pilot_path, root / "data/cache", root / "data/raw", rules, queries
    )
    intent, family, relation, controls = coverage_tables(
        decisions, queries, assignment.group_id
    )
    sources = []
    for pid in available_ids:
        files = patch_files(
            pid, root / "data/raw/BigEarthNet-S2", root / "data/raw/Reference_Maps"
        )
        with rasterio.open(files["reference"]) as raster:
            causes = reference_unknown_sources(raster.read(1, masked=True), rules)
        sources.append({"patch_id": pid, **causes})
    source_table = pd.DataFrame(sources).set_index("patch_id")
    test_ids = assignment.index[assignment.split == "test"].tolist()
    if test_ids:
        raise ValueError("Previously developed pilot must never enter test")
    blockers = freeze_blockers(
        pd.DataFrame(), pd.DataFrame(), design["coverage"], len(selected), queries
    )
    blockers += [
        "Broader development reference/preprocessing plausibility is unverified",
        "Native coordinates for the selected inventory are unavailable; "
        "country/tile IDs do not establish cross-tile separation",
    ]
    inputs = [
        "manifests/data-pilot-v1.json",
        "manifests/coverage-selection-v1.csv",
        "manifests/coverage-access-v1.json",
        "config/benchmark-design-v1.json",
        "config/reference-rules-v1.json",
        "config/query-specification-v1.json",
        "config/frozen-models-v1.json",
        "uv.lock",
        "scripts/prepare_benchmark.py",
        "src/earth_observation/benchmark.py",
        "src/earth_observation/reference.py",
        "src/earth_observation/raster.py",
        "src/earth_observation/data.py",
        "src/earth_observation/encoding.py",
        "src/earth_observation/retrieval.py",
        "data/cache/metadata.parquet",
    ]
    inputs.extend(
        "data/raw/" + member["name"]
        for asset in pilot["raster_prefixes"]
        for member in asset["members"]
    )
    inputs.extend("data/cache/" + asset["name"] for asset in access["tail_probes"])
    record = {
        "version": "benchmark-candidate-v1",
        "status": "blocked-not-frozen",
        "blockers": blockers,
        "data_version": "BigEarthNet-v2 2.0.0 / data-pilot-v1",
        "design_version": design["version"],
        "reference_version": rules["version"],
        "query_version": queries["version"],
        "model_specification": "config/frozen-models-v1.json",
        "evaluation_specification": "config/benchmark-design-v1.json#evaluation",
        "previous_development_ids": available_ids,
        "main_candidates": {"development": available_ids, "test": test_ids},
        "relation_controls": {
            "development": controls,
            "test": {intent_id: [] for intent_id in controls},
        },
        "unassigned_selection": selected.patch_id.tolist(),
        "spatial_inventory": footprints.join(assignment)
        .reset_index()
        .to_dict("records"),
        "relevance": {
            "patch_ids": available_ids,
            "intent_ids": decisions.columns.tolist(),
            "states": decisions.to_numpy().tolist(),
        },
        "available_coverage": {
            "intent": intent.reset_index().to_dict("records"),
            "family": family.reset_index().to_dict("records"),
            "relations": relation.reset_index().to_dict("records"),
        },
        "unknown_pixel_sources": source_table.reset_index().to_dict("records"),
        "access": {
            "planned_count": len(selected),
            "planned_tiles": selected.tile.nunique(),
            "verified_new_patches": 0,
            "test_count": len(test_ids),
            "additional_archive_bytes": sum(
                a["size_bytes"] for a in access["tail_probes"]
            ),
            "selected_ids_in_cached_prefixes": len(reached),
        },
        "inputs_sha256": {name: file_digest(root / name) for name in inputs},
    }
    output = root / "outputs/coverage-v1"
    output.mkdir(parents=True, exist_ok=True)
    for name, table in [
        ("intent", intent),
        ("family", family),
        ("relations", relation),
        ("spatial", footprints.join(assignment)),
        ("unknown", source_table),
    ]:
        table.to_csv(output / f"{name}.csv")
    (output / "assessment.json").write_text(json.dumps(record, indent=2) + "\n")
    if write_record:
        write_benchmark_record(root / "manifests/benchmark-candidate-v1.json", record)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-record", action="store_true")
    args = parser.parse_args()
    record = prepare(Path(__file__).resolve().parents[1], args.write_record)
    print(record["status"])
    print(record["access"])
    for blocker in record["blockers"]:
        print("-", blocker)
