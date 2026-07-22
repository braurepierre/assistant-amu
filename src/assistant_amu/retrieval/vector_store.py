"""ChromaDB persistent vector store (PRD §7.3, §7.5).

Single collection created with ``metadata={"hnsw:space": "cosine"}`` (piège n°2:
Chroma defaults to L2). Passages are embedded with the ``passage: `` prefix and
queries with ``query: `` via the :class:`Embedder`. Chunk ids dedup on re-index
(F2 "0 doublon"); ``doc_id`` is stored in metadata for document-level dedup
(/ingest 409). Scores exposed as cosine similarity ``1 - distance`` (§7.5).
"""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import Settings, get_settings
from ..models import Chunk, RetrievedChunk
from .embedder import Embedder


class VectorStore:
    def __init__(self, *, path: Path | str, collection_name: str, embedder: object):
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        self._embedder = embedder

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        embedder: object | None = None,
        collection_name: str | None = None,
    ) -> "VectorStore":
        settings = settings or get_settings()
        return cls(
            path=settings.chroma_path,
            collection_name=collection_name or settings.chroma_collection,
            embedder=embedder or Embedder(settings.embedding_model),
        )

    def count(self) -> int:
        return self._collection.count()

    def document_count(self) -> int:
        """Number of distinct source documents currently indexed."""
        metas = self._collection.get(include=["metadatas"])["metadatas"] or []
        return len({m.get("doc_id") for m in metas})

    def has_document(self, doc_id: str) -> bool:
        return len(self._collection.get(where={"doc_id": doc_id}, limit=1)["ids"]) > 0

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """Add chunks not already present (by chunk_id). Returns the number added."""
        if not chunks:
            return 0
        existing = set(self._collection.get(ids=[c.chunk_id for c in chunks])["ids"])
        new = [c for c in chunks if c.chunk_id not in existing]
        if not new:
            return 0
        self._collection.add(
            ids=[c.chunk_id for c in new],
            embeddings=self._embedder.embed_passages([c.text for c in new]),
            documents=[c.text for c in new],
            metadatas=[_sanitize({**c.metadata, "doc_id": c.doc_id}) for c in new],
        )
        return len(new)

    def query(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []
        embedding = self._embedder.embed_queries([question])[0]
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        return _to_retrieved(result)


def _sanitize(metadata: dict[str, object]) -> dict[str, object]:
    """Chroma metadata must be str/int/float/bool; drop None, stringify the rest."""
    clean: dict[str, object] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        clean[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
    return clean


def _to_retrieved(result: dict) -> list[RetrievedChunk]:
    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    retrieved: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        score = max(0.0, min(1.0, 1.0 - float(distance)))  # similarity in [0, 1]
        retrieved.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=str(metadata.get("doc_id", "")),
                text=text,
                metadata=metadata,
                score=score,
            )
        )
    return retrieved
