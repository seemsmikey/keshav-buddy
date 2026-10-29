"""Build the vector index from the knowledge_base documents.

Usage:
    python ingest.py
"""

from __future__ import annotations

import re

from config import CHUNK_OVERLAP, CHUNK_SIZE, EMBED_MODEL, INDEX_FILE, KB_DIR
from embeddings import VectorStore, embed_texts


def load_documents(kb_dir=KB_DIR) -> list[dict]:
    """Read every .md / .txt file in the knowledge base directory."""
    documents = []
    for path in sorted(kb_dir.glob("*")):
        if path.suffix.lower() not in (".md", ".txt", ".markdown"):
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append({"source": path.name, "text": text})
    return documents


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(document: dict, chunk_size: int = CHUNK_SIZE,
                   overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split a document into overlapping chunks, keeping section headings as context."""
    source = document["source"]
    paragraphs = _split_paragraphs(document["text"])

    chunks: list[dict] = []
    buffer = ""
    heading = ""

    for para in paragraphs:
        if para.startswith("#"):
            heading = para.splitlines()[0].lstrip("# ").strip()

        candidate = f"{buffer}\n\n{para}".strip() if buffer else para

        if len(candidate) > chunk_size and buffer:
            chunks.append(_make_chunk(source, heading, buffer))
            tail = buffer[-overlap:] if overlap else ""
            buffer = f"{tail}\n\n{para}".strip()
        else:
            buffer = candidate

    if buffer:
        chunks.append(_make_chunk(source, heading, buffer))

    return chunks


def _make_chunk(source: str, heading: str, body: str) -> dict:
    text = f"[{heading}]\n{body}".strip() if heading else body.strip()
    return {"source": source, "heading": heading, "text": text}


def build_index() -> VectorStore:
    documents = load_documents()
    if not documents:
        raise SystemExit(f"No documents found in {KB_DIR}")

    all_chunks: list[dict] = []
    for document in documents:
        all_chunks.extend(chunk_document(document))

    print(f"Loaded {len(documents)} documents -> {len(all_chunks)} chunks.")
    print(f"Embedding with model '{EMBED_MODEL}' via Ollama ...")

    texts = [chunk["text"] for chunk in all_chunks]
    vectors = embed_texts(texts, model=EMBED_MODEL)

    store = VectorStore()
    store.build(all_chunks, vectors, EMBED_MODEL)
    store.save(INDEX_FILE)

    print(f"Saved index ({vectors.shape[0]} vectors, dim={vectors.shape[1]}) to {INDEX_FILE}")
    return store


if __name__ == "__main__":
    build_index()
