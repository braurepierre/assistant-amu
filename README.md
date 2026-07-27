# AssistantAMU

**AssistantAMU** est un système documentaire fondé sur une architecture **RAG** (*Retrieval-Augmented Generation*), conçu pour interroger les documents publics d'Aix-Marseille Université (règlements de scolarité, guides étudiants, pages des composantes). À partir d'une requête formulée en français, le système produit une réponse construite exclusivement à partir du corpus indexé, **cite explicitement les passages sources** et **formule un refus** lorsque l'information demandée est absente de la base documentaire.

Le système est **indépendant du modèle de langage utilisé** (commutation par variable d'environnement entre un backend local sous Ollama et l'API Mistral) et intègre un **harnais d'évaluation reproductible** comparant les performances de la recherche sémantique, de l'approche lexicale BM25 et de leur fusion par classement réciproque (*Reciprocal Rank Fusion* — RRF).

> **Note de conception :** le périmètre a été spécifié avant d'être implémenté, et le pipeline est écrit en Python pur — le framework vient ensuite (voir la branche d'expérimentation LangChain). L'objectif explicite est de garantir la transparence complète de chaque composant.

## Documentation du projet

| Document | Objet |
| :--- | :--- |
| [`docs/concepts-assistant-amu.html`](docs/concepts-assistant-amu.html) | **Page pédagogique** — ce que fait le système, brique par brique, avec des démonstrations manipulables (découpage, requête RAG, réécriture) et un glossaire relié aux fichiers du code. Page autonome : aucun serveur ni étape de compilation, il suffit de l'ouvrir dans un navigateur. |
| [`docs/architecture-assistant-amu.html`](docs/architecture-assistant-amu.html) | **Carte du code** — l'organisation du dépôt en cinq ensembles, la chaîne d'ingestion et la chaîne de réponse. Schémas manipulables : survoler une étape en donne le rôle et le fichier. |
| [`docs/mesures.md`](docs/mesures.md) | **Mesures et évaluation** — résultats détaillés, tables par question, commentaire des mécanismes. |
| [`DEMO.md`](DEMO.md) | Parcours de démonstration de bout en bout, requêtes prêtes à l'emploi. |
| [`prompts/CHANGELOG.md`](prompts/CHANGELOG.md) | Ingénierie de prompt — chaque itération des trois prompts système avec sa raison et le cas de test qui l'a motivée. |
| [`docs/README.md`](docs/README.md) | Index de `docs/` et mode d'emploi de la page pédagogique : d'où viennent ses chiffres, comment la tenir à jour. |
| [`eval/reports/`](eval/reports/) | Rapports bruts produits par le harnais d'évaluation, un par mesure. |

---

## Motivation architecturale : RAG et fenêtre de contexte étendue

Pour des corpus de taille modérée (< ~200 000 tokens), Anthropic recommande d'insérer l'intégralité des documents dans le prompt système (*in-context learning* avec mise en cache) plutôt que de recourir au RAG. L'approche RAG a néanmoins été retenue pour ce projet, pour quatre raisons structurelles :

1. **Maîtrise de l'ingénierie RAG** — l'implémentation et la maîtrise explicite du pipeline d'indexation et de recherche constituent l'objectif technique principal.
2. **Contraintes d'infrastructure locale** — Ollama expose le modèle `mistral` avec une fenêtre de contexte réduite par défaut (voir *Gestion du contexte Ollama*).
3. **Optimisation des ressources** — l'envoi récurrent d'un contexte volumineux induit des coûts d'API et une latence d'inférence CPU incompatibles avec les contraintes du projet.
4. **Précision du sourçage** — le découpage en fragments (*chunks*) permet une attribution contextuelle et une citation exacte des passages sources, fonction centrale du produit.

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

### Contraintes techniques identifiées et résolutions

