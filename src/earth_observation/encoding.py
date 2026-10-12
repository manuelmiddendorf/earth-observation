"""Frozen ViT-B/32 encoding and content-identified local embedding artifacts.

Only RGB measurements, query text and model configuration enter this module.
Reference maps, captions and land-cover metadata are not model inputs.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from earth_observation.data import fetch_asset
from earth_observation.raster import RGB_BANDS, read_rgb_bands
from earth_observation.retrieval import normalize_embeddings, validate_ids

if TYPE_CHECKING:
    import torch
    from open_clip.tokenizer import SimpleTokenizer


def file_digest(path: Path) -> str:
    """Return the SHA-256 of file bytes, streamed in bounded memory.

    Parameters
    ----------
    path : Path
        Existing input, source or checkpoint file.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def model_rgb(values: np.ma.MaskedArray | np.ndarray, upper_dn: float) -> Image.Image:
    """Convert raw Sentinel-2 RGB explicitly to checkpoint-compatible RGB bytes.

    Parameters
    ----------
    values : array
        H x W x 3 raw DN values, ordered B04/B03/B02. NoData masks are retained
        until this boundary; no imputation or reference-based masking occurs.
    upper_dn : float
        Positive development saturation DN. Values clip to [0, upper_dn].

    Returns
    -------
    PIL.Image.Image
        RGB uint8 image: round-to-even(255 * clip(DN / upper_dn, 0, 1)).
        Spatial resizing and checkpoint normalization happen separately.

    Raises
    ------
    ValueError
        Nonfinite/masked pixels, invalid shape/dtype or invalid saturation.
        Patches with NoData are rejected rather than silently filtered out.
    """
    values = np.ma.asarray(values)
    if (
        values.ndim != 3
        or values.shape[-1] != 3
        or 0 in values.shape
        or values.dtype.kind not in "fiu"
        or np.ma.getmaskarray(values).any()
        or not np.isfinite(values.data).all()
        or not np.isfinite(upper_dn)
        or upper_dn <= 0
    ):
        raise ValueError("Require finite unmasked H x W x 3 RGB and positive DN scale")
    pixels = np.rint(255 * np.clip(values.data.astype(np.float64) / upper_dn, 0, 1))
    return Image.fromarray(pixels.astype(np.uint8))


def embedding_identity(
    model: dict,
    config: dict,
    patch_ids: list[str],
    image_files: list[dict[str, Path]],
    query_ids: list[str],
    texts: list[str],
) -> dict:
    """Identify all encoding dependencies and ordered inputs before cache lookup.

    Parameters
    ----------
    model, config : dict
        Checkpoint specification and explicit runtime/RGB/preprocessing settings.
    patch_ids, query_ids : list of str
        Unique IDs in encoding order.
    image_files : list of dict
        One exactly three-band path dictionary per patch; actual bytes hashed.
    texts : list of str
        Nonempty query texts in query ID order, without implicit coercion.

    Returns
    -------
    dict
        JSON-serializable cache identity including checkpoint, transforms,
        tokenizer asset, relevant versions and implementation source digests.
        No reference information is included. Machine paths are not included.

    Raises
    ------
    ValueError
        Counts, IDs, texts or band identities do not satisfy the contract.
    """
    validate_ids(patch_ids)
    validate_ids(query_ids)
    if len(patch_ids) != len(image_files) or len(query_ids) != len(texts):
        raise ValueError("Input rows do not match IDs")
    if any(type(t) is not str or not t.strip() for t in texts):
        raise ValueError("Require nonempty text strings")
    if any(set(files) != set(RGB_BANDS) for files in image_files):
        raise ValueError("Require exactly RGB files per patch")
    import open_clip

    tokenizer_file = Path(open_clip.__file__).parent / "bpe_simple_vocab_16e6.txt.gz"
    return {
        "schema": "embedding-cache-v1",
        "experiment_version": config["version"],
        "model": model,
        "architecture": config["architecture"],
        "embedding_dimension": config["embedding_dimension"],
        "activation": config["activation"],
        "runtime": config["runtime"],
        "rgb": config["rgb"],
        "preprocessing": config["preprocessing"],
        "tokenizer_sha256": file_digest(tokenizer_file),
        "software": {
            name: importlib.metadata.version(name)
            for name in (
                "torch",
                "torchvision",
                "open-clip-torch",
                "numpy",
                "pillow",
                "ftfy",
                "regex",
                "rasterio",
                "timm",
            )
        },
        "implementation": {
            name: file_digest(Path(__file__).with_name(name))
            for name in ("encoding.py", "raster.py", "retrieval.py")
        },
        "images": [
            {"patch_id": pid, "bands": {b: file_digest(files[b]) for b in RGB_BANDS}}
            for pid, files in zip(patch_ids, image_files, strict=True)
        ],
        "queries": [
            {"query_id": qid, "text": text}
            for qid, text in zip(query_ids, texts, strict=True)
        ],
    }


