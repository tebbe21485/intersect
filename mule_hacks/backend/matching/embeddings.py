"""Lazy CPU MiniLM encoder. Matching reads stored vectors and never calls this.

Model downloads are explicit through the prepare-matching CLI command. Normal
requests use the workspace cache only, so offline startup cannot trigger a
network download or silently substitute a different model.
"""

import math
import threading
from pathlib import Path

from ..errors import AppError
from ..sqlite import PROJECT_ROOT
from .config import EMBEDDING_DIMENSIONS, MODEL_NAME

MODEL_CACHE = PROJECT_ROOT / ".cache" / "matching" / "models"
_model = None
_lock = threading.Lock()


def validate_embedding(vector, dimensions=EMBEDDING_DIMENSIONS):
    try:
        values = tuple(float(x) for x in vector)
    except (TypeError, ValueError):
        raise ValueError("Invalid embedding") from None
    if (
        len(values) != dimensions
        or any(not math.isfinite(x) for x in values)
        or not math.hypot(*values)
    ):
        raise ValueError("Invalid embedding dimensions or values")
    return values


def _load_model(*, download=False):
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            MODEL_NAME,
            device="cpu",
            cache_folder=str(MODEL_CACHE),
            local_files_only=not download,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        raise AppError(
            "Text matching is not ready. Run uv sync, then python -m mule_hacks.backend.cli prepare-matching on the server.",
            503,
        ) from error


def prepare_model():
    """Explicit operator action to download the specified model to this project."""
    global _model
    with _lock:
        Path(MODEL_CACHE).mkdir(parents=True, exist_ok=True)
        _model = _load_model(download=True)
    return {"model": MODEL_NAME, "cache": str(MODEL_CACHE)}


def generate_embedding(text: str) -> tuple[float, ...]:
    """Called only for a changed free-response record or explicit backfill."""
    global _model
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Cannot embed empty text")
    with _lock:
        if _model is None:
            _model = _load_model()
        # Reject overlong text instead of silently embedding only its beginning.
        tokens = _model.tokenizer.encode(
            text, add_special_tokens=True, truncation=False
        )
        if len(tokens) > _model.max_seq_length:
            raise AppError(
                "Please shorten this answer so text matching can use the whole response."
            )
        vector = _model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return validate_embedding(vector)
