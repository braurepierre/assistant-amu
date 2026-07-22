"""ChromaDB persistent vector store.

Single collection ``amu_docs`` created with ``metadata={"hnsw:space": "cosine"}``
(piège n°2: Chroma defaults to L2). Exposes cosine *similarity* (1 - distance),
never the raw distance. PRD §7.3 / Phase 2.

Not yet implemented — Phase 2.
"""

from __future__ import annotations

# TODO(Phase 2): persistent ChromaDB store with cosine space (§7.3).