* **Formatage des préfixes E5** — les modèles de la famille E5 requièrent impérativement les préfixes `"query: "` pour les requêtes et `"passage: "` pour les documents. Leur absence dégrade silencieusement la qualité des représentations vectorielles. Le module `embedder.py` gère ces spécificités au moyen d'une table {famille de modèles → préfixes} et désactive tout préfixe pour les modèles non concernés (`sentence-camembert-base`, comparaison des modèles d'embeddings).
* **Espace métrique ChromaDB** — la collection est explicitement initialisée avec le paramètre `metadata={"hnsw:space": "cosine"}`, afin de remplacer la métrique euclidienne L2 appliquée par défaut par ChromaDB.
* **Gestion du contexte Ollama** — Ollama tronque silencieusement, et sans erreur, les prompts dépassant la variable `num_ctx` (fixée par défaut à 2048 ou 4096 tokens) plutôt que la capacité réelle du modèle. Cette variable a été portée à `OLLAMA_NUM_CTX=8192` afin de prévenir toute perte involontaire d'information lors de l'injection des contextes.

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

Le backend LLM n'est pas conteneurisé : il est soit externe (API Mistral), soit déjà installé sur la machine hôte — embarquer Ollama et ses modèles ajouterait plusieurs gigaoctets à une image dont l'objet est le service RAG. Renseigner `MISTRAL_API_KEY` pour l'API, ou laisser le backend `ollama` par défaut si une instance est active sur l'hôte — le conteneur l'atteint par `host.docker.internal`. L'intégration continue (`.github/workflows/ci.yml`) exécute la suite de tests, construit cette même image et interroge son point de contrôle `/health`.

---

## Contrats d'interface API

| Point d'entrée | Méthode | Description | Réponses / Codes HTTP |
| :--- | :--- | :--- | :--- |
| `/ask` | `POST` | Traitement complet d'une requête `{question, k}` | `{answer, sources[], model, retrieved_chunks, condensed_question}`<br/>`503 Service Unavailable` si le backend est injoignable. |
| `/ingest` | `POST` | Ingestion d'un document en multipart (`file`, `title`, `url?`, `category?`) | `{document_id, chunks_added}`<br/>`409 Conflict` en cas de doublon. |
| `/health` | `GET` | Contrôle de l'état des services et métriques | `{chroma, llm_backend, documents, chunks}` |

---

## Métriques et évaluation

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur équivalent au *context recall* du framework RAGAS) selon trois stratégies de recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown daté est automatiquement généré dans `eval/reports/`, incluant une section « désaccords » recensant les questions pour lesquelles une seule méthode identifie le fragment attendu.

> **Résultats de référence**
> *Corpus de test : 18 documents, 316 fragments, 50 questions d'évaluation, k=5.*
>
> | Méthode | k=2 | k=3 | k=5 | k=8 |
> |---|---|---|---|---|
> | semantic | 0,80 | 0,82 | 0,86 | 0,86 |
> | bm25 | 0,70 | 0,78 | 0,84 | 0,88 |
> | rrf | 0,74 | 0,82 | 0,86 | **0,92** |
>
> La mesure antérieure sur 16 questions (0,94 / 0,81 / 0,88) est supplantée par celle-ci, établie sur un jeu trois fois plus grand : elle en reste l'historique, pas la référence.

Quatre études complètent cette référence :

* **Modèles d'embeddings** — `e5-small` devance nettement CamemBERT et FlauBERT à k = 3 et k = 5 (+16 et +10 points sur le premier), pour une empreinte mémoire deux fois moindre. Aucune bascule n'est justifiée. Ce résultat **corrige une lecture antérieure** établie sur 16 questions.
* **Contextual Retrieval** — la contextualisation de l'index améliore la recherche : au mieux 8 questions gagnées sur les formulations conversationnelles (sémantique, k=3), pour une pire perte de 2 questions qui reste sous le seuil de signification. Somme des écarts sur les douze cellules mesurées : +18 questions. Subsiste une sensibilité de BM25 au budget de découpage, à comprendre avant de généraliser la méthode.
* **Sensibilité à la taille du corpus** — un corpus élargi de 18 à 28 documents ne coûte **aucune question** au sémantique ni à BM25. La RRF est la seule méthode à céder, ce qui oppose un contrepoids à son avance mesurée à k = 8.
* **Latence et refus** — ~3,0 s par requête sur l'API Mistral ; **100 % des requêtes hors-corpus rejetées** sur les deux backends. L'inférence locale sur CPU reste lente par nature (repli documenté `num_ctx=4096`, `k ≤ 5`).

