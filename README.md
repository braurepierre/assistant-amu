# AssistantAMU

**AssistantAMU** est un système documentaire fondé sur une architecture **RAG** (*Retrieval-Augmented Generation*), conçu pour interroger les documents publics d'Aix-Marseille Université (règlements de scolarité, guides étudiants, pages des composantes). À partir d'une requête formulée en français, le système produit une réponse construite exclusivement à partir du corpus indexé, cite les passages sources et formule un refus lorsque l'information demandée est absente de la base documentaire.

Le système est indépendant du modèle de langage utilisé (commutation par variable d'environnement entre un backend local sous Ollama et l'API Mistral) et intègre un harnais d'évaluation reproductible comparant la recherche sémantique, l'approche lexicale BM25 et leur fusion par classement réciproque (*Reciprocal Rank Fusion* — RRF).

## Documentation du projet

L'ensemble de ces documents est également publié sous forme de site, construit par Pelican depuis les fichiers du dépôt (`docs/site/`, publication Read the Docs).

| Document | Objet |
| :--- | :--- |
| [`docs/mesures.md`](docs/mesures.md) | **Mesures et évaluation** — tous les chiffres du projet : rappel par méthode, comparaison des encodeurs, contextualisation de l'index, latences, refus. Tables par question et limites de chaque étude. |
| [`docs/concepts-assistant-amu.html`](docs/concepts-assistant-amu.html) | **Page pédagogique** — ce que fait le système, brique par brique, avec des démonstrations manipulables (découpage, requête RAG, réécriture) et un glossaire relié aux fichiers du code. Page autonome, à ouvrir directement dans un navigateur. |
| [`docs/architecture-assistant-amu.html`](docs/architecture-assistant-amu.html) | **Organisation du code et chaînes de traitement** — l'organisation du dépôt en cinq ensembles, la chaîne d'ingestion et la chaîne de réponse, en schémas manipulables à deux niveaux. |
| [`DEMO.md`](DEMO.md) | Parcours de démonstration de bout en bout, requêtes prêtes à l'emploi. |
| [`prompts/CHANGELOG.md`](prompts/CHANGELOG.md) | Ingénierie de prompt — chaque itération des trois prompts système avec sa raison et le cas de test qui l'a motivée. |
| [`docs/maintenance.md`](docs/maintenance.md) | Guide de maintenance de la documentation : origine des chiffres, régénération, construction du site. Destiné au contributeur. |
| [`eval/reports/`](eval/reports/) | Rapports bruts produits par le harnais d'évaluation, un par mesure. |

---

## Choix de l'architecture

Pour un corpus de cette taille (< ~200 000 tokens), l'insertion de l'intégralité des documents dans le prompt système (*in-context learning* avec mise en cache) est une alternative documentée au RAG. Le RAG a été retenu pour trois raisons : la citation exacte des passages sources — fonction centrale du produit — suppose un découpage en fragments ; la fenêtre de contexte du backend local est limitée (voir *Gestion du contexte Ollama*) ; l'envoi récurrent d'un contexte volumineux induit des coûts d'API et une latence d'inférence CPU incompatibles avec les contraintes du projet.

Le pipeline est écrit en Python pur, chaque composant restant explicite ; un portage LangChain existe sur une branche d'expérimentation, à des fins de comparaison.

---

## Architecture du système

```text
TRAITEMENT ET INDEXATION (hors ligne)
sources.yaml ──> Téléchargement ──> Extraction (pdfplumber/bs4) ──> Nettoyage ──> Chunking (≤ 500 tk, chevauchement : 50)
     └──> Vectorisation ("passage: " + texte, e5-small) ──> Stockage ChromaDB (distance cosinus)
     └──> [Évaluation] Génération de l'index BM25 en mémoire à partir des mêmes fragments

PIPELINE DE REQUÊTE (temps réel)
Requête utilisateur ──> Vectorisation ("query: " + question) ──> Recherche k-NN ChromaDB
     └──> Construction du prompt RAG (consignes système + contexte XML + requête)
     └──> Inférence via LLMBackend ──> Génération de la réponse et restitution des références
```

### Contraintes techniques et résolutions

* **Formatage des préfixes E5** — les modèles de la famille E5 requièrent les préfixes `"query: "` pour les requêtes et `"passage: "` pour les documents ; leur absence dégrade silencieusement la qualité des représentations vectorielles. Le module `embedder.py` gère ces spécificités au moyen d'une table {famille de modèles → préfixes} et désactive tout préfixe pour les modèles non concernés.
* **Espace métrique ChromaDB** — la collection est initialisée avec `metadata={"hnsw:space": "cosine"}`, afin de remplacer la métrique euclidienne L2 appliquée par défaut par ChromaDB.
* **Gestion du contexte Ollama** — Ollama tronque silencieusement, sans erreur, les prompts dépassant la variable `num_ctx` (2048 ou 4096 tokens par défaut) plutôt que la capacité réelle du modèle. Cette variable est portée à `OLLAMA_NUM_CTX=8192` afin de prévenir toute perte d'information lors de l'injection des contextes.

---

## Spécifications technologiques

