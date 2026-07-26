# Rapport — Contextual Retrieval (mesure seule) — 2026-07-26

- Embeddeur : `intfloat/multilingual-e5-small` · collections comparées : `amu_docs_440` (baseline) vs `amu_docs_440_ctx` (contextuelle) · 332 fragments de part et d'autre.
- Contextes générés : 332/332 fragments, 25.2 mots en moyenne (maximum 45). Prompt : `prompts/context_system.md`.
- Les deux index de la collection contextuelle sont contextuels : les embeddings **et** BM25 sont calculés sur le fragment préfixé — c'est la configuration à laquelle Anthropic attribue −49 % d'échecs de recherche.
- Mesure seule : `/ask` reste branché sur la collection de production (même esprit que la RRF et la réécriture, §5.1.8 / §5.3.5).

> **Règle de comptage.** Le contexte généré nomme presque toujours le sujet du fragment qu'il préfixe. Or le jeu « facile » exige la présence de mots-clés *dans le fragment récupéré* : compter sur le texte contextualisé reviendrait à valider « la phrase de contexte dit *césure* » comme une réussite de recherche. Le contexte sert donc à **trouver** le fragment, jamais à **prouver** la réussite : après classement, le texte de chaque fragment est ramené à sa version d'origine (`metadata["text_raw"]`) avant le test. L'ampleur de l'artefact évité est chiffrée plus bas.

## Recall@k — baseline contre contextuel

### Jeu « dur » (formulations conversationnelles) (25 questions ; 1 question ≈ 0.040)

| Méthode | baseline k=3 | contextuel k=3 | Δ k=3 | baseline k=5 | contextuel k=5 | Δ k=5 |
|---|---|---|---|---|---|---|
| semantic | 0.48 | 0.72 | +0.24 (+6 q) | 0.72 | 0.84 | +0.12 (+3 q) |
| bm25 | 0.72 | 0.60 | -0.12 (-3 q) | 0.84 | 0.76 | -0.08 (-2 q) |
| rrf | 0.76 | 0.80 | +0.04 (+1 q) | 0.88 | 0.80 | -0.08 (-2 q) |

### Jeu « facile » (formulations définitionnelles) (16 questions ; 1 question ≈ 0.062)

| Méthode | baseline k=3 | contextuel k=3 | Δ k=3 | baseline k=5 | contextuel k=5 | Δ k=5 |
|---|---|---|---|---|---|---|
| semantic | 0.88 | 0.81 | -0.06 (-1 q) | 0.94 | 0.81 | -0.12 (-2 q) |
| bm25 | 0.75 | 0.75 | ±0 | 0.81 | 0.81 | ±0 |
| rrf | 0.88 | 0.88 | ±0 | 0.88 | 0.88 | ±0 |

## Ce que coûterait un comptage naïf

Mêmes classements, même index contextuel : seule change la version du texte sur laquelle les mots-clés attendus sont cherchés (jeu « facile », seul à porter des `expected_keywords`).

| Méthode | strict k=3 | naïf k=3 | écart | strict k=5 | naïf k=5 | écart |
|---|---|---|---|---|---|---|
| semantic | 0.81 | 0.81 | ±0 | 0.81 | 0.81 | ±0 |
| bm25 | 0.75 | 0.75 | ±0 | 0.81 | 0.81 | ±0 |
| rrf | 0.88 | 0.88 | ±0 | 0.88 | 0.88 | ±0 |

> L'écart mesure exactement la part de « réussite » qu'un comptage naïf aurait attribuée à la contextualisation sans qu'aucun fragment ne soit mieux trouvé. C'est le résultat méthodologique de cette expérience.

## Détail par question — jeu « dur » (k=5)

**semantic** — gagnées : 4 · perdues : 1

| id | question | baseline | contextuel |
|---|---|---|---|
| h04 | Je voudrais des infos sur le contrôle des connaissances. | ❌ | ✅ |
| h12 | Je voudrais des infos sur les dates de rentrée à la faculté… | ❌ | ✅ |
| h15 | Je n'arrive pas à décoder les abréviations employées à l'AL… | ❌ | ✅ |
| h20 | On m'a dit que tout se faisait sur internet désormais pour … | ❌ | ✅ |
| h17 | Je suis en licence et j'envisage une pause d'un an avant de… | ✅ | ❌ |

**bm25** — gagnées : 1 · perdues : 3

| id | question | baseline | contextuel |
|---|---|---|---|
| h22 | Si je rate une matière, est-ce que les autres notes peuvent… | ❌ | ✅ |
| h01 | Parle-moi des régimes spéciaux. | ✅ | ❌ |
| h04 | Je voudrais des infos sur le contrôle des connaissances. | ✅ | ❌ |
| h17 | Je suis en licence et j'envisage une pause d'un an avant de… | ✅ | ❌ |

**rrf** — gagnées : 1 · perdues : 3

