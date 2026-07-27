# Comparaison avec AnythingLLM — mesures

Cette page réunit les résultats de l'expérience conduite sur la branche
`worktree-compare-anythingllm` et leur commentaire. Le `README.md` de cette
branche n'en conserve que le mode d'emploi ; celui de `main`, une synthèse.

L'expérience situe le pipeline maison face à un produit RAG clé en main, dans
la configuration par défaut de chaque produit. Expérience annexe, hors du
périmètre spécifié du projet : rien n'est intégré au pipeline de production, et
la mesure porte sur le produit tiers tel qu'installé, non sur son plafond de
capacité.

---

## Synthèse des résultats

* **4/4 refus contre 1/4** sur les questions hors-corpus ; **14/16 réponses
  correctes et ancrées contre 0/16** sur les questions répondables.
* La correction des deux réglages par défaut du produit tiers — réponse de
  refus non configurée, échec du scraper sur le gabarit Drupal d'AMU — **ne
  comble pas l'écart** : après correction, toujours 0/4 refus nets, et plus
  aucune réponse pleinement ancrée.
* Une réserve appartient au harnais de ce dépôt : le workspace du produit tiers
  contenait chaque source en double, ce qui ramenait sa profondeur de recherche
  effective de 4 à 2. La mesure n'a pas été rejouée à profondeur corrigée.
* Le jeu de questions (20) et le corpus sont antérieurs aux chiffres de
  référence du projet : cette comparaison ne se lit pas à côté du recall@5
  courant.

---

## Protocole

### 1. Comparaison et constantes

AssistantAMU est confronté à **AnythingLLM v1.15.0** (image Docker officielle
`mintplexlabs/anythingllm`, instance sur `localhost:3001`), dans la
configuration par défaut de chaque produit :

| | assistant-amu | AnythingLLM |
| :--- | :--- | :--- |
| Corpus | 19 sources de `corpus/sources.yaml` (10 PDF, 9 pages web) | les mêmes fichiers et URL, importés tels quels |
| Backend LLM | `mistral-small-latest` | `mistral-small-latest` |
| Profondeur de récupération | `k=5` (défaut) | `topN=4` (défaut) |
| Régime | tour unique | mode de chat `query`, tour unique |

Le modèle est tenu constant des deux côtés : la mesure porte sur l'effet du
pipeline RAG, non sur celui du modèle. Les paramètres de récupération ne sont
pas alignés — comparaison produit contre produit dans son réglage par défaut,
non comparaison de recherche isolée à paramètres égaux.

### 2. Jugement

Les verdicts sont posés par huit agents indépendants, une paire de questions
chacun, sur un barème commun, à l'aveugle : les juges ignorent l'identité des
systèmes et reçoivent les passages réellement lus par chacun. Chaque verdict a
été confronté aux réponses brutes, versionnées avec les rapports. Le volet
« produit configuré » est jugé selon le même dispositif, les réponses avant et
après reconfiguration étant présentées comme systèmes A et B.

---

## Résultats de référence

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus sur 4 questions volontairement hors-corpus | **4/4** | **1/4** |
| Questions répondables (16) — correcte et ancrée | **14/16** | **0/16** |
| — refus à tort | 2/16 | 1/16 |
| — plausible mais non ancrée, ou partiellement ancrée | 0/16 | 13/16 |
| — substantiellement fausse | 0/16 | 2/16 |

> **Réserve sur la profondeur de recherche.** La colonne AnythingLLM a été
> mesurée avec un workspace contenant chaque source en double, ce qui ramenait
> son `topN = 4` à deux textes distincts. Le défaut vient de
> `anythingllm_compare.py ingest`, qui ajoute au workspace sans réconcilier et
> a été exécuté deux fois ; il appartient au harnais de ce dépôt, non au
> produit. Ces chiffres n'ont pas été rejoués à profondeur corrigée.

---

## Produit configuré — mesure avant/après

Deux réglages par défaut du produit tiers dégradent son résultat et ont été
corrigés, pour en mesurer la part dans l'écart :

1. **`queryRefusalResponse` laissé à `null`.** Le mode `query` est censé se
   limiter au contenu du workspace ; faute de réponse de refus configurée, le
   modèle retombe sur ses connaissances générales.
2. **Échec du scraper par défaut sur le gabarit Drupal central d'AMU.** Cinq
   des neuf pages web — toutes sur `www.univ-amu.fr` — sont extraites à un seul
   mot. L'extracteur `bs4` d'assistant-amu traite ces neuf pages sans échec.

