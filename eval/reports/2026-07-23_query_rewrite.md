# Rapport — réécriture de requête (mesure seule) — 2026-07-23

- Backend LLM (stratégie `llm`) : `mistral/mistral-small-latest` (température 0) | Embeddeur : `intfloat/multilingual-e5-small`
- Jeu « dur » : 8 formulations impératives/conversationnelles (toutes answerable) · jeu « facile » (contrôle de non-régression) : 16 questions answerable.
- `recall@k` = proxy de *context recall* (RAGAS). Réécriture **mesurée, non branchée** dans `/ask` (même esprit que la RRF, §5.1.8 / §5.3.5).
- Stratégies : `raw` (identité, baseline) · `strip` (retrait heuristique de l'ouverture conversationnelle, **déterministe**) · `llm` (réécriture Mistral en requête factuelle, **non déterministe** — chiffres d'un run unique ; lancer à `LLM_TEMPERATURE=0` pour limiter la variance).

## Recall@k par stratégie

### Jeu « dur » (8 questions ; granularité 1/8 ≈ 0.125)

| Stratégie | recall@3 | recall@5 |
|---|---|---|
| raw | 0.38 | 0.62 |
| strip | 0.75 | 0.88 |
| llm | 0.75 | 0.88 |

### Jeu « facile » — contrôle de non-régression (16 questions ; granularité 1/16 ≈ 0.062)

| Stratégie | recall@3 | recall@5 |
|---|---|---|
| raw | 0.88 | 0.94 |
| strip | 0.88 | 0.94 |
| llm | 0.81 | 0.88 |

**Où `llm` régresse (jeu facile, k=3)** — questions récupérées par `raw` mais perdues après réécriture LLM (`strip`, lui, les laisse intactes) :

| id | question d'origine | réécriture `llm` |
|---|---|---|
| q02 | Puis-je interrompre mes études pendant un an puis les … | Interruption études reprise après un an |
| q03 | Quels aménagements existent pour un étudiant salarié o… | aménagements étudiants salariés ou sportifs de haut ni… |

> La réécriture LLM *paraphrase* la question et peut effacer le signal lexical qui la rapprochait du bon document (ex. « interrompre mes études pendant un an » → perte du lien vers « césure »). `strip` ne retire que l'ouverture conversationnelle et ne touche jamais ces questions.

## Avant / après — « Parle-moi des régimes spéciaux »

Cible : la page **définitionnelle centrale** « Régime spécial d'études (RSE) » (distincte de « Droit — Régimes spéciaux d'études », qui, elle, est récupérée dans tous les cas). Rang = position de la page RSE centrale dans le top-8.

| Stratégie | requête effectivement recherchée | RSE centrale récupérée ? |
|---|---|---|
| raw | Parle-moi des régimes spéciaux. | ❌ absente du top-8 |
| strip | régimes spéciaux | ✅ rang 4 |
| llm | régimes spéciaux | ✅ rang 4 |

<details><summary>Top-5 documents récupérés (question phare)</summary>

**raw** — requête : `Parle-moi des régimes spéciaux.`
  1. Droit — Régimes spéciaux d'études
  2. Droit — Régimes spéciaux d'études
  3. Droit — Guide de la vie étudiante 2025
  4. Droit — Guide de la vie étudiante 2025
  5. Droit — Guide de la vie étudiante 2025

**strip** — requête : `régimes spéciaux`
  1. Droit — Régimes spéciaux d'études
  2. IUT — Services de la scolarité
  3. Droit — Régimes spéciaux d'études
  4. Régime spécial d'études (RSE) ⟵ RSE centrale
  5. ALLSH — Cadrage M3C Master 2025-2026

**llm** — requête : `régimes spéciaux`
  1. Droit — Régimes spéciaux d'études
  2. IUT — Services de la scolarité
  3. Droit — Régimes spéciaux d'études
  4. Régime spécial d'études (RSE) ⟵ RSE centrale
  5. ALLSH — Cadrage M3C Master 2025-2026

</details>

## Détail par question — jeu « dur » (k=5)

| id | question | raw | strip | llm |
|---|---|---|---|---|
| h01 | Parle-moi des régimes spéciaux. | ❌ | ✅ | ✅ |
| h02 | Explique-moi la césure. | ✅ | ✅ | ✅ |
| h03 | Dis-moi comment marche la compensation des notes. | ✅ | ✅ | ✅ |
| h04 | Je voudrais des infos sur le contrôle des connaissances. | ❌ | ✅ | ✅ |
| h05 | Raconte-moi les aménagements pour le handicap. | ❌ | ❌ | ❌ |
| h06 | Donne-moi des informations sur le logement étudiant. | ✅ | ✅ | ✅ |
| h07 | Peux-tu me parler de l'inscription administrative en ligne ? | ✅ | ✅ | ✅ |
| h08 | J'aimerais en savoir plus sur la charte des examens. | ✅ | ✅ | ✅ |

## Conclusion

- **Stratégie gagnante : `strip`** — meilleur recall@k sur le jeu « dur » sans dégrader le jeu « facile ».
- Jeu « dur » : recall@3 0.38 (raw) → 0.75 (strip) · recall@5 0.62 (raw) → 0.88 (strip).
- Non-régression (jeu facile) : recall@3 0.88 (raw) vs 0.88 (strip) · recall@5 0.94 (raw) vs 0.94 (strip).
- Verdict de régression (`strip`) : **pas de régression** (écart nul, `strip` est identité sur les questions définitionnelles).
- `llm` écartée bien qu'elle répare le jeu « dur » autant que `strip` (recall@3 0.75 · recall@5 0.88) : elle **déstabilise le jeu facile** — solde recall@3 0.88→0.81 (-1 q) · recall@5 0.94→0.88 (-1 q), mais casse en réalité 2 question(s) définitionnelle(s) qui marchaient (table ci-dessus), n'en regagnant qu'ailleurs. Elle paraphrase, est non déterministe, et coûte un appel LLM par requête — `strip` non.

> Rappel de granularité (le dénominateur = questions *answerable*) : jeu « dur » = 1 question ≈ 0.125 ; jeu « facile » = 1 question ≈ 0.062. Un écart inférieur à un cran de question n'est pas significatif.