| Composant | Technologie retenue |
| :--- | :--- |
| **Langage** | Python ≥ 3.11 (environnement de référence : 3.12) |
| **Embeddings** | `sentence-transformers` (`intfloat/multilingual-e5-small`) |
| **Base de données vectorielle** | `chromadb` (instance locale persistante, métrique cosinus) |
| **Recherche lexicale** | `rank_bm25` (utilisé à des fins d'évaluation comparative) |
| **Inférence LLM (local)** | Ollama (modèle `mistral` 7B) |
| **Inférence LLM (API)** | Mistral La Plateforme (`mistral-small-latest`) |
| **Extraction de texte** | `pdfplumber` (escalade sur `docling`), `beautifulsoup4` |
| **Interface API** | `fastapi`, `uvicorn`, `pydantic` v2 |
| **Suite de tests** | `pytest` (isolation stricte : aucun appel réseau ni LLM en exécution de test) |

---

## Guide d'installation et d'exécution

### Prérequis

* Python ≥ 3.11
* Backend local (optionnel) : [Ollama](https://ollama.com) initialisé avec le modèle `mistral` (`ollama pull mistral`).

### Initialisation de l'environnement

```bash
# Configuration via le gestionnaire 'uv' (recommandé — gère également la version de Python)
uv venv --python 3.12
uv pip install -e ".[dev]"

# Configuration via pip standard
python -m venv .venv
source .venv/bin/activate  # Sous Windows : .venv\Scripts\activate
pip install -e ".[dev]"

# Initialisation des variables d'environnement
cp .env.example .env       # Renseigner MISTRAL_API_KEY en cas d'utilisation de l'API
pytest
```

### Processus d'exécution

```bash
# 1. Traitement et indexation du corpus (sur la base de corpus/sources.yaml, 15-30 URL)
python -m assistant_amu.ingestion.download          # Téléchargement des ressources dans corpus/raw/
python -m assistant_amu.ingestion stats             # Métriques du corpus (documents/exclusions/fragments)
python -m assistant_amu.ingestion dump -n 5         # Inspection structurale des fragments
python -m assistant_amu.ingestion index             # Génération des embeddings et indexation ChromaDB (idempotent)
python -m assistant_amu.ingestion search "césure ?" # Validation de la recherche k-NN (top-k)

# 2. Inférence de bout en bout (recherche + génération)
python -m assistant_amu.generation ask "Quelles sont les modalités de césure ?"

# 3. Lancement du service API
uvicorn assistant_amu.api.main:app --reload         # Interface de démonstration sur / · OpenAPI sur /docs

# 4. Évaluation des performances
python eval/evaluate.py --mode retrieval --method all --k 5
python eval/evaluate.py --mode end-to-end --k 5
python eval/evaluate.py --mode retrieval --embedding-model dangvantuan/sentence-camembert-base

# 5. Expérimentation Contextual Retrieval (index parallèle, mesure seule)
python -m assistant_amu.ingestion contextualize --dry-run -n 3   # Inspection des contextes générés
python -m assistant_amu.ingestion contextualize                  # Indexation dans la collection <prod>_ctx
python eval/contextual_retrieval_experiment.py                   # Comparaison baseline / contextuel
```

*Pour basculer d'un backend à l'autre, modifier la variable `LLM_BACKEND` (`mistral` ou `ollama`) dans le fichier `.env`.*

Le parcours de démonstration complet — interface conversationnelle, multi-tour, refus hors-corpus — est décrit dans [`DEMO.md`](DEMO.md).

### Exécution par conteneur

```bash
docker compose up --build          # http://127.0.0.1:8000/ · /docs · /health
```

L'image embarque les dépendances et le modèle d'embeddings ; l'index vectoriel réside dans un volume, dont l'alimentation requiert un corpus téléchargé :

```bash
docker compose run --rm api python -m assistant_amu.ingestion index
```

Le backend LLM n'est pas conteneurisé : il est soit externe (API Mistral), soit installé sur la machine hôte, que le conteneur atteint par `host.docker.internal` (embarquer Ollama et ses modèles ajouterait plusieurs gigaoctets à l'image). Renseigner `MISTRAL_API_KEY` pour l'API, ou laisser le backend `ollama` par défaut si une instance est active sur l'hôte. L'intégration continue (`.github/workflows/ci.yml`) exécute la suite de tests, construit cette même image et interroge son point de contrôle `/health`.

### Construction du site de documentation

```bash
uv run --no-project --with-requirements docs/site/requirements.txt \
    python docs/site/build_site.py       # site écrit dans docs/site/output/
```

Le site compose les documents existants du dépôt. Procédure détaillée : [`docs/maintenance.md`](docs/maintenance.md).

---

## Contrats d'interface API

| Point d'entrée | Méthode | Description | Réponses / Codes HTTP |
| :--- | :--- | :--- | :--- |
| `/ask` | `POST` | Traitement complet d'une requête `{question, k}` | `{answer, sources[], model, retrieved_chunks, condensed_question}`<br/>`503 Service Unavailable` si le backend est injoignable. |
| `/ingest` | `POST` | Ingestion d'un document en multipart (`file`, `title`, `url?`, `category?`) | `{document_id, chunks_added}`<br/>`409 Conflict` en cas de doublon. |
| `/health` | `GET` | Contrôle de l'état des services et métriques | `{chroma, llm_backend, documents, chunks}` |

La recherche multi-tour procède par condensation de requête ; en l'absence d'historique de conversation (`history`), `/ask` reproduit exactement le comportement mono-tour.

---

## Métriques et évaluation

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur équivalent au *context recall* du framework RAGAS) selon trois stratégies de recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown daté est généré dans `eval/reports/` à chaque exécution.