Les deux réglages corrigés, les vingt questions ont été reposées et les seize
questions répondables rejugées à l'aveugle avant/après :

| | défaut | configuré |
|---|---|---|
| Refus nets sur les 4 questions hors-corpus | 0/4 | **0/4** |
| Correcte et ancrée, sur 16 | 2/16 | **0/16** |
| Partiellement ancrée | 3/16 | 7/16 |
| Non ancrée (plausible) | 7/16 | 5/16 |
| Substantiellement fausse | 3/16 | 4/16 |

La correction ne comble pas l'écart, pour deux raisons mesurées. Le réglage du
refus est sans effet : en mode `query`, la phrase de refus n'est rendue que si
la recherche ne remonte aucun passage — or elle en remonte quatre, pertinents
ou non. La réimportation des cinq pages ne produit pas davantage d'ancrage :
elles passent de 1 mot à 13 000-18 000, mais le parseur conserve le balisage
HTML, et sur les 24 extraits des six questions que ces pages devaient réparer,
2 en proviennent.

Le décompte avant/après se lit d'ensemble plutôt que question par question :
deux jurys ayant jugé le même run par défaut ne s'accordent que sur 12 verdicts
sur 16, si bien que les déplacements individuels ne sont pas séparables du
bruit de jugement. Ce qui y résiste : les deux réponses pleinement ancrées
disparaissent, l'ancrage partiel passe de 3 à 7.

---

## Accord inter-juges

Les seize questions ont été jugées trois fois, chaque passe changeant une
condition de présentation. Accord sur 29 des 32 couples, soit 91 % ; 31
verdicts sur 32 sont identiques lorsque les étiquettes A et B sont échangées.
Les trois désaccords ne franchissent qu'une catégorie, portent tous sur
AnythingLLM, et aucun chiffre publié ne bouge.

À lire avec sa réserve : le 16/16 d'assistant-amu est un accord bon marché,
quatorze de ses verdicts tombant dans la même catégorie. Le chiffre informatif
est le 13/16 d'AnythingLLM, réparti sur quatre catégories.

---

## Limites

* **Le produit correctement configuré n'est pas mesuré.** La réimportation en
  HTML brut n'est qu'un chemin de correction parmi d'autres, et le résultat
  indique qu'il n'est pas le bon. Ce que donnerait le produit avec un
  connecteur web adapté, ou ces pages fournies en texte, reste inconnu.
* **Les chiffres ne sont pas recoupables avec ceux de `main`.** L'expérience
  porte sur le jeu de 20 questions antérieur au passage à 50, et sur le corpus
  sans les dix distracteurs.
* **Le jury n'est indépendant que d'une manière.** Les trois passes emploient
  le même modèle et le même barème : la mesure établit la stabilité d'un
  verdict quand la présentation change, non la convergence de points de vue
  indépendants.
* **L'anonymisation retire les titres de source** des passages, ce qui prive
  assistant-amu d'une information que son prompt lui fournit en production —
  sans effet sur les questions de contenu, mais le champ `answer_was_available`
  du verdict `q16` n'est pas fiable.
* **La profondeur de recherche corrigée n'a pas été remesurée** sur les
  chiffres de référence (voir la réserve ci-dessus).

---

## Reproduction

La configuration initiale d'AnythingLLM — choix du fournisseur, création du
workspace — n'a pas d'API et se fait à la main, après activation de WSL2 sur un
poste Windows (redémarrage requis). Une fois le workspace en place :

```bash
# .env : ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE_SLUG
python eval/anythingllm_compare.py ingest                        # importe le corpus dans le workspace
python eval/anythingllm_compare.py ask --questions eval/questions.yaml
```

`ingest` ajoute au workspace sans réconcilier : l'exécuter deux fois y laisse
chaque source en double et divise par deux la profondeur de recherche
effective. Vérifier le nombre de documents avant de mesurer — c'est le défaut
qui grève les chiffres de référence ci-dessus.

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
| `2026-07-27_blind_rejudge.md` | Jugement à l'aveugle et ancrage instrumenté |
| `2026-07-27_inter_judge_agreement.md` | Accord inter-juges sur trois passes |
| `2026-07-27_anythingllm_configured.md` | Le produit une fois ses deux réglages corrigés |

Les réponses brutes des deux systèmes et les dossiers de jugement anonymisés
accompagnent ces rapports dans `eval/reports/` (`anythingllm_raw_answers.json`,
`assistant_amu_full_answers.json`, `blind_rejudge/`, `configured_rejudge/`…).
Ils sont versionnés, par exception à la règle qui écarte les données dérivées :
ils sont la base probante des verdicts.
