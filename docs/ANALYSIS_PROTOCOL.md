# Frozen partial-reference analysis protocol

## 1. Authorized revision and scope

`benchmark-design-v3` and `analysis-protocol-v1` revise design v2 after the human
merge of PR #8. The reason is reference coverage, without final model results:
all main known-positive/negative/geographic minima pass, but seven intents have
unknown judgments and both-present controls have insufficient false cases.
Previous designs and candidates, including their source-code pins, are unchanged.

The estimand remains agreement with generalized CLC2018 maps, not independently
verified visible objects. All eight intents / 24 formulations, class mappings,
5% full-area presence, 60-m four-neighbor contact, selected IDs, native geometry,
spatial components, Development anchors and split seed remain fixed. Main
retrieval uses all 871 Test images for every formulation, including unknowns.
Labels, maps and captions never enter model input or ranking. Complete rankings
use descending cosine similarity then ascending full Unicode patch ID.
No new images, text requests, embeddings or final rankings accompany this freeze.

## 2. Reference completion space and outputs

For intent i, let K+ and K- be known positive and negative patch IDs, and U_i
its unknown IDs. Define Z_i = {0,1}^{|U_i|}: every binary labeling of unknown
relevance, with known states held fixed. This is a *marginal label-completion*
space, not a claim that every completion corresponds to a realizable CLC raster.
Unknown area/contact bounds can already be loose. No latent map is inferred.
The same patch's completion is shared across all formulations and both models
within an intent. Different intents can have logical dependencies (adjacency
implies conjunction); independent marginal completions need not satisfy them.
Consequently cross-intent aggregation below is explicitly a conservative outer
hull, not an assertion of jointly attainable physical-reference extrema.

Report N, known true/false/unknown counts and judged fraction
(|K+|+|K-|)/N for each intent, plus unknown IDs and the number of completions.
No candidate removal, judged-only ranking compression or unknown-to-false coding.
With no unknowns, report the exact value. With unknowns, report a
**reference-uncertainty interval**, including a collapsed interval if its ends
coincide; this does not mean the references have become fully known.
These bounds are not statistical confidence intervals.

The technical limit is **12 unknown IDs per intent**, at most 4,096 assignments.
Above this limit the affected main/control analysis is blocked, not sampled or
approximated. The main freeze requires every intent to be within the limit.
The present main counts are 0 for forest, 2 for arable, and 3 for each other
intent: 1, 4 and 8 completions respectively. Control counts are currently zero.

## 3. Exact marginal metric bounds, implemented later in WP5

Fix a complete ranking pi of N unique candidate IDs, independently of reference
completion. Write y_r(z) for completed binary relevance at rank r, and
R(z) = sum_{r=1}^N y_r(z). Never recompute or reorder the ranking for z.

For N >= 10, with a known-positive and b unknown IDs among the first ten:

\[
P@10(z)=\frac{1}{10}\sum_{r=1}^{10}y_r(z),\qquad
[L_{P},U_{P}]=[a/10,(a+b)/10].
\]

These endpoints are attained by appropriate top-ten assignments. Remaining
unknowns do not affect this metric. N < 10 makes P@10 undefined, not a changed
denominator; the unchanged main minimum N >= 20 rules this out here.

For R(z) > 0:

\[
AP(z)=\frac{1}{R(z)}\sum_{r=1}^{N}y_r(z)
       \frac{\sum_{s=1}^{r}y_s(z)}{r},\qquad
[L_{AP},U_{AP}]=[\min_{z\in Z_i}AP(z),\max_{z\in Z_i}AP(z)].
\]

WP5 must enumerate all permitted assignments with the assignment-dependent
positive denominator. All-unknown-zero/all-unknown-one are not assumed to
supply extrema. A hand-computed counterexample is the ranking [?, 0, 1, ?]:
assignments (0,0), (0,1), (1,0), (1,1) yield AP 1/3, 5/12, 5/6, 29/36.
The maximum is the mixed assignment (1,0).

If any permitted assignment has R=0, AP analysis for that intent is **blocked**;
report the possible-zero-positive reason, not zero or a silently skipped result.
P@10 may remain defined separately. Main freeze still requires at least ten
*known* positives, so every current completion has R>0. A diagnostic restricted
to R>0 would be a different, explicitly conditional analysis, not the main AP.
Missing formulations/metrics block their aggregate; no NaN skipping.