Résultat de référence : **0,86 de rappel sémantique à k = 5**, sur un corpus de 18 documents et 316 fragments interrogé par 50 questions d'évaluation. Cinq études complètent cette référence — courbe recall@k et fusion RRF, comparaison des modèles d'embeddings, contextualisation de l'index, réécriture de requête, sensibilité à la taille du corpus — ainsi que les latences et le taux de refus hors-corpus.

La fusion RRF, la réécriture de requête et le *Contextual Retrieval* sont mesurés sans être intégrés au pipeline `/ask`, qui reste purement sémantique.

> Chiffres complets, tables par question, limites et diagnostics : **[`docs/mesures.md`](docs/mesures.md)**. Rapports bruts datés : `eval/reports/`.

---

## Périmètre fonctionnel et limitations

* **Inclus :** architecture RAG complète, gestion des refus, traçabilité des citations, API REST, harnais d'évaluation, conteneurisation et intégration continue.
* **Exclus du périmètre :** authentification, traitement en flux (*streaming*), ré-ordonnancement (*reranking*) par cross-encoder, recherche hybride dans `/ask`, traitement OCR (les PDF scannés sont exclus et signalés), support multilingue (français uniquement), automatisation du calcul des métriques RAGAS.

**Limite connue.** Elle porte sur la recherche et non sur la génération : une page institutionnelle peut se faire évincer du top-k par une page de composante, et 11,7 % de l'index est constitué de fragments de moins de 50 caractères qui captent les requêtes courtes. C'est ce qui plafonne l'évaluation conversationnelle multi-tour à 3 tours répondus sur 6.

Deux bascules restent ouvertes — l'activation de la recherche hybride dans `/ask` et la contextualisation sélective de l'index. Chacune est soutenue par une mesure et contredite par une autre ; l'arbitrage, avec les chiffres des deux côtés, est exposé dans [`docs/mesures.md`](docs/mesures.md).

---

## Expérimentations sur branches dédiées

Deux travaux comparatifs sont conduits hors de la branche principale ; aucun n'est intégré au pipeline de production. Le détail — méthode, chiffres, limites — se lit sur la branche concernée.

### Portage LangChain — branche `langchain-port`

Réimplémentation du pipeline de requête avec LangChain (LCEL), à des fins d'analyse comparative des abstractions apportées par le framework. `eval/compare_pipelines.py` rejoue le même jeu de questions dans les deux implémentations, à collection ChromaDB, prompt système et backend identiques : **parité des refus de 19/20** (`mistral-small-latest`, k = 5, 20 questions), l'unique divergence venant de la génération et non de l'agencement du pipeline.

Analyse des limites de l'abstraction : README de la branche `langchain-port`.

### Comparaison avec AnythingLLM — branche `worktree-compare-anythingllm`

Le pipeline est confronté à **AnythingLLM v1.15.0** en déploiement Docker par défaut, à corpus identique et backend LLM constant des deux côtés : **4/4 refus contre 1/4** sur les questions hors-corpus, **14/16 réponses correctes et ancrées contre 0/16** sur les questions répondables (jeu de 20 questions et corpus antérieurs à la référence ci-dessus).

Deux réserves bornent ces chiffres. Les deux réglages par défaut du produit tiers dont la correction a été testée ne comblent pas l'écart. Le workspace du produit tiers contenait chaque source en double — défaut du harnais de ce dépôt — ce qui ramenait sa profondeur de recherche effective de 4 à 2, sans que la mesure ait été rejouée à profondeur corrigée. La mesure porte sur la configuration par défaut du produit, non sur son plafond de capacité.

Méthode, chiffres, tables par question et procédure de reprise : **`docs/mesures-anythingllm.md` sur la branche `worktree-compare-anythingllm`**.

---

## Références bibliographiques et état de l'art

* Anthropic — [*Contextual Retrieval*](https://www.anthropic.com/engineering/contextual-retrieval)
* Claude Cookbook — [*Contextual Embeddings Guide*](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
* Framework RAGAS — [*Automated Evaluation of Retrieval Augmented Generation*](https://docs.ragas.io) : vocabulaire d'évaluation (*faithfulness*, *context recall*)
* Projet Docling (IBM) — [*Structured Document Parsing*](https://github.com/docling-project/docling) : analyse de documents PDF (mise en page, tableaux)
* Références applicatives : [RAGFlow](https://github.com/infiniflow/ragflow), kotaemon

AssistantAMU réimplémente le cœur fonctionnel de ces moteurs en quelques centaines de lignes, chaque composant restant explicite.
