# Rapport — sensibilité à la taille du corpus (mesure seule) — 2026-07-26

- Embeddeur : `intfloat/multilingual-e5-small` · découpage 500 tokens / recouvrement 50.
- Collections comparées : `amu_docs__d19` (18 documents indexés, 316 fragments) contre `amu_docs__d29` (28 documents indexés, 378 fragments, +62).
- Documents listés : 19 + 10 distracteurs. 1 exclu(s) à l'ingestion, donc absent(s) des deux index : « Calendrier universitaire 2026-2027 (arrêté du Président) ».
- Les deux index sont reconstruits dans le même passage, même embeddeur et même découpage : la seule différence mesurée, ce sont les 10 documents. `amu_docs` (production) n'est jamais ouverte en écriture.
- Le jeu de questions ne bouge pas. Aucun appel LLM.

> **Seuil, fixé avant la mesure.** Le recall bouge par pas de 0.020 sur le jeu facile et 0.040 sur le jeu dur. Un écart n'est retenu qu'à partir de **3 questions** — la barre déjà utilisée pour conclure que la RRF dépassait le sémantique à k=8. En deçà, on lit du bruit.

## Recall@k — 19 documents contre 29

### Jeu « facile » (formulations définitionnelles) (50 questions ; 1 question = 0.020)

| Méthode | 19 docs k=3 | 29 docs k=3 | Δ k=3 | 19 docs k=5 | 29 docs k=5 | Δ k=5 | 19 docs k=8 | 29 docs k=8 | Δ k=8 |
|---|---|---|---|---|---|---|---|---|---|
| semantic | 0.82 | 0.82 | ±0 | 0.86 | 0.86 | ±0 | 0.86 | 0.86 | ±0 |
| bm25 | 0.78 | 0.78 | ±0 | 0.84 | 0.84 | ±0 | 0.88 | 0.88 | ±0 |
| rrf | 0.82 | 0.84 | +0.02 (+1 q) | 0.86 | 0.88 | +0.02 (+1 q) | 0.92 | 0.92 | ±0 |

### Jeu « dur » (formulations conversationnelles) (25 questions ; 1 question = 0.040)

| Méthode | 19 docs k=3 | 29 docs k=3 | Δ k=3 | 19 docs k=5 | 29 docs k=5 | Δ k=5 | 19 docs k=8 | 29 docs k=8 | Δ k=8 |
|---|---|---|---|---|---|---|---|---|---|
| semantic | 0.48 | 0.48 | ±0 | 0.72 | 0.72 | ±0 | 0.84 | 0.84 | ±0 |
| bm25 | 0.68 | 0.68 | ±0 | 0.84 | 0.84 | ±0 | 0.88 | 0.88 | ±0 |
| rrf | 0.80 | 0.72 | -0.08 (-2 q) | 0.88 | 0.80 | -0.08 (-2 q) | 0.96 | 0.96 | ±0 |

## La prédiction énoncée avant la mesure

« Si e5 dilue les sigles, le sémantique doit reculer plus que BM25. »

| Jeu | pire écart sémantique | pire écart BM25 | prédiction |
|---|---|---|---|
| facile | +0 q | +0 q | sans objet — aucune des deux ne recule |
| dur | +0 q | +0 q | sans objet — aucune des deux ne recule |

## Les distracteurs ont-ils concouru ?

Un recall inchangé peut signifier deux choses opposées : la recherche résiste, ou le lot n'est jamais monté assez haut pour la gêner. Ce diagnostic tranche. Nombre de questions dont le top-k contient au moins un fragment distracteur, et meilleur rang jamais atteint par le lot.

### Jeu « facile » (50 questions)

| Méthode | top-3 | top-5 | top-8 | top-50 (profondeur de fusion) | meilleur rang | fragments cumulés |
|---|---|---|---|---|---|---|
| semantic | 4/50 | 8/50 | 14/50 | 48/50 | rang 1 | 260 |
| bm25 | 6/50 | 8/50 | 15/50 | 46/50 | rang 1 | 170 |

### Jeu « dur » (25 questions)

| Méthode | top-3 | top-5 | top-8 | top-50 (profondeur de fusion) | meilleur rang | fragments cumulés |
|---|---|---|---|---|---|---|
| semantic | 2/25 | 4/25 | 5/25 | 25/25 | rang 1 | 175 |
| bm25 | 4/25 | 8/25 | 12/25 | 23/25 | rang 1 | 105 |

> Lecture. Si la colonne top-8 est proche de zéro alors que la colonne top-50 ne l'est pas, le lot perturbe le classement profond sans atteindre la zone servie à l'utilisateur — ce qui explique mécaniquement qu'un recall@k≤8 ne bouge pas, et que la RRF, seule à fusionner à cette profondeur, bouge.

## Détail par question — jeu « facile » (k=5)

**rrf** — perdues : 0 · regagnées : 1

| id | question | 19 docs | 29 docs | à trier |
|---|---|---|---|---|
| q34 | Quelles règles de compensation s'appliquent en licence à l'… | ❌ | ✅ |  |

## Détail par question — jeu « dur » (k=5)

**rrf** — perdues : 2 · regagnées : 0

| id | question | 19 docs | 29 docs | à trier |
|---|---|---|---|---|
| h01 | Parle-moi des régimes spéciaux. | ✅ | ❌ |  |
| h20 | On m'a dit que la réinscription se faisait désormais sur in… | ✅ | ❌ |  |

> **Ce qu'une bascule ne dit pas.** Un recall qui baisse signifie que le document *annoté* est sorti du top-k, pas nécessairement qu'une mauvaise réponse serait produite : un distracteur peut avoir pris sa place en répondant tout aussi bien. Le lot a été choisi disjoint par le contenu pour rendre ce cas rare, mais trois questions restent exposées (marquées ⚠ ci-dessus) et demandent la lecture du fragment récupéré.

## Conclusion

- Sur ce corpus et ces jeux, le passage à 28 documents **ne dégrade pas la recherche de façon mesurable** : le pire écart atteint 2 question(s) (`rrf`, k=3, jeu « dur »), sous le seuil de 3.

| Jeu | méthode | pire écart | à quel k |
|---|---|---|---|
| facile | semantic | +0 q | 3 |
| facile | bm25 | +0 q | 3 |
| facile | rrf | +0 q | 8 |
| dur | semantic | +0 q | 3 |
| dur | bm25 | +0 q | 3 |
| dur | rrf | -2 q | 3 |

**Portée.** Les décisions du jour (e5 gagnant, k=5) **résistent** à un corpus porté à 28 documents indexés. C'est un argument de robustesse, pas une preuve de passage à l'échelle : le corpus reste petit, et le lot est disjoint par construction du contenu annoté.

**Le lot a bien concouru** : il atteint le top-8 sur jusqu'à 15 questions et le classement profond sur 48. L'écart mesuré porte donc sur une concurrence réelle, pas sur un lot resté hors de portée.

**Ce que la mesure ne couvre pas.** Le lot est disjoint par le contenu : il teste la dilution, pas l'ambiguïté entre deux documents qui répondent tous deux. Le document le plus adverse disponible — un second règlement intérieur, celui des bibliothèques — a dû être écarté : son titre serait compté comme source attendue par six questions. L'instruire suppose de resserrer leur annotation, au prix de la comparabilité avec les rapports datés du 23 juillet.

**Décision.** Le corpus de production reste à 19 documents (`corpus/sources.yaml` inchangé) : mesuré, documenté, non branché — même régime que la RRF, la réécriture et la contextualisation.

