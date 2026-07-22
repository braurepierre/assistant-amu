"""In-memory BM25 index (rank_bm25.BM25Okapi) — evaluation only (PRD §7.3, §7.6).

Built on the fly from the stored chunks to compare lexical retrieval against
semantic and their RRF fusion in the harness. The /ask pipeline stays
semantic-only in V1 (§5.1.8). Tokenisation is deliberately simple — lowercase +
split on non-alphanumerics — which is enough for evaluation.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from ..models import Chunk, RetrievedChunk

_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Bm25Index:
    """Ranks stored chunks by BM25 score for a query."""

    def __init__(self, ids: list[str], texts: list[str], metadatas: list[dict]):
        self._ids = ids
        self._texts = texts
        self._metadatas = metadatas
        self._bm25 = BM25Okapi([tokenize(t) for t in texts]) if texts else None

    @classmethod
    def from_chunks(cls, chunks: list[Chunk]) -> "Bm25Index":
        return cls(
            ids=[c.chunk_id for c in chunks],
            texts=[c.text for c in chunks],
            metadatas=[dict(c.metadata, doc_id=c.doc_id) for c in chunks],
        )

    def rank(self, question: str, depth: int) -> list[RetrievedChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(question))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:depth]
        return [
            RetrievedChunk(
                chunk_id=self._ids[i],
                doc_id=str(self._metadatas[i].get("doc_id", "")),
                text=self._texts[i],
                metadata=self._metadatas[i],
                score=float(scores[i]),
            )
            for i in order
        ]