**Une convention gouverne l'ensemble de ces travaux : mesurer n'est pas brancher.** La fusion RRF, la réécriture de requête et le *Contextual Retrieval* sont mesurés, documentés et **non intégrés** au pipeline `/ask`, qui demeure purement sémantique.

> Chiffres complets, tables par question, désaccords commentés et diagnostics : **[`docs/mesures.md`](docs/mesures.md)**. Rapports bruts datés : `eval/reports/`.

---

## Périmètre fonctionnel et limitations

Les choix d'implémentation suivants découlent du périmètre arrêté au départ et constituent des décisions assumées, non des omissions :

* **Inclus :** architecture RAG complète, gestion des refus, traçabilité des citations, API REST, harnais d'évaluation.
* **Exclus du périmètre :** authentification, traitement en flux (*streaming*), ré-ordonnancement (*reranking*) par cross-encoder, recherche hybride dans `/ask` (la fusion RRF est **mesurée mais non intégrée au pipeline de production**), traitement OCR (les PDF scannés sont exclus et signalés), support multilingue (français uniquement).
* **Ajouté après la première livraison :** conteneurisation et intégration continue, ainsi que l'expérimentation *Contextual Retrieval* — cette dernière sous forme d'index parallèle mesuré, sans modification du pipeline `/ask`.

**Perspectives d'évolution :**

1. *Contextual Retrieval* **mesuré** (voir [`docs/mesures.md`](docs/mesures.md)) : la contextualisation systématique de l'index gagne plus qu'elle ne perd sur ce corpus, sans que cela suffise à la brancher — le pipeline s'en tient au principe « mesurer n'est pas brancher ». La piste à instruire consiste à ne contextualiser que les fragments effectivement décontextualisés — ceux dont le texte ne nomme ni son document ni son sujet — plutôt que la totalité de l'index.
2. Activation de la recherche hybride (sémantique + BM25 via RRF) au niveau du pipeline de production, sous réserve de validation par les mesures. Deux mesures s'y opposent partiellement et doivent être arbitrées ensemble : la RRF gagne 3 questions sur le sémantique à k = 8, mais elle est **la seule méthode que l'élargissement du corpus dégrade**. Une bascule décidée sur le seul gain à k = 8 échangerait donc une amélioration constatée sur un corpus figé contre une fragilité au passage à l'échelle.
3. Module de ré-ordonnancement (*reranking*) par cross-encoder.
4. Automatisation du calcul des métriques RAGAS.

---

## État du projet et feuille de route

- [x] **Phase 0** — Structure et socle logiciel
- [x] **Phase 1** — Acquisition et ingestion des données
- [x] **Phase 2** — Indexation vectorielle et moteur de recherche
- [x] **Phase 3** — Pipeline de génération sourcée et ingénierie de prompt
- [x] **Phase 4** — Déploiement de l'interface API FastAPI
- [x] **Phase 5** — Implémentation du harnais d'évaluation
- [x] **Phase 6** — Implémentation alternative LangChain (branche `langchain-port`)
- [x] **Phase 7** — Support de la recherche multi-tour par condensation de requêtes

