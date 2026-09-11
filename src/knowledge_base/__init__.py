"""LanceDB-backed storage and retrieval for the medical knowledge base."""

from .embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingProvider,
    HashEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)
from .store import KnowledgeBaseStore

__all__ = [
    "EmbeddingProvider",
    "DEFAULT_EMBEDDING_MODEL",
    "HashEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "KnowledgeBaseStore",
]
