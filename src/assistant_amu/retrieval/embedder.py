"""Embedding wrapper over sentence-transformers (PRD §7.3).

Owns a {model family -> prefixes} table and applies the right set: E5 models
require ``"query: "`` / ``"passage: "`` (piège n°1 — omitting them silently
degrades retrieval); CamemBERT-family models take no prefix (adding one would
pollute their inputs and skew the Phase 5 comparison). No other module encodes
text directly — everything goes through :class:`Embedder`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Query/passage prefixes per model family. The table is the single source of
# truth for piège n°1 (PRD §7.3).
_E5_PREFIXES = ("query: ", "passage: ")
_NO_PREFIXES = ("", "")


@dataclass(frozen=True, slots=True)
class _Prefixes:
    query: str
    passage: str


def prefixes_for(model_name: str) -> _Prefixes:
    """Return the (query, passage) prefixes for a model, by family."""
    name = model_name.lower()
    if "e5" in name:
        return _Prefixes(*_E5_PREFIXES)
    # sentence-camembert and any other non-E5 encoder: no prefix.
    return _Prefixes(*_NO_PREFIXES)


class Embedder:
    """Encode queries and passages with family-appropriate prefixes.

    The underlying model is loaded lazily on first use (or injected for tests,
    so unit tests never download the real 470 MB model).
    """

    def __init__(self, model_name: str, *, model: object | None = None, normalize: bool = True):
        self.model_name = model_name
        self.prefixes = prefixes_for(model_name)
        self._model = model
        self._normalize = normalize

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.prefixes.passage)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.prefixes.query)

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        prefixed = [prefix + text for text in texts]
        vectors = self.model.encode(
            prefixed, normalize_embeddings=self._normalize, convert_to_numpy=True
        )
        return [vector.tolist() for vector in vectors]
