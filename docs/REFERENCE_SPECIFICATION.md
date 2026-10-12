# Provisional reference rules and query specification

Versions: `reference-rules-v1`, `query-specification-v1`; evaluated on the unchanged
`data-pilot-v1 / archive-prefix-v1`. These are development specifications, not a
final benchmark freeze. No model or text-answer-derived relevance is involved.

## Source semantics and concept mapping

The [official BigEarthNet v2 description, Table 1](https://bigearth.net/static/documents/Description_BigEarthNet_v2.pdf)
identifies the original map values as CLC level-3 IDs. Its SHA-256 is recorded in
[the rules](../config/reference-rules-v1.json), matching the data pilot manifest.
The complete documented source-code vocabulary is explicitly enumerated so
known non-target cover is distinguished from unrecognized/unknown information.
Our target mapping is deliberately narrower than all agriculture or seminatural
cover and does not silently apply the recommended 19-class conversion.

| Concept | Raw CLC codes | Included meaning |
|---|---|---|
| forest | 311, 312, 313 | Broad-leaved, coniferous and mixed forest |
| inland_water | 511, 512 | Water courses and bodies; excludes marine water |
| arable_land | 211, 212, 213 | Non-irrigated, irrigated arable land and rice fields |
| pasture | 231 | Pastures |

These mappings are disjoint. Woodland/shrub 324, heterogeneous agriculture
242/243 and other documented classes remain known other cover. Code 999 is
unlabeled; actual pilot NoData is 0. Declared raster masks, configured unknown
codes and unexpected raw IDs provide unknown area. Unexpected codes are also
reported explicitly. Missing maps return unknown states and absent numeric
evidence (`None`), never invented zero area or absence.

## Area, denominators and provisional presence

For a native north-up projected metre grid with pixel width `dx` and height `dy`,
each cell covers `dx * dy` projected m². No geodesic area correction or
resampling occurs. Geographic degrees, nonmetre
projected units, rotated/skewed grids and reversed orientation are rejected.

Let $A$ be full patch area, $A_c$ known mapped area of concept $c$, and $U$ unknown
area. The evidence interval is

$$a_c^- = A_c / A, \qquad a_c^+ = (A_c+U)/A.$$

Unknown cells stay in the denominator. Each class has an independent upper bound;
those bounds need not sum to one. Presence is **true** when $a_c^-\ge t_c$,
**false** when $a_c^+<t_c$, **unknown** otherwise. Thus partial maps can resolve a
condition when evidence suffices, without assuming missing cells are negative.
A false decision means failure of the minimum fraction, not necessarily absence
of every pixel of the class.

All four provisional thresholds are $t_c=0.05$. This avoids interpreting tiny
mapped islands as sufficient cover, but ten related patches cannot validate the
choice. On this 1,440,000-m² pilot, the threshold is 72,000 m². Broader development
coverage and map plausibility checks must precede final threshold selection.
Neither thresholds nor query wording were selected from model results.

## Adjacency in metres and three-state relevance

Only horizontal/vertical native-cell neighbors count. Their shared edge lengths
are `dy` for left/right neighbors and `dx` for above/below neighbors. Count every
undirected edge once; ignore external patch edges and diagonal corner contact.
Sum known forest/water or arable/pasture contacts into $L^-$. No single connected
region or single uninterrupted boundary is required: the rule uses total contact
between the two class masks.

A conservative upper bound $L^+$ adds edges touching an unknown cell when the
other cell is the target class A, B, or also unknown. Unknown-to-known-other edges
cannot become A/B contact. Upper bounds may overcount incompatible assignments
of the same unknown cell, making them conservative rather than exact maxima.
They are evidence bounds, not statistical confidence intervals or probabilities.

Boundary state is true for $L^-\ge L_0$, false for $L^+<L_0$, unknown otherwise.
The **provisional $L_0=60$ m** is six native 10-m edges. It is an illustrative
minimum positive contact, not an empirically optimized robustness threshold.
A relation intent also requires **both** presence conditions. Logical AND returns
false if any necessary condition is false; true if all are true; unknown otherwise.
Known failure can therefore resolve a conjunction even when another condition is
unknown. Thresholds are inclusive; units and native edge orientation matter.

The [BigEarthNet.txt paper, §3.1](https://arxiv.org/html/2603.29630v2#S3.SS1)
describes extracting pairwise adjacency from maps but does not identify this
four-neighbor definition or a 60-m contact minimum. The reviewed official text
card documents loading, not an equivalent contact algorithm. Original-generation
equivalence is therefore **unconfirmed**: this is our own derived reference
rule. “Adjacent”, “sharing a boundary” and “bordering” share the same declared
condition; “near” would require a different distance definition and is excluded.

## Stable intents, paraphrases and direct families

[The query specification](../config/query-specification-v1.json) contains eight
intents, each with three English paraphrases. Singles, conjunctions and adjacency
have explicit class conditions and reference version. Numeric thresholds apply
to every paraphrase of the intent; the prose does not silently introduce different
quantities, distances or direction. Text answers/captions are never used to infer
absence or replace maps. Semantic equivalence was manually checked in Review 1;
structural validation alone cannot prove paraphrase equivalence.

Each intent belongs to exactly one predeclared direct family:

- `forest-water`: forest single, inland-water single, their conjunction and adjacency.
- `arable-pasture`: arable-land single, pasture single, their conjunction and adjacency.

This preserves direct dependence for later paired resampling; it does not remove
all correlations between families or nearby patches. No bootstrap is implemented.
The 24 formulations represent eight intent conditions, not 24 independent cases.

## Observed pilot coverage

All ten actual maps have zero unknown area/unexpected codes under this vocabulary.
Masks, affine transforms, metre units and reference/image alignment were checked.

| Intent | True | False | Unknown |
|---|---:|---:|---:|
| single-forest | 10 | 0 | 0 |
| single-inland-water | 6 | 4 | 0 |
| single-arable-land | 3 | 7 | 0 |
| single-pasture | 5 | 5 | 0 |
| both-forest-water | 6 | 4 | 0 |
| adjacent-forest-water | 6 | 4 | 0 |
| both-arable-pasture | 2 | 8 | 0 |
| adjacent-arable-pasture | 2 | 8 | 0 |

There is no forest-negative and **no both-present/nonadjacent case** for either
pair. The relation conditions do not distinguish the positive conjunction set
on this pilot. This is a coverage limitation, not evidence of model ability or
adequate final benchmark coverage. Thresholds were not adjusted to create cases.
The one Austria tile retains the provider's `test` split, but has been inspected
for development here; it is not an untouched project final test set.

Three fixed examples (pilot positions 1–3) were visually inspected in
[Benchmark Construction](../notebooks/02_benchmark_construction.ipynb). Patch
27_55 illustrates why mapped/visually plausible water can still fail our minimum
fraction: about 4.24% water, despite 1,130 m of mapped forest/water contact.
Patch 27_56 passes at about 9.83% water and 3,330 m contact. Broad field/woodland
and river placement are plausible in RGB; precise class labels, percentages and
fine boundaries are not independently verified visually. The fixed RGB scale is
raw DN/3000; derived-mask colors are display only and no raster is interpolated.
A map stored at 10 m retains the accuracy limitations of its CORINE source.

The notebook saves decisions, coverage, input/output digests and the figure under
ignored `outputs/`. Artifacts are labeled provisional and preserve patch/intent
ordering. Regenerate them by executing the notebook from a fresh kernel; no
cross-notebook variables or machine-specific public paths are needed.

## Review 1: separate final-diff audit

On 2026-10-12, reviewed the changed reference module, JSON specifications,
controlled tests, real integration results, notebook outputs and scientific
claims as a separate pass. Scope: exact image/map identity, native alignment,
source-code mapping, area denominators/units, shared-edge counting, unknown
states, paraphrase/family semantics and model-reference independence.

- Identity/alignment uses the existing checksum-verified acquisition and native
  raster checks; metre/native-area requirements are explicit. No text answer,
  caption or model ranking influences a reference calculation.
- Manually checked disjoint source mappings, all 24 formulations, one direct
  family per intent, inclusive thresholds, rectangular edge orientation,
  zero diagonal contact, full-area denominators and conservative unknown bounds.
- Found an API provenance gap: evidence dictionaries did not carry their rules
  version, so a caller could combine evidence with another query reference
  version. Fixed by recording the version in every summary and rejecting
  mismatched evidence/query versions; added a targeted regression test.
- Clarified projected rather than geodesic area, conservative unattainable contact
  upper bounds, and display-only concept colors. Corrected crowded figure ticks
  and a duplicated docstring fragment. No consequential finding remains open.
- Remaining scientific limits are provisional 5%/60-m choices, unconfirmed
  original adjacency equivalence, coarse reference accuracy, one-tile sampling,
  two families and missing forest-negative/both-present-nonadjacent coverage.
  These need broader development evidence, not reinterpretation as final results.
