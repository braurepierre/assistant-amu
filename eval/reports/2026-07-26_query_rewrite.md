# Rapport — réécriture de requête (mesure seule) — 2026-07-26

- Backend LLM (stratégie `llm`) : `mistral/mistral-small-latest` (température 0) | Embeddeur : `intfloat/multilingual-e5-small`
- Jeu « dur » : 25 formulations impératives/conversationnelles (toutes answerable) · jeu « facile » (contrôle de non-régression) : 50 questions answerable.
- `recall@k` = proxy de *context recall* (RAGAS). Réécriture **mesurée, non branchée** dans `/ask` (même esprit que la RRF, §5.1.8 / §5.3.5).
- Stratégies : `raw` (identité, baseline) · `strip` (retrait heuristique de l'ouverture conversationnelle, **déterministe**) · `llm` (réécriture Mistral en requête factuelle, **non déterministe** — chiffres d'un run unique ; lancer à `LLM_TEMPERATURE=0` pour limiter la variance).

## Recall@k par stratégie

### Jeu « dur » (25 questions ; granularité 1/25 ≈ 0.040)

| Stratégie | recall@3 | recall@5 |
|---|---|---|
| raw | 0.48 | 0.72 |
| strip | 0.72 | 0.88 |
| llm | 0.84 | 0.88 |

### Jeu « facile » — contrôle de non-régression (50 questions ; granularité 1/50 ≈ 0.020)

| Stratégie | recall@3 | recall@5 |
|---|---|---|
| raw | 0.82 | 0.86 |
| strip | 0.82 | 0.86 |
| llm | 0.80 | 0.88 |

**Où `llm` régresse (jeu facile, k=3)** — questions récupérées par `raw` mais perdues après réécriture LLM (`strip`, lui, les laisse intactes) :

| id | question d'origine | réécriture `llm` |
|---|---|---|
| q01 | Comment demander une césure à l'université ? | procédure demande césure études universitaires |
| q02 | Puis-je interrompre mes études pendant un an puis les … | Interruption études reprise après un an |
| q03 | Quels aménagements existent pour un étudiant salarié o… | aménagements étudiants salariés ou sportifs de haut ni… |
| q32 | Comment les sessions d'examen sont-elles organisées en… | organisation sessions examen licence ALL |
| q47 | Comment contacter la Mission Handicap de son campus ? | Mission Handicap campus contact |

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
| h09 | Donne-moi les horaires du service de scolarité de l'IUT. | ✅ | ✅ | ✅ |
| h10 | Parle-moi des services proposés aux étudiants de la faculté… | ✅ | ✅ | ✅ |
| h11 | Explique-moi les règles à respecter dans les locaux de l'un… | ✅ | ✅ | ✅ |
| h12 | Je voudrais des infos sur les dates de rentrée à la faculté… | ❌ | ✅ | ✅ |
| h13 | Peux-tu me parler de la charte que l'on signe au moment de … | ❌ | ✅ | ✅ |
| h14 | Dis-moi combien coûtent les droits d'inscription. | ✅ | ✅ | ✅ |
| h15 | Je n'arrive pas à décoder les abréviations employées à l'AL… | ❌ | ❌ | ❌ |
| h16 | Je suis sportif de haut niveau et inscrit en droit, à quoi … | ✅ | ✅ | ✅ |
| h17 | Je suis en licence et j'envisage une pause d'un an avant de… | ❌ | ❌ | ❌ |
| h18 | Où peut-on manger le midi lorsqu'on étudie en droit ? | ✅ | ✅ | ✅ |
| h19 | Je n'ai toujours rien trouvé pour me loger à la rentrée, ex… | ✅ | ✅ | ✅ |
| h20 | On m'a dit que la réinscription se faisait désormais sur in… | ✅ | ✅ | ✅ |
| h21 | En master, de quelle façon les sessions d'examen sont-elles… | ✅ | ✅ | ✅ |
| h22 | Si j'échoue à une matière, les autres notes peuvent-elles l… | ✅ | ✅ | ✅ |
| h23 | En droit, quelles démarches faut-il engager pour obtenir un… | ✅ | ✅ | ✅ |
| h24 | A-t-on le droit d'afficher des messages associatifs dans le… | ✅ | ✅ | ✅ |
| h25 | Au bout de combien de temps les résultats sont-ils affichés… | ✅ | ✅ | ✅ |

## Conclusion

- **Meilleur sur le jeu « dur » : `llm`** — recall@3 0.48 (raw) → 0.84 · recall@5 0.72 (raw) → 0.88.
- Contrôle de non-régression, jeu « facile » : `strip` recall@3 0.82→0.82 (±0 q) · recall@5 0.86→0.86 (±0 q) · `llm` recall@3 0.82→0.80 (-1 q) · recall@5 0.86→0.88 (+1 q).
- **Meilleur rappel sans coût sur le jeu « facile » : `llm`** — exposée en option de `/ask`, le comportement V1 restant le défaut.
- **Réserve opérationnelle.** `llm` coûte **un appel au backend par requête** et n'est pas déterministe : deux exécutions peuvent différer, et le rapport ci-dessus vaut pour un run. `strip`, gratuite et reproductible, obtient recall@3 0.72 · recall@5 0.88 sur le jeu « dur », soit 3 question(s) de moins à k=3 et 0 question(s) de moins à k=5. L'arbitrage se joue donc sur ce que doit coûter une requête, non sur le seul rappel.

> Rappel de granularité (le dénominateur = questions *answerable*) : jeu « dur » = 1 question ≈ 0.040 ; jeu « facile » = 1 question ≈ 0.020. Un écart inférieur à un cran de question n'est pas significatif.

