# AssistantAMU — branche `worktree-compare-anythingllm`

> Cette branche ne porte qu'une expérience annexe, **hors du périmètre spécifié
> du projet**. Pour le projet lui-même — architecture, installation, mesures de
> recherche, périmètre et limites — se reporter au `README.md` de la branche
> `main`, qui fait référence. Ce document ne décrit que ce qui est propre à la
> branche.

L'expérience situe le pipeline maison face à un produit RAG clé en main,
**AnythingLLM v1.15.0** en déploiement Docker par défaut, à corpus identique et
backend LLM tenu constant des deux côtés. Rien n'en est répercuté dans la branche
principale au-delà d'un renvoi, et rien n'est intégré au pipeline de production.

## Résultat

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus sur 4 questions volontairement hors-corpus | **4/4** | **1/4** |
| Questions répondables (16) — correcte et ancrée | **14/16** | **0/16** |

Trois éléments bornent la lecture de ces chiffres et se lisent avec eux :
l'explication d'abord avancée — deux réglages par défaut du produit tiers — a été
corrigée, remesurée et **n'est pas confirmée** ; le workspace du produit tiers
contenait chaque source en double, ce qui ramenait sa profondeur de recherche
effective de 4 à 2, défaut qui appartient au harnais de ce dépôt et grève la
mesure d'origine ; enfin le jeu de questions et le corpus sont antérieurs aux
chiffres de référence de `main`.

**Protocole, tables, attribution des écarts, solidité des verdicts, limites et
procédure de reprise : [`docs/mesures-anythingllm.md`](docs/mesures-anythingllm.md).**

## Fichiers de cette branche

| Fichier | Contenu |
| :--- | :--- |
| `docs/mesures-anythingllm.md` | Document de mesure — résultats, méthode, limites |
| `eval/anythingllm_compare.py` | Pilotage : import du corpus et interrogation du workspace |
| `eval/serialize_retrieved_sources.py` | Récupère les passages lus par assistant-amu, sans appel de modèle |
| `eval/blind_rejudge_bundle.py`, `…_prompts.py`, `…_agreement.py` | Dossiers de jugement anonymisés, clé, accord inter-juges |
| `eval/anythingllm_retest_configured.py` | Corrige les réglages, réimporte les cinq pages, repose les questions |
| `eval/configured_bundle.py`, `eval/configured_tally.py` | Jugement à l'aveugle avant/après reconfiguration, puis décomptes |
| `eval/reports/` | Cinq rapports datés, les réponses brutes des deux systèmes et les dossiers de jugement — inventaire dans le document de mesure |

## Reprise

La procédure complète, avec les précautions à prendre avant de mesurer, est dans
[`docs/mesures-anythingllm.md`](docs/mesures-anythingllm.md). En bref :

```bash
# .env : ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE_SLUG
python eval/anythingllm_compare.py ingest       # à n'exécuter qu'une fois : voir la réserve
python eval/anythingllm_compare.py ask --questions eval/questions.yaml
python eval/evaluate.py --mode end-to-end --k 5 # côté assistant-amu
```

La configuration initiale d'AnythingLLM n'a pas d'API et se fait à la main.
Les deux côtés consomment des appels à l'API Mistral.
