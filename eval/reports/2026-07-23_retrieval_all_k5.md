# Rapport d'évaluation — retrieval — 2026-07-23

- Méthodes : semantic, bm25, rrf
- k = 5 | questions answerable = 16
- Backend LLM : `ollama/mistral` | Modèle d'embedding : `intfloat/multilingual-e5-small`

## Recall@k (proxy de *context recall*, RAGAS)

| Méthode | Recall@k |
|---|---|
| semantic | 0.81 |
| bm25 | 0.75 |
| rrf | 0.81 |

## Détail par question

| id | question | semantic | bm25 | rrf |
|---|---|---|---|---|
| q01 | Comment demander une césure à l'université ? | ✅ | ✅ | ✅ |
| q02 | Puis-je interrompre mes études pendant un an puis les reprendre ? | ✅ | ❌ | ❌ |
| q03 | Quels aménagements existent pour un étudiant salarié ou sportif de ha… | ❌ | ❌ | ❌ |
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ❌ | ✅ |
| q05 | Quels aménagements pour un étudiant en situation de handicap ? | ✅ | ✅ | ✅ |
| q06 | Comment trouver un job à côté de mes études ? | ✅ | ✅ | ✅ |
| q07 | Comment obtenir un duplicata de mon diplôme à l'IUT ? | ✅ | ✅ | ✅ |
| q08 | Qu'est-ce que le régime spécial d'études (RSE) ? | ✅ | ✅ | ✅ |
| q09 | Qu'est-ce que la CVEC ? | ✅ | ✅ | ✅ |
| q10 | Quelles sont les modalités de contrôle des connaissances (M3C) en ALL… | ❌ | ❌ | ❌ |
| q11 | Comment fonctionne la compensation des notes en licence ? | ✅ | ✅ | ✅ |
| q12 | Que signifie le sigle BCC ? | ✅ | ✅ | ✅ |
| q13 | Comment s'inscrire administrativement en ligne (IA web) ? | ✅ | ✅ | ✅ |
| q14 | Que dit la charte des examens ? | ✅ | ✅ | ✅ |
| q15 | Quels sont les droits et devoirs figurant dans la charte des étudiant… | ✅ | ✅ | ✅ |
| q16 | Où consulter le calendrier universitaire de la faculté des sciences ? | ✅ | ✅ | ✅ |

## Désaccords sémantique vs BM25

| id | question | trouvé par |
|---|---|---|
| q02 | Puis-je interrompre mes études pendant un an puis les reprendre ? | semantic |
