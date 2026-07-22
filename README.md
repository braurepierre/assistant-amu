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
bon choix ici, pour quatre raisons : (1) c'est la compétence visée ; (2) le
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

> **Baseline** — `[À_PRÉCISER après le premier run sur le corpus réel]`. Le premier
> run fait référence ; les suivants s'y comparent. Latences `/ask` par backend
> (ordres de grandeur : secondes via API, dizaines de secondes en local) à
> consigner ici après mesure.

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
- [ ] **Phase 7 (V2)** — Multi-turn par condensation (F10-F12)

> **Statut** : code V1 (phases 0-6) implémenté et testé. La *validation chiffrée*
> de F1/F4/F7-latence/F8-baseline et le test d'intégration des deux backends
> attendent le corpus AMU réel (`corpus/sources.yaml`) et un backend LLM (clé
> Mistral et/ou Ollama). Voir `JOURNAL.md`.

## Port LangChain (cette branche)

> Vous êtes sur la branche **`langchain-port`**. Le pipeline de requête single-turn
> est réimplémenté avec **LangChain (LCEL)** dans
> `src/assistant_amu/langchain_port/pipeline.py`, à des fins de comparaison. Il
> réutilise **la même collection ChromaDB** et **le même prompt système** que la
> version écrite à la main, donc les réponses sont comparables.
>
> Installation : `uv pip install -e ".[dev,langchain]"`.

### Ce que LangChain abstrait

- **L'orchestration** : `{"context": retriever | format_docs, "question": passthrough}
  | prompt | llm | StrOutputParser()` remplace l'assemblage explicite du message
  et l'appel backend. Concis, mais le flux de données devient implicite.
- **Le vectorstore et le retriever** : `Chroma(...).as_retriever(k=...)` masque
  la requête ChromaDB, la conversion distance→similarité et la sélection top-k.
- **Le modèle de chat** : `ChatOllama` / `ChatMistralAI` unifient les deux
  backends (l'équivalent de notre `LLMBackend`), mais avec une surface d'API et
  un graphe de dépendances bien plus larges.

### Ce que LangChain n'abstrait **pas** (et qu'il faut toujours écrire)

- **Les préfixes E5** (piège n°1) : `HuggingFaceEmbeddings` par défaut n'ajoute pas
  `query:`/`passage:` → il faut quand même une classe `Embeddings` maison
  (`E5Embeddings`) pour réutiliser correctement la collection.
- **La logique produit** : citations `[S1]` fiabilisées, **détection de refus** et
  mise à zéro des sources, mapping d'erreurs backend → **503**, `condensed_question`.
  La chaîne LCEL renvoie une chaîne de caractères ; tout le contrat de `/ask`
  (`api/schemas.py`) reste à notre charge.

**Bilan** : LangChain fait gagner quelques lignes d'orchestration au prix d'une
grosse dépendance et d'un contrôle moindre sur les pièges (préfixes, métrique
cosinus, `num_ctx`) — précisément les points que ce projet veut savoir expliquer.

## Références (état de l'art)

- Anthropic — [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Claude Cookbook — Contextual Embeddings](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
- [RAGAS](https://docs.ragas.io) — vocabulaire d'évaluation (faithfulness, context recall…)
- [Docling](https://github.com/docling-project/docling) (IBM) — parsing PDF (layout, tableaux)
- Étalons « produit » : [RAGFlow](https://github.com/infiniflow/ragflow), kotaemon

> AssistantAMU ne concurrence pas ces moteurs : il en réimplémente le cœur en
> quelques centaines de lignes pour pouvoir en expliquer chaque brique.
