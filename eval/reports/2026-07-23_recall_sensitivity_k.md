# Sensibilité recall@k — 2026-07-23

- Corpus : 17 docs / 269 chunks · 16 questions answerable · embeddeur `intfloat/multilingual-e5-small`
- recall@k = proxy de *context recall* (RAGAS). RRF = fusion sémantique+BM25 (mesurée seulement).

| Méthode | k=2 | k=3 | k=5 | k=8 |
|---|---|---|---|---|
| semantic | 0.88 | 0.88 | 0.94 | 0.94 |
| bm25 | 0.69 | 0.75 | 0.81 | 0.81 |
| rrf | 0.75 | 0.88 | 0.88 | 0.88 |
