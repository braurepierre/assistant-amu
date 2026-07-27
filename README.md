# AssistantAMU — branche `worktree-compare-anythingllm`

> Cette branche ne porte qu'une expérience annexe, **hors du périmètre spécifié
> du projet**. Pour le projet lui-même — architecture, installation, mesures de
> recherche, périmètre et limites — se reporter au `README.md` de la branche
> `main`, qui fait référence. Ce document ne décrit que ce qui est propre à la
> branche.

L'expérience situe le pipeline maison face à un produit RAG clé en main. Rien
n'en est répercuté dans la branche principale au-delà d'un renvoi, et rien n'est
intégré au pipeline de production.

## Ce qui est comparé, et ce qui est tenu constant

AssistantAMU est confronté à **AnythingLLM v1.15.0** (image Docker officielle
`mintplexlabs/anythingllm`, instance sur `localhost:3001`), dans la
**configuration par défaut de chaque produit** :

| | assistant-amu | AnythingLLM |
| :--- | :--- | :--- |
| Corpus | 19 sources de `corpus/sources.yaml` (10 PDF, 9 pages web) | les **mêmes** fichiers et URL, importés tels quels |
| Backend LLM | `mistral-small-latest` | `mistral-small-latest` |
| Profondeur de récupération | `k=5` (défaut) | `topN=4` (défaut) |
| Régime | tour unique | mode de chat `query`, tour unique |

Le modèle est donc tenu constant des deux côtés : ce qui est mesuré est
l'effet du **pipeline RAG**, non celui du modèle. En revanche les paramètres de
récupération ne sont **pas** alignés — c'est une comparaison produit contre
produit, dans son réglage sorti de la boîte, pas une comparaison de recherche
isolée à paramètres égaux.

## Résultats

Chiffres après la vérification du 27 juillet, qui a confronté chaque verdict aux
réponses réellement produites (`2026-07-27_anythingllm_verdicts_verification.md`).

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus sur 4 questions volontairement hors-corpus | **4/4** | **1/4** |
| Questions répondables (16) — correcte et ancrée | **14/16** | **0/16** |
| — refus à tort | 2/16 | 1/16 |
| — plausible mais non ancrée, ou partiellement ancrée | 0/16 | 13/16 |
| — substantiellement fausse | 0/16 | 2/16 |

> **Réserve établie le 27 juillet.** La colonne AnythingLLM a été mesurée avec un
> workspace contenant chaque source en double, ce qui ramenait son `topN = 4` à
> **deux textes distincts**. Le défaut vient du harnais de ce dépôt, non du
> produit. Ces chiffres n'ont pas été rejoués à profondeur corrigée : ils restent
> un artefact daté.

## Deux causes structurelles, et non une infériorité générale du produit

1. **`queryRefusalResponse` laissé à `null`.** Le mode `query` est censé se
   limiter au contenu du workspace ; faute de réponse de refus configurée, le
   modèle retombe sur ses connaissances générales au lieu de refuser. Un réglage
   d'une ligne aurait probablement corrigé le 0/4.
2. **Échec du scraper par défaut sur le gabarit Drupal central d'AMU.** Cinq des
   neuf pages web — toutes sur `www.univ-amu.fr` — sont extraites à **un seul
   mot**. La source pertinente existe dans le workspace mais n'est qu'une
   coquille vide, et le modèle comble le vide. C'est la cause directe des
   hallucinations sur la césure, le RSE, le logement et le handicap.
   L'extracteur `bs4` d'assistant-amu traite ces neuf pages sans échec.

> **Ces deux causes ont été corrigées et remesurées le 27 juillet
> (`2026-07-27_anythingllm_configured.md`). L'attribution ne tient pas.** Le
> réglage du refus est sans effet mesurable — 0/4 refus nets avant comme après —
> parce qu'il ne couvre que le workspace vide, non la question hors sujet. Le
> défaut d'extraction est bien réel, mais le corriger ne produit aucune réponse
> pleinement ancrée. Les deux points ci-dessus restent le constat exact de ce qui
> a été observé le 26 juillet ; c'est leur portée explicative qui est démentie.

## Ce que ce rapport ne montre pas

- **La performance d'AnythingLLM correctement configuré** — refus paramétré,
  connecteur web adapté, éventuellement un autre embeddeur. Le cadrage est
  *out-of-the-box*, ce n'est pas un plafond de capacité produit. *Deux de ces
  trois réglages ont été corrigés et remesurés depuis :
  `2026-07-27_anythingllm_configured.md`.*
- **Une mesure recoupable avec les chiffres de tête du README.** L'expérience
  porte sur le jeu de **20 questions** antérieur au passage à 50, et sur le
  corpus sans les dix distracteurs. La colonne assistant-amu (14/16, 4/4) se lit
  à sa date, pas à côté du recall@5 courant.
- **Un jugement aveugle.** Les verdicts ont été posés par huit agents
  indépendants, une paire de questions chacun, mais leurs notes **nomment les
  deux systèmes** : devant un écart de 14/16 à 0/16, c'est un biais à nommer.
  Chaque question n'a par ailleurs été jugée qu'une fois — aucun accord
  inter-juges n'est mesurable.
- **La preuve du tableau d'extraction.** Le décompte de mots par page provient
  de la sortie standard de `cmd_ingest`, qui l'imprime sans jamais l'écrire : il
  n'est pas persisté. *Corrigé le 27 juillet : `anythingllm_configured_ingest.json`
  conserve les décomptes avant et après réimportation.*

## Rejouer l'expérience

La configuration initiale d'AnythingLLM — choix du fournisseur, création du
workspace — **n'a pas d'API** et se fait à la main, après activation de WSL2 sur
un poste Windows (redémarrage requis). Une fois le workspace en place :

```bash
# .env : ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE_SLUG
python eval/anythingllm_compare.py ingest                        # importe le corpus dans le workspace
python eval/anythingllm_compare.py ask --questions eval/questions.yaml
```

`ingest` **ajoute** au workspace sans réconcilier : l'exécuter deux fois y laisse
chaque source en double et divise par deux la profondeur de recherche effective.
Vérifier le nombre de documents avant de mesurer.

Le volet « produit configuré » se rejoue ensuite ainsi :

```bash
python eval/anythingllm_retest_configured.py plan     # état du workspace, sans écriture
python eval/anythingllm_retest_configured.py apply    # refus, retrait des doublons, réimportation
python eval/anythingllm_retest_configured.py ask --all
python eval/configured_bundle.py                      # dossiers à l'aveugle avant/après
python eval/blind_rejudge_prompts.py --bundles eval/reports/configured_rejudge/bundles.json \
    --out-dir eval/reports/configured_rejudge/briefs
python eval/configured_tally.py                       # levée de l'aveugle et décomptes
```

Le côté assistant-amu se rejoue par `python eval/evaluate.py --mode end-to-end --k 5`.
Les deux côtés consomment des appels à l'API Mistral.

## Fichiers de cette branche

