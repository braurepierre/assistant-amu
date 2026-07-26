# Rapport — comparaison d'embeddeurs (mesure seule) — 2026-07-26

- Corpus : 18 docs / 316 chunks — 50 questions answerable (granularité 1/50 ≈ 0.020).
- Chunks ré-embarqués depuis la collection `amu_docs` (mêmes chunks pour tous les modèles) ; collections éphémères supprimées après mesure.
- `recall@k` (sémantique) = proxy de *context recall* (RAGAS). BM25 = référence lexicale, indépendante de l'embeddeur. **Mesure seule** : le pipeline `/ask` reste sémantique pur avec l'embeddeur de production (§5.1.8).
- Modèles E5 : préfixes `query:`/`passage:` ; CamemBERT & FlauBERT : aucun préfixe (table par famille dans `retrieval/embedder.py`).

## Recall@k par embeddeur

| Embeddeur | recall@3 | recall@5 | recall@8 |
|---|---|---|---|
| `intfloat/multilingual-e5-small` | 0.82 | 0.86 | 0.86 |
| `dangvantuan/sentence-camembert-base` | 0.66 | 0.76 | 0.86 |
| `hugorosen/flaubert_base_uncased-xnli-sts` | 0.68 | 0.76 | 0.86 |
| _BM25 (référence lexicale)_ | 0.78 | 0.84 | 0.88 |

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
| q21 | Quelles règles d'hygiène et de sécurité s'appliquent dans les locaux … | ✅ | ✅ | ✅ |
| q22 | À quelles conditions une réunion peut-elle être organisée dans les lo… | ✅ | ✅ | ✅ |
| q23 | Que prévoit le règlement intérieur en matière de liberté d'expression… | ✅ | ✅ | ✅ |
| q24 | L'affichage est-il libre dans les bâtiments universitaires ? | ✅ | ✅ | ✅ |
| q25 | Quel est le montant des droits d'inscription ? | ✅ | ✅ | ✅ |
| q26 | Quels modes de paiement sont acceptés pour les droits d'inscription ? | ✅ | ✅ | ✅ |
| q27 | Que signifie le sigle LANSAD ? | ✅ | ✅ | ✅ |
| q28 | Que signifie le sigle FOAD ? | ✅ | ❌ | ❌ |
| q29 | Quelles démarches un étudiant sportif de haut niveau doit-il accompli… | ✅ | ✅ | ✅ |
| q30 | Comment un étudiant artiste peut-il obtenir un aménagement de son cur… | ✅ | ✅ | ✅ |
| q31 | Auprès de qui se signaler pour bénéficier d'un régime spécial à la fa… | ❌ | ❌ | ✅ |
| q32 | Comment les sessions d'examen sont-elles organisées en licence à l'AL… | ✅ | ❌ | ❌ |
| q33 | Quelles absences sont considérées comme justifiées en licence à l'ALL… | ✅ | ✅ | ❌ |
| q34 | Quelles règles de compensation s'appliquent en licence à l'ALLSH ? | ❌ | ❌ | ❌ |
| q35 | Comment le jury délibère-t-il en master à l'ALLSH ? | ❌ | ❌ | ✅ |
| q36 | Quelles sont les modalités d'évaluation en master à l'ALLSH ? | ✅ | ✅ | ✅ |
| q37 | Comment candidater à l'IUT ? | ✅ | ✅ | ✅ |
| q38 | Quelles démarches administratives le service de scolarité de l'IUT pr… | ✅ | ✅ | ✅ |
| q39 | Comment se déroule une césure à l'IUT ? | ✅ | ❌ | ✅ |
| q40 | Quels services de santé sont proposés aux étudiants de la faculté de … | ✅ | ✅ | ❌ |
| q41 | Où les étudiants en droit peuvent-ils se restaurer sur le campus ? | ❌ | ✅ | ✅ |
| q42 | Comment s'engager dans une association étudiante à la faculté de droi… | ✅ | ❌ | ✅ |
| q43 | Comment la compensation s'opère-t-elle à l'intérieur d'un bloc de con… | ✅ | ✅ | ❌ |
| q44 | La compensation s'applique-t-elle entre les semestres d'une licence d… | ❌ | ❌ | ✅ |
| q45 | Quelles aides financières existent pour le logement étudiant ? | ✅ | ✅ | ✅ |
| q46 | Quelles structures accompagnent les étudiants dans leur recherche de … | ✅ | ✅ | ✅ |
| q47 | Comment contacter la Mission Handicap de son campus ? | ✅ | ✅ | ✅ |
| q48 | Que prévoit la charte des étudiants en matière de plagiat ? | ✅ | ✅ | ✅ |
| q49 | À quoi sert le FSDIE ? | ✅ | ❌ | ✅ |
| q50 | Quand ont lieu les inscriptions administratives à la faculté des scie… | ✅ | ✅ | ✅ |
| q51 | Quel est le calendrier pédagogique du master à la faculté des science… | ✅ | ❌ | ❌ |
| q52 | Quelles pièces justificatives faut-il fournir lors de l'inscription e… | ❌ | ✅ | ❌ |
| q53 | Comment se connecter à la plateforme d'inscription administrative en … | ✅ | ✅ | ✅ |
| q54 | Dans quelles conditions les copies d'examen peuvent-elles être consul… | ✅ | ❌ | ❌ |

