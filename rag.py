"""Retrieval Augmented Generation pipeline for the Keshav Mahavidyalaya helpdesk.

The pipeline:
1. Embeds the user question with the local embedding model.
2. Retrieves the most relevant chunks from the numpy vector store.
3. Builds a grounded prompt and asks the free, local LLM (via Ollama) to answer.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests

import config
from embeddings import VectorStore, embed_query


class RAGEngine:
    def __init__(self) -> None:
        self._store: VectorStore | None = None

    def _store_or_build(self) -> VectorStore:
        if self._store is not None and self._store.is_ready:
            return self._store
        if config.INDEX_FILE.exists():
            store = VectorStore.load(config.INDEX_FILE)
            if store.embed_model != config.EMBED_MODEL:
                store = self._rebuild()
        else:
            store = self._rebuild()
        self._store = store
        return store

    def _rebuild(self) -> VectorStore:
        from ingest import build_index

        return build_index()

    def reload(self) -> None:
        """Force a rebuild of the index from the knowledge base."""
        self._store = self._rebuild()

    def retrieve(self, question: str, top_k: int = config.TOP_K) -> list[dict]:
        store = self._store_or_build()
        query_vector = embed_query(question, model=store.embed_model or config.EMBED_MODEL)
        results = store.search(query_vector, top_k=top_k)
        return [r for r in results if r["score"] >= config.MIN_SCORE] or results[:1]

    def _build_messages(self, question: str, contexts: list[dict]) -> list[dict]:
        if contexts:
            context_blocks = []
            for i, chunk in enumerate(contexts, start=1):
                context_blocks.append(f"[Source {i}: {chunk['source']}]\n{chunk['text']}")
            context = "\n\n".join(context_blocks)
        else:
            context = "No relevant context was found in the knowledge base."

        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer the question using only the context above."
        )
        return [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _sources(self, contexts: list[dict]) -> list[dict]:
        seen = set()
        sources = []
        for chunk in contexts:
            label = chunk.get("heading") or chunk["source"]
            key = (chunk["source"], label)
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "source": chunk["source"],
                "heading": label,
                "score": round(chunk.get("score", 0.0), 3),
            })
        return sources

    def answer(self, question: str) -> dict[str, object]:
        contexts = self.retrieve(question)
        messages = self._build_messages(question, contexts)
        reply = self._chat(messages)
        return {
            "answer": reply,
            "sources": self._sources(contexts),
        }

    def stream_answer(self, question: str) -> Iterator[dict]:
        contexts = self.retrieve(question)
        messages = self._build_messages(question, contexts)

        yield {"type": "sources", "sources": self._sources(contexts)}

        for token in self._chat_stream(messages):
            yield {"type": "token", "token": token}

        yield {"type": "done"}

    def _chat(self, messages: list[dict]) -> str:
        resp = requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={
                "model": config.CHAT_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    def _chat_stream(self, messages: list[dict]) -> Iterator[str]:
        with requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={
                "model": config.CHAT_MODEL,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.3},
            },
            timeout=config.REQUEST_TIMEOUT,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    payload = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                token = payload.get("message", {}).get("content", "")
                if token:
                    yield token
                if payload.get("done"):
                    break
