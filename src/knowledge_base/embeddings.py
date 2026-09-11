from __future__ import annotations

from hashlib import sha256
import math
import re
from typing import Protocol, Sequence


DEFAULT_EMBEDDING_MODEL = r"D:\papers\models\bge-m3"


class EmbeddingProvider(Protocol):
    """Small provider contract so production and test embeddings are interchangeable."""

    model_name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class HashEmbeddingProvider:
    """Deterministic local baseline that requires no model download.

    This is useful for reproducible ingestion and development. It is not intended
    to replace a semantic medical embedding model in production.
    """

    def __init__(self, dimension: int = 256, model_name: str = "hash-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self.model_name = model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        vector = [0.0] * self.dimension
        for token in tokens or [text.casefold()]:
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class SentenceTransformerEmbeddingProvider:
    """Optional provider for a local sentence-transformers model."""

    def __init__(self, model_name: str, *, device: str | None = None, batch_size: int = 32) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for local semantic embeddings; "
                "install with `pip install -e .[embedding]`."
            ) from exc
        self.model_name = model_name
        self.device = device
        self._model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = self._model.get_sentence_embedding_dimension
        self.dimension = int(get_dimension())

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


def create_embedding_provider(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    *,
    dimension: int = 256,
    device: str | None = None,
    batch_size: int = 32,
) -> EmbeddingProvider:
    if model_name == "hash-v1":
        return HashEmbeddingProvider(dimension=dimension)
    return SentenceTransformerEmbeddingProvider(model_name, device=device, batch_size=batch_size)
