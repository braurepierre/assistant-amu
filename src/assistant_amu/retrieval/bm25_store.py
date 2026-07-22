"""In-memory BM25 index (rank_bm25.BM25Okapi).

Built on the fly from the stored chunks for *evaluation only* (semantic vs BM25
vs RRF, PRD §5.1.8 / §7.6). Tokenisation: lowercase + split on non-alphanumerics.
The /ask pipeline stays semantic-only in V1. PRD §7.3 / Phase 5.

Not yet implemented — Phase 5.
"""

from __future__ import annotations

# TODO(Phase 5): BM25Okapi index over stored chunks (§7.3, §7.6).