## Désaccords entre embeddeurs (k=5)

| id | question | e5-small | camembert | flaubert |
|---|---|---|---|---|
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | ✅ | ❌ | ❌ |
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ✅ | ✅ |
| q08 | Qu'est-ce que le régime spécial d'études (RSE) ? | ✅ | ✅ | ❌ |
| q09 | Qu'est-ce que la CVEC ? | ✅ | ✅ | ❌ |
| q28 | Que signifie le sigle FOAD ? | ✅ | ❌ | ❌ |
| q31 | Auprès de qui se signaler pour bénéficier d'un régime spécial à la fa… | ❌ | ❌ | ✅ |
| q32 | Comment les sessions d'examen sont-elles organisées en licence à l'AL… | ✅ | ❌ | ❌ |
| q33 | Quelles absences sont considérées comme justifiées en licence à l'ALL… | ✅ | ✅ | ❌ |
| q35 | Comment le jury délibère-t-il en master à l'ALLSH ? | ❌ | ❌ | ✅ |
| q39 | Comment se déroule une césure à l'IUT ? | ✅ | ❌ | ✅ |
| q40 | Quels services de santé sont proposés aux étudiants de la faculté de … | ✅ | ✅ | ❌ |
| q41 | Où les étudiants en droit peuvent-ils se restaurer sur le campus ? | ❌ | ✅ | ✅ |
| q42 | Comment s'engager dans une association étudiante à la faculté de droi… | ✅ | ❌ | ✅ |
| q43 | Comment la compensation s'opère-t-elle à l'intérieur d'un bloc de con… | ✅ | ✅ | ❌ |
| q44 | La compensation s'applique-t-elle entre les semestres d'une licence d… | ❌ | ❌ | ✅ |
| q49 | À quoi sert le FSDIE ? | ✅ | ❌ | ✅ |
| q51 | Quel est le calendrier pédagogique du master à la faculté des science… | ✅ | ❌ | ❌ |
| q52 | Quelles pièces justificatives faut-il fournir lors de l'inscription e… | ❌ | ✅ | ❌ |
| q54 | Dans quelles conditions les copies d'examen peuvent-elles être consul… | ✅ | ❌ | ❌ |

## Conclusion

- **Meilleur recall@k moyen : `e5-small`** (intfloat/multilingual-e5-small).
- Classement (moyenne recall@3/5/8) : `e5-small` 0.85 · `flaubert` 0.77 · `camembert` 0.76.
- Rappel : un écart inférieur à un cran de question (≈ 0.020) n'est pas significatif sur ce jeu de 50 questions.
- La bascule éventuelle de l'embeddeur de production est une décision distincte (coût, taille, latence CPU), pas seulement un delta de recall.

