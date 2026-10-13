# Completion review

The main experiment is complete: frozen CLIP/RemoteCLIP retrieval, map-based
reference bounds, wording diagnostics and the predefined qualitative sample.
The completion pass improves explanation and checks reproducibility without
changing the benchmark or rerunning inference.

## Added descriptive context

A uniform random permutation has expected P@10 equal to prevalence, R/N.
For AP, condition on a positive at rank r: the expected preceding positive
count is (r−1)(R−1)/(N−1). Summing its expected precision contribution gives

$$
\mathbb E[AP]=\frac{H_N}{N}
 +\frac{(R-1)(N-H_N)}{N(N-1)},\qquad
H_N=\sum_{r=1}^{N}\frac{1}{r}.
$$

This applies to distinct candidates, N ≥ 10 and R ≥ 1. Expected AP is not
exactly prevalence at finite N. Possible unknown labels give expectation bounds
via their possible total positive counts; those bounds are not sampling CIs.
The kernel is tested against exhaustive relevant-position sets for a small pool.

The [identified artifact](../results/final-evaluation-v1/random-reference.json)
uses only counts from the published final summary. It is **post-hoc descriptive
context**, not part of the frozen primary analysis and not a significance test.
Main intents and separate control populations remain separate.

- Main forest: random expected P@10 0.6303, CLIP 0.9667, RemoteCLIP 0.8333.
- Forest/water control: random expected P@10 0.9459, both models 1.0000.
- Arable/pasture control: random expected P@10 0.8939, CLIP 0.9667,
  RemoteCLIP 0.8000.

This context strengthens the caution about relation controls. High raw quality
in mostly positive pools does not isolate spatial reasoning. Above/below a
random expectation alone is not a statistical comparison.

## Findings addressed

| Finding | Resolution |
|---|---|
| Notebook 02 opened with an obsolete blocked status. | Lead with the current freeze and mark intermediate candidates as historical. |
| Fresh execution tried to validate historical candidates against current source. | Remove retired candidate executions from the notebook; preserve their history in the access documentation and fully validate the final expanded inventory and current freeze. |
| Three existing tests assumed retrieval.py was the first changed historical input. | Assert the actual first changed input; isolate readiness in a temporary fixture with current source hashes. Production manifests and loaders are unchanged. |
| README and notebooks repeated low-level details and handover language. | Keep the scientific argument in prose, put reproduction details in a dedicated document, and remove repeated panel caveats. |
| High exploratory control scores lacked an explicit random expectation. | Add the separate analytical reference above without altering primary results. |

## Verification

All four notebooks were executed with fresh kernels against real local artifacts:
6, 15, 18 and 10 code cells, respectively, with no error outputs. Representative
RGB/map panels from each data stage, the final quality figure and the water-error
panel were visually inspected for readability and agreement with the narrative.

The complete test suite, Ruff checks and format checks cover source, scripts,
tests and all notebooks. The first full run exposed the three historical-test
assumptions above; their targeted regressions subsequently passed. The final
full suite passed **132 tests with zero skips**; Ruff check and format passed
for source, tests, scripts and all four notebooks.

The earlier independent result check reconstructed all 32 intent/model metrics
from saved ranks and frozen relevance, with differences below 1e−12. The current
integration tests reconstruct all Test scores/ranks without inference.
All freeze-pinned and final-result-pinned inputs retain their original hashes.
No images, queries, reference rules, model configuration or primary results change.

## Remaining limits

The study measures agreement with generalized maps on a country-balanced subset,
not independently validated visual truth. Eight intents in two families cannot
support broad model-superiority inference. The controls have few negatives;
the fixed qualitative sample contains no both-present false relation. Possible
pretraining overlap is not resolved by the spatial Development/Test separation.

Reproduction needs local rasters, checkpoints and saved acquisition artifacts;
Git alone does not contain those bulk prerequisites. An optional demo or stronger
relation benchmark would be separate work. No required implementation remains
for this scoped study after human review and merge.
