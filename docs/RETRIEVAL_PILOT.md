# Frozen retrieval development pilot

Version `frozen-retrieval-pilot-v1`, executed 2026-10-12. This connects the
unchanged ten-patch data pilot to two frozen models, exact rankings and map
references. It is not a final benchmark or a relation-control experiment.

## Identified checkpoints and conditions of use

| Model | Official file | Bytes | Identity |
|---|---|---:|---|
| OpenAI CLIP | `ViT-B-32.pt` | 353,976,522 | SHA-256 `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af` |
| RemoteCLIP | `RemoteCLIP-ViT-B-32.pt` | 605,208,421 | SHA-256 `60014e395d930a3f2963d1d89c8522bf4ad56775571e4356e866864789af85c4` |

CLIP uses the [official OpenAI loader/checkpoint](https://github.com/openai/CLIP/blob/main/clip/clip.py):
the download URL includes its published digest. The official repository is MIT
licensed. RemoteCLIP comes from the authors'
[Hugging Face repository](https://huggingface.co/chendelong/RemoteCLIP/tree/bf1d8a3ccf2ddbf7c875705e46373bfe542bce38),
pinned at revision `bf1d8a3ccf2ddbf7c875705e46373bfe542bce38`; the digest and
size match its LFS metadata. The
[official RemoteCLIP code repository](https://github.com/ChenDelong1999/RemoteCLIP)
is Apache-2.0 licensed. Its weight repository has no separate model card/license
declaration; do not infer an independently stated weight license from the code.
The BigEarthNet subset's CDLA-Permissive-1.0 terms remain separate.

RemoteCLIP's [official retrieval setup](https://github.com/ChenDelong1999/RemoteCLIP/blob/a6a4787507e441f444c20404c90dd18520a8960d/retrieval.py#L49)
initializes `pretrained='openai'` before strictly loading RemoteCLIP weights.
Therefore both checkpoints use **QuickGELU**, rather than the ordinary GELU of
an unqualified OpenCLIP architecture. We instantiate this same ViT-B/32
architecture locally and load the selected state dictionary strictly, avoiding
an extra automatic checkpoint download. OpenAI's JIT archive is used only to
extract its state dictionary; the encoders run in OpenCLIP. Both visual towers
have 12 layers, 768 width, 32-pixel patches and 224-pixel image size; text has
12 layers, 512 width, 8 heads and context length 77. Output dimension is 512.
The observed missing-pretrained warning occurs before strict local weight
loading; it does not indicate that the subsequent encodings use random weights.

Only these two checkpoints were downloaded: 959,184,943 bytes total. Sizes were
checked before downloading, and SHA-256 and sizes verified before loading.
The canonical bounded asset loader reuses valid weight files, failing closed on
changed bytes. Weights remain ignored under `models/weights/`.

## Input conversion and checkpoint preprocessing

The model path reads **only** B04/B03/B02 rasters, in that order, on their shared
native grid. No reference map, caption, metadata feature or label enters encoding
or scoring. The unfiltered manifest determines candidates before model results.
Any masked/nonfinite RGB value raises an error, without imputation or silently
removing the patch; the actual thirty bands contain no masked pixels.

`model-rgb-v1` explicitly converts raw DN to RGB uint8:

$$x = \operatorname{round}_{\mathrm{even}}\left(255\,
\operatorname{clip}(DN/3000,0,1)\right).$$

This is a development radiometric choice, not a calibrated reflectance claim.
Its 3000-DN saturation is numerically the same as the display choice, but it is
an independently specified model conversion with integer quantization and a
strict NoData contract. It is not implicitly inherited from `load_rgb` or tuned
from these retrieval scores. Broader development validation precedes freeze.

Both checkpoint transforms use shortest-edge bicubic resize to 224, center crop
224 × 224, RGB conversion, float32 CHW tensor scaled by 1/255, and channel
normalization with mean `(0.48145466, 0.4578275, 0.40821073)` and standard deviation
`(0.26862954, 0.26130258, 0.27577711)`. The actual transform representation is
saved. Text uses OpenCLIP's CLIP `SimpleTokenizer`: byte-pair vocabulary,
BOS/EOS, vocabulary size 49,408, context 77. Sequences exceeding the context are
rejected, not truncated. The packaged vocabulary bytes are identified by SHA-256.

## Runtime, embeddings and reuse

Verified hardware: Apple M2 Pro, 32 GiB memory. Runtime: native arm64 CPython
3.12.12, CPU float32, four PyTorch threads, batch size five, seed zero,
deterministic PyTorch algorithms. No accelerator fallback is implemented.
The former local Intel Python was incompatible with current macOS PyTorch
wheels; a native Python environment was created while preserving the old local
environment. Reproduction requires a native supported interpreter.

Locked versions used: PyTorch 2.14.1, torchvision 0.29.1, OpenCLIP 3.3.0,
Pillow 12.3.0, NumPy 2.5.4, timm 1.0.30, ftfy 6.3.1, regex 2026.9.29,
rasterio 1.5.2. `uv.lock` records transitive versions. Models are in evaluation
mode, all parameters have gradients disabled, and inference uses
`torch.inference_mode()` without autocast or training.

Each model produces image embeddings `(10, 512)` and text embeddings `(24, 512)`.
Finite nonzero norms are required; stored arrays are normalized float32 with
unit-norm checks. Patch rows follow the original manifest. Query rows follow
intent and paraphrase order, with stable IDs `<intent_id>/p1`, `/p2`, `/p3`.

A content-addressed NPZ cache contains the exact JSON identity, arrays, byte
digests and measured original run metadata. Identity includes checkpoint,
architecture/activation, preprocessing and RGB versions/settings, tokenizer
bytes, relevant software, implementation digests, actual RGB file digests,
ordered patch IDs and ordered query IDs/texts. Reference labels are excluded.
Existing incompatible identities or corrupted arrays raise errors. Different
identities create distinct cache files; no stale artifact is silently reused.
A hit verifies stored arrays without loading a model or checkpoint into memory.

Measured one-run wall times (not repeated-run performance estimates):

| Model | Weight verification + load, s | 10 images, s | 24 texts, s | Total, s |
|---|---:|---:|---:|---:|
| CLIP | 1.6570 | 0.2046 | 0.9478 | 2.8094 |
| RemoteCLIP | 1.8004 | 0.1800 | 0.9608 | 2.9412 |

Downloads and software installation are excluded. Hash checking is included in
load time; raster reading/conversion is included in image time. The notebook
reports cache lookup and ranking times separately alongside these original
measurements. Both artifacts were reused with unchanged modification times and
identical result tables, without repeated inference.

## Exact rankings and metric contracts

Unit image/text vectors yield the complete cosine matrix by direct multiplication
(float64 scoring from normalized float32 embeddings). Scores are similarities,
not probabilities. Sort descending by score and, for exact ties, ascending full
Unicode patch ID. No top-k approximation, relevance filtering or candidate
reordering from map information occurs. Reference states attach afterward by
explicit patch/intent identities; missing or extra IDs fail validation.

For complete judgments, $r_j$ is binary relevance at rank $j$ and
$R=\sum_{j=1}^{N}r_j$:

$$P@10=\frac{\sum_{j=1}^{10}r_j}{10},\qquad
AP=\frac{1}{R}\sum_{j=1}^{N}r_j\frac{\sum_{\ell=1}^{j}r_\ell}{j}.$$

- P@10 is undefined (`NaN`) for fewer than ten candidates.
- AP is undefined with zero positives. P@10 is zero with at least ten fully
  judged negative candidates.
- Any unknown judgment makes both main metrics undefined under this conservative
  pilot policy. Counts of candidates/judged/unknown/known positives and judged
  fraction are always reported. Unknown never becomes false.
- Explicitly separate `judged_only_average_precision` and
  `judged_only_p_at_available` diagnostics remove unknowns from the fixed ranking.
  Their precision denominator is min(10, judged count); neither is a main metric
  on an unrestricted candidate set. No judged candidates yields undefined values.
- No candidate input is an invalid ranking contract. Duplicate IDs, mismatched
  reference IDs and invalid states fail explicitly.

## Observations and limits

There are 48 model/formulation results and 480 scored ranking rows. All ten
candidates are judged for every intent under the provisional rules. With ten
candidates, P@10 is reference prevalence and identical across models and
formulations of an intent. All forest candidates are positive, so forest AP = 1
also provides no discrimination. No intent average or bootstrap is calculated.

For the unchanged first formulations, arable-land AP is 0.8095 (CLIP) and 0.3417
(RemoteCLIP); inland-water AP is 0.6607 and 0.8179. These examples do not establish
an overall model advantage. The executed notebook reports all 24 formulations
separately and visually inspects top-three results for fixed arable-land and
forest/water adjacency formulations from both models.

Both models rank patch `28_56` first for that adjacency formulation. RGB shows
forest and a water strip, but the map's 4.5278% water is below the provisional
5% presence requirement despite 880 m shared boundary. The negative reference
reflects the operational definition; it does not prove a visual relation error.
Map agreement and visual truth remain distinct.

No pair has a both-present/nonadjacent candidate. Conjunction/adjacency reference
sets coincide, so AP differences between these query types cannot isolate spatial
relation understanding. One tile, ten neighboring patches and provisional rules
cannot establish generalization. Queries, thresholds and preprocessing were not
changed in response to the model scores. Next: reference coverage analysis and
benchmark freeze, including spatial separation and separate relation-control sets.

## Verification and reproduction

`python scripts/run_retrieval_pilot.py` acquires only missing bounded pilot assets
and these two weights, runs or reuses embeddings, and saves complete CSVs and run
provenance under ignored `outputs/frozen-retrieval-pilot-v1/`. On a cache miss,
network access is required. A valid cache hit does not download or encode weights.
The third notebook independently loads configurations/artifacts and checks a
second run's cache hits and exactly equal tables; it needs no preceding kernel.

53 tests passed, none skipped, including real input integration and both real
embedding cache integrations. Hand-computed tests cover cosine/normalization,
ID/order/ties, P@10/AP, zero positives, fewer than ten candidates, unknown states,
RGB quantization/NoData, cache changes and corruption. Ruff checks passed. The
retrieval notebook executed in a fresh kernel; the saved real top-result figure
was visually inspected. A focused self-check found no remaining consequential
implementation issue. No extra agents or full-repository review were used.
