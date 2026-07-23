# AssistantAMU

Assistant documentaire **RAG** (Retrieval-Augmented Generation) construit sur les
documents publics d'Aix-Marseille Université (règlements de scolarité, guides
étudiants, pages des composantes). On lui pose une question en français, il répond
en **citant les passages sources** et **refuse explicitement** de répondre quand
l'information est absente du corpus.

Le système est **LLM-agnostique** (backend local Ollama ↔ API Mistral, commutable
par variable d'environnement) et livré avec un **harnais d'évaluation
reproductible** comparant recherche sémantique, BM25 et leur fusion RRF.

> Développé d'après un PRD versionné ([`PRD-AssistantAMU-V1_3.md`](PRD-AssistantAMU-V1_3.md)),
> en Python pur (le pipeline d'abord, le framework ensuite — voir le port
> LangChain). Objectif : pouvoir expliquer **chaque brique**.

## Pourquoi RAG plutôt que « tout mettre dans le contexte » ?

Anthropic recommande, pour une base < ~200 000 tokens, de placer tout le corpus
dans le prompt (avec prompt caching) plutôt que de faire du RAG. Le RAG reste le
bon choix ici, pour quatre raisons : (1) maîtriser le RAG de bout en bout est
l'objectif du projet ; (2) le
backend local est contraint — Ollama sert `mistral` avec une fenêtre réduite par
défaut (voir *piège n°3*) ; (3) coût/latence d'un contexte massif à chaque requête
incompatibles avec un CPU et un free tier ; (4) les **citations passage par
passage**, cœur du produit, sont natives en RAG.

## Architecture

```
INDEXATION (hors ligne)
sources.yaml → download → extract (pdfplumber/bs4) → clean → chunk (≤ 500 tk, ov. 50)
     → embed ("passage: " + texte, e5-small) → ChromaDB (cosine)
     → [pour l'éval : index BM25 en mémoire depuis les mêmes chunks]

REQUÊTE V1 (temps réel)
question → embed ("query: " + question) → ChromaDB top-k
     → prompt RAG (règles en système ; sources XML puis question en user)
     → LLMBackend.generate → réponse + sources
```

### Deux pièges documentés et neutralisés

1. **Préfixes E5** — les modèles E5 exigent `"query: "` (questions) et
   `"passage: "` (chunks) ; sans eux les performances chutent silencieusement.
   `embedder.py` porte une table {famille → préfixes} et n'applique **aucun**
   préfixe à `sentence-camembert-base` (comparaison Phase 5).
2. **Métrique ChromaDB** — la collection est créée avec
   `metadata={"hnsw:space": "cosine"}` (Chroma est en L2 par défaut).
3. **`num_ctx` Ollama** — Ollama tronque le prompt à `num_ctx` (souvent 2048/4096),
   pas à la capacité du modèle, **sans erreur**. `OLLAMA_NUM_CTX=8192` par défaut.

## Stack

| Composant | Choix |
|---|---|
| Langage | Python ≥ 3.11 (développé/testé sous 3.12) |
| Embeddings | `sentence-transformers` + `intfloat/multilingual-e5-small` |
| Base vectorielle | `chromadb` (persistant local, cosinus) |
| Recherche lexicale | `rank_bm25` (comparaison d'évaluation) |
| LLM local | Ollama (`mistral` 7B) |
| LLM API | Mistral La Plateforme (`mistral-small-latest`) |
| Extraction | `pdfplumber` (+ `docling` en escalade), `beautifulsoup4` |
| API | `fastapi` + `uvicorn` + `pydantic` v2 |
| Tests | `pytest` (aucun test n'appelle un vrai LLM ni le réseau) |

## Installation

Prérequis : Python ≥ 3.11 ; pour le backend local, [Ollama](https://ollama.com)
avec `ollama pull mistral`.

```bash
# Avec uv (recommandé — gère aussi la version de Python)
uv venv --python 3.12
uv pip install -e ".[dev]"

# Ou avec pip standard
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env    # renseigner MISTRAL_API_KEY si backend API
pytest
```

## Utilisation

```bash
# 1. Constituer corpus/sources.yaml (15-30 URLs), puis :
python -m assistant_amu.ingestion.download          # télécharge dans corpus/raw/
python -m assistant_amu.ingestion stats             # documents/exclusions/chunks
python -m assistant_amu.ingestion dump -n 5         # inspection visuelle des chunks
python -m assistant_amu.ingestion index             # embeddings → ChromaDB (idempotent)
python -m assistant_amu.ingestion search "césure ?" # top-k (contrôle de pertinence)

# 2. Question de bout en bout (retrieval + génération)
python -m assistant_amu.generation ask "Quelles sont les modalités de césure ?"

# 3. API
uvicorn assistant_amu.api.main:app --reload         # docs interactives sur /docs

# 4. Évaluation
python eval/evaluate.py --mode retrieval --method all --k 5
python eval/evaluate.py --mode end-to-end --k 5
python eval/evaluate.py --mode retrieval --embedding-model dangvantuan/sentence-camembert-base
```

Basculer de backend : `LLM_BACKEND=mistral` (API) ou `ollama` (local) dans `.env`.

## API (contrats)

| Endpoint | Rôle |
|---|---|
| `POST /ask` | `{question, k}` → `{answer, sources[], model, retrieved_chunks, condensed_question}` ; `503` si backend indisponible |
| `POST /ingest` | multipart (`file`, `title`, `url?`, `category?`) → `{document_id, chunks_added}` ; `409` si doublon |
| `GET /health` | `{chroma, llm_backend, documents, chunks}` |

## Évaluation

Le harnais mesure le **recall@k** (proxy de *context recall*, terminologie RAGAS)
pour trois méthodes — sémantique, BM25 et leur fusion **RRF** — et produit un
rapport Markdown daté dans `eval/reports/`, avec une section « désaccords »
(questions où une seule méthode trouve le bon chunk). La fusion RRF est **mesurée
seulement** ; le pipeline `/ask` reste sémantique pur en V1.

> **Baseline** (2026-07-23 — corpus 18 docs / 316 chunks, 16 questions, k=5) :
> recall@5 **sémantique 0.94**, **BM25 0.81**, **RRF 0.88**. Obtenue après un
> raffinage **diagnostiqué** (0.81 → 0.94) : q03 était une annotation trop stricte
> (le chunk RSE dit « RSE », pas « régime spécial »), q10 une **lacune de données**
> (la page M3C n'était qu'un index de liens → ajout des PDF « Cadrage M3C »). La
> seule question que le sémantique rate encore (q04, logement) est **récupérée par
> la RRF** — argument concret pour l'hybride, laissé tel quel plutôt que gonflé.
> Courbe recall@k ∈ {2,3,5,8} et détail par question : `eval/reports/`.

**Comparaison d'embeddeurs** (recall@k sémantique, mêmes 16 questions et mêmes
chunks, mesure seule — le pipeline `/ask` garde l'embeddeur de production) :

| Embeddeur | @3 | @5 | @8 |
|---|---|---|---|
| `intfloat/multilingual-e5-small` (production, 384 dims) | 0.88 | 0.94 | 0.94 |
| `dangvantuan/sentence-camembert-base` (768 dims) | 0.81 | 0.94 | **1.00** |
| `hugorosen/flaubert_base_uncased-xnli-sts` (768 dims) | 0.81 | 0.81 | 0.94 |

e5 et CamemBERT sont **à égalité en moyenne (0.92)** : CamemBERT récupère tout au
rang 8, e5 est le plus régulier — et le plus léger. FlauBERT est en retrait,
surtout sur les sigles/définitions (rate RSE et CVEC). Les écarts (1-2 questions
≈ granularité 0.06) ne justifient pas de changer l'embeddeur de production. Le
modèle *cased* `Lajavaness/sentence-flaubert-base` ne se charge pas sous
sentence-transformers 5.6.1 (tokenizer Moses sans `basic_tokenizer`), d'où la
variante *uncased*. Script : `eval/embedder_comparison.py`, rapport daté dans
`eval/reports/`.

**End-to-end & latences par backend** (mesuré le 2026-07-23, corpus réel) :

| Backend | Latence `/ask` | Refus (end-to-end) |
|---|---|---|
| Mistral API (`mistral-small-latest`) | ~3 s/question | **4/4** questions hors-corpus refusées correctement |
| Ollama local (mistral 7B, CPU) | > 120 s à `num_ctx=8192`/`k=5` (timeout géré) ; ~190 s à chaud avec repli `num_ctx=4096`/`k=3` | — |

Sur cette machine (CPU), Ollama est lent : conforme à l'arbitrage du PRD
(*développer sur l'API, démontrer en local*) et au repli documenté `num_ctx=4096`,
`k≤5`. Le dépassement de délai remonte proprement en `LLMBackendError(timeout)`
→ `503` (F5). Rapport : `eval/reports/2026-07-23_end-to-end_k5.md`.

## Périmètre et limites (assumés)

Pas d'authentification, pas de déploiement/Docker/CI, pas de streaming, pas de
reranking ni de recherche hybride dans `/ask` (RRF est mesuré, pas branché), pas
d'OCR (PDF scannés exclus et signalés), français uniquement. Ce sont des choix
de périmètre (§3 du PRD), pas des oublis. Évolutions futures documentées :
**Contextual Retrieval** (candidate n°1 pour une V2.1), bascule hybride si les
chiffres la justifient, reranking cross-encoder, évaluation RAGAS automatisée.

## Feuille de route

- [x] **Phase 0** — Squelette
- [x] **Phase 1** — Corpus & ingestion (F1, F2)
- [x] **Phase 2** — Indexation & retrieval (F3, F4)
- [x] **Phase 3** — Génération sourcée + itérations de prompt (F5, F6)
- [x] **Phase 4** — API FastAPI (F7)
- [x] **Phase 5** — Harnais d'évaluation (F8)
- [x] **Phase 6** — Port LangChain (branche `langchain-port`, F9)
- [x] **Phase 7 (V2)** — Multi-turn par condensation (F10-F12)

> **Statut** : phases 0-7 implémentées, testées et **validées sur le corpus réel**
> (18 docs / 316 chunks) avec les deux backends — baseline de retrieval, latences
> `/ask`, comparaison d'embeddeurs et équivalence du port LangChain sont toutes
> mesurées et reportées ci-dessus.
>
> Le rapport conversationnel V2 (F12) est produit
> (`eval/reports/2026-07-23_conversation_k5.md`) : recall **3/6** sur les tours
> answerable — chiffre à lire avec précaution, car `eval/scenarios.yaml` est un
> premier jet. Deux biais identifiés : (1) les annotations `expected_source` y sont
> trop strictes (pour la césure, les chunks récupérés parlent bien de césure mais
> viennent de la page « IUT — Services de la scolarité », dont le titre ne contient
> pas le mot) ; (2) un tour annoté `answerable` **refuse correctement**, faute de
> règle spécifique au droit dans le corpus — et le refus vide les sources (F6), donc
> compte comme un raté de recall. **Prochain pas** : raffiner ces annotations comme
> cela a été fait pour le jeu single-turn (q03).
>
> La V2 reste rétrocompatible : sans `history`, `/ask` reproduit exactement la V1.
> Voir `JOURNAL.md`.

## Port LangChain (branche `langchain-port`)

Le pipeline de requête est réimplémenté avec LangChain sur la branche dédiée
`langchain-port`, à des fins de comparaison. Le README de cette branche détaille
« ce que LangChain abstrait » — et ce que l'on perd en lisibilité/contrôle.

L'équivalence est **mesurée**, pas postulée : `eval/compare_pipelines.py` (sur la
branche) rejoue les mêmes questions dans les deux implémentations, avec la même
collection Chroma, le même prompt système et le même backend. Résultat (2026-07-23,
`mistral-small-latest`, k=5, 20 questions) : **parité de refus 19/20** (dont les 4
questions hors-corpus), parité de citations 15/20, recouvrement lexical moyen 0.75.
L'unique divergence (q16) se situe au niveau de la *génération* sur une question
limite, pas dans le câblage. Ce que LangChain **n'abstrait pas** reste visible : la
chaîne LCEL rend une `str`, là où `/ask` doit encore produire un `RagResult`
structuré (sources, refus → sources vidées, erreur backend → `503`).

## Références (état de l'art)

- Anthropic — [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Claude Cookbook — Contextual Embeddings](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
- [RAGAS](https://docs.ragas.io) — vocabulaire d'évaluation (faithfulness, context recall…)
- [Docling](https://github.com/docling-project/docling) (IBM) — parsing PDF (layout, tableaux)
- Étalons « produit » : [RAGFlow](https://github.com/infiniflow/ragflow), kotaemon

> AssistantAMU ne concurrence pas ces moteurs : il en réimplémente le cœur en
> quelques centaines de lignes pour pouvoir en expliquer chaque brique.
