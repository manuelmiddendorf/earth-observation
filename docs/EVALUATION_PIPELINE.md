# Evaluation pipeline under benchmark-design-v3

## Binding contracts and scope

This implementation follows the unchanged [frozen protocol](ANALYSIS_PROTOCOL.md).
Shared assignments across models and formulations are mandatory within an intent.
Across related intents the freeze explicitly defines marginal completion spaces
and conservative aggregate envelopes, not jointly attainable map completions.
No new joint physical-reference constraints are inferred or silently added.
The optional two-family bootstrap is a restricted sensitivity diagnostic; its
reference-envelope endpoints and resampling percentiles are distinct quantities.

One edge case in the frozen error taxonomy is underspecified: a composite can
be known false because one class is false while another class remains unknown.
Then neither `class-a-only`, `class-b-only` nor `neither` is identified, yet
`unknown-reference` would incorrectly describe its known relevance. Before
implementing the affected classification, the decision is to emit **no category**,
with explicit `unresolved-class-pattern` diagnostic status and the original
false relevance. This does not add a scientific error category or alter labels.
No such case occurs in any of the 2,013 frozen image/reference records. If one
occurs in a future reference version, its category needs an authorized taxonomy
clarification; main metric relevance remains valid. Missing requested ranks in
small exploratory controls likewise produce explicit unavailable-rank records.

WP5 implements evaluation from complete stored rankings to versioned results;
its executable integration accepts Development IDs only. It neither encodes nor
acquires data. Final Test model evaluation belongs to WP6 after human merge.

## Calculations and result schema

`retrieval.ranking_metrics(..., protocol=...)` extends the existing scalar API;
`completion_metrics` uses one canonical binary P@10/AP kernel for every allowed
assignment, in sorted unknown-ID order. The historical default remains only for
old pilot callers, with its explicitly separate judged-only diagnostics. V3 has
no judged-only fallback. Unknowns at unranked cutoff positions still contribute
to AP's denominator; a zero-positive possibility blocks the whole AP result.

`evaluation.evaluate_rankings` verifies complete integer ranks, exact candidate
sets, all formulations of both models, optional score/text identity, and canonical
three-state composite evidence. It aggregates score vectors under shared
assignments before taking extrema, also for wording ranges and paired differences.
`validate_benchmark_candidates` rejects split mixing and requires the entire
frozen pool for Test input. It is a pure membership guard; no final Test ranking
was constructed to exercise it. Cross-intent means explicitly retain conservative
reference-envelope labels. No independently optimized endpoints are represented
as jointly attainable paired/formulation bounds.

Results keep separate tables: `reference_coverage`, `formulations`, `intents`,
`paired_intents`, `quality_variation`, `top_k_jaccard`, `error_samples`, and
`descriptive_*`. Metric records use status/value/lower/upper/reason and
`uncertainty_type`; partial references never receive an imputed scalar value.
Over-limit/undefined inputs propagate into affected aggregates without dropping
intents or formulations. Jaccard concerns ranking stability only, including
available-k metadata for small controls. Error samples are the fixed p1 ranks
1/5/10; missing ranks are explicit and repeated image IDs remain visible.

Exploratory controls report false/unknown-presence exclusions and separate
three-state relevance counts, group counts/dispersion and complete metric tables.
They are never pooled with the main results. The optional family sensitivity
keeps model pairing, dependent intents and drawn-family multiplicities intact;
its estimator divides by the number of sampled **intents**, not families.
It exposes the three multiplicity configurations, plus distinct percentile
summaries of lower/upper conservative reference envelopes. Those percentiles
are explicitly restricted sensitivity, not confidence intervals.

## Reproduction from existing Development artifacts

```bash
uv run python scripts/evaluate_development.py
# Optional restricted sensitivity, never a superiority confidence interval:
uv run python scripts/evaluate_development.py --family-sensitivity
uv run pytest
uv run ruff check src tests scripts notebooks/03_retrieval_evaluation.ipynb
uv run ruff format --check src tests scripts notebooks/03_retrieval_evaluation.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/03_retrieval_evaluation.ipynb
```

The executable revalidates `benchmark-freeze-v1`, original run/ranking hashes,
checkpoint/preprocessing/query identities, native RGB hashes and both historical
embedding cache contents. Every stored image must be Development. Missing inputs
fail with no acquisition/encoding fallback. It reads the stored rankings directly
and joins the frozen relevance afterward. No complete Test rankings or embeddings
are created. Results under ignored `outputs/evaluation-development-v3` include
benchmark/design/protocol versions, model/checkpoint identities, source ranking
and cache digests, historical encoding hashes, current analysis hashes and actual
Python/NumPy/pandas versions. JSON contains no silently serialized NaN.

The existing ten-image integration has fully judged references. Descriptive mean
AP difference (RemoteCLIP minus CLIP) is −0.094003; P@10 difference is zero because
N=10. All top-ten Jaccards are one regardless of order. The controls contain six
and two true cases, no negatives, in one spatial group; their AP=1 cannot isolate
relations and P@10 is undefined. These are Development observations only.
Controlled cases and an independent Fraction-based brute-force oracle exercise
unknowns, variable denominators, mixed extrema, shared formulations/models,
collapsed intervals, undefined completions, cap violations and aggregation.

Canonical metric extension changes `retrieval.py`, which was pinned by historical
candidate v1/v2 and original embedding identities. Their bytes/manifests are
preserved, and current source-integrity loading correctly rejects their stale
metric pin. They can be replayed at their historical Git revision; historical
notebook-02 sections are not a current-source reproduction command. No source
hash is silently repinned and no duplicate metric implementation is introduced.
The current freeze and v3/v4 candidates do not pin this module; their inputs stay
valid. Historical embedding caches remain independently verified source evidence,
not newly generated identities or encodings.

## Review 2: separate targeted pass, 2026-10-13

Scope: changed metric/paired/diagnostic/artifact code and its scientific contracts;
no agents or full-repository review. Review followed controlled tests and the first
fresh notebook run, before any final Test model evaluation.

| Finding | Resolution and verification |
|---|---|
| Input labels could contradict canonical conjunction/presence implications | Reject inconsistent three-state composite evidence; regression test covers contradiction. Completion spaces themselves stay marginal, as frozen. |
| Executable integration accepted an externally supplied “validated” record | Removed that shortcut; it now invokes the full native freeze validator itself. Development-only membership and complete-Test-pool guard have controlled tests. |
| Resampling generator/multiplicity weighting were insufficiently observable | Validate PCG64 and integer draw parameters; expose all three multiplicity estimates. Independent unequal-family hand calculation verifies the mixed draw uses 1/3, not 1/2. |
| Old candidate/cache tests implicitly expected unchanged metric source | Retain immutable historical pins and test their explicit rejection; a temporary fixture isolates false-status readiness protection. Historical caches are read with their original identities and never re-encoded. |

The review also checked variable AP denominators/zero positives, stable completion
identity across formulations/models, cap propagation, complete pools/ties,
conservative versus exact bounds, three uncertainty types, control separation,
rank sampling, model provenance and leakage. The known-negative/uncertain-pattern
category ambiguity was documented before classification and has zero applicable
cases in the frozen inventory; it does not block the current benchmark.

Final verification results are recorded in the implementation plan and PR.
Subject to those checks and human merge, the pipeline is ready for WP6. Its first
final model evaluation remains a separate authorized stage, not executed here.
