# AssistantAMU

Assistant documentaire **RAG** (Retrieval-Augmented Generation) construit sur les
documents publics d'Aix-Marseille Université (règlements de scolarité, guides
étudiants, pages des composantes). On lui pose une question en français, il répond
en **citant les passages sources** et **refuse explicitement** de répondre quand
l'information est absente du corpus.

Le système est **LLM-agnostique** (backend local Ollama ↔ API Mistral, commutable
par variable d'environnement) et livré avec un **harnais d'évaluation
reproductible** comparant recherche sémantique, BM25 et leur fusion RRF.

> Projet développé d'après un PRD versionné ([`PRD-AssistantAMU-V1_3.md`](PRD-AssistantAMU-V1_3.md)),
> en deux temps : **V1 single-turn** (MVP) puis **V2 multi-turn** par condensation
> de requête. Ce README sera complété au fil des phases (baseline d'évaluation,
> latences, comparaison LangChain) — voir la feuille de route ci-dessous.

## Statut

**Phase 0 — Squelette : ✅ terminée.** Structure du projet, configuration,
`.gitignore`, `.env.example`, `config.py` validé, `pyproject.toml`, tests amorcés.
Le reste des phases n'est pas encore implémenté (voir feuille de route).

## Architecture

```
INDEXATION (hors ligne)
sources.yaml → download → extract (pdfplumber/bs4) → clean → chunk (≤ 500 tk, ov. 50)
     → embed ("passage: " + texte, e5-small) → ChromaDB (cosine)
     → [en parallèle, pour l'éval : index BM25 en mémoire depuis les mêmes chunks]

REQUÊTE V1 (temps réel)
question → embed ("query: " + question) → ChromaDB top-k
     → prompt RAG (règles en système ; sources XML puis question en user)
     → LLMBackend.generate → réponse + sources
```

## Stack

| Composant | Choix |
|---|---|
| Langage | Python ≥ 3.11 |
| Embeddings | `sentence-transformers` + `intfloat/multilingual-e5-small` |
| Base vectorielle | `chromadb` (persistant local, distance cosinus) |
| Recherche lexicale | `rank_bm25` (comparaison d'évaluation) |
| LLM local | Ollama (`mistral` 7B) |
| LLM API | Mistral La Plateforme (`mistral-small-latest`) |
| Extraction | `pdfplumber` (+ `docling` en escalade), `beautifulsoup4` |
| API | `fastapi` + `uvicorn` + `pydantic` v2 |
| Tests | `pytest` |

## Structure du dépôt

```
assistant-amu/
├── corpus/            # sources.yaml (versionné), ingested.jsonl, raw/ (non versionné)
├── src/assistant_amu/ # config, ingestion, retrieval, generation, api
├── prompts/           # prompts RAG + CHANGELOG
├── eval/              # jeu de questions + harnais + rapports
├── tests/
├── .env.example
└── pyproject.toml
```

## Installation

Prérequis : Python ≥ 3.11 ; pour le backend local, [Ollama](https://ollama.com)
avec le modèle `mistral` (`ollama pull mistral`).

```bash
# Environnement virtuel
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/macOS : source .venv/bin/activate

# Dépendances (mode éditable) + outils de test
pip install -e ".[dev]"

# Configuration
cp .env.example .env    # puis renseigner les valeurs (clé Mistral si backend API)

# Tests
pytest
```

## Feuille de route (V1)

- [x] **Phase 0** — Squelette (structure, config, tooling)
- [ ] **Phase 1** — Corpus & ingestion (F1, F2) — *nécessite `sources.yaml`*
- [ ] **Phase 2** — Indexation & retrieval (F3, F4)
- [ ] **Phase 3** — Génération sourcée + itérations de prompt (F5, F6)
- [ ] **Phase 4** — API FastAPI `/ask` `/ingest` `/health` (F7)
- [ ] **Phase 5** — Harnais d'évaluation + mesures de sensibilité (F8)
- [ ] **Phase 6** — Port LangChain + finition (F9), tag `v1.0`
- [ ] **Phase 7 (V2)** — Multi-turn par condensation (F10-F12), tag `v2.0`

## Références (état de l'art)

- Anthropic — [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Claude Cookbook — Contextual Embeddings](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
- [RAGAS](https://docs.ragas.io) — vocabulaire d'évaluation (faithfulness, context recall…)
- [Docling](https://github.com/docling-project/docling) (IBM) — parsing PDF (layout, tableaux)

> AssistantAMU ne concurrence pas les moteurs RAG clé en main : il en réimplémente
> le cœur en quelques centaines de lignes pour pouvoir en expliquer chaque brique.
