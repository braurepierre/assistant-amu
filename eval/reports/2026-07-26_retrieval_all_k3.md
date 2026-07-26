# Rapport d'évaluation — retrieval — 2026-07-26

- Méthodes : semantic, bm25, rrf
- k = 3 | questions answerable = 50
- Backend LLM : `ollama/mistral` | Modèle d'embedding : `intfloat/multilingual-e5-small`

## Recall@k (proxy de *context recall*, RAGAS)

| Méthode | Recall@k |
|---|---|
| semantic | 0.82 |
| bm25 | 0.78 |
| rrf | 0.82 |

## Détail par question

| id | question | semantic | bm25 | rrf |
|---|---|---|---|---|
| q01 | Comment demander une césure à l'université ? | ✅ | ❌ | ✅ |
| q02 | Puis-je interrompre mes études pendant un an puis les reprendre ? | ✅ | ❌ | ❌ |
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | ✅ | ❌ | ❌ |
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ❌ | ✅ |
| q05 | Quels aménagements pour un étudiant en situation de handicap ? | ❌ | ✅ | ✅ |
| q06 | Comment trouver un job à côté de mes études ? | ✅ | ✅ | ✅ |
| q07 | Comment obtenir un duplicata de mon diplôme à l'IUT ? | ✅ | ✅ | ✅ |
| q08 | Qu'est-ce que le régime spécial d'études (RSE) ? | ✅ | ✅ | ✅ |
| q09 | Qu'est-ce que la CVEC ? | ✅ | ✅ | ✅ |
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
| q28 | Que signifie le sigle FOAD ? | ✅ | ✅ | ✅ |
| q29 | Quelles démarches un étudiant sportif de haut niveau doit-il accompli… | ✅ | ✅ | ✅ |
| q30 | Comment un étudiant artiste peut-il obtenir un aménagement de son cur… | ✅ | ✅ | ✅ |
| q31 | Auprès de qui se signaler pour bénéficier d'un régime spécial à la fa… | ❌ | ✅ | ✅ |
| q32 | Comment les sessions d'examen sont-elles organisées en licence à l'AL… | ✅ | ❌ | ❌ |
| q33 | Quelles absences sont considérées comme justifiées en licence à l'ALL… | ✅ | ✅ | ✅ |
| q34 | Quelles règles de compensation s'appliquent en licence à l'ALLSH ? | ❌ | ❌ | ❌ |
| q35 | Comment le jury délibère-t-il en master à l'ALLSH ? | ❌ | ✅ | ❌ |
| q36 | Quelles sont les modalités d'évaluation en master à l'ALLSH ? | ✅ | ✅ | ✅ |
| q37 | Comment candidater à l'IUT ? | ✅ | ✅ | ✅ |
| q38 | Quelles démarches administratives le service de scolarité de l'IUT pr… | ✅ | ✅ | ✅ |
| q39 | Comment se déroule une césure à l'IUT ? | ✅ | ✅ | ✅ |
| q40 | Quels services de santé sont proposés aux étudiants de la faculté de … | ✅ | ✅ | ✅ |
| q41 | Où les étudiants en droit peuvent-ils se restaurer sur le campus ? | ❌ | ❌ | ❌ |
| q42 | Comment s'engager dans une association étudiante à la faculté de droi… | ✅ | ✅ | ✅ |
| q43 | Comment la compensation s'opère-t-elle à l'intérieur d'un bloc de con… | ❌ | ❌ | ❌ |
| q44 | La compensation s'applique-t-elle entre les semestres d'une licence d… | ❌ | ❌ | ❌ |
| q45 | Quelles aides financières existent pour le logement étudiant ? | ✅ | ✅ | ✅ |
| q46 | Quelles structures accompagnent les étudiants dans leur recherche de … | ✅ | ✅ | ✅ |
| q47 | Comment contacter la Mission Handicap de son campus ? | ✅ | ❌ | ✅ |
| q48 | Que prévoit la charte des étudiants en matière de plagiat ? | ✅ | ✅ | ✅ |
| q49 | À quoi sert le FSDIE ? | ✅ | ✅ | ✅ |
| q50 | Quand ont lieu les inscriptions administratives à la faculté des scie… | ✅ | ✅ | ✅ |
| q51 | Quel est le calendrier pédagogique du master à la faculté des science… | ✅ | ✅ | ✅ |
| q52 | Quelles pièces justificatives faut-il fournir lors de l'inscription e… | ❌ | ✅ | ✅ |
| q53 | Comment se connecter à la plateforme d'inscription administrative en … | ✅ | ❌ | ❌ |
| q54 | Dans quelles conditions les copies d'examen peuvent-elles être consul… | ✅ | ✅ | ✅ |

## Désaccords sémantique vs BM25

| id | question | trouvé par |
|---|---|---|
| q01 | Comment demander une césure à l'université ? | semantic |
| q02 | Puis-je interrompre mes études pendant un an puis les reprendre ? | semantic |
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | semantic |
| q05 | Quels aménagements pour un étudiant en situation de handicap ? | bm25 |
| q31 | Auprès de qui se signaler pour bénéficier d'un régime spécial à la fa… | bm25 |
| q32 | Comment les sessions d'examen sont-elles organisées en licence à l'AL… | semantic |
| q35 | Comment le jury délibère-t-il en master à l'ALLSH ? | bm25 |
| q47 | Comment contacter la Mission Handicap de son campus ? | semantic |
| q52 | Quelles pièces justificatives faut-il fournir lors de l'inscription e… | bm25 |
| q53 | Comment se connecter à la plateforme d'inscription administrative en … | semantic |
