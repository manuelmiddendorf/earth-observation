"""Model-independent selection, spatial separation and benchmark readiness.

Catalog labels never determine the main candidate collection. Native spatial
measurements, not filename grid indices, establish geographic separation.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from rasterio.warp import transform_bounds

from earth_observation.encoding import file_digest
from earth_observation.raster import inspect_patch, patch_files
from earth_observation.retrieval import validate_ids

_PATCH_PATTERN = re.compile(
    r"S2[AB]_MSIL2A_\d{8}T\d{6}_N\d{4}_R\d{3}_T(\d{2}[C-X][A-Z]{2})_\d+_\d+"
)


def select_catalog(metadata: pd.DataFrame, policy: dict) -> pd.DataFrame:
    """Select a bounded, country-balanced inventory without model/label inputs.

    Parameters
    ----------
    metadata : pandas.DataFrame
        Checksum-verified official catalog with unique patch_id and country.
    policy : dict
        Selection configuration: seed, per-country quota, target_count and
        excluded prior-development MGRS tiles. Labels are never consulted.

    Returns
    -------
    pandas.DataFrame
        selection_rank, patch_id, country, tile. Countries sort lexicographically;
        seeded SHA-256 ordering and tile round-robin spread each quota. This is
        a planned acquisition inventory, not proof of raster availability.

    Raises
    ------
    ValueError
        Invalid IDs/countries, inconsistent quotas or insufficient eligible rows.
    """
    validate_ids(metadata["patch_id"].tolist())
    if not metadata.country.map(lambda c: type(c) is str and bool(c)).all():
        raise ValueError("Require nonempty catalog country strings")
    frame = metadata[["patch_id", "country"]].copy()
    matches = frame.patch_id.map(_PATCH_PATTERN.fullmatch)
    if matches.isna().any():
        raise ValueError("Malformed Sentinel-2 patch identity")
    frame["tile"] = matches.map(lambda match: match.group(1))
    frame = frame[~frame.tile.isin(policy["exclude_development_tiles"])]
    countries = sorted(metadata.country.unique())
    quota = policy["per_country"]
    if (
        type(quota) is not int
        or quota < 1
        or quota * len(countries) != policy["target_count"]
    ):
        raise ValueError("Quota must match the declared target and country population")
    seed = policy["seed"]
    frame["key"] = frame.patch_id.map(lambda pid: _selection_hash(seed, pid))
    chosen = []
    for country in countries:
        subset = frame[frame.country == country]
        if len(subset) < quota:
            raise ValueError(f"Insufficient eligible country inventory: {country}")
        tiles = sorted(
            subset.tile.unique(), key=lambda t: (_selection_hash(seed, t), t)
        )
        queues = [
            subset[subset.tile == tile].sort_values(["key", "patch_id"])
            for tile in tiles
        ]
        country_rows = []
        offset = 0
        while len(country_rows) < quota:
            for queue in queues:
                if offset < len(queue) and len(country_rows) < quota:
                    country_rows.append(
                        queue.iloc[offset][["patch_id", "country", "tile"]].to_dict()
                    )
            offset += 1
        chosen.extend(country_rows)
    result = pd.DataFrame(chosen)
    result.insert(0, "selection_rank", range(1, len(result) + 1))
    return result


def _selection_hash(seed: str, identity: str) -> str:
    return hashlib.sha256(f"{seed}|{identity}".encode()).hexdigest()


def verified_footprints(patch_ids: list[str], raw_root: Path) -> pd.DataFrame:
    """Measure native aligned RGB/map extents in a shared European metric CRS.

    Parameters
    ----------
    patch_ids : list of str
        Unique available patch IDs in manifest order.
    raw_root : Path
        Verified BigEarthNet-S2 and Reference_Maps extraction root.

    Returns
    -------
    pandas.DataFrame
        Patch-indexed EPSG:3035 left/bottom/right/top metres plus native CRS,
        bounds and source date/tile identity. Densified transformed bounding
        boxes are conservative envelopes, not resampled rasters.

    Raises
    ------
    ValueError
        Missing, incompatible or non-European footprints; no filename-derived
        coordinates or incomplete data are accepted.
    """
    validate_ids(patch_ids)
    rows = []
    for pid in patch_ids:
        paths = patch_files(
            pid, raw_root / "BigEarthNet-S2", raw_root / "Reference_Maps"
        )
        checked = inspect_patch(paths)
        if checked["status"] != "aligned":
            raise ValueError(
                "Verified complete aligned rasters required for spatial split"
            )
        native = checked["rasters"]["B04"]
        geographic = transform_bounds(
            native["crs"], "EPSG:4326", *native["bounds"], densify_pts=21
        )
        if not (
            -15 <= geographic[0] < geographic[2] <= 40
            and 30 <= geographic[1] < geographic[3] <= 75
        ):
            raise ValueError(
                "Spatial protocol is restricted to the European source region"
            )
        bounds = transform_bounds(
            native["crs"], "EPSG:3035", *native["bounds"], densify_pts=21
        )
        rows.append(
            {
                "patch_id": pid,
                **dict(zip(("left", "bottom", "right", "top"), bounds, strict=True)),
                "native_crs": native["crs"],
                "native_bounds": list(native["bounds"]),
                "date": pid.split("_")[2],
                "tile": _PATCH_PATTERN.fullmatch(pid).group(1),
            }
        )
    return pd.DataFrame(rows).set_index("patch_id").assign(crs="EPSG:3035")


def spatial_split(
    footprints: pd.DataFrame, previous_development_ids: list[str], policy: dict
) -> pd.DataFrame:
    """Keep overlapping/near/repeated observations in complete spatial components.

    Parameters
    ----------
    footprints : pandas.DataFrame
        Unique patch-indexed EPSG:3035 envelopes with left/bottom/right/top metres.
        All acquisition dates participate. Must originate from verified rasters.
    previous_development_ids : list of str
        Already used images, all of which must be present and remain development.
    policy : dict
        Metric distance_m, split_seed, test_fraction and crs=EPSG:3035.

    Returns
    -------
    pandas.DataFrame
        Same row order, group_id (minimum full patch ID in component), split,
        component_size. Inclusive Euclidean envelope distance creates graph edges;
        transitive closure is deliberately conservative. Anchored groups are
        development; remaining groups use a fixed hash fraction, without balancing
        based on labels. This is separation, not proof of statistical independence.

    Raises
    ------
    ValueError
        Invalid geometry, CRS/settings, IDs or absent development anchors.
    """
    ids = footprints.index.tolist()
    validate_ids(ids)
    if len(set(previous_development_ids)) != len(previous_development_ids):
        raise ValueError("Duplicate development anchors")
    if not set(previous_development_ids).issubset(ids):
        raise ValueError("Development anchors missing from spatial inventory")
    boxes = footprints[["left", "bottom", "right", "top"]].to_numpy(dtype=float)
    distance = policy["distance_m"]
    if (
        policy["crs"] != "EPSG:3035"
        or "crs" not in footprints
        or not footprints["crs"].eq("EPSG:3035").all()
        or not np.isfinite(boxes).all()
        or np.any(boxes[:, 0] >= boxes[:, 2])
        or np.any(boxes[:, 1] >= boxes[:, 3])
        or not np.isfinite(distance)
        or distance < 0
        or not 0 < policy["test_fraction"] < 1
    ):
        raise ValueError(
            "Require finite European metric envelopes and valid split settings"
        )
    parent = list(range(len(ids)))

    def component(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(ids)):
        for j in range(i):
            dx = max(boxes[i, 0] - boxes[j, 2], boxes[j, 0] - boxes[i, 2], 0)
            dy = max(boxes[i, 1] - boxes[j, 3], boxes[j, 1] - boxes[i, 3], 0)
            if np.hypot(dx, dy) <= distance:
                parent[component(i)] = component(j)
    groups = {}
    for i, pid in enumerate(ids):
        groups.setdefault(component(i), []).append(pid)
    assignments = {}
    anchors = set(previous_development_ids)
    for members in groups.values():
        group_id = min(members)
        fraction = int(_selection_hash(policy["split_seed"], group_id), 16) / 2**256
        split = (
            "development"
            if anchors.intersection(members)
            else ("test" if fraction < policy["test_fraction"] else "development")
        )
        assignments.update(
            {
                pid: {
                    "group_id": group_id,
                    "split": split,
                    "component_size": len(members),
                }
                for pid in members
            }
        )
    return pd.DataFrame([assignments[pid] for pid in ids], index=footprints.index)


def coverage_tables(
    decisions: pd.DataFrame, queries: dict, groups: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    """Count three-state coverage and both-present relation controls once per intent.

    Parameters
    ----------
    decisions : pandas.DataFrame
        Exact patch x declared-intent table with true/false/unknown states.
    queries : dict
        Validated existing query specification with direct families.
    groups : pandas.Series
        Nonempty spatial group IDs with exactly the decision index in same order.

    Returns
    -------
    tuple
        Intent coverage (including positives outside largest group), family
        patch-intent counts (not independent images), relation counts separating
        presence failure/unknown from actual relation false/unknown, and ordered
        control IDs per adjacency intent. Control candidates require BOTH true
        presences; unknown relation states stay unknown inside the control.

    Raises
    ------
    ValueError
        Identity/order/state mismatch or malformed control specifications.
    """
    validate_ids(decisions.index.tolist())
    intents = [i["intent_id"] for i in queries["intents"]]
    if (
        decisions.columns.tolist() != intents
        or not groups.index.equals(decisions.index)
        or not groups.map(lambda g: type(g) is str and bool(g)).all()
        or not set(decisions.to_numpy().ravel()).issubset({"true", "false", "unknown"})
    ):
        raise ValueError(
            "Coverage requires exact declared ID order and three-state evidence"
        )
    rows, relations, controls = [], [], {}
    for intent in queries["intents"]:
        states = decisions[intent["intent_id"]]
        positives = groups[states == "true"].value_counts()
        negative_groups = groups[states == "false"].value_counts()
        counts = {s: int((states == s).sum()) for s in ("true", "false", "unknown")}
        rows.append(
            {
                "intent_id": intent["intent_id"],
                "family_id": intent["family_id"],
                **counts,
                "judged_fraction": 1 - counts["unknown"] / len(states),
                "spatial_groups": groups.nunique(),
                "positive_groups": len(positives),
                "negative_groups": len(negative_groups),
                "positive_outside_largest_group": counts["true"]
                - (int(positives.max()) if len(positives) else 0),
                "negative_outside_largest_group": counts["false"]
                - (int(negative_groups.max()) if len(negative_groups) else 0),
            }
        )
        if intent["kind"] != "adjacency":
            continue
        singles = []
        for concept in intent["classes"]:
            matches = [
                i["intent_id"]
                for i in queries["intents"]
                if i["kind"] == "single" and i["classes"] == [concept]
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Require one canonical single intent per control class"
                )
            singles.append(decisions[matches[0]])
        both = (singles[0] == "true") & (singles[1] == "true")
        missing_class = (singles[0] == "false") | (singles[1] == "false")
        uncertain_presence = ~both & ~missing_class
        controls[intent["intent_id"]] = decisions.index[both].tolist()
        control_states = states[both]
        positive_groups = groups[both & (states == "true")].value_counts()
        false_groups = groups[both & (states == "false")].value_counts()
        relations.append(
            {
                "intent_id": intent["intent_id"],
                "family_id": intent["family_id"],
                "both_present": int(both.sum()),
                "missing_class": int(missing_class.sum()),
                "unknown_presence": int(uncertain_presence.sum()),
                **{
                    s: int((control_states == s).sum())
                    for s in ("true", "false", "unknown")
                },
                "judged_fraction": float((control_states != "unknown").mean())
                if len(control_states)
                else None,
                "spatial_groups": groups[both].nunique(),
                "true_outside_largest_group": int((control_states == "true").sum())
                - (int(positive_groups.max()) if len(positive_groups) else 0),
                "false_outside_largest_group": int((control_states == "false").sum())
                - (int(false_groups.max()) if len(false_groups) else 0),
            }
        )
    intent_table = pd.DataFrame(rows).set_index("intent_id")
    family_table = intent_table.groupby("family_id", sort=False)[
        ["true", "false", "unknown"]
    ].sum()
    family_table["patch_intent_count"] = family_table.sum(axis=1)
    family_table["judged_fraction"] = (
        1 - family_table.unknown / family_table.patch_intent_count
    )
    family_table["unique_images"] = len(decisions)
    return (
        intent_table,
        family_table,
        pd.DataFrame(relations).set_index("intent_id"),
        controls,
    )


def reference_unknown_sources(labels: np.ma.MaskedArray | None, rules: dict) -> dict:
    """Count disjoint native-pixel causes of missing reference evidence.

    Parameters
    ----------
    labels : numpy.ma.MaskedArray or None
        Native integer H x W map with its source mask; None means no map.
    rules : dict
        Validated known and configured unknown raw CLC codes.

    Returns
    -------
    dict
        missing_map flag and mutually exclusive masked_nodata_pixels,
        configured_unknown_pixels, unexpected_code_pixels counts. For a missing
        map pixel counts are None, not invented zeros. These are pixel counts,
        not intent-decision counts: unknown area can leave an intent decidable.

    Raises
    ------
    ValueError
        A present reference is empty, noninteger or not two-dimensional.
    """
    if labels is None:
        return {
            "missing_map": True,
            "masked_nodata_pixels": None,
            "configured_unknown_pixels": None,
            "unexpected_code_pixels": None,
        }
    labels = np.ma.asarray(labels)
    if labels.ndim != 2 or labels.size == 0 or labels.dtype.kind not in "iu":
        raise ValueError("Require a native integer reference map")
    mask = np.ma.getmaskarray(labels)
    known = np.isin(labels.data, rules["known_clc_codes"])
    configured = np.isin(labels.data, rules["unknown_codes"])
    return {
        "missing_map": False,
        "masked_nodata_pixels": int(mask.sum()),
        "configured_unknown_pixels": int((configured & ~mask).sum()),
        "unexpected_code_pixels": int((~known & ~configured & ~mask).sum()),
    }


def freeze_blockers(
    main: pd.DataFrame,
    relations: pd.DataFrame,
    policy: dict,
    missing_selected_count: int,
    queries: dict,
) -> list[str]:
    """Apply predeclared reference/spatial feasibility gates without model scores.

    Parameters
    ----------
    main, relations : pandas.DataFrame
        TEST-split coverage tables from coverage_tables; empty before verified test.
    policy : dict
        Versioned minimum-count, judged-fraction and group-removal criteria.
    missing_selected_count : int
        Number of planned acquisition IDs lacking complete verified inputs.
    queries : dict
        Fixed query specification; every declared intent/control must be reported.

    Returns
    -------
    list of str
        Explicit blockers. Empty only if every fixed intent/control passes.
        These are feasibility criteria, not statistical-power guarantees.
    """
    blockers = []
    if missing_selected_count:
        blockers.append(
            f"{missing_selected_count} selected patches lack verified RGB/map access"
        )
    if main.empty:
        return blockers + ["No verified spatially held-out test candidate collection"]
    expected_intents = {i["intent_id"] for i in queries["intents"]}
    expected_controls = {
        i["intent_id"] for i in queries["intents"] if i["kind"] == "adjacency"
    }
    if set(main.index) != expected_intents or set(relations.index) != expected_controls:
        blockers.append(
            "Coverage does not include every fixed intent and relation control"
        )
    for intent_id, row in main.iterrows():
        checks = {
            "candidate count": (
                row[["true", "false", "unknown"]].sum(),
                policy["main_min_candidates"],
            ),
            "positives": (row["true"], policy["main_min_positive"]),
            "negatives": (row["false"], policy["main_min_negative"]),
            "positive dispersion": (
                row.positive_outside_largest_group,
                policy["main_min_positive_outside_largest_group"],
            ),
            "spatial groups": (row.spatial_groups, policy["main_min_groups"]),
            "judged fraction": (
                row.judged_fraction,
                policy["main_required_judged_fraction"],
            ),
        }
        for name, (value, minimum) in checks.items():
            if value < minimum:
                blockers.append(f"{intent_id}: {name} {value} < {minimum}")
    for intent_id, row in relations.iterrows():
        checks = {
            "relation true": (row["true"], policy["control_min_true"]),
            "relation false": (row["false"], policy["control_min_false"]),
            "true dispersion": (
                row.true_outside_largest_group,
                policy["control_min_true_outside_largest_group"],
            ),
            "false dispersion": (
                row.false_outside_largest_group,
                policy["control_min_false_outside_largest_group"],
            ),
            "control groups": (row.spatial_groups, policy["control_min_groups"]),
            "control judged fraction": (
                row.judged_fraction,
                policy["control_required_judged_fraction"],
            ),
        }
        for name, (value, minimum) in checks.items():
            if pd.isna(value) or value < minimum:
                blockers.append(
                    f"{intent_id}: {name} {value} below requirement {minimum}"
                )
    return blockers


def write_benchmark_record(path: Path, record: dict) -> None:
    """Save a lightweight versioned record with a canonical content digest.

    Parameters
    ----------
    path : Path
        Explicit destination. Existing different records are not overwritten.
    record : dict
        JSON-serializable record; includes status, blockers, inputs_sha256 and
        specifications. A blocked candidate is expressly not a benchmark freeze.

    Raises
    ------
    ValueError
        An existing version has different content; create a new version instead.
    """
    payload = {k: v for k, v in record.items() if k != "content_sha256"}
    payload["content_sha256"] = _record_digest(payload)
    content = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if path.exists() and json.loads(path.read_text()) != payload:
        raise ValueError("Existing benchmark version changed; choose a new version")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _record_digest(record: dict) -> str:
    payload = {k: v for k, v in record.items() if k != "content_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def load_benchmark_record(path: Path, root: Path, require_frozen: bool = True) -> dict:
    """Verify recorded specifications and reject blocked candidates for evaluation.

    Parameters
    ----------
    path : Path
        Versioned JSON with status, content digest and repository-relative inputs.
    root : Path
        Repository root; input digests must match actual file bytes.
    require_frozen : bool
        Default True refuses blocked/non-frozen records; False permits inspection.

    Returns
    -------
    dict
        Integrity-verified benchmark record, without implicit compatibility repair.

    Raises
    ------
    ValueError
        Changed record/inputs, unsafe input paths, or incomplete/non-frozen status.
    """
    record = json.loads(path.read_text())
    if record["content_sha256"] != _record_digest(record):
        raise ValueError("Benchmark record content digest changed")
    for name, expected in record["inputs_sha256"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe benchmark input path")
        if file_digest(root / relative) != expected:
            raise ValueError(f"Changed benchmark input: {name}")
    if require_frozen and (record["status"] != "frozen" or record["blockers"]):
        raise ValueError(
            "Benchmark is blocked, not frozen; final evaluation is prohibited"
        )
    if require_frozen:
        main = record.get("main_candidates", {})
        if not main.get("test") or record.get("unassigned_selection"):
            raise ValueError("Incomplete verified test inventory; cannot accept freeze")
        development = main.get("development", [])
        test = main["test"]
        if set(development) & set(test) or not set(
            record["previous_development_ids"]
        ).issubset(development):
            raise ValueError("Development/test identity leakage in freeze")
        spatial = pd.DataFrame(record["spatial_inventory"]).set_index("patch_id")
        if (
            set(spatial.index) != set(development + test)
            or not spatial.index.is_unique
            or spatial.groupby("group_id").split.nunique().gt(1).any()
            or set(spatial.index[spatial.split == "test"]) != set(test)
        ):
            raise ValueError("Spatial group/split mismatch in freeze")
        matrix = record["relevance"]
        decisions = pd.DataFrame(
            matrix["states"], index=matrix["patch_ids"], columns=matrix["intent_ids"]
        )
        if not decisions.index.is_unique or set(decisions.index) != set(spatial.index):
            raise ValueError("Relevance/candidate identity mismatch in freeze")
        queries = json.loads((root / "config/query-specification-v1.json").read_text())
        design = json.loads((root / "config/benchmark-design-v1.json").read_text())
        selected = decisions.loc[test]
        intent, _, relations, controls = coverage_tables(
            selected, queries, spatial.loc[test, "group_id"]
        )
        if controls != record["relation_controls"]["test"]:
            raise ValueError(
                "Frozen relation controls differ from true presence evidence"
            )
        if freeze_blockers(intent, relations, design["coverage"], 0, queries):
            raise ValueError("Frozen test coverage does not pass the declared gates")
    return record
