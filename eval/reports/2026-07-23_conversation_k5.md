# Rapport d'évaluation — conversation (V2) — 2026-07-23

- Backend LLM : `mistral/mistral-small-latest` | k = 5
- Recall des tours answerable : 3/6

| scénario | tour | question | question condensée | recall | refus | condensation OK (man.) | fidélité (man.) |
|---|---|---|---|---|---|---|---|
| s1_cesure_droit | 1 | Quelles sont les modalités de la césure… | — | ❌ | — |  |  |
| s1_cesure_droit | 2 | Et pour un étudiant en droit ? | Quelles sont les modalités de la césure… | ❌ | — |  |  |
| s2_rse_salarie | 1 | Qu'est-ce que le régime spécial d'étude… | — | ✅ | — |  |  |
| s2_rse_salarie | 2 | Et pour un étudiant salarié ? | Quels aménagements spécifiques le Régim… | ✅ | — |  |  |
| s3_inscription_droits | 1 | Comment s'inscrire administrativement e… | — | ✅ | — |  |  |
| s3_inscription_droits | 2 | Et quels en sont les droits à payer ? | Quels sont les droits à payer pour l'in… | ❌ | — |  |  |

> Colonnes *condensation OK* et *fidélité* : jugement manuel (§7.7).
