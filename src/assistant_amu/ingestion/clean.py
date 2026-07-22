"""Clean extracted text.

Remove repeated headers/footers (identical lines recurring on >= 3 pages),
normalise whitespace and line breaks, drop tables of contents (dot-leader /
page-number density heuristic). PRD §7.2 / Phase 1.

Not yet implemented — Phase 1.
"""

from __future__ import annotations

# TODO(Phase 1): text cleaning heuristics (F2).
