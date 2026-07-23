# Rapport — comparaison d'embeddeurs (mesure seule) — 2026-07-23

- Corpus : 18 docs / 316 chunks — 16 questions answerable (granularité 1/16 ≈ 0.062).
- Chunks ré-embarqués depuis la collection `amu_docs` (mêmes chunks pour tous les modèles) ; collections éphémères supprimées après mesure.
- `recall@k` (sémantique) = proxy de *context recall* (RAGAS). BM25 = référence lexicale, indépendante de l'embeddeur. **Mesure seule** : le pipeline `/ask` reste sémantique pur avec l'embeddeur de production (§5.1.8).
- Modèles E5 : préfixes `query:`/`passage:` ; CamemBERT & FlauBERT : aucun préfixe (table par famille dans `retrieval/embedder.py`).

## Recall@k par embeddeur

| Embeddeur | recall@3 | recall@5 | recall@8 |
|---|---|---|---|
| `intfloat/multilingual-e5-small` | 0.88 | 0.94 | 0.94 |
| `dangvantuan/sentence-camembert-base` | 0.81 | 0.94 | 1.00 |
| `hugorosen/flaubert_base_uncased-xnli-sts` | 0.81 | 0.81 | 0.94 |
| _BM25 (référence lexicale)_ | 0.75 | 0.81 | 0.81 |

## Détail par question (sémantique, k=5)

| id | question | e5-small | camembert | flaubert |
|---|---|---|---|---|
| q01 | Comment demander une césure à l'université ? | ✅ | ✅ | ✅ |
| q02 | Puis-je interrompre mes études pendant un an puis les reprendre ? | ✅ | ✅ | ✅ |
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | ✅ | ❌ | ❌ |
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ✅ | ✅ |
| q05 | Quels aménagements pour un étudiant en situation de handicap ? | ✅ | ✅ | ✅ |
| q06 | Comment trouver un job à côté de mes études ? | ✅ | ✅ | ✅ |
| q07 | Comment obtenir un duplicata de mon diplôme à l'IUT ? | ✅ | ✅ | ✅ |
| q08 | Qu'est-ce que le régime spécial d'études (RSE) ? | ✅ | ✅ | ❌ |
| q09 | Qu'est-ce que la CVEC ? | ✅ | ✅ | ❌ |
| q10 | Quelles sont les modalités de contrôle des connaissances (M3C) en ALL… | ✅ | ✅ | ✅ |
| q11 | Comment fonctionne la compensation des notes en licence ? | ✅ | ✅ | ✅ |
| q12 | Que signifie le sigle BCC ? | ✅ | ✅ | ✅ |
| q13 | Comment s'inscrire administrativement en ligne (IA web) ? | ✅ | ✅ | ✅ |
| q14 | Que dit la charte des examens ? | ✅ | ✅ | ✅ |
| q15 | Quels sont les droits et devoirs figurant dans la charte des étudiant… | ✅ | ✅ | ✅ |
| q16 | Où consulter le calendrier universitaire de la faculté des sciences ? | ✅ | ✅ | ✅ |

## Désaccords entre embeddeurs (k=5)

| id | question | e5-small | camembert | flaubert |
|---|---|---|---|---|
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | ✅ | ❌ | ❌ |
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ✅ | ✅ |
| q08 | Qu'est-ce que le régime spécial d'études (RSE) ? | ✅ | ✅ | ❌ |
| q09 | Qu'est-ce que la CVEC ? | ✅ | ✅ | ❌ |

## Conclusion

- **Meilleur recall@k moyen : `e5-small`** (intfloat/multilingual-e5-small).
- Classement (moyenne recall@3/5/8) : `e5-small` 0.92 · `camembert` 0.92 · `flaubert` 0.85.
- Rappel : un écart inférieur à un cran de question (≈ 0.062) n'est pas significatif sur ce jeu de 16 questions.
- La bascule éventuelle de l'embeddeur de production est une décision distincte (coût, taille, latence CPU), pas seulement un delta de recall.

