from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EmbeddingResult:
    enabled: bool
    provider: str
    model_name: str
    vectors: Any
    index_by_message_id: dict[str, int]
    used_fallback: bool
    metadata: dict[str, Any]


def build_message_embeddings(
    messages: list[Any],
    output_dir: Path,
    enabled: bool = True,
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    batch_size: int = 8,
    min_batch_size: int = 1,
    max_seq_length: int | None = 256,
    device: str = "auto",
    precision: str = "fp16",
    normalize: bool = True,
    cache: bool = True,
) -> EmbeddingResult:
    """Build optional sentence-transformer embeddings and persist audit artifacts.

    The function intentionally falls back without failing the pipeline when the
    optional dependency or model is unavailable.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    index_by_message_id = {
        message.message_id: index for index, message in enumerate(messages)
    }
    index_path = output_dir / "message_embedding_index.csv"
    metadata_path = output_dir / "embedding_metadata.json"
    vectors_path = output_dir / "message_embeddings.npy"

    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["message_id", "embedding_index"])
        writer.writeheader()
        for message_id, index in index_by_message_id.items():
            writer.writerow({"message_id": message_id, "embedding_index": index})

    metadata: dict[str, Any] = {
        "enabled_requested": enabled,
        "provider": "sentence_transformers",
        "model_name": model_name,
        "message_count": len(messages),
        "requested_batch_size": batch_size,
        "min_batch_size": min_batch_size,
        "max_seq_length": max_seq_length,
        "requested_device": device,
        "precision": precision,
        "normalize": normalize,
        "cache": cache,
    }
    if not enabled:
        metadata.update({"enabled": False, "used_fallback": True, "reason": "disabled_by_config"})
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return EmbeddingResult(False, "tfidf_fallback", model_name, [], index_by_message_id, True, metadata)

    content_hash = _content_hash([message.content_normalized for message in messages])
    metadata["content_hash"] = content_hash
    try:
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer

        resolved_device = _resolve_device(device, torch)
        metadata["resolved_device"] = resolved_device

        if cache and vectors_path.exists() and metadata_path.exists():
            previous = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                previous.get("content_hash") == content_hash
                and previous.get("model_name") == model_name
                and previous.get("enabled")
                and not previous.get("used_fallback")
            ):
                vectors = np.load(vectors_path).astype("float32")
                metadata.update(previous)
                return EmbeddingResult(
                    True,
                    "sentence_transformers",
                    model_name,
                    vectors,
                    index_by_message_id,
                    False,
                    metadata,
                )

        print(
            "[discord_disentanglement] Loading sentence-transformer model: "
            f"{model_name} on {resolved_device} with batch_size={batch_size}"
        )
        model = SentenceTransformer(model_name, device=resolved_device)
        if max_seq_length and hasattr(model, "max_seq_length"):
            model.max_seq_length = max_seq_length
        if resolved_device.startswith("cuda") and precision.casefold() in {"fp16", "float16", "half"}:
            model = model.half()
        embeddings, effective_batch_size = _encode_with_retry(
            model=model,
            texts=[message.content_normalized for message in messages],
            batch_size=max(1, batch_size),
            min_batch_size=max(1, min_batch_size),
            normalize=normalize,
            torch_module=torch,
        )
        embeddings = np.asarray(embeddings, dtype="float32")
        if normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings = embeddings / norms
        np.save(vectors_path, embeddings)
        metadata.update(
            {
                "enabled": True,
                "used_fallback": False,
                "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
                "effective_batch_size": effective_batch_size,
                "artifact": vectors_path.name,
            }
        )
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return EmbeddingResult(
            True,
            "sentence_transformers",
            model_name,
            embeddings,
            index_by_message_id,
            False,
            metadata,
        )
    except Exception as exc:
        metadata.update(
            {
                "enabled": False,
                "used_fallback": True,
                "reason": f"{type(exc).__name__}: {exc}",
                "fallback": "tfidf",
            }
        )
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return EmbeddingResult(False, "tfidf_fallback", model_name, [], index_by_message_id, True, metadata)


def embedding_cosine(vectors: Any, left_index: int, right_index: int) -> float:
    if vectors is None or len(vectors) == 0:
        return 0.0
    left = vectors[left_index]
    right = vectors[right_index]
    if len(left) == 0 or len(right) == 0:
        return 0.0
    return float(sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False)))


def _resolve_device(device: str, torch_module: Any) -> str:
    requested = (device or "auto").casefold()
    if requested == "auto":
        return "cuda" if torch_module.cuda.is_available() else "cpu"
    if requested.startswith("cuda") and not torch_module.cuda.is_available():
        return "cpu"
    return requested


def _encode_with_retry(
    model: Any,
    texts: list[str],
    batch_size: int,
    min_batch_size: int,
    normalize: bool,
    torch_module: Any,
) -> tuple[Any, int]:
    current_batch_size = batch_size
    while True:
        try:
            return (
                model.encode(
                    texts,
                    batch_size=current_batch_size,
                    normalize_embeddings=normalize,
                    show_progress_bar=True,
                    convert_to_numpy=True,
                ),
                current_batch_size,
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            is_oom = "out of memory" in message or ("cuda error" in message and "memory" in message)
            if not is_oom or current_batch_size <= min_batch_size:
                raise
            if torch_module.cuda.is_available():
                torch_module.cuda.empty_cache()
            next_batch_size = max(min_batch_size, current_batch_size // 2)
            print(
                "[discord_disentanglement] CUDA OOM while encoding embeddings; "
                f"retrying with batch_size={next_batch_size}"
            )
            current_batch_size = next_batch_size


def _content_hash(texts: list[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        digest.update(text.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()