| id | question | baseline | contextuel |
|---|---|---|---|
| h16 | Je suis sportif de haut niveau et inscrit en droit, à quoi … | ❌ | ✅ |
| h01 | Parle-moi des régimes spéciaux. | ✅ | ❌ |
| h13 | Peux-tu me parler de la charte que l'on signe au moment de … | ✅ | ❌ |
| h20 | On m'a dit que tout se faisait sur internet désormais pour … | ✅ | ❌ |

## Détail par question — jeu « facile » (k=5)

**semantic** — gagnées : 1 · perdues : 3

| id | question | baseline | contextuel |
|---|---|---|---|
| q04 | Où puis-je me loger en tant qu'étudiant ? | ❌ | ✅ |
| q02 | Puis-je interrompre mes études pendant un an puis les repre… | ✅ | ❌ |
| q03 | Quels aménagements existent pour un étudiant salarié ou spo… | ✅ | ❌ |
| q05 | Quels aménagements pour un étudiant en situation de handica… | ✅ | ❌ |

## Question phare — « Parle-moi des régimes spéciaux »

Cible : la page définitionnelle centrale « Régime spécial d'études (RSE) ». Rang dans le top-8 (`—` = absente).

| Index | sémantique | BM25 |
|---|---|---|
| baseline | — (absente du top-8) | rang 2 |
| contextuel | rang 7 | — (absente du top-8) |

## Diagnostic — le préfixe tient-il dans la fenêtre de 512 tokens ?

Le contexte s'ajoute au budget de tokens du fragment : 25.2 mots en moyenne ici. Un fragment déjà proche de la fenêtre de l'encodeur en sort donc, et **rien ne le signale à l'exécution** — le contexte est lu, la fin du fragment ne l'est pas. Ce contrôle vérifie que les écarts mesurés plus haut ne sont pas cet artefact.

| Collection | fragments hors fenêtre | part | plus long fragment | tokens perdus |
|---|---|---|---|---|
| baseline | 0 | 0% | 438 | 0 |
| contextuelle | 0 | 0% | 475 | 0 |

> **Artefact écarté.** Aucun fragment ne déborde de la fenêtre, ni avant ni après contextualisation (le plus long atteint 475 tokens sur 512). Le préfixe tient dans le budget : aucun écart mesuré plus haut ne peut être imputé à une troncature silencieuse.

<details><summary>Exemple de contexte généré (longueur médiane)</summary>

> Cadrage ALLSH — M3C Master 2025-2026, partie « Niveau 2 : Précisions du cadrage propres à l’UFR ALLSH » — Liste des absences justifiées et motifs d’absence.

</details>

## Conclusion

- Sur ce corpus et ce jeu d'évaluation, la contextualisation **gagne nettement plus qu'elle ne perd** (6 questions contre 3).
- **Ce qu'elle répare** : les formulations conversationnelles en recherche sémantique — jeu « dur », `semantic` à k=3, +0.24 (+6 questions). C'est le mode d'échec que la méthode vise : un fragment que rien ne rattachait à son sujet devient retrouvable.
- **Ce qu'elle casse** : les formulations définitionnelles — jeu « facile », `semantic` à k=5, -0.12 (-2 questions). Ces questions fonctionnaient déjà ; le préfixe déplace le vecteur du fragment vers le sujet du *document* et l'éloigne de son contenu propre.
- Sur le jeu « dur », le pire écart est -0.12 (-3 question, `bm25` à k=3) ; sur le jeu « facile », le meilleur est +0.00 (+0 question, `bm25` à k=3).
- La troncature est écartée : aucun fragment ne sort de la fenêtre de 512 tokens, ni avant ni après contextualisation. L'écart mesuré porte donc bien sur la méthode elle-même.
- Artefact évité par le comptage strict : jusqu'à +0.00 de recall (+0 question) qu'un comptage naïf aurait crédité à la contextualisation sans qu'aucun fragment ne soit mieux trouvé.
- Rappel de granularité : le jeu « dur » compte 25 questions (1 question ≈ 0.040) et le jeu « facile » 16 (1 question ≈ 0.062). Les chiffres d'Anthropic portent sur des corpus de plusieurs milliers de fragments et une évaluation à l'échelle : un écart d'une question ici ne les confirme ni ne les infirme.

**Décision.** `/ask` reste, à ce stade, sur la collection de production : la contextualisation demeure mesurée et non branchée, comme la RRF et la réécriture. L'arbitrage est ici établi sans confusion possible avec la troncature — le préfixe déplace le vecteur du fragment vers le sujet de son document, ce qui sert les formulations vagues et dessert les questions précises. Reste à trancher, au vu du rapport ci-dessus entre questions gagnées et perdues, laquelle des deux populations `/ask` doit servir en priorité — et si une contextualisation *sélective*, limitée aux fragments réellement décontextualisés, ne prendrait pas les deux.

