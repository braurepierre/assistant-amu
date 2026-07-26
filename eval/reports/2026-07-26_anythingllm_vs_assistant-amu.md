# Rapport — comparaison avec AnythingLLM (déploiement par défaut) — 2026-07-26

> **Trois chiffres de ce rapport ont été corrigés le 2026-07-27**, après
> confrontation des verdicts aux réponses brutes :
> `2026-07-27_anythingllm_verdicts_verification.md`. Les cellules concernées sont
> signalées ci-dessous par ⚠. Les valeurs d'origine sont conservées — ce rapport
> est un artefact daté — et le sens du résultat n'en est pas modifié.

- **Expérience annexe**, hors périmètre du PRD contractuel d'AssistantAMU — menée à la demande de l'utilisateur (réf. projet `rag-admin-fr`) pour situer le pipeline maison face à un produit RAG « clé en main ».
- **Corpus identique** : les 19 documents sources de `corpus/sources.yaml` (10 PDF, 9 pages web), importés tels quels dans les deux systèmes — mêmes fichiers, pas de nouveau scraping côté assistant-amu.
- **Backend LLM tenu constant** : `mistral/mistral-small-latest` (API Mistral La Plateforme) des deux côtés, pour isoler l'effet du pipeline RAG plutôt que celui du modèle.
- **Configuration par défaut de chaque produit** conservée (chunking, embeddeur, prompt système, profondeur de récupération — `k=5` côté assistant-amu, `topN=4` côté AnythingLLM) : comparaison **produit contre produit**, pas une comparaison de récupération isolée à paramètres alignés.
- **AnythingLLM v1.15.0**, déploiement Docker officiel (`mintplexlabs/anythingllm`), un workspace dédié, mode de chat `query` (mono-tour, sans historique — l'équivalent le plus proche du régime d'évaluation d'assistant-amu).
- **Jury indépendant** : les verdicts de fidélité (« grounding ») sur les 16 questions répondables ont été posés par 8 agents indépendants (un par paire de questions), à l'aveugle de ma propre lecture — voir `eval/reports/anythingllm_judge_verdicts.json`.

## Vue d'ensemble

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus hors-corpus (4 questions volontairement hors-sujet) | **4/4** corrects | **0/4** corrects ⚠ *(lire 1/4 : q18 refuse sur le fond)* |
| Questions répondables (16) — réponse correcte et ancrée dans le corpus | **14/16** | **0/16** |
| Questions répondables — refus à tort (question répondable mais système muet) | 2/16 | 0/16 ⚠ *(lire 1/16 : q01 est un refus)* |
| Questions répondables — réponse plausible mais non ancrée (« hallucination ») ou partiellement ancrée | 0/16 | 13/16 |
| Questions répondables — réponse substantiellement fausse | 0/16 | 3/16 ⚠ *(lire 2/16 : q01 reclassée)* |

## Refus hors-corpus (4 questions)

| id | question | assistant-amu | AnythingLLM |
|---|---|---|---|
| q17 | Quelle est la capitale de l'Australie ? | ✅ refuse | ❌ « La capitale de l'Australie est **Canberra**. » |
| q18 | Quel temps fera-t-il demain à Marseille ? | ✅ refuse | ❌ redirige vers Météo France (pas un refus net) |
| q19 | Combien coûte un abonnement à un service de streaming vidéo ? | ✅ refuse | ❌ tableau de prix Netflix/Disney+/Canal+… |
| q20 | Peux-tu me donner une recette de ratatouille ? | ✅ refuse | ❌ recette complète (ingrédients, temps de cuisson) |

Le mode `query` d'AnythingLLM est censé se limiter au contenu du workspace, mais son paramètre `queryRefusalResponse` est resté à `null` par défaut : à l'absence de source pertinente, le modèle retombe sur ses connaissances générales au lieu de refuser.

## Questions répondables (16)

| id | question | assistant-amu | AnythingLLM |
|---|---|---|---|
| q01 | Comment demander une césure à l'université ? | ✅ correct, sourcé [S3-S5] | ❌ nie à tort que l'info existe |
| q02 | Puis-je interrompre mes études un an puis les reprendre ? | ⚠️ refuse à tort | ⚠️ plausible mais non ancré (l'admet) |
| q03 | Aménagements étudiant salarié / sportif de haut niveau ? | ✅ correct, cite RSE + SHN-AMU | ⚠️ générique, non spécifique à AMU |
| q04 | Où se loger comme étudiant ? | ✅ correct, sourcé [S4] | ⚠️ admet l'absence d'info, complète en générique |
| q05 | Aménagements handicap ? | ✅ correct, dates 2025-2026 sourcées | ⚠️ liste générique non vérifiable |
| q06 | Trouver un job étudiant ? | ✅ correct (règle SMIC exacte) | ❌ erreur factuelle (SMIC annuel vs mensuel) |
| q07 | Duplicata de diplôme à l'IUT ? | ✅ correct, sourcé [S1,S2] | ⚠️ admet l'absence d'info, procédure inventée |
| q08 | Qu'est-ce que le RSE ? | ✅ correct, sourcé [S1,S3,S4] | ⚠️ nie l'info alors qu'une source s'y consacre |
| q09 | Qu'est-ce que la CVEC ? | ✅ correct, sourcé | ⚠️ détails (montant, site) non vérifiés, l'admet |
| q10 | Modalités M3C en ALLSH ? | ✅ correct, sourcé | 🟡 structure correcte, détails ajoutés non sourcés |
| q11 | Compensation des notes en licence ? | ✅ correct, règle exacte | ❌ mécanisme inventé, contredit la vraie règle |
| q12 | Sigle BCC ? | ✅ correct | 🟡 correct + précisions non vérifiées |
| q13 | Inscription IA web ? | ✅ correct, détails propres à AMU | ⚠️ admet le non-ancrage, URL inventée |
| q14 | Que dit la charte des examens ? | ✅ correct, concis | 🟡 bonne source, chiffres ajoutés invérifiables |
| q15 | Droits et devoirs charte étudiants ? | ✅ correct (AMeTICE, FSDIE…) | ⚠️ liste générique non ancrée |
| q16 | Calendrier faculté des Sciences ? | ⚠️ refuse à tort (source ratée) | 🟡 URL correcte + détails génériques |

✅ correct et sourcé · ⚠️ hallucination plausible (ou refus à tort) · ❌ faux/substantiellement erroné · 🟡 partiellement ancré.

## Constat majeur — fidélité de l'extraction web

Sur les 9 pages web du corpus, le scraper par défaut d'AnythingLLM échoue à extraire un contenu exploitable pour **5 d'entre elles** — toutes situées sur le domaine central `www.univ-amu.fr` (gabarit Drupal différent des sous-domaines de composantes) :

| Page | Mots extraits (AnythingLLM) |
|---|---|
| La césure à AMU | 1 |
| Régime spécial d'études (RSE) | 1 |
| Droits d'inscription et aides financières | 1 |
| Se loger — vie des campus AMU | 1 |
| Mission handicap AMU | 1 |
| ALLSH — modalités M3C | 647 |
| Droit — régimes spéciaux | 400 |
| Sciences — calendriers | 380 |
| IUT — services de la scolarité | 320 |

L'extracteur `bs4` maison d'assistant-amu traite ces 9 pages sans échec. C'est la cause directe des hallucinations sur les questions césure, RSE, logement et handicap (q01-q05, q08) : la source pertinente existe dans le workspace mais n'est qu'une coquille vide, et le modèle comble le vide avec ses connaissances générales plutôt que de refuser.

## Conclusion

- **Verdict net sur ce corpus et cette configuration** : assistant-amu l'emporte largement — refus fiable (4/4 vs 0/4) et zéro hallucination (0/16 vs 13/16 partielles ou totales), au prix de 2 refus par excès de prudence (q02, q16) qui n'induisent jamais l'usager en erreur.
- **Deux causes structurelles, pas une infériorité générale du produit** : (1) l'absence de `queryRefusalResponse` configuré côté AnythingLLM — un réglage d'une ligne aurait probablement corrigé le 0/4 sur les refus ; (2) l'échec du scraper par défaut sur le gabarit Drupal central d'AMU — un connecteur web plus robuste (ou un import de fichiers HTML bruts) aurait probablement comblé une bonne part des 5 échecs d'extraction.
- **Ce que ce rapport ne montre pas** : la performance d'AnythingLLM correctement configuré (refus paramétré, connecteur adapté, éventuellement un autre embeddeur). C'est une comparaison *out-of-the-box*, pas un plafond de capacité produit.
- **Coût de mise en œuvre** : contrairement à `uv venv && uv pip install`, le déploiement Docker d'AnythingLLM a nécessité l'activation de WSL2 (redémarrage machine) — friction absente du côté assistant-amu.