> **Statut actuel :** l'ensemble des fonctionnalités des phases 0 à 7 est développé, couvert par les tests unitaires et **validé sur le corpus réel** (18 documents, 316 fragments) avec les deux backends. Les résultats de référence en recherche, les latences `/ask`, la comparaison des modèles d'embeddings et l'équivalence du port LangChain ont tous fait l'objet de mesures rapportées.
>
> **Évaluation conversationnelle multi-tour.** Le rapport fait état d'un rappel de **3/6** sur les tours de conversation annotés comme répondables, attribué à une **limitation avérée de la recherche** et non à un défaut d'annotation. Le diagnostic — éviction de la page institutionnelle par une page de composante, 11,7 % de l'index constitué de fragments de moins de 50 caractères — est détaillé dans [`docs/mesures.md`](docs/mesures.md).
>
> Le multi-tour maintient une rétrocompatibilité descendante complète : en l'absence d'historique de conversation (`history`), le point d'entrée `/ask` reproduit exactement le comportement mono-tour.

---

## Expérimentations sur branches dédiées

Deux travaux comparatifs sont conduits hors de la branche principale. Ils y restent : chacun est mesuré et documenté, aucun n'est intégré au pipeline de production. Le détail — méthode, chiffres, limites — se lit sur la branche concernée.

### Portage LangChain — branche `langchain-port`

Réimplémentation parallèle du pipeline de requête, à des fins d'analyse comparative des abstractions apportées par le framework. L'équivalence fonctionnelle des deux implémentations est **mesurée et non postulée** : `eval/compare_pipelines.py` rejoue le même jeu de questions dans les deux implémentations, à collection ChromaDB, prompt système et backend identiques — **parité des refus de 19/20** (`mistral-small-latest`, k=5, 20 questions), l'unique divergence relevant de la génération et non de l'agencement du pipeline.

Détail et analyse des limites de l'abstraction : **README de la branche `langchain-port`**.

### Comparaison avec AnythingLLM — branche `worktree-compare-anythingllm`

Confrontation du pipeline maison à **AnythingLLM v1.15.0** en déploiement Docker par défaut, à corpus strictement identique et backend LLM tenu constant des deux côtés. Expérience annexe, **hors du périmètre spécifié** : elle mesure un produit tiers *out-of-the-box*, non une infériorité intrinsèque de celui-ci — le rapport impute l'essentiel de l'écart à deux réglages par défaut.

Deux réserves bornent sa portée, énoncées par le rapport lui-même : la mesure porte sur le **jeu de 20 questions et le corpus antérieurs** aux chiffres de référence ci-dessus, et le jury n'était pas aveugle à l'identité des systèmes.

Le rapport imputait l'essentiel de l'écart à deux réglages par défaut du produit tiers. Ces deux réglages ont été **corrigés et remesurés**, les vingt questions reposées et les seize répondables rejugées à l'aveugle : l'attribution **n'est pas confirmée**. Le refus paramétré est sans effet mesurable (0/4 refus nets avant comme après) et la réparation de l'extraction ne produit aucune réponse pleinement ancrée. Une troisième cause a été identifiée à cette occasion, et elle appartient au harnais de ce dépôt : le workspace du produit tiers contenait chaque source en double, ce qui ramenait sa profondeur de recherche effective de 4 à 2 — y compris lors de la mesure d'origine.

Méthode, chiffres, limites et procédure de reprise : **README de la branche `worktree-compare-anythingllm`**. Rapport complet et réponses brutes des deux systèmes : `eval/reports/2026-07-26_anythingllm_vs_assistant-amu.md` sur cette même branche.

---

## Références bibliographiques et état de l'art

* Anthropic — [*Contextual Retrieval*](https://www.anthropic.com/engineering/contextual-retrieval)
* Claude Cookbook — [*Contextual Embeddings Guide*](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
* Framework RAGAS — [*Automated Evaluation of Retrieval Augmented Generation*](https://docs.ragas.io) : vocabulaire d'évaluation (*faithfulness*, *context recall*)
* Projet Docling (IBM) — [*Structured Document Parsing*](https://github.com/docling-project/docling) : analyse de documents PDF (mise en page, tableaux)
* Références applicatives : [RAGFlow](https://github.com/infiniflow/ragflow), kotaemon

> AssistantAMU ne se positionne pas en concurrence de ces moteurs : le projet en réimplémente le cœur fonctionnel en quelques centaines de lignes, dans un objectif de maîtrise et d'explicabilité de chaque composant.