## 4. Formulation, intent and paired aggregation

For each model/intent and metric M, first compute
A_{mi}(z) = (1/3) sum_{p=1}^3 M_{mip}(z) under the **same** z for all three
formulations. Its exact marginal interval is min/max_z A_{mi}(z).
A mean of independently optimized formulation endpoints is only an outer bound,
and must not be reported as these exact within-intent extrema.
Report all formulations; formulation variation is max_p M(z)-min_p M(z)
under the same completion, with its own min/max over z when unknowns occur.
This variation describes wording sensitivity, not reference or sampling error.

For the descriptive overall mean, weight the eight intent means equally.
A guaranteed conservative reference envelope is
[(1/8) sum_i L_i, (1/8) sum_i U_i], also separately by single/conjunction/adjacency
block. It is exact over a Cartesian product of marginal label spaces, but may
be loose when cross-intent logical/reference constraints are imposed. Label it
**conservative aggregate reference envelope**, never a jointly attainable
physical-reference interval. Do not pool relation controls with main results.

For paired differences, at every completion compute
D_i(z) = A_{RemoteCLIP,i}(z)-A_{CLIP,i}(z), then take min/max_z D_i(z).
Both models and all paraphrases use identical unknown assignments and candidate
IDs. Subtracting independently optimized model endpoints only gives an outer
bound; it is not the exact paired interval. Descriptive aggregation of paired
intent bounds uses the same equal-intent conservative-envelope rule.
When fully judged these expressions reduce to paired exact values.

## 5. Exploratory relations and limited statistical inference

Both-present controls remain separate, reference-filtered additional analyses:
require both *known true* presence states, retain unknown relation states, and
report exclusions for false/unknown presence. They are never unfiltered retrieval.
Their old minimum targets remain visible but are no longer confirmatory freeze
gates. Current Test counts and dispersion are:

| Control | True / false / unknown | Groups | True / false outside largest group |
|---|---:|---:|---:|
| Forest-water | 35 / 2 / 0 | 35 | 33 / 1 |
| Arable-pasture | 59 / 7 / 0 | 48 | 53 / 6 |

Both fail the old ten-false target; forest-water also fails false dispersion five.
These controls cannot replace a confirmatory isolation of relation capability.
Unknown-limit/definedness contracts also apply to their eventual metrics, but
control analysis failure cannot be hidden or treated as a main retrieval result.

Primary presentation is paired per-intent results and descriptive equal-intent
aggregation. There are only **two direct families** (forest-water and
arable-pasture), not eight independent intent replicates or 24 independent
formulations. A family bootstrap is at most an optional restricted sensitivity
diagnostic, preserving each whole family, paraphrases and model pairing. The
previous seed/replicates/weighting remain documented for that diagnostic only.
With two families sampled twice with replacement, there are just three distinct
family multiplicity combinations; 10,000 draws do not create independent evidence.
Do not call its percentile range a robust confidence interval or use it as
proof of general model superiority. If calculated later with unknown references,
apply a shared completion within each paired resample and explicitly separate
completion envelopes from resampling variation; no hidden imputation or pooling.

Keep three distinct quantities: reference uncertainty from incomplete judgments;
variation between paraphrases on the fixed data; and statistical uncertainty
requiring independent sampling units/assumptions. No general geographic,
query-population or model-superiority inference is warranted by this design.

## 6. Freeze validation and human boundary

`manifests/benchmark-freeze-v1.json` pins its immutable v4 predecessor, both
historical/new specifications, canonical code, model specification and all native
source bytes. `load_frozen_benchmark` checks those pins, the explicit supported
protocol, unchanged foundational fields, complete candidate/control identities,
prior Development anchoring, native footprints and recomputed spatial components,
and native-map-derived three-state decisions. Main known-count/dispersion gates
remain unchanged; permitted unknowns additionally require bounded exact enumeration
and AP defined for every completion. Changing a status label cannot bypass this.
The inherited coverage tables record real evidence, not completed labels.

Only the specification/readiness validator is implemented here. Final bound
calculation, model comparisons and statistical procedures belong to WP5 after
the human merge of this valid freeze. No final model results are present.
Revalidate using existing local inputs:

```bash
uv run python scripts/freeze_benchmark.py
```
