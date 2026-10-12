"""Derive three-state map references independently of text answers or model scores.

Native projected metre grids are required. Unknown pixels bound possible area
and contact rather than being silently excluded from denominators or set false.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.crs import CRS

from earth_observation.data import acquire_rasters, load_pilot
from earth_observation.raster import inspect_patch, patch_files


def load_specifications(rules_path: Path, queries_path: Path) -> tuple[dict, dict]:
    """Load and validate versioned map rules and query conditions.

    Parameters
    ----------
    rules_path, queries_path : Path
        JSON specifications with integer CLC codes, fractions in (0, 1],
        positive boundary metres, unique intent IDs and direct family IDs.

    Returns
    -------
    tuple of dict
        Validated rules and queries, preserving their declared ordering.

    Raises
    ------
    ValueError
        Ambiguous mappings, inconsistent versions, malformed conditions,
        unsupported neighborhood or invalid numeric thresholds/identities.
    """
    rules = json.loads(rules_path.read_text())
    queries = json.loads(queries_path.read_text())
    if queries["reference_version"] != rules["version"]:
        raise ValueError("Query/reference versions differ")
    known = rules["known_clc_codes"]
    unknown = rules["unknown_codes"]
    if (
        not known
        or len(set(known)) != len(known)
        or not all(type(c) is int for c in known + unknown)
        or set(known) & set(unknown)
    ):
        raise ValueError("Invalid known/unknown source codes")
    assigned = set()
    for specification in rules["classes"].values():
        codes = specification["codes"]
        threshold = specification["presence_fraction"]
        if (
            not codes
            or len(set(codes)) != len(codes)
            or not all(type(c) is int for c in codes)
            or not set(codes).issubset(known)
            or assigned & set(codes)
        ):
            raise ValueError("Class mappings must be disjoint known CLC codes")
        if (
            type(threshold) not in (float, int)
            or not np.isfinite(threshold)
            or not 0 < threshold <= 1
        ):
            raise ValueError("Presence fractions must be in (0, 1]")
        assigned.update(codes)
    boundary = rules["adjacency"]["min_shared_boundary_m"]
    if (
        rules["adjacency"]["neighborhood"] != 4
        or type(boundary) not in (float, int)
        or not np.isfinite(boundary)
        or boundary <= 0
    ):
        raise ValueError("Require four-neighbor contact and positive boundary metres")
    seen = set()
    for intent in queries["intents"]:
        intent_id = intent["intent_id"]
        family = intent["family_id"]
        classes = intent["classes"]
        kind = intent["kind"]
        expected_count = 1 if kind == "single" else 2
        if (
            not isinstance(intent_id, str)
            or not intent_id
            or intent_id in seen
            or family not in queries["families"]
            or kind not in {"single", "conjunction", "adjacency"}
            or len(classes) != expected_count
            or len(set(classes)) != len(classes)
            or not set(classes).issubset(rules["classes"])
        ):
            raise ValueError("Invalid intent identity, family or reference condition")
        paraphrases = intent["paraphrases"]
        if (
            len(paraphrases) < 2
            or len(set(paraphrases)) != len(paraphrases)
            or not all(isinstance(p, str) and p.strip() for p in paraphrases)
        ):
            raise ValueError("Require distinct nonempty paraphrases")
        seen.add(intent_id)
    if not seen:
        raise ValueError("At least one intent is required")
    return rules, queries


def conjunction(states: list[str]) -> str:
    """Combine map decisions using three-valued logical AND.

    Parameters
    ----------
    states : list of str
        Nonempty sequence containing only true, false, or unknown.

    Returns
    -------
    str
        False if any necessary condition is false; true if all are true;
        unknown otherwise. Missing evidence alone never becomes false.

    Raises
    ------
    ValueError
        An empty or invalid state sequence is supplied.
    """
    if not states or not set(states).issubset({"true", "false", "unknown"}):
        raise ValueError("Expected nonempty three-state conditions")
    if "false" in states:
        return "false"
    return "unknown" if "unknown" in states else "true"


def summarize_reference(
    labels: np.ma.MaskedArray | np.ndarray | None,
    transform: Affine,
    crs: CRS,
    rules: dict,
    pairs: list[tuple[str, str]],
) -> dict:
    """Compute native-cell class areas and shared-boundary evidence intervals.

    Parameters
    ----------
    labels : array or None
        Nonempty H x W integer CLC raster. Masked pixels, configured unknown
        codes and unrecognized IDs are unknown. None means a missing map.
    transform : affine.Affine
        Native north-up, unrotated transform. No resampling is performed.
    crs : rasterio.crs.CRS
        Projected CRS whose linear unit conversion factor is one metre.
    rules : dict
        Validated versioned rules from load_specifications.
    pairs : list of tuple
        Distinct class pairs; unordered keys are sorted in the result.

    Returns
    -------
    dict
        Full native projected patch area and unknown area in m² (no geodesic
        correction); per-class area/fraction lower
        and upper bounds with presence state; per-pair boundary lower/upper
        metres and boundary state. Denominator includes ALL native cells.
        Unknown pixels may belong to any requested class. Also returns per-class
        H x W Boolean masks and an unknown mask for
        display reuse without reimplementing aggregation. Boundary upper
        bounds sum potentially compatible unknown edges and may be loose,
        because assignments need not be jointly achievable. Missing maps have
        None numeric evidence and unknown decisions, not zero measurements.

    Raises
    ------
    ValueError
        Nonmetric/rotated/non-north-up grids, noninteger/empty arrays, invalid
        pairs, or overlapping class masks. Cells outside the patch do not
        contribute boundaries. Diagonal contact contributes zero metres.
    """
    if (
        not crs.is_projected
        or crs.linear_units_factor[1] != 1
        or transform.b != 0
        or transform.d != 0
        or not np.isfinite(tuple(transform)).all()
        or transform.a <= 0
        or transform.e >= 0
    ):
        raise ValueError("Reference calculations require a north-up metre grid")
    unique_pairs = set()
    for a, b in pairs:
        if (
            a == b
            or a not in rules["classes"]
            or b not in rules["classes"]
            or set(rules["classes"][a]["codes"]) & set(rules["classes"][b]["codes"])
        ):
            raise ValueError("Adjacency needs distinct disjoint mapped classes")
        unique_pairs.add(tuple(sorted((a, b))))
    if labels is None:
        return {
            "reference_version": rules["version"],
            "total_area_m2": None,
            "unknown_area_m2": None,
            "unexpected_codes": [],
            "class_masks": None,
            "unknown_mask": None,
            "classes": {
                name: {
                    "area_lower_m2": None,
                    "area_upper_m2": None,
                    "fraction_lower": None,
                    "fraction_upper": None,
                    "state": "unknown",
                }
                for name in rules["classes"]
            },
            "pairs": {
                pair: {
                    "boundary_lower_m": None,
                    "boundary_upper_m": None,
                    "state": "unknown",
                }
                for pair in sorted(unique_pairs)
            },
        }
    data = np.ma.asarray(labels)
    if data.ndim != 2 or data.size == 0 or data.dtype.kind not in "iu":
        raise ValueError("Expected a nonempty two-dimensional integer reference map")
    values = data.data
    invalid = np.ma.getmaskarray(data) | ~np.isin(values, rules["known_clc_codes"])
    unexpected = sorted(
        set(np.unique(values[~np.ma.getmaskarray(data)]).tolist())
        - set(rules["known_clc_codes"])
        - set(rules["unknown_codes"])
    )
    pixel_area = transform.a * -transform.e
    total_area = data.size * pixel_area
    unknown_area = np.count_nonzero(invalid) * pixel_area
    masks = {
        name: np.isin(values, definition["codes"]) & ~invalid
        for name, definition in rules["classes"].items()
    }
    classes = {}
    for name, mask in masks.items():
        lower = np.count_nonzero(mask) * pixel_area
        upper = lower + unknown_area
        threshold = rules["classes"][name]["presence_fraction"]
        state = (
            "true"
            if lower / total_area >= threshold
            else "false"
            if upper / total_area < threshold
            else "unknown"
        )
        classes[name] = {
            "area_lower_m2": lower,
            "area_upper_m2": upper,
            "fraction_lower": lower / total_area,
            "fraction_upper": upper / total_area,
            "state": state,
        }
    boundaries = {}
    for a, b in sorted(unique_pairs):
        lower = upper = 0.0
        for first, second, edge_length in [
            (
                (slice(None), slice(None, -1)),
                (slice(None), slice(1, None)),
                -transform.e,
            ),
            (
                (slice(None, -1), slice(None)),
                (slice(1, None), slice(None)),
                transform.a,
            ),
        ]:
            a1, a2 = masks[a][first], masks[a][second]
            b1, b2 = masks[b][first], masks[b][second]
            u1, u2 = invalid[first], invalid[second]
            observed = (a1 & b2) | (b1 & a2)
            possible = (u1 & (u2 | a2 | b2)) | (u2 & (a1 | b1))
            lower += np.count_nonzero(observed) * edge_length
            upper += np.count_nonzero(observed | possible) * edge_length
        threshold = rules["adjacency"]["min_shared_boundary_m"]
        state = (
            "true"
            if lower >= threshold
            else "false"
            if upper < threshold
            else "unknown"
        )
        boundaries[(a, b)] = {
            "boundary_lower_m": lower,
            "boundary_upper_m": upper,
            "state": state,
        }
    return {
        "reference_version": rules["version"],
        "total_area_m2": total_area,
        "unknown_area_m2": unknown_area,
        "unexpected_codes": unexpected,
        "class_masks": masks,
        "unknown_mask": invalid,
        "classes": classes,
        "pairs": boundaries,
    }


def evaluate_intents(summary: dict, queries: dict) -> dict[str, str]:
    """Evaluate each declared intent once, independent of its paraphrases.

    Parameters
    ----------
    summary : dict
        Class and pair evidence returned by summarize_reference.
    queries : dict
        Validated query specification; each intent has one direct family.

    Returns
    -------
    dict of str to str
        Intent ID to true/false/unknown reference decision in declared order.
        Adjacency requires BOTH presences and sufficient shared boundary.

    Raises
    ------
    ValueError
        The evidence version differs from the query's declared reference version.
    """
    if summary["reference_version"] != queries["reference_version"]:
        raise ValueError("Reference evidence/query versions differ")
    results = {}
    for intent in queries["intents"]:
        states = [summary["classes"][c]["state"] for c in intent["classes"]]
        if intent["kind"] == "adjacency":
            states.append(summary["pairs"][tuple(sorted(intent["classes"]))]["state"])
        results[intent["intent_id"]] = conjunction(states)
    return results


def evaluate_pilot(
    manifest_path: Path, cache: Path, raw_root: Path, rules: dict, queries: dict
) -> tuple[dict, pd.DataFrame]:
    """Evaluate checksum-verified native maps for the existing identified pilot.

    Parameters
    ----------
    manifest_path, cache, raw_root : Path
        Existing source manifest, cache, and extracted local data roots.
    rules, queries : dict
        Validated versioned specifications. Text answers are not used.

    Returns
    -------
    tuple
        Patch-keyed evidence summaries and patch × intent three-state table,
        preserving manifest patch order and declared intent order.

    Raises
    ------
    ValueError
        Source identity, version or spatial contracts fail. Missing source files
        are acquired only by the existing bounded acquisition implementation.
    """
    patches, _ = load_pilot(manifest_path, cache)
    acquire_rasters(manifest_path, cache, raw_root)
    pairs = [
        tuple(i["classes"]) for i in queries["intents"] if i["kind"] == "adjacency"
    ]
    summaries = {}
    decisions = {}
    for patch in patches:
        patch_id = patch["patch_id"]
        files = patch_files(
            patch_id, raw_root / "BigEarthNet-S2", raw_root / "Reference_Maps"
        )
        if inspect_patch(files)["status"] != "aligned":
            raise ValueError("Complete spatially verified pilot required")
        with rasterio.open(files["reference"]) as raster:
            summaries[patch_id] = summarize_reference(
                raster.read(1, masked=True), raster.transform, raster.crs, rules, pairs
            )
        decisions[patch_id] = evaluate_intents(summaries[patch_id], queries)
    table = pd.DataFrame.from_dict(decisions, orient="index")
    table.index.name = "patch_id"
    return summaries, table
