"""Lazy singletons for the embedding model and cross-encoder reranker."""
import threading

from config import EMBEDDING_MODEL, RERANK_MODEL

_lock = threading.Lock()
_embedder = None
_reranker = None


def get_embedding_function():
    """Return embed(texts) -> list[list[float]] backed by sentence-transformers."""
    global _embedder
    with _lock:
        if _embedder is None:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
    model = _embedder

    def embed(texts):
        return model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False).tolist()

    return embed


def get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker
