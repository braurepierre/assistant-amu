# Comparaison avec AnythingLLM — mesures

Cette page réunit les résultats de l'expérience conduite sur la branche
`worktree-compare-anythingllm` et leur commentaire. Le `README.md` de cette
branche n'en conserve que le mode d'emploi ; celui de `main` n'en conserve
qu'une synthèse.

L'expérience situe le pipeline maison face à un produit RAG clé en main.
**Expérience annexe, hors du périmètre spécifié du projet** : rien n'en est
répercuté dans la branche principale au-delà d'un renvoi, et rien n'est intégré
au pipeline de production. Ce qui est mesuré est un produit tiers *out-of-the-box*,
non une infériorité intrinsèque de celui-ci.

---

## Synthèse des résultats

* **L'écart mesuré est net.** 4/4 refus contre 1/4 sur les questions hors-corpus,
  14/16 réponses correctes et ancrées contre 0/16 sur les questions répondables.
* **La colonne assistant-amu est établie, pas inférée.** Le 14/16 a été rejugé à
  l'aveugle par des juges disposant des passages réellement lus, et non déduit de
  la présence de marqueurs de source.
* **L'explication d'abord avancée ne tient pas.** Deux réglages par défaut du
  produit tiers étaient tenus pour la cause de l'écart ; corrigés et remesurés,
  ils ne le comblent pas.
* **Une cause appartient au harnais de ce dépôt.** Le workspace du produit tiers
  contenait chaque source en double, ce qui ramenait sa profondeur de recherche
  effective de 4 à 2 — y compris lors de la mesure d'origine, qui n'a pas été
  rejouée à profondeur corrigée.
* **La portée reste bornée.** Le jeu de questions et le corpus sont antérieurs
  aux chiffres de référence du projet : cette comparaison ne se lit pas à côté du
  recall@5 courant.

---

## Protocole

### 1. Comparaison et constantes

AssistantAMU est confronté à **AnythingLLM v1.15.0** (image Docker officielle
`mintplexlabs/anythingllm`, instance sur `localhost:3001`), dans la
**configuration par défaut de chaque produit** :

| | assistant-amu | AnythingLLM |
| :--- | :--- | :--- |
| Corpus | 19 sources de `corpus/sources.yaml` (10 PDF, 9 pages web) | les **mêmes** fichiers et URL, importés tels quels |
| Backend LLM | `mistral-small-latest` | `mistral-small-latest` |
| Profondeur de récupération | `k=5` (défaut) | `topN=4` (défaut) |
| Régime | tour unique | mode de chat `query`, tour unique |

Le modèle est donc tenu constant des deux côtés : ce qui est mesuré est l'effet
du **pipeline RAG**, non celui du modèle. En revanche les paramètres de
récupération ne sont **pas** alignés — c'est une comparaison produit contre
produit, dans son réglage sorti de la boîte, pas une comparaison de recherche
isolée à paramètres égaux.

### 2. Jury

Les verdicts sont posés par huit agents indépendants, une paire de questions
chacun, sur un barème commun. Trois régimes de jugement se sont succédé et sont
distingués dans ce document : le jury d'origine, **nommant les deux systèmes** ;
un jury **aveugle** recevant les passages réellement lus ; et un jury aveugle
**avant/après** reconfiguration du produit tiers.

---

## Résultats de référence

Chiffres établis après confrontation de chaque verdict aux réponses réellement
produites.

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus sur 4 questions volontairement hors-corpus | **4/4** | **1/4** |
| Questions répondables (16) — correcte et ancrée | **14/16** | **0/16** |
| — refus à tort | 2/16 | 1/16 |
| — plausible mais non ancrée, ou partiellement ancrée | 0/16 | 13/16 |
| — substantiellement fausse | 0/16 | 2/16 |

> **Réserve sur la profondeur de recherche.** La colonne AnythingLLM a été
> mesurée avec un workspace contenant chaque source **en double**, ce qui
> ramenait son `topN = 4` à **deux textes distincts**. Le défaut vient de
> `anythingllm_compare.py ingest`, qui ajoute au workspace sans réconcilier et a
> été exécuté deux fois ; il n'appartient donc pas au produit mais au harnais de
> ce dépôt. Ces chiffres **n'ont pas été rejoués** à profondeur corrigée : ils
> restent un artefact daté.

---

## Attribution des écarts

### 1. Hypothèse d'origine

Deux réglages par défaut du produit tiers ont d'abord été tenus pour la cause de
l'essentiel de l'écart :

1. **`queryRefusalResponse` laissé à `null`.** Le mode `query` est censé se
   limiter au contenu du workspace ; faute de réponse de refus configurée, le
   modèle retombe sur ses connaissances générales au lieu de refuser.
2. **Échec du scraper par défaut sur le gabarit Drupal central d'AMU.** Cinq des
   neuf pages web — toutes sur `www.univ-amu.fr` — sont extraites à **un seul
   mot**. La source pertinente existe dans le workspace mais n'est qu'une
   coquille vide. L'extracteur `bs4` d'assistant-amu traite ces neuf pages sans
   échec.

Ces deux constats décrivent exactement ce qui a été observé. C'est leur **portée
explicative** qui a été mise à l'épreuve.

### 2. Mesure après correction

Les deux réglages ont été corrigés, les vingt questions reposées, et les seize
questions répondables rejugées à l'aveugle par huit juges recevant la réponse
*avant* et la réponse *après* comme systèmes A et B, sans savoir laquelle suit le
correctif.

| | défaut | configuré |
|---|---|---|
| Refus nets sur les 4 questions hors-corpus | 0/4 | **0/4** |
| Correcte et ancrée, sur 16 | 2/16 | **0/16** |
| Partiellement ancrée | 3/16 | 7/16 |
| Non ancrée (plausible) | 7/16 | 5/16 |
| Substantiellement fausse | 3/16 | 4/16 |

**L'attribution n'est pas confirmée.** Le réglage du refus est sans effet
mesurable : pas une des quatre réponses hors-corpus ne change de catégorie, parce
qu'en mode `query` la phrase de refus n'est rendue que si la recherche ne remonte
**aucun** passage — or elle en remonte quatre, pertinents ou non. Réparer
l'extraction ne produit pas davantage d'ancrage : les cinq pages passent de 1 mot
à 13 000-18 000, mais le parseur conserve le balisage HTML, et sur les 24 extraits
des six questions que ces pages devaient réparer, **2** en proviennent — contre
**10 sur 16** pour les quatre questions hors-corpus.

### 3. Portée du décompte avant/après

Le nombre de questions déplacées ne se lit pas seul. Le jury du rejugement à
l'aveugle et celui de ce volet ont jugé **le même** run par défaut : ils
s'accordent sur 12 verdicts sur 16. Sept questions sont déplacées par le
correctif, contre quatre par le seul changement de jury — l'écart n'est pas
séparable du bruit question par question. Ce qui y résiste est d'ensemble : les
deux réponses pleinement ancrées disparaissent, l'ancrage partiel passe de 3
à 7.

---

## Solidité des verdicts

### 1. Vérification sur les réponses brutes

Les vingt lignes du rapport d'origine ont été confrontées aux réponses réellement
produites. Dix-sept tiennent. **Trois cellules étaient fausses, et les trois dans
le même sens**, au détriment d'AnythingLLM : une réponse qui décline et redirige
comptée « substantiellement fausse » alors que c'est un refus ; un refus compté
comme échec de refus, le verdict d'assistant-amu étant établi par la fonction
`is_refusal()` et celui d'AnythingLLM par lecture — deux instruments dans une
même case ; une réponse classée sans ancrage alors qu'elle cite la charte des
étudiants. Le sens du résultat ne change pas.

### 2. Rejugement à l'aveugle

Les seize questions ont été rejugées par huit juges ignorant l'identité des
systèmes, **avec les passages fournis à chacun**. Deux résultats : la colonne
assistant-amu tient et **devient vérifiable** — 14/16 correctes et ancrées,
2 refus, désormais établis par des juges disposant des fragments réellement lus
plutôt qu'inférés de la présence de marqueurs `[S1]` ; et le biais de nommage est
**confirmé et borné** — quatre verdicts sur seize diffèrent, trois en faveur
d'AnythingLLM, un contre.

Ce rejugement a réfuté deux constats intermédiaires, tous deux appuyés sur les
titres des documents sans ouvrir le texte des passages : une reclassification
proposée pour `q15`, et un troisième mode d'échec annoncé sur `q11`, où le bon
document avait bien été remonté mais pas le fragment portant la règle.

### 3. Accord inter-juges

Les seize questions ont été jugées trois fois, chaque passe changeant une
condition plutôt que rejouant le même prompt — ce qui aurait mesuré le
déterminisme du modèle et non la solidité du jugement. **Accord sur 29 des
32 couples, soit 91 %.** Le biais de position est nul ou presque : 31 verdicts
sur 32 sont identiques lorsque les étiquettes A et B sont échangées. Les trois
désaccords ne franchissent qu'une catégorie, portent tous sur AnythingLLM, et
aucun chiffre publié ne bouge.

À lire avec sa réserve : le 16/16 d'assistant-amu est un accord bon marché,
quatorze de ses verdicts tombant dans la même catégorie. Le chiffre informatif
est le 13/16 d'AnythingLLM, réparti sur quatre catégories.

---

## Limites

* **Le produit correctement configuré n'est pas mesuré.** Le cadrage est
  *out-of-the-box* ; ce n'est pas un plafond de capacité produit. Deux réglages
  sur trois ont été corrigés depuis, mais la réimportation en **HTML brut** n'est
  qu'un chemin de correction parmi d'autres, et le résultat suggère qu'il n'est
  pas le bon. Ce que donnerait le produit avec un connecteur web adapté, ou ces
  pages fournies en texte, reste inconnu.
* **Les chiffres ne sont pas recoupables avec ceux de `main`.** L'expérience
  porte sur le jeu de **20 questions** antérieur au passage à 50, et sur le corpus
  sans les dix distracteurs. La colonne assistant-amu (14/16, 4/4) se lit à sa
  date, pas à côté du recall@5 courant.
* **Le jury n'est indépendant que d'une manière.** Les trois passes emploient le
  **même modèle et le même barème** : ce qui est mesuré est la stabilité d'un
  verdict quand la présentation change, non la convergence de points de vue
  indépendants. Un juge humain, ou un modèle d'une autre famille, dirait seul si
  le barème lui-même oriente les verdicts.
* **L'anonymisation retire les titres de source** des passages, ce qui prive
  assistant-amu d'une information que son prompt lui fournit en production — sans
  effet sur les questions de contenu, mais le champ `answer_was_available` du
  verdict `q16` n'est pas fiable.
* **La profondeur de recherche corrigée n'a pas été remesurée** sur les chiffres
  de référence (voir la réserve ci-dessus).

---

## Reproduction

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
Vérifier le nombre de documents avant de mesurer — c'est le défaut qui grève les
chiffres de référence ci-dessus.

Le volet « produit configuré » se rejoue ainsi :

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

---

## Index des rapports datés

| Rapport | Objet |
| :--- | :--- |
| `2026-07-26_anythingllm_vs_assistant-amu.md` | Mesure d'origine, tableau question par question |
| `2026-07-27_anythingllm_verdicts_verification.md` | Confrontation des verdicts aux réponses brutes |
| `2026-07-27_blind_rejudge.md` | Rejugement à l'aveugle et ancrage instrumenté |
| `2026-07-27_inter_judge_agreement.md` | Accord inter-juges sur trois passes |
| `2026-07-27_anythingllm_configured.md` | Le produit une fois ses deux réglages corrigés |

Les réponses brutes des deux systèmes et les dossiers de jugement anonymisés
accompagnent ces rapports dans `eval/reports/` (`anythingllm_raw_answers.json`,
`assistant_amu_full_answers.json`, `blind_rejudge/`, `configured_rejudge/`…).
**Ces fichiers sont versionnés par exception** à la règle qui écarte les données
dérivées, parce qu'ils sont la seule base probante des verdicts — le même
arbitrage que celui retenu sur `main` pour `corpus/contexts.jsonl`.