| Fichier | Contenu |
| :--- | :--- |
| `eval/anythingllm_compare.py` | Pilotage : import du corpus et interrogation du workspace |
| `eval/serialize_retrieved_sources.py` | Récupère les passages lus par assistant-amu, sans appel de modèle |
| `eval/blind_rejudge_bundle.py`, `…_prompts.py` | Construit les dossiers de jugement anonymisés et la clé |
| `eval/blind_rejudge_agreement.py` | Accord inter-juges sur les trois passes |
| `eval/anythingllm_retest_configured.py` | Corrige les réglages, réimporte les cinq pages, repose les questions |
| `eval/configured_bundle.py` | Dossiers de jugement à l'aveugle avant/après reconfiguration |
| `eval/configured_tally.py` | Levée de l'aveugle, décomptes, critères de refus |
| `eval/reports/2026-07-26_anythingllm_vs_assistant-amu.md` | Rapport complet, tableau question par question |
| `eval/reports/2026-07-27_anythingllm_verdicts_verification.md` | Confrontation des verdicts aux réponses brutes |
| `eval/reports/2026-07-27_blind_rejudge.md` | Rejugement à l'aveugle et ancrage instrumenté |
| `eval/reports/2026-07-27_inter_judge_agreement.md` | Accord inter-juges sur trois passes |
| `eval/reports/2026-07-27_anythingllm_configured.md` | Le produit une fois ses deux réglages corrigés |
| `eval/reports/anythingllm_judge_verdicts.json` | Verdicts du jury d'origine |
| `eval/reports/blind_rejudge/` | Dossiers anonymisés, clé, verdicts du jury aveugle |
| `eval/reports/configured_rejudge/` | Dossiers, clé et verdicts du jury avant/après |
| `eval/reports/anythingllm_raw_answers.json` | Réponses brutes d'AnythingLLM, passages inclus |
| `eval/reports/anythingllm_configured_answers.json` | Les 20 réponses du produit reconfiguré |
| `eval/reports/anythingllm_configured_ingest.json` | Journal d'ingestion : refus posé, retraits, décomptes de mots |
| `eval/reports/assistant_amu_full_answers.json` | Réponses brutes d'assistant-amu |
| `eval/reports/assistant_amu_retrieved_sources.json` | Passages récupérés par assistant-amu, par question |

Les deux fichiers de réponses brutes sont versionnés — sans précédent dans le
dépôt, où seuls les rapports `.md` l'étaient — parce qu'ils sont la seule base
probante des verdicts.

## Ce que la vérification des verdicts a corrigé

Les vingt lignes du rapport ont été confrontées aux réponses brutes le
27 juillet. Dix-sept tiennent. **Trois cellules étaient fausses, et les trois
dans le même sens** — au détriment d'AnythingLLM :

- **q01** était comptée « substantiellement fausse ». La réponse ne contient
  aucune affirmation fausse : elle décline et redirige. C'est un refus, comme les
  deux d'assistant-amu — qui sont, eux, comptés `refused_incorrectly`.
- **q18** était comptée comme un échec de refus. La réponse dit ne pas pouvoir
  répondre faute d'information dans les documents, et ne fabrique aucune
  prévision. Le 4/4 d'assistant-amu était établi par `is_refusal()`, le 0/4
  d'AnythingLLM par lecture : deux instruments dans une même case.
- **q15** était classée sans ancrage alors qu'elle cite la charte des étudiants
  et en reprend de la matière réelle. Sans effet sur les chiffres publiés.

Le sens du résultat ne change pas : 4/4 contre 1/4 sur les refus, 14/16 contre
0/16 sur l'ancrage.

## Ce que le rejugement à l'aveugle a établi

Les seize questions ont été rejugées par huit juges indépendants ne connaissant
pas l'identité des systèmes, cette fois **avec les passages fournis à chacun**
(`2026-07-27_blind_rejudge.md`). Deux résultats :

- **La colonne assistant-amu tient et devient vérifiable.** 14/16 correctes et
  ancrées, 2 refus — identique au rapport d'origine, mais désormais établi par
  des juges disposant des fragments réellement lus, et non inféré de la présence
  de marqueurs `[S1]`. C'est le chiffre qui n'avait jamais été instruit.
- **Le biais est confirmé et borné.** Quatre verdicts sur seize diffèrent, trois
  en faveur d'AnythingLLM, un contre. Réel, donc, mais pas systématique.

Le rejugement a aussi **réfuté deux conclusions de la vérification du matin** :
la reclassification proposée pour q15, et le « troisième mode d'échec » annoncé
sur q11 — où le bon document avait bien été remonté, mais pas le fragment portant
la règle. Les deux constats s'appuyaient sur les titres des documents sans ouvrir
le texte des passages.

## Ce que l'accord inter-juges a établi

