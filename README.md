# AssistantAMU

**AssistantAMU** est un système documentaire fondé sur une architecture **RAG** (*Retrieval-Augmented Generation*), conçu pour interroger les documents publics d'Aix-Marseille Université (règlements de scolarité, guides étudiants, pages des composantes). À partir d'une requête formulée en français, le système produit une réponse construite exclusivement à partir du corpus indexé, **cite explicitement les passages sources** et **formule un refus** lorsque l'information demandée est absente de la base documentaire.

Le système est **indépendant du modèle de langage utilisé** (commutation par variable d'environnement entre un backend local sous Ollama et l'API Mistral) et intègre un **harnais d'évaluation reproductible** comparant les performances de la recherche sémantique, de l'approche lexicale BM25 et de leur fusion par classement réciproque (*Reciprocal Rank Fusion* — RRF).

> **Note de conception :** ce projet a été développé conformément aux spécifications d'un document d'exigences produit versionné ([`PRD-AssistantAMU-V1_3.md`](PRD-AssistantAMU-V1_3.md)), en Python pur — le pipeline d'abord, le framework ensuite (voir la branche d'expérimentation LangChain). L'objectif explicite est de garantir la transparence complète de chaque composant.

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

PIPELINE DE REQUÊTE V1 (temps réel)
Requête utilisateur ──> Vectorisation ("query: " + question) ──> Recherche k-NN ChromaDB
     └──> Construction du prompt RAG (consignes système + contexte XML + requête)
     └──> Inférence via LLMBackend ──> Génération de la réponse et restitution des références
