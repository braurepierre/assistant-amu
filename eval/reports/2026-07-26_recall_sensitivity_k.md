# Sensibilité recall@k — 2026-07-26

- Corpus : 18 docs / 316 chunks · 50 questions answerable (jeu élargi du 2026-07-26, contre 16 le 2026-07-23) · embeddeur `intfloat/multilingual-e5-small`
- recall@k = proxy de *context recall* (RAGAS). RRF = fusion sémantique+BM25 (mesurée seulement).
- Assemblé à partir de `eval/reports/2026-07-26_retrieval_all_k{2,3,5,8}.md` (mêmes runs, un k par fichier).

| Méthode | k=2 | k=3 | k=5 | k=8 |
|---|---|---|---|---|
| semantic | 0.80 | 0.82 | 0.86 | 0.86 |
| bm25 | 0.70 | 0.78 | 0.84 | 0.88 |
| rrf | 0.74 | 0.82 | 0.86 | **0.92** |

**Ce qui change par rapport à la mesure du 23 juillet (16 questions) : la RRF dépasse le sémantique pur à k=8** (0.92 contre 0.86, soit 3 questions sur 50 — au-delà de la granularité 1/50 = 0.02). Sur le jeu à 16 questions, RRF plafonnait avec le sémantique (0.88 tous les deux) ; l'écart n'était pas mesurable avec cette résolution. `/ask` reste semantic-pur en V1 (k par défaut = 5, où RRF et sémantique sont encore à égalité) ; la bascule vers RRF reste documentée en évolution V2.1 (PRD §5.3) mais dispose désormais d'un premier indice chiffré en sa faveur, à confirmer si k venait à être relevé en production.