Les seize questions ont été jugées trois fois, chaque passe changeant une
condition plutôt que rejouant le même prompt — ce qui aurait mesuré le
déterminisme du modèle et non la solidité du jugement
(`2026-07-27_inter_judge_agreement.md`). **Accord sur 29 des 32 couples, soit
91 %.** Le biais de position est nul ou presque : 31 verdicts sur 32 sont
identiques lorsque les étiquettes A et B sont échangées. Les trois désaccords ne
franchissent qu'une catégorie, portent tous sur AnythingLLM, et **aucun chiffre
publié ne bouge**.

À lire avec sa réserve : le 16/16 d'assistant-amu est un accord bon marché,
quatorze de ses verdicts tombant dans la même catégorie. Le chiffre informatif
est le 13/16 d'AnythingLLM, réparti sur quatre catégories.

## Ce que la reconfiguration d'AnythingLLM a établi

Les deux réglages mis en cause ont été corrigés et les vingt questions reposées
(`2026-07-27_anythingllm_configured.md`). Les seize questions répondables ont été
rejugées à l'aveugle par huit juges recevant la réponse *avant* et la réponse
*après* comme systèmes A et B, sans savoir laquelle suit le correctif.

| | défaut | configuré |
|---|---|---|
| Refus nets sur les 4 questions hors-corpus | 0/4 | **0/4** |
| Correcte et ancrée, sur 16 | 2/16 | **0/16** |
| Partiellement ancrée | 3/16 | 7/16 |
| Non ancrée (plausible) | 7/16 | 5/16 |
| Substantiellement fausse | 3/16 | 4/16 |

Trois conclusions, dans l'ordre de ce qu'elles coûtent :

- **Le réglage du refus ne change rien.** Pas une des quatre réponses
  hors-corpus ne bouge de catégorie. En mode `query`, la phrase de refus n'est
  rendue que si la recherche ne remonte **aucun** passage — or elle en remonte
  quatre, pertinents ou non.
- **Réparer l'extraction ne produit pas d'ancrage.** Les cinq pages passent de
  1 mot à 13 000-18 000, mais le parseur conserve le balisage HTML : sur les
  24 extraits des six questions que ces pages devaient réparer, **2** en
  proviennent — contre **10 sur 16** pour les quatre questions hors-corpus. Des
  fragments qui ne ressemblent à rien remontent là où rien ne correspond.
- **Un troisième changement, qui nous appartient.** Le workspace contenait chaque
  source **en double** : `topN = 4` ne rendait que deux textes distincts. Ce
  défaut vient de `anythingllm_compare.py ingest`, exécuté deux fois, et il
  affectait toute la mesure du 26 juillet — dont le 0/16.

Le chiffre à ne pas lire seul est le nombre de questions déplacées. Le jury du
27 juillet et celui de ce rapport ont jugé **le même** run par défaut : ils
s'accordent sur 12 verdicts sur 16. Sept questions déplacées par le correctif,
contre quatre par le seul changement de jury — l'écart n'est pas séparable du
bruit question par question. Ce qui y résiste est d'ensemble : les deux réponses
pleinement ancrées disparaissent, l'ancrage partiel passe de 3 à 7.

## Fil ouvert

Les trois passes emploient le **même modèle et le même barème** : ce qui est
mesuré est la stabilité d'un verdict quand la présentation change, non la
convergence de points de vue indépendants. Un juge humain, ou un modèle d'une
autre famille, dirait seul si le barème lui-même oriente les verdicts.

L'anonymisation retire par ailleurs les titres de source des passages, ce qui
prive assistant-amu d'une information que son prompt lui fournit en production —
sans effet sur les questions de contenu, mais le `answer_was_available` du
verdict q16 n'est pas fiable.

Sur la reconfiguration, deux points restent ouverts. La réimportation en **HTML
brut** n'est qu'un chemin de correction parmi d'autres, et le résultat suggère
qu'il n'est pas le bon : ce que donnerait le produit avec un connecteur web
adapté, ou ces pages fournies en texte, n'est pas mesuré. Et les chiffres du
26 juillet **n'ont pas été rejoués** à profondeur de recherche corrigée : ils
restent un artefact daté, dont on sait désormais qu'il a été mesuré à deux textes
distincts au lieu de quatre.