```

### Contraintes techniques identifiées et résolutions

* **Formatage des préfixes E5** — les modèles de la famille E5 requièrent impérativement les préfixes `"query: "` pour les requêtes et `"passage: "` pour les documents. Leur absence dégrade silencieusement la qualité des représentations vectorielles. Le module `embedder.py` gère ces spécificités au moyen d'une table {famille de modèles → préfixes} et désactive tout préfixe pour les modèles non concernés (`sentence-camembert-base`, comparaison de la Phase 5).
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
uvicorn assistant_amu.api.main:app --reload         # Documentation OpenAPI accessible sur /docs

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

### Exécution par conteneur

```bash
docker compose up --build          # http://127.0.0.1:8000/ · /docs · /health
```

L'image embarque les dépendances et le modèle d'embeddings ; l'index vectoriel réside dans un volume, dont l'alimentation requiert un corpus téléchargé :

```bash
docker compose run --rm api python -m assistant_amu.ingestion index
```

Le backend LLM n'est pas conteneurisé, conformément au §6.1 du PRD : renseigner `MISTRAL_API_KEY` pour l'API, ou laisser le backend `ollama` par défaut si une instance Ollama est active sur la machine hôte — le conteneur l'atteint par `host.docker.internal`. L'intégration continue (`.github/workflows/ci.yml`) exécute la suite de tests, construit cette même image et interroge son point de contrôle `/health`.

---

## Contrats d'interface API

| Point d'entrée | Méthode | Description | Réponses / Codes HTTP |
| :--- | :--- | :--- | :--- |
| `/ask` | `POST` | Traitement complet d'une requête `{question, k}` | `{answer, sources[], model, retrieved_chunks, condensed_question}`<br/>`503 Service Unavailable` si le backend est injoignable. |
| `/ingest` | `POST` | Ingestion d'un document en multipart (`file`, `title`, `url?`, `category?`) | `{document_id, chunks_added}`<br/>`409 Conflict` en cas de doublon. |
| `/health` | `GET` | Contrôle de l'état des services et métriques | `{chroma, llm_backend, documents, chunks}` |

---

## Métriques et évaluation

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur équivalent au *context recall* du framework RAGAS) selon trois stratégies de recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown daté est automatiquement généré dans `eval/reports/`, incluant une section « désaccords » recensant les questions pour lesquelles une seule méthode identifie le fragment attendu. La fusion RRF fait l'objet d'une **mesure comparative uniquement** : le pipeline `/ask` demeure purement sémantique en V1.

> **Résultats de référence (2026-07-23)**
> *Corpus de test : 18 documents, 316 fragments, 16 questions d'évaluation, k=5.*
>
> * **Rappel sémantique @5 :** 0,94
> * **Rappel BM25 @5 :** 0,81
> * **Rappel RRF @5 :** 0,88
>
> *Analyse des résultats :* la progression du rappel sémantique (de 0,81 à 0,94) résulte d'un raffinage diagnostiqué et documenté. La requête `q03` relevait d'une annotation excessivement stricte (le fragment pertinent emploie le sigle « RSE » et non la forme développée « régime spécial ») ; la requête `q10` révélait une lacune du corpus (la page M3C se limitait à un index de liens, corrigé par l'ajout des documents « Cadrage M3C »). L'unique requête non couverte par la recherche sémantique seule (`q04`, relative au logement) est correctement identifiée par la méthode RRF, ce qui documente concrètement l'intérêt d'une approche hybride — résultat conservé en l'état plutôt que corrigé artificiellement. La courbe recall@k pour k ∈ {2, 3, 5, 8} et le détail par question sont consignés dans `eval/reports/`.

### Analyse comparative des modèles d'embeddings

Mesures de rappel sémantique effectuées sur les mêmes 16 questions et les mêmes fragments. Cette comparaison relève d'une démarche d'évaluation : le pipeline `/ask` conserve le modèle d'embeddings de production.

| Modèle d'embeddings | @3 | @5 | @8 |
| :--- | :---: | :---: | :---: |
| `intfloat/multilingual-e5-small` (production, 384 dimensions) | 0,88 | 0,94 | 0,94 |
| `dangvantuan/sentence-camembert-base` (768 dimensions) | 0,81 | 0,94 | **1,00** |
| `hugorosen/flaubert_base_uncased-xnli-sts` (768 dimensions) | 0,81 | 0,81 | 0,94 |

Les modèles e5 et CamemBERT présentent des performances **équivalentes en moyenne (0,92)** : CamemBERT atteint une couverture complète au rang 8, tandis que e5 offre la plus grande régularité pour une empreinte mémoire nettement inférieure. FlauBERT se situe en retrait, en particulier sur les sigles et les définitions (échecs sur les requêtes RSE et CVEC). Les écarts observés (1 à 2 questions, soit une granularité de 0,06) ne justifient pas de modifier le modèle d'embeddings de production. Le modèle *cased* `Lajavaness/sentence-flaubert-base` ne s'initialise pas sous `sentence-transformers` 5.6.1 (tokenizer Moses dépourvu de `basic_tokenizer`), d'où le recours à la variante *uncased*. Script d'évaluation : `eval/embedder_comparison.py` ; rapport daté dans `eval/reports/`.

### Contextual Retrieval — index contextuel comparé à la référence

Chaque fragment a été préfixé, avant l'embedding **et** l'indexation BM25, d'une phrase générée par le LLM le situant dans son document (méthode Anthropic, septembre 2024 ; §5.3.1 du PRD). L'index correspondant est constitué dans une collection parallèle : le pipeline `/ask` n'est pas modifié. Mesures effectuées sur les deux jeux de questions, le jeu « dur » réunissant les formulations conversationnelles.

| Jeu de questions | Méthode | Référence | Index contextuel |
| :--- | :--- | :---: | :---: |
| **Dur** (25 questions, k=3) | sémantique | 0,48 | **0,80** |
| **Dur** (25 questions, k=5) | BM25 | **0,84** | 0,80 |
| **Facile** (16 questions, k=5) | sémantique | **0,94** | 0,81 |
| **Facile** (16 questions, k=5) | RRF | 0,88 | 0,88 |

La contextualisation **gagne nettement plus qu'elle ne perd** : **8 questions gagnées** sur les formulations conversationnelles — le mode d'échec qu'elle vise — contre **2 perdues** sur les formulations définitionnelles. Le préfixe rapproche le vecteur du fragment du sujet de son *document*, ce qui sert les requêtes vagues et dessert les requêtes précises.

Ce rapport n'est devenu lisible qu'après avoir porté le jeu difficile de 8 à 25 questions : sur 8 questions, un cran valait 0,125 et l'écart se confondait avec le bruit de mesure. La même expérience, conduite sur le jeu réduit, concluait à un échange équilibré — un jeu d'évaluation trop petit ne se contente pas d'être imprécis, il peut désigner la mauvaise conclusion.

Deux précautions déterminent la validité de ces chiffres :

1. **Comptage strict.** Le jeu « facile » exige la présence de mots-clés dans le fragment récupéré, or un contexte généré nomme presque toujours le sujet du fragment qu'il préfixe. Le texte d'origine est donc conservé et restauré après classement : le contexte sert à *trouver* le fragment, jamais à *prouver* la réussite. Le rapport chiffre l'artefact ainsi évité (jusqu'à une question de rappel).
2. **Troncature contrôlée.** Le découpage vise 500 tokens contre une fenêtre d'encodeur de 512 : le préfixe faisait sortir 23 fragments (7 %) de cette fenêtre, tronqués sans avertissement. L'expérience a été rejouée sur un corpus redécoupé à 440 tokens, où aucun fragment ne déborde — **les conclusions sont inchangées**.

Les chiffres publiés par Anthropic (−49 % d'échecs de recherche) portent sur des corpus de plusieurs milliers de fragments ; 25 et 16 questions ne sauraient les confirmer ni les infirmer. Ce qui est établi ici, c'est le sens de l'arbitrage sur ce corpus. Reste à trancher laquelle des deux populations de requêtes `/ask` doit servir en priorité, et si une contextualisation *sélective* — limitée aux fragments réellement décontextualisés — ne prendrait pas les deux. Rapports : `eval/reports/2026-07-26_contextual_retrieval.md` et `…_440.md`.

### Performances d'inférence et latence

*Mesures effectuées le 2026-07-23 sur le corpus de référence :*

| Backend LLM | Latence moyenne (`/ask`) | Taux de rejet contextuel (hors-corpus) |
| :--- | :--- | :--- |
| **Mistral API** (`mistral-small-latest`) | ~3,0 s / requête | **100 % (4/4)** des requêtes hors-corpus rejetées |
| **Ollama local** (`mistral` 7B, CPU) | > 120 s à `num_ctx=8192` / `k=5` (dépassement de délai intercepté) ; ~190 s à chaud avec repli `num_ctx=4096` / `k=3` | **100 % (4/4)** des requêtes hors-corpus rejetées *(mesure du 2026-07-26)* |

Le taux de rejet du backend local a été mesuré le 2026-07-26 sur les quatre requêtes hors-corpus de `eval/questions.yaml` (q17 à q20), dans la configuration de repli `num_ctx=4096` / `k=3`, modèle maintenu chaud. Les quatre réponses reproduisent le refus canonique à l'identique, sans source associée ; le verdict est établi par la fonction `is_refusal()` du projet, sur comparaison normalisée. La latence propre à ces refus (31 à 135 s, moyenne 103 s) n'est pas comparable aux valeurs de la colonne précédente : un refus ne génère qu'une douzaine de tokens, contre plusieurs centaines pour une réponse complète. Le préchauffage du modèle a requis 306 s, ce qui confirme le coût du chargement à froid documenté pour ce backend.

*Note sur l'exécution locale :* l'inférence du modèle local en environnement CPU présente des latences élevées. Ce comportement est conforme aux arbitrages du PRD (*développement sur API, démonstration en local*) ainsi qu'au repli documenté `num_ctx=4096`, `k ≤ 5`. Les dépassements de délai sont interceptés et remontent une exception `LLMBackendError(timeout)`, traduite par un code HTTP `503` (F5). Rapport détaillé : `eval/reports/2026-07-23_end-to-end_k5.md`.

---

## Périmètre fonctionnel et limitations

Les choix d'implémentation suivants découlent des spécifications initiales (§3 du PRD) et constituent des décisions de périmètre assumées, non des omissions :

* **Inclus :** architecture RAG complète, gestion des refus, traçabilité des citations, API REST, harnais d'évaluation.
* **Exclus du périmètre V1 :** authentification, traitement en flux (*streaming*), ré-ordonnancement (*reranking*) par cross-encoder, recherche hybride dans `/ask` (la fusion RRF est **mesurée mais non intégrée au pipeline de production**), traitement OCR (les PDF scannés sont exclus et signalés), support multilingue (français uniquement).
* **Ajouté après la V1 :** conteneurisation et intégration continue (§5.3.6), ainsi que l'expérimentation *Contextual Retrieval* (§5.3.1) — cette dernière sous forme d'index parallèle mesuré, sans modification du pipeline `/ask`.

**Perspectives d'évolution (V2+) :**

1. *Contextual Retrieval* **mesuré** (voir ci-dessus) : la contextualisation systématique de l'index constitue un arbitrage défavorable sur ce corpus. La piste subsistante consiste à ne contextualiser que les fragments effectivement décontextualisés — ceux dont le texte ne nomme ni son document ni son sujet — plutôt que la totalité de l'index.
2. Activation de la recherche hybride (sémantique + BM25 via RRF) au niveau du pipeline de production, sous réserve de validation par les mesures.
3. Module de ré-ordonnancement (*reranking*) par cross-encoder.
4. Automatisation du calcul des métriques RAGAS.

---

## État du projet et feuille de route

- [x] **Phase 0** — Structure et socle logiciel
- [x] **Phase 1** — Acquisition et ingestion des données (F1, F2)
- [x] **Phase 2** — Indexation vectorielle et moteur de recherche (F3, F4)
- [x] **Phase 3** — Pipeline de génération sourcée et ingénierie de prompt (F5, F6)
- [x] **Phase 4** — Déploiement de l'interface API FastAPI (F7)
- [x] **Phase 5** — Implémentation du harnais d'évaluation (F8)
- [x] **Phase 6** — Implémentation alternative LangChain (branche `langchain-port`, F9)
- [x] **Phase 7 (V2)** — Support de la recherche multi-tour par condensation de requêtes (F10-F12)

> **Statut actuel :** l'ensemble des fonctionnalités des phases 0 à 7 est développé, couvert par les tests unitaires et **validé sur le corpus réel** (18 documents, 316 fragments) avec les deux backends. Les résultats de référence en recherche, les latences `/ask`, la comparaison des modèles d'embeddings et l'équivalence du port LangChain ont tous fait l'objet de mesures rapportées ci-dessus.
>
> **Évaluation conversationnelle V2 (F12).** Le rapport est disponible (`eval/reports/2026-07-23_conversation_k5.md`) et fait état d'un rappel de **3/6** sur les tours de conversation annotés comme répondables. L'analyse diagnostique (détaillée dans `JOURNAL.md`) attribue ce résultat à une **limitation avérée de la recherche**, et non à un défaut d'annotation. Sur la requête relative à la césure, les cinq fragments retournés proviennent tous du document « IUT — Services de la scolarité », soit le traitement de la césure par une composante unique, tandis que la page institutionnelle « La césure à AMU », qui porte la réponse attendue, est **absente du top-5** : il s'agit du même mécanisme d'éviction de la page centrale que celui déjà observé sur la requête RSE.
>
> Un facteur aggravant a été quantifié : **11,7 % de l'index est constitué de fragments de moins de 50 caractères** (`FAQ`, `Césure`, `Bonus`, etc. — éléments de navigation devenus unités indexées), contre une médiane de 786 caractères. Un fragment très court et quasi identique à une requête courte obtient un score de similarité élevé, occupe une position du top-k et évince du contenu substantiel. Un second biais, de nature différente, relève effectivement de l'annotation : un tour annoté `answerable` **produit un refus correct** (le corpus ne contient aucune règle de césure propre à la filière droit), or un refus vide la liste des sources (F6) et se comptabilise donc mécaniquement comme un échec de recherche.
>
> L'architecture V2 maintient une rétrocompatibilité descendante complète : en l'absence d'historique de conversation (`history`), le point d'entrée `/ask` reproduit exactement le comportement de la V1. Voir `JOURNAL.md`.

---

## Expérimentation LangChain (branche `langchain-port`)

Une réimplémentation parallèle du pipeline de requête est disponible sur la branche dédiée `langchain-port`, à des fins d'analyse comparative. Le README de cette branche détaille les abstractions apportées par LangChain ainsi que leur impact sur la lisibilité et le contrôle fin des composants du RAG.

L'équivalence fonctionnelle des deux implémentations est **mesurée et non postulée** : le script `eval/compare_pipelines.py` (disponible sur la branche) rejoue le même jeu de questions dans les deux implémentations, avec une collection ChromaDB, un prompt système et un backend identiques. Résultats (2026-07-23, `mistral-small-latest`, k=5, 20 questions) : **parité des refus de 19/20** (incluant les 4 requêtes hors-corpus), parité des citations de 15/20, recouvrement lexical moyen de 0,75. L'unique divergence observée (`q16`) se situe au niveau de la *génération*, sur une question limite, et non dans l'agencement du pipeline. Les limites de l'abstraction restent apparentes : la chaîne LCEL retourne une chaîne de caractères, là où le point d'entrée `/ask` doit produire un objet `RagResult` structuré (sources, refus entraînant la remise à zéro des sources, erreur backend traduite en `503`).

---

## Comparaison avec AnythingLLM — contenu propre à cette branche

> **C'est l'objet de la branche `worktree-compare-anythingllm`.** Expérience
> annexe, **hors périmètre du PRD** : elle situe le pipeline maison face à un
> produit RAG clé en main. Rien n'en est répercuté dans la branche principale
> au-delà d'un renvoi, et rien n'est intégré au pipeline de production.

### Ce qui est comparé, et ce qui est tenu constant

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

### Résultats

Chiffres après la vérification du 27 juillet, qui a confronté chaque verdict aux
réponses réellement produites (`2026-07-27_anythingllm_verdicts_verification.md`).

| | assistant-amu | AnythingLLM |
|---|---|---|
| Refus sur 4 questions volontairement hors-corpus | **4/4** | **1/4** |
| Questions répondables (16) — correcte et ancrée | **14/16** | **0/16** |
| — refus à tort | 2/16 | 1/16 |
| — plausible mais non ancrée, ou partiellement ancrée | 0/16 | 13/16 |
| — substantiellement fausse | 0/16 | 2/16 |

### Deux causes structurelles, et non une infériorité générale du produit

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

### Ce que ce rapport ne montre pas

- **La performance d'AnythingLLM correctement configuré** — refus paramétré,
  connecteur web adapté, éventuellement un autre embeddeur. Le cadrage est
  *out-of-the-box*, ce n'est pas un plafond de capacité produit.
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
  n'est pas persisté.

### Rejouer l'expérience

La configuration initiale d'AnythingLLM — choix du fournisseur, création du
workspace — **n'a pas d'API** et se fait à la main, après activation de WSL2 sur
un poste Windows (redémarrage requis). Une fois le workspace en place :

```bash
# .env : ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, ANYTHINGLLM_WORKSPACE_SLUG
python eval/anythingllm_compare.py ingest                        # importe le corpus dans le workspace
python eval/anythingllm_compare.py ask --questions eval/questions.yaml
```

Le côté assistant-amu se rejoue par `python eval/evaluate.py --mode end-to-end --k 5`.
Les deux côtés consomment des appels à l'API Mistral.

### Fichiers de cette branche

| Fichier | Contenu |
| :--- | :--- |
| `eval/anythingllm_compare.py` | Pilotage : import du corpus et interrogation du workspace |
| `eval/reports/2026-07-26_anythingllm_vs_assistant-amu.md` | Rapport complet, tableau question par question |
| `eval/reports/anythingllm_judge_verdicts.json` | Verdicts des huit juges |
| `eval/reports/anythingllm_raw_answers.json` | Réponses brutes d'AnythingLLM |
| `eval/reports/assistant_amu_full_answers.json` | Réponses brutes d'assistant-amu |

Les deux fichiers de réponses brutes sont versionnés — sans précédent dans le
dépôt, où seuls les rapports `.md` l'étaient — parce qu'ils sont la seule base
probante des verdicts.

### Ce que la vérification des verdicts a corrigé

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
0/16 sur l'ancrage. Ce que la vérification établit en plus, c'est que le biais
pressenti — un jury qui nommait les deux systèmes devant un écart annoncé de
14/16 à 0/16 — a bien produit des effets mesurables, tous du même côté.

Elle isole également un mode d'échec que les **deux causes structurelles ne
couvrent pas** : sur q11, AnythingLLM avait récupéré le bon PDF, correctement
ingéré, et l'a contredit sur deux points.

### Fil ouvert

Les réponses d'assistant-amu jugées « correctes et ancrées » n'ont pas été
revérifiées **contre le corpus lui-même** — cela suppose de rouvrir les documents
sources, question par question. Et le rejugement à l'aveugle de l'identité des
systèmes reste à faire : la vérification constate le biais par ses effets, elle
ne le supprime pas.

---

## Références bibliographiques et état de l'art

* Anthropic — [*Contextual Retrieval*](https://www.anthropic.com/engineering/contextual-retrieval)
* Claude Cookbook — [*Contextual Embeddings Guide*](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
* Framework RAGAS — [*Automated Evaluation of Retrieval Augmented Generation*](https://docs.ragas.io) : vocabulaire d'évaluation (*faithfulness*, *context recall*)
* Projet Docling (IBM) — [*Structured Document Parsing*](https://github.com/docling-project/docling) : analyse de documents PDF (mise en page, tableaux)
* Références applicatives : [RAGFlow](https://github.com/infiniflow/ragflow), kotaemon

> AssistantAMU ne se positionne pas en concurrence de ces moteurs : le projet en réimplémente le cœur fonctionnel en quelques centaines de lignes, dans un objectif de maîtrise et d'explicabilité de chaque composant.
