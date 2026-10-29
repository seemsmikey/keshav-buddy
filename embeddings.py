"""Vector embeddings via Ollama and a lightweight numpy-based vector store.

Embeddings are produced locally by a free, open-source embedding model served through Ollama
(by default `nomic-embed-text`). Similarity search is done with normalized cosine similarity in
plain numpy, so no external vector database is required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import requests

from config import EMBED_MODEL, INDEX_FILE, OLLAMA_HOST, REQUEST_TIMEOUT


def embed_texts(texts: list[str], model: str = EMBED_MODEL) -> np.ndarray:
    """Embed a list of texts and return an (N, D) float32 array of unit vectors."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    vectors = _embed_batch(texts, model)

    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _embed_batch(texts: list[str], model: str) -> list[list[float]]:
    """Try Ollama's batch `/api/embed` endpoint, fall back to per-text `/api/embeddings`."""
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/embed",
            json={"model": model, "input": texts},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
    except requests.RequestException:
        pass

    return [_embed_one(text, model) for text in texts]


def _embed_one(text: str, model: str) -> list[float]:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def embed_query(text: str, model: str = EMBED_MODEL) -> np.ndarray:
    """Embed a single query string and return a unit (D,) vector."""
    return embed_texts([text], model=model)[0]


@dataclass
class VectorStore:
    """In-memory cosine similarity index with save/load to a compressed .npz file."""

    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    chunks: list[dict] = field(default_factory=list)
    dim: int = 0
    embed_model: str = EMBED_MODEL

    def build(self, chunks: list[dict], vectors: np.ndarray, embed_model: str) -> None:
        self.chunks = chunks
        self.vectors = vectors
        self.dim = int(vectors.shape[1]) if vectors.size else 0
        self.embed_model = embed_model

    def search(self, query_vector: np.ndarray, top_k: int) -> list[dict]:
        """Return the top_k most similar chunks with their cosine scores."""
        if self.vectors.size == 0 or not self.chunks:
            return []

        scores = self.vectors @ query_vector
        top_k = min(top_k, len(self.chunks))
        order = np.argsort(-scores)[:top_k]

        results = []
        for idx in order:
            chunk = dict(self.chunks[int(idx)])
            chunk["score"] = float(scores[int(idx)])
            results.append(chunk)
        return results

    def save(self, path=INDEX_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.dumps({
            "chunks": self.chunks,
            "embed_model": self.embed_model,
            "dim": self.dim,
        })
        np.savez_compressed(
            path,
            vectors=self.vectors,
            metadata=np.array(metadata),
        )

    @classmethod
    def load(cls, path=INDEX_FILE) -> VectorStore:
        data = np.load(path, allow_pickle=False)
        metadata = json.loads(str(data["metadata"]))
        store = cls()
        store.vectors = data["vectors"].astype(np.float32)
        store.chunks = metadata["chunks"]
        store.dim = int(metadata.get("dim", store.vectors.shape[1] if store.vectors.size else 0))
        store.embed_model = metadata.get("embed_model", EMBED_MODEL)
        return store

    @property
    def is_ready(self) -> bool:
        return self.vectors.size > 0 and len(self.chunks) > 0