def identity_key(identity: dict) -> str:
    """Hash a JSON encoding identity using sorted keys and exact list order.

    Parameters
    ----------
    identity : dict
        JSON-serializable encoding identity.

    Returns
    -------
    str
        SHA-256 hex key for a content-addressed local cache path.
    """
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def cached_embeddings(
    path: Path,
    identity: dict,
    encode: Callable[[], tuple[np.ndarray, np.ndarray, dict]],
) -> tuple[np.ndarray, np.ndarray, dict, bool]:
    """Read a compatible artifact or encode once and atomically save it.

    Parameters
    ----------
    path : Path
        Local ignored NPZ artifact. An existing incompatible file fails closed.
    identity : dict
        Complete dependency/input identity with images/queries and dimension.
    encode : callable
        Invoked ONLY on a cache miss; returns image/text arrays and run metadata.

    Returns
    -------
    tuple
        Float32 unit image/text arrays in identity order, original measured
        run metadata and cache-hit flag. Cached arrays have byte digests.

    Raises
    ------
    ValueError
        Identity mismatch, corruption, wrong shapes/dtypes or invalid unit norms.
    """
    hit = path.is_file()
    if hit:
        with np.load(path, allow_pickle=False) as stored:
            metadata = json.loads(str(stored["metadata"]))
            images, texts = stored["images"], stored["texts"]
        if metadata["identity"] != identity:
            raise ValueError("Incompatible embedding cache identity")
    else:
        images, texts, run = encode()
        metadata = {"identity": identity, "run": run}
        metadata["array_sha256"] = [
            hashlib.sha256(a.tobytes()).hexdigest() for a in (images, texts)
        ]
    for array, rows, digest in zip(
        (images, texts),
        (len(identity["images"]), len(identity["queries"])),
        metadata["array_sha256"],
        strict=True,
    ):
        if (
            array.shape != (rows, identity["embedding_dimension"])
            or array.dtype != np.float32
            or not np.isfinite(array).all()
            or not np.allclose(np.linalg.norm(array, axis=1), 1, rtol=0, atol=1e-5)
            or hashlib.sha256(array.tobytes()).hexdigest() != digest
        ):
            raise ValueError("Corrupt or invalid embedding cache arrays")
    if not hit:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".part")
        with temporary.open("wb") as stream:
            np.savez_compressed(
                stream, images=images, texts=texts, metadata=json.dumps(metadata)
            )
        temporary.replace(path)
    return images, texts, metadata["run"], hit


def encode_images(
    model: torch.nn.Module,
    transform: Callable[[Image.Image], torch.Tensor],
    image_files: list[dict[str, Path]],
    upper_dn: float,
    batch_size: int,
) -> np.ndarray:
    """Encode native RGB files with a frozen CPU model and checkpoint transform.

    Parameters
    ----------
    model : torch.nn.Module
        Loaded float32 CPU model in evaluation mode with all parameters frozen.
    transform : callable
        Checkpoint RGB-to-tensor preprocessing, including resize/normalization.
    image_files : list of dict
        Ordered three-band dictionaries; only image measurements are read.
    upper_dn : float
        Positive saturation DN for the separately specified model RGB conversion.
    batch_size : int
        Positive image batch size; input ordering is preserved.

    Returns
    -------
    numpy.ndarray
        N x D normalized float32 image vectors, finite with nonzero source norms.

    Raises
    ------
    ValueError
        Empty inputs, invalid batch size, unfrozen/training model or invalid RGB.
    """
    import torch

    if (
        not image_files
        or type(batch_size) is not int
        or batch_size <= 0
        or model.training
        or any(p.requires_grad for p in model.parameters())
    ):
        raise ValueError("Require images, positive batch size and frozen eval model")
    vectors = []
    with torch.inference_mode():
        for offset in range(0, len(image_files), batch_size):
            tensors = [
                transform(model_rgb(read_rgb_bands(files), upper_dn))
                for files in image_files[offset : offset + batch_size]
            ]
            vectors.append(model.encode_image(torch.stack(tensors)).numpy())
    return normalize_embeddings(np.concatenate(vectors))


def encode_texts(
    model: torch.nn.Module,
    tokenizer: SimpleTokenizer,
    texts: list[str],
    batch_size: int,
) -> np.ndarray:
    """Encode ordered text without truncation using a frozen CPU CLIP model.

    Parameters
    ----------
    model : torch.nn.Module
        Loaded float32 CPU model in evaluation mode with all parameters frozen.
    tokenizer : open_clip.tokenizer.SimpleTokenizer
        Checkpoint byte-pair tokenizer with BOS/EOS and context 77.
    texts : list of str
        Ordered nonempty queries. No captions or reference labels are supplied.
    batch_size : int
        Positive text batch size; query ordering is preserved.

    Returns
    -------
    numpy.ndarray
        Q x D normalized float32 text vectors, finite with nonzero source norms.

    Raises
    ------
    ValueError
        Empty/non-string text, invalid batch size, unfrozen/training model,
        or a token sequence exceeding the 77-token context including BOS/EOS.
    """
    import torch

    if (
        not texts
        or any(type(t) is not str or not t.strip() for t in texts)
        or type(batch_size) is not int
        or batch_size <= 0
        or model.training
        or any(p.requires_grad for p in model.parameters())
    ):
        raise ValueError("Require queries, positive batch size and frozen eval model")
    if any(len(tokenizer.encode(text)) + 2 > 77 for text in texts):
        raise ValueError("Query exceeds 77-token context; truncation is prohibited")
    vectors = []
    with torch.inference_mode():
        for offset in range(0, len(texts), batch_size):
            vectors.append(
                model.encode_text(tokenizer(texts[offset : offset + batch_size]))
            )
    return normalize_embeddings(np.concatenate([v.numpy() for v in vectors]))


def encode_frozen(
    model_spec: dict,
    config: dict,
    weights_root: Path,
    image_files: list[dict[str, Path]],
    texts: list[str],
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Encode one identified frozen checkpoint on CPU, without gradient tracking.

    Parameters
    ----------
    model_spec, config : dict
        Versioned local specifications; only ViT-B-32/QuickGELU CPU float32
        is implemented. Checkpoint bytes must match declared SHA-256 and size.
    weights_root : Path
        Ignored weight directory; only the specified bounded asset is acquired.
    image_files : list of dict
        Ordered native RGB band paths; no maps are read.
    texts : list of str
        Ordered nonempty English queries. Overlong token sequences are rejected.

    Returns
    -------
    tuple
        N x 512 image and Q x 512 text float32 unit embeddings plus measured
        load/encoding seconds, actual transform, device and frozen-state checks.

    Raises
    ------
    ValueError
        Unsupported settings, input/weight mismatch, invalid embeddings or
        queries exceeding the checkpoint's 77-token context including BOS/EOS.
    """
    import open_clip
    import torch

    runtime = config["runtime"]
    preprocessing = config["preprocessing"]
    if (
        config["architecture"] != "ViT-B-32"
        or config["embedding_dimension"] != 512
        or runtime["device"] != "cpu"
        or runtime["precision"] != "float32"
        or not config["activation"].startswith("QuickGELU")
        or config["rgb"]["bands"] != list(RGB_BANDS)
        or preprocessing["image_size"] != 224
        or preprocessing["resize"] != "shortest edge, bicubic"
        or preprocessing["crop"] != "center 224 x 224"
        or preprocessing["mode"] != "RGB"
        or preprocessing["tensor"] != "float32 CHW divided by 255"
        or preprocessing["mean"] != [0.48145466, 0.4578275, 0.40821073]
        or preprocessing["std"] != [0.26862954, 0.26130258, 0.27577711]
        or type(runtime["batch_size"]) is not int
        or runtime["batch_size"] <= 0
        or type(runtime["torch_threads"]) is not int
        or runtime["torch_threads"] <= 0
        or not image_files
        or not texts
        or any(type(t) is not str or not t.strip() for t in texts)
    ):
        raise ValueError("Require the specified CPU ViT-B/32 pilot and nonempty inputs")
    torch.manual_seed(runtime["seed"])
    torch.set_num_threads(runtime["torch_threads"])
    torch.use_deterministic_algorithms(True)
    start = time.perf_counter()
    weight = fetch_asset(model_spec, weights_root, max_bytes=625_000_000)
    model, _, transform = open_clip.create_model_and_transforms(
        "ViT-B-32",
        pretrained=None,
        force_quick_gelu=True,
        precision="fp32",
        device="cpu",
        image_mean=preprocessing["mean"],
        image_std=preprocessing["std"],
        image_interpolation="bicubic",
        image_resize_mode="shortest",
    )
    if model_spec["format"] == "openai-jit":
        state = torch.jit.load(str(weight), map_location="cpu").state_dict()
        for key in ("input_resolution", "context_length", "vocab_size"):
            state.pop(key, None)
    elif model_spec["format"] == "state-dict":
        state = torch.load(weight, map_location="cpu", weights_only=True)
    else:
        raise ValueError("Unknown checkpoint format")
    model.load_state_dict(state, strict=True)
    del state
    model.float().eval().requires_grad_(False)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    loaded = time.perf_counter()
    image_vectors = encode_images(
        model, transform, image_files, config["rgb"]["upper_dn"], runtime["batch_size"]
    )
    image_done = time.perf_counter()
    text_vectors = encode_texts(model, tokenizer, texts, runtime["batch_size"])
    finished = time.perf_counter()
    run = {
        "load_seconds": loaded - start,
        "image_encoding_seconds": image_done - loaded,
        "text_encoding_seconds": finished - image_done,
        "total_seconds": finished - start,
        "device": str(next(model.parameters()).device),
        "dtype": str(next(model.parameters()).dtype),
        "evaluation_mode": not model.training,
        "all_parameters_frozen": all(not p.requires_grad for p in model.parameters()),
        "inference_mode": True,
        "transform": str(transform),
    }
    return (
        image_vectors,
        text_vectors,
        run,
    )
