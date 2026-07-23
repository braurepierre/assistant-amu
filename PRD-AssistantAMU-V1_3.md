# PRD — AssistantAMU

> **Version 1.3** — correctifs de spécification issus d'une relecture technique (juillet 2026). Changements vs v1.2 : piège n°3 documenté — troncature silencieuse au `num_ctx` d'Ollama, `num_ctx` explicite dans `OllamaBackend`, argument « 32k » corrigé (§2, §7.4) ; préfixes E5 appliqués par famille de modèle, jamais à `sentence-camembert-base` (§6.1, §7.3, §7.6) ; chunking à plafond dur ≤ 500 tokens, préfixe compris (§5.1.2, §7.2) ; `--embedding-model` opère sur une collection parallèle éphémère, la collection de production n'est jamais touchée (§7.6) ; refus vérifié par comparaison normalisée plutôt qu'au caractère près (§7.6, F6) ; sémantique du champ `score` définie (§7.5) ; manifeste `corpus/ingested.jsonl` traçant les documents ajoutés via `/ingest` (§6.3, §7.1, §7.5) ; unités du plan explicitées, 1 j = 1 soirée (§10). Le périmètre fonctionnel est inchangé.

> **Version 1.2** — passe de conformité à la documentation Anthropic et à l'état de l'art RAG achevée (sources vérifiées en juillet 2026, listées en fin de document). Changements vs v1.0 : décision RAG vs long-contexte documentée (§2) ; prompt RAG restructuré — règles en système, sources en balises XML, question en fin de prompt (§7.4) ; fusion `rrf` mesurée par le harnais dès la V1 (§5.1.8, §7.6) ; comparaison de modèles d'embedding dont `sentence-camembert-base` (§6.1, §7.6, Phase 5) ; escalade Docling par document pour les PDF difficiles (§7.2) ; terminologie d'évaluation alignée sur RAGAS (§7.6) ; feuille de route hiérarchisée, Contextual Retrieval en tête (§5.3) ; section Références ajoutée. Le périmètre fonctionnel V1 est inchangé.

> **Document de référence pour le développement.** Ce PRD est destiné à être lu par Claude (Claude Code ou claude.ai) comme brief de développement. Les sections « Non-objectifs » (§3) et « Instructions pour Claude » (§11) sont contractuelles : toute fonctionnalité absente du périmètre §5 requiert l'accord explicite de l'utilisateur avant implémentation. Les placeholders `[À_PRÉCISER]` signalent une information à demander à l'utilisateur — ne jamais les combler par une invention.

---

## 1. Résumé exécutif

AssistantAMU est un assistant documentaire RAG (Retrieval-Augmented Generation) construit sur les documents publics d'Aix-Marseille Université (règlements de scolarité, guides étudiants, pages des composantes). Il expose une API FastAPI : on lui pose une question en français, il répond en citant les passages sources, et refuse explicitement de répondre quand l'information est absente du corpus. Le système est **LLM-agnostique par construction** (backend local Ollama ou API Mistral, commutable par configuration) et livré avec un **harnais d'évaluation reproductible** comparant recherche sémantique et BM25. Le développement se fait en deux versions : **V1 single-turn** (MVP, 3-4 semaines en soirées), puis **V2 multi-turn** par query condensation (+4-6 soirées), l'API V1 étant conçue pour cette extension sans rupture de contrat.

## 2. Contexte et motivation

- **Finalité** : un artefact technique fonctionnel et démontrable — un assistant documentaire construit sur des documents publics réels.
- **Conséquence sur les choix** : chaque décision technique privilégie la compréhension démontrable (pipeline en Python pur d'abord, framework ensuite) et l'évaluation rigoureuse (harnais scripté) plutôt que la richesse fonctionnelle.
- Le développeur (Claude) travaille par sessions courtes avec un utilisateur disposant de quelques soirées par semaine : chaque phase doit livrer un incrément testable de manière autonome.

**Décision de conception — pourquoi RAG plutôt que long-contexte ?** Anthropic recommande, pour une base documentaire inférieure à ~200 000 tokens (~500 pages), de placer l'intégralité du corpus dans le prompt avec prompt caching plutôt que de faire du RAG (voir Références). Le corpus AMU pourrait approcher ce seuil. Le RAG reste néanmoins le bon choix ici, pour quatre raisons : (1) maîtriser le RAG de bout en bout est l'objectif même du projet ; (2) le backend local est contraint — le modèle `mistral` 7B annonce 32k tokens, mais Ollama le sert par défaut avec une fenêtre bien plus réduite (piège n°3, §7.4), et même portée à 8k elle exclut un corpus entier en contexte ; (3) coût et latence par requête d'un contexte massif sont incompatibles avec un free tier et un CPU ; (4) les citations passage par passage — cœur du produit — sont natives en RAG. La question « pourquoi ne pas tout mettre dans le contexte ? » est un classique : la réponse est désormais documentée.

## 3. Objectifs et non-objectifs

### Objectifs (hiérarchisés)

1. Pipeline RAG complet fonctionnel en local : ingestion → indexation → retrieval → génération sourcée en français.
2. Harnais d'évaluation reproductible en une commande : recall@k du retrieval, comparaison sémantique vs BM25, taux de refus correct, sensibilité aux paramètres (taille de chunks, k).
3. API documentée (`/ask`, `/ingest`, `/health`) avec contrats stables et rétrocompatibles V1→V2.
4. Backend LLM commutable par variable d'environnement (Ollama local ↔ API Mistral) via une abstraction unique.
5. V2 : gestion conversationnelle par query condensation, évaluée sur des scénarios de dialogue.
6. Dépôt GitHub exemplaire : commits atomiques, README argumenté, JOURNAL.md des problèmes/solutions, prompts versionnés.

### Non-objectifs (contractuels — ne pas implémenter, même « pour bien faire »)

- **Pas d'authentification** ni de gestion multi-utilisateurs (projet local mono-utilisateur). La gestion des *secrets* (clé API) reste en revanche dans le périmètre.
- **Pas de déploiement** : ni cloud, ni Docker, ni CI. Tout tourne en local.
- **Pas de crawling automatique** ni de mise à jour planifiée du corpus. Le corpus est constitué manuellement (liste versionnée + script one-shot) et enrichi via `/ingest`.
- **Pas de streaming** des réponses (SSE/websockets).
- **Pas de reranking** (cross-encoder) ni de fusion hybride dans le pipeline de réponse `/ask` en V1/V2 (→ évolutions futures). Nuance : la *mesure* de la fusion RRF par le harnais d'évaluation (§5.1.8) fait bien partie de la V1 — mesurer n'est pas brancher.
- **Pas d'OCR** : les PDF scannés sans couche texte sont signalés et exclus.
- **Pas d'autre langue** que le français (questions et réponses).
- **UI strictement plafonnée** au bonus décrit en §5.4 — jamais au-delà.
- **Pas de LangChain en V1** : le port LangChain est un exercice de comparaison isolé sur une branche dédiée (Phase 6).

## 4. Utilisateurs et cas d'usage

**Persona principal** : étudiant(e) ou personnel d'AMU cherchant une information administrative précise (césure, MCC, CVEC, calendriers, régimes spéciaux d'études). **Persona secondaire** : le mainteneur qui démontre le système — la robustesse d'une question isolée prime sur le spectaculaire.

User stories :

1. En tant qu'étudiant, je pose une question en français et j'obtiens une réponse citant document et passage, afin de pouvoir vérifier la source moi-même.
2. En tant qu'étudiant, si l'information n'est pas dans le corpus, le système me le dit explicitement, afin de ne jamais recevoir une réponse inventée.
3. En tant que mainteneur, j'ajoute un nouveau document via `/ingest` sans réindexer l'existant, afin d'enrichir le corpus au fil de l'eau.
4. En tant que développeur, je bascule du LLM local à l'API en changeant une variable d'environnement, afin d'itérer vite (API) et de démontrer en local (souveraineté).
5. En tant qu'évaluateur, je lance une commande et j'obtiens un rapport chiffré du retrieval (sémantique vs BM25), afin de mesurer l'effet de chaque changement de paramètre.
6. *(V2)* En tant qu'étudiant, je pose une question de suivi elliptique (« Et pour un étudiant en droit ? ») et le système la comprend dans le contexte de la conversation.

## 5. Périmètre fonctionnel

### 5.1 MVP — V1 (single-turn)

1. **Constitution du corpus** : script de téléchargement piloté par `corpus/sources.yaml` (15-30 documents PDF/HTML du site amu.fr).
2. **Pipeline d'ingestion** : extraction (PDF/HTML) → nettoyage → chunking (≤ 500 tokens, préfixe compris — §7.2 ; chevauchement ~50, frontières de paragraphes respectées) → métadonnées conservées.
3. **Indexation** : embeddings `intfloat/multilingual-e5-small` → ChromaDB persistant (distance cosinus).
4. **Retrieval** : top-k sémantique (k=5 par défaut, paramétrable par requête).
5. **Abstraction LLM** : protocole unique, deux implémentations (Ollama `mistral` / API Mistral `mistral-small-latest`), sélection par `LLM_BACKEND`.
6. **Prompt RAG** versionné dans `prompts/` avec changelog ; v0 fourni en §7.4 ; cas limites gérés (hors corpus, contradictions, hors sujet).
7. **API FastAPI** : `POST /ask`, `POST /ingest`, `GET /health` — contrats en §7.5.
8. **Harnais d'évaluation** : jeu de 15-20 questions annotées + 3-4 questions volontairement sans réponse ; `evaluate.py` mesure recall@k pour trois méthodes — sémantique, BM25, et leur **fusion RRF** (~30 lignes, les deux index existant déjà) — et produit un rapport Markdown daté. La fusion est *mesurée seulement* : le pipeline de réponse `/ask` reste en sémantique pur en V1 ; la bascule en hybride est une décision V2.1 fondée sur ces chiffres.
9. **Port LangChain** (Phase 6) : réimplémentation du pipeline de requête sur branche `langchain-port`, à des fins de comparaison documentée dans le README (« ce que le framework abstrait »).

### 5.2 V2 (multi-turn)

10. **Champ `history` optionnel** dans `/ask` (rétrocompatible : son absence = comportement V1 inchangé).
11. **Query condensation** : reformulation de la question courante en question autonome avant retrieval (prompt dédié, v0 fourni en §7.7).
12. **Évaluation conversationnelle** : 5-8 scénarios de 3 tours dans `eval/scenarios.yaml`, mesures par tour.

### 5.3 Évolutions futures (documentées, non implémentées — par ordre de priorité)

1. **Contextual Retrieval** (Anthropic, sept. 2024) : préfixer chaque chunk d'un court contexte généré par LLM le situant dans son document (« Extrait du Règlement des études 2025-2026, section césure : … ») **avant** l'embedding *et* l'indexation BM25. Résout la décontextualisation typique des chunks administratifs (« l'article 12 » — de quel règlement ?). Chiffres publiés par Anthropic : −49 % d'échecs de retrieval (embeddings + BM25 contextuels), −67 % en ajoutant un reranking. Coût : 1 appel LLM par chunk à l'indexation (document entier en contexte) — faisable via Ollama ou l'API sur un corpus de cette taille. L'effet est directement mesurable par le harnais §7.6 : **c'est la candidate n°1 pour une V2.1.** Réf. : `https://www.anthropic.com/engineering/contextual-retrieval`
2. **Bascule du pipeline en recherche hybride** : la mesure `--method rrf` existe dès la V1 ; si elle domine le sémantique pur sur le jeu d'évaluation, brancher `/ask` dessus est un petit changement dans `retrieval/`.
3. **Reranking cross-encoder** sur un top-20 élargi (candidat : `BAAI/bge-reranker-v2-m3`, multilingue, CPU).
4. **Évaluation automatisée RAGAS** (faithfulness, answer relevancy, context precision/recall) — adoptée *après* avoir pratiqué ces mesures manuellement en V1, pour savoir ce que le framework automatise.
5. **Multi-query / RAG-Fusion et HyDE** (variantes de la question générées avant retrieval) : bon à connaître ; disproportionné ici.
6. Streaming des réponses ; Dockerfile ; GitHub Action pytest ; re-crawl périodique avec détection de changements.

*Écartés délibérément comme disproportionnés pour un corpus de 15-30 documents : GraphRAG, RAG agentique, fine-tuning d'un modèle d'embedding.*

### 5.4 Bonus plafonné (hors critères d'acceptation)

- Interface Gradio de démonstration : **un seul fichier `demo.py`, ≤ 60 lignes, pur client HTTP de l'API, zéro logique métier**. À ne réaliser que si toutes les phases V1 sont validées.

## 6. Stack technique et architecture

### 6.1 Stack

| Composant | Choix | Justification |
|---|---|---|
| Langage | Python ≥ 3.11 | Type hints modernes, écosystème NLP |
| Embeddings | `sentence-transformers` + `intfloat/multilingual-e5-small` | Léger, CPU-friendly, bon en français |
| Embeddings — comparaison Phase 5 | `dangvantuan/sentence-camembert-base` | Encodeur français fine-tuné pour la similarité (dérivé de CamemBERT) ; mesuré contre e5-small par le harnais, non utilisé par le pipeline V1 ; n'utilise pas les préfixes E5 (§7.3) |
| Base vectorielle | `chromadb` (mode persistant local) | Zéro infrastructure |
| Recherche lexicale | `rank_bm25` | Référence de comparaison, 5 lignes d'usage |
| LLM local | Ollama, modèle `mistral` (7B) | Gratuit, données privées ; alternative `llama3.2` (3B) si machine modeste — voir points ouverts |
| LLM API | Mistral La Plateforme, `mistral-small-latest` | Plan gratuit, latence faible pour itérer |
| Extraction PDF | `pdfplumber` (premier choix) ; `docling` (escalade) | pdfplumber : léger et lisible pour les PDF simples. Docling (IBM, open source, local) : analyse de layout + structure de tableaux (TableFormer), export Markdown — réservé aux PDF à mise en page complexe, voir §7.2 |
| Extraction HTML | `beautifulsoup4` | Standard |
| API | `fastapi` + `uvicorn` + `pydantic` v2 | Doc interactive `/docs` incluse |
| HTTP client | `httpx` | Appels Ollama et Mistral |
| Tests | `pytest` | — |
| Config | `python-dotenv` + module `config.py` | — |

### 6.2 Architecture

```
INDEXATION (hors ligne)
sources.yaml → download → extract (pdfplumber/bs4) → clean → chunk (~500 tk, ov. 50)
     → embed ("passage: " + texte, e5-small) → ChromaDB (cosine) 
     → [en parallèle, pour l'éval : index BM25 en mémoire depuis les mêmes chunks]

REQUÊTE V1 (temps réel)
question → embed ("query: " + question) → ChromaDB top-k
     → prompt RAG (règles en système ; sources XML puis question en user) → LLMBackend.generate → réponse + sources

REQUÊTE V2 (temps réel)
question + history → [si history non vide : condensation via LLMBackend] → question autonome
     → retrieval sur la question autonome → génération (question originale + condensée + extraits) → réponse + sources + condensed_question
```

### 6.3 Structure de fichiers

```
assistant-amu/
├── corpus/
│   ├── sources.yaml          # liste versionnée des documents sources
│   ├── ingested.jsonl        # manifeste des documents ajoutés via /ingest — versionné
│   └── raw/                  # documents téléchargés — NON versionné (.gitignore)
├── src/assistant_amu/
│   ├── config.py             # lecture .env, valeurs par défaut, validation
│   ├── ingestion/
│   │   ├── download.py       # sources.yaml → corpus/raw/
│   │   ├── extract.py        # PDF/HTML → texte brut
│   │   ├── clean.py          # nettoyage
│   │   └── chunk.py          # chunking + métadonnées
│   ├── retrieval/
│   │   ├── embedder.py       # wrapper e5 (gère les préfixes query:/passage:)
│   │   ├── vector_store.py   # ChromaDB
│   │   └── bm25_store.py     # index BM25 (usage : évaluation)
│   ├── generation/
│   │   ├── llm.py            # protocole LLMBackend + OllamaBackend + MistralBackend
│   │   └── rag.py            # assemblage prompt, pipeline de requête, condensation (V2)
│   └── api/
│       ├── main.py           # app FastAPI, endpoints
│       └── schemas.py        # modèles Pydantic (contrats §7.5)
├── prompts/
│   ├── rag_system.md         # prompt système RAG (version courante)
│   ├── condense_system.md    # V2 — prompt de condensation
│   └── CHANGELOG.md          # chaque version : date, diff résumé, raison
├── eval/
│   ├── questions.yaml        # jeu single-turn annoté
│   ├── scenarios.yaml        # V2 — scénarios de dialogue
│   ├── evaluate.py           # harnais (retrieval + end-to-end)
│   └── reports/              # rapports datés générés
├── tests/
├── demo.py                   # bonus plafonné (≤ 60 lignes)
├── .env.example              # toutes les variables, valeurs factices
├── .gitignore                # dès le premier commit : .env, chroma_db/, corpus/raw/, __pycache__
├── JOURNAL.md                # problème → diagnostic → solution, daté
└── README.md
```

## 7. Spécifications techniques détaillées

### 7.1 Corpus et téléchargement

- `corpus/sources.yaml` : liste d'entrées `{url, type: pdf|html, title, category}`. Catégories initiales : `reglement-scolarite`, `guide-etudiant`, `composante`. Une entrée peut aussi pointer un chemin local (`path:` au lieu de `url:`) pour les documents récupérés manuellement.
- `[À_PRÉCISER]` : la liste exacte des 15-30 URLs — à constituer par l'utilisateur en Phase 1 ; le développeur fournit le format et le script, pas la liste.
- Téléchargement : User-Agent identifiable (`AssistantAMU-corpus-builder/0.1 (projet etudiant)`), respect de `robots.txt`, délai ≥ 1 s entre requêtes, échec d'une URL loggé sans interrompre le lot.
- `corpus/raw/` est exclu de git : la reproductibilité passe par `sources.yaml` + le script, pas par le stockage des binaires (poids, et prudence vis-à-vis de la redistribution de documents tiers). Les documents ajoutés via `/ingest` — donc hors `sources.yaml` — sont tracés dans `corpus/ingested.jsonl` (§7.5) : la reconstruction du corpus = `sources.yaml` + `ingested.jsonl` + les scripts.

### 7.2 Ingestion

- **PDF — escalade en trois niveaux** : (1) `pdfplumber` par défaut, extraction page par page ; (2) si le dump d'inspection (F2) révèle une sortie incohérente pour un document — tableaux détruits, colonnes entrelacées — le passer par **Docling** (export Markdown, entièrement local), le basculement étant déclaré par document dans `sources.yaml` (`extractor: docling`) ; (3) si le document est scanné sans couche texte (texte vide) → exclusion loggée (pas d'OCR — non-objectif). Chaque escalade = une entrée JOURNAL.
- **HTML** : BeautifulSoup ; extraire le contenu principal, retirer `nav`, `footer`, `script`, `style`, menus. Conserver la hiérarchie de titres (`h1`-`h3`) traversée par chaque passage dans une métadonnée `section` du chunk — coût quasi nul, utile aux réponses sourcées et prérequis du Contextual Retrieval (§5.3.1).
- **Nettoyage** : suppression des en-têtes/pieds répétés (détection : lignes identiques récurrentes sur ≥ 3 pages), normalisation des espaces et sauts de ligne, retrait des sommaires (heuristique : forte densité de points de conduite ou de numéros de page).
- **Chunking** : plafond dur ≤ 500 tokens par chunk, préfixe `passage: ` compris (tokenizer du modèle d'embedding) — e5-small tronque silencieusement au-delà de 512 tokens, la marge est délibérée. Chevauchement ~50, découpe prioritairement aux frontières de paragraphes (double saut de ligne), jamais au milieu d'une phrase si évitable ; si respecter une frontière ferait dépasser le plafond, la frontière cède (découpe à la fin de phrase la plus proche sous le plafond). Chaque chunk porte : `{source_title, source_url, page (si PDF), chunk_index, category}`.
- **Identifiant de chunk** : hash stable (source + index) ; **identifiant de document** : hash du contenu extrait — utilisé pour le dédoublonnage à l'ingestion et par `/ingest` (409 si déjà présent).

### 7.3 Retrieval

- **Piège documenté n°1** : les modèles E5 exigent les préfixes `"query: "` (questions) et `"passage: "` (chunks) à l'encodage. Sans eux, les performances chutent silencieusement. Symétriquement, ces préfixes sont propres à la famille E5 : les imposer à `sentence-camembert-base` (comparaison Phase 5) polluerait ses entrées et fausserait la mesure. Le wrapper `embedder.py` porte donc une table {modèle → préfixes} et applique le bon jeu selon la famille (E5 : oui ; CamemBERT : aucun) — aucun appel direct au modèle ailleurs dans le code.
- **Piège documenté n°2** : la métrique par défaut de ChromaDB est L2. Créer la collection avec `metadata={"hnsw:space": "cosine"}`.
- ChromaDB en mode persistant (`./chroma_db`), une collection unique `amu_docs`.
- BM25 (`rank_bm25.BM25Okapi`) : construit à la volée depuis les chunks stockés (tokenisation : minuscules + découpe sur les non-alphanumériques — suffisant pour l'évaluation, ne pas sur-raffiner).

### 7.4 Génération

**Abstraction — verrou anti-sur-ingénierie** : une seule méthode, pas de streaming, pas de retry élaboré, pas d'état.

```python
class LLMBackend(Protocol):
    name: str  # ex. "ollama/mistral" — repris dans les réponses API et les rapports d'éval
    def generate(self, system: str, user: str) -> str: ...

class LLMBackendError(Exception):
    """Cause normalisée : 'timeout' | 'connection' | 'auth' | 'quota' | 'other'."""
```

- `OllamaBackend` : `POST http://localhost:11434/api/chat`, `stream=false`, timeout 120 s, modèle via `OLLAMA_MODEL` (défaut `mistral`), `options: {"num_ctx": N}` avec N lu dans `OLLAMA_NUM_CTX` (défaut 8192).
- `MistralBackend` : API chat completions officielle, clé via `MISTRAL_API_KEY`, timeout 30 s, modèle via `MISTRAL_MODEL` (défaut `mistral-small-latest`).
- Sélection : `LLM_BACKEND=ollama|mistral` (défaut `ollama`). Température 0.2 pour la factualité.
- **Piège documenté n°3** : Ollama tronque silencieusement le prompt à `num_ctx` (2048 ou 4096 par défaut selon la version installée), pas à la capacité du modèle. À k=5, les sources pèsent déjà ~2 500-3 000 tokens : sans `num_ctx` explicite, des pans du prompt disparaissent sans erreur ni avertissement côté client — seule la qualité des réponses se dégrade. 8192 couvre k=10 avec marge (système + question + génération). Coût : le cache KV est alloué pour `num_ctx` entier ; sur machine modeste, replier sur `OLLAMA_NUM_CTX=4096` et k ≤ 5.

**Prompt RAG v0** (`prompts/rag_system.md` — point de départ, à itérer et versionner en Phase 3). Structure conforme aux recommandations de prompting d'Anthropic : les règles vivent dans le message *système* ; le message *utilisateur* place les sources balisées en XML d'abord et la question **en fin de prompt** — pour les contextes longs, données avant question améliore le suivi des instructions, et le balisage XML sépare sans ambiguïté les données des consignes.

Message système :

```
Tu es AssistantAMU, un assistant documentaire d'Aix-Marseille Université.
Tu réponds à la question de l'utilisateur en te fondant EXCLUSIVEMENT sur les
extraits fournis entre balises <sources>.

Règles impératives :
1. Si les extraits ne contiennent pas l'information demandée, réponds
   exactement : « Je ne trouve pas cette information dans les documents
   disponibles. » N'utilise jamais tes connaissances générales pour combler.
2. Cite tes sources dans le corps de la réponse au format [S1], [S2]…,
   correspondant aux identifiants des balises <source>.
3. Si deux extraits se contredisent, signale explicitement la contradiction
   et cite les deux sources.
4. Réponds en français, de façon concise et factuelle.
```

Gabarit du message utilisateur (assemblé par `rag.py`) :

```
<sources>
<source id="S1" titre="{titre}" page="{page}" section="{section}">
{texte du chunk}
</source>
<source id="S2" …>…</source>
</sources>

Question : {question}
```

**Itération candidate documentée pour la Phase 3** (technique de fidélité issue des pratiques Anthropic) : le *quotes-first* — demander au modèle d'extraire d'abord, entre balises `<citations>`, les passages des sources pertinents pour la question, puis de rédiger la réponse uniquement à partir de ces citations. À tester contre la v0 sur le jeu d'évaluation, en particulier sur le taux de refus corrects et la fidélité.

**Cas limites à couvrir explicitement lors des itérations de Phase 3** (chaque itération = une entrée dans `prompts/CHANGELOG.md` avec la raison du changement) : réponse absente du corpus ; sources contradictoires ; question hors sujet (« quelle heure est-il ? ») ; question ambiguë entre deux composantes.

### 7.5 API — contrats

**`POST /ask`**

Requête (V1 ; le champ `history` est ajouté en V2 comme optionnel — rétrocompatible) :

```json
{ "question": "Quelles sont les modalités de césure à AMU ?", "k": 5 }
```

- `question` : chaîne, 1-500 caractères (422 sinon). `k` : entier 1-10, défaut 5.

Réponse 200 :

```json
{
  "answer": "La césure à AMU… [S1]",
  "sources": [
    { "title": "Règlement des études 2025-2026", "url": "https://…", "page": 12,
      "excerpt": "premiers ~300 caractères du chunk…", "score": 0.83 }
  ],
  "model": "ollama/mistral",
  "retrieved_chunks": 5,
  "condensed_question": null
}
```

- `score` : similarité cosinus `= 1 − distance`, ∈ [0, 1], plus haut = plus pertinent. ChromaDB renvoie des *distances* (plus bas = plus proche) : convertir, ne jamais exposer la valeur brute.

Erreurs : `422` (validation Pydantic) ; `503 {"detail": "LLM backend unavailable: <cause>"}` quand `LLMBackendError` remonte.

**`POST /ingest`** — multipart : `file` (pdf ou html), champs `title` (requis), `url` (optionnel), `category` (optionnel). Réponse 200 : `{"document_id": "…", "chunks_added": 42}`. `409` si le hash du contenu existe déjà. `422` si le type de fichier n'est pas géré. Chaque ingestion réussie ajoute une ligne au manifeste versionné `corpus/ingested.jsonl` : `{document_id, title, url, category, ingested_at}` — traçabilité des documents hors `sources.yaml` (§7.1).

**`GET /health`** — `{"chroma": "ok", "llm_backend": "ok|unreachable", "documents": 23, "chunks": 812}`. Le ping LLM est un `generate` minimal ou un appel de liste de modèles, timeout court (5 s).

### 7.6 Harnais d'évaluation

- `eval/questions.yaml` : entrées `{id, question, answerable: true|false, expected_source (titre), expected_keywords: [mots devant figurer dans le bon chunk]}`. 15-20 questions answerable + 3-4 non-answerable. **Astuce de constitution** : rédiger les questions au fil de la lecture des documents en Phase 1.
- Le jeu doit inclure délibérément les deux régimes de retrieval : questions à sigles/termes exacts (CVEC, MCC, « article N ») et questions en paraphrase (« interrompre mes études un an » pour la césure).
- `evaluate.py` :
  - `--mode retrieval` : pour chaque question answerable, le chunk attendu (identifié par `expected_source` + `expected_keywords`) est-il dans le top-k ? Métrique : recall@k, calculée pour `--method semantic|bm25|rrf|all` — `rrf` étant la fusion Reciprocal Rank Fusion des deux classements (score = Σ 1/(60 + rang), ~30 lignes au-dessus des deux index existants), *mesurée seulement* : le pipeline `/ask` reste en sémantique pur (§5.1.8).
  - `--mode end-to-end` : appelle le pipeline complet ; vérifie le refus sur les questions non-answerable par comparaison normalisée avec la phrase attendue (minuscules, ponctuation retirée, espaces repliés — un match au caractère près est fragile avec un 7B, même à température 0.2) ; produit une colonne « fidélité » à remplir manuellement (jugement humain, pas de LLM-juge en V1).
  - `--k N`, `--chunk-report` et `--embedding-model <id_hf>` pour les mesures de sensibilité (Phase 5) : tailles de chunks, valeurs de k, et modèles d'embedding — `intfloat/multilingual-e5-small` (défaut) contre `dangvantuan/sentence-camembert-base` (§6.1). Mécanique : `--embedding-model` construit une collection ChromaDB parallèle éphémère (nom suffixé, ex. `amu_docs__camembert`), ré-embarque les mêmes chunks avec les préfixes propres à la famille du modèle (§7.3), mesure, puis supprime la collection — `amu_docs` n'est jamais modifiée ; compter quelques minutes de ré-embedding CPU par modèle sur un corpus de cette taille. Justification de méthode : les classements génériques (MTEB) ne prédisent pas le comportement sur un corpus spécifique, et le choix de l'embeddeur peut décaler sensiblement la précision du retrieval — d'où la primauté du harnais maison sur le leaderboard.
- Sortie : `eval/reports/AAAA-MM-JJ_<method>_k<k>.md` — tableau par question, agrégats, et **section « désaccords »** listant les questions où une seule des deux méthodes trouve le bon chunk. Ces désaccords alimentent le README (3 exemples de chaque régime).
- Aucun seuil de performance imposé a priori : le premier run établit la *baseline*, consignée dans le README ; les runs suivants s'y comparent.
- **Terminologie alignée sur RAGAS**, le cadre de référence de l'évaluation RAG : le recall@k du harnais est un proxy de *context recall* (la vérité terrain nécessaire est-elle récupérée ?), et la colonne « fidélité » correspond à *faithfulness* (part des affirmations de la réponse soutenues par les extraits). Employer ces termes dans les rapports et le README. Le jugement reste manuel en V1 — plus fiable qu'un LLM-juge à l'échelle de ~20 questions, et pédagogiquement supérieur ; l'automatisation RAGAS est l'évolution §5.3, point 4.

### 7.7 V2 — multi-turn par query condensation

- **Contrat** : `history` optionnel dans `/ask` : liste de `{"role": "user"|"assistant", "content": str}`. Au-delà des 6 derniers tours, troncature silencieuse (documentée dans `/docs`). Aucun stockage serveur : l'API reste stateless, le client renvoie l'historique.
- **Pipeline** : si `history` est non vide → appel `LLMBackend.generate` avec `prompts/condense_system.md` et l'historique + la question → question autonome → retrieval sur cette question → génération avec, dans le prompt utilisateur, la question originale ET la question condensée + les extraits.
- La réponse renvoie `condensed_question` (chaîne) — transparence et débogage ; `null` en single-turn.
- **Prompt de condensation v0** (`prompts/condense_system.md`) :

```
Tu reformules la dernière question d'un utilisateur en une question autonome,
compréhensible sans l'historique de conversation.

Règles :
1. Résous les références implicites (« et pour… », « celle-ci »,
   « dans ce cas ») à partir de l'historique fourni.
2. N'ajoute AUCUNE information absente de l'historique ou de la question.
3. Si la question est déjà autonome, renvoie-la strictement inchangée.
4. Réponds uniquement par la question reformulée, sans commentaire ni guillemets.
```

- **Évaluation** : `eval/scenarios.yaml` — 5-8 scénarios de 3 tours, chaque tour annoté comme les questions V1. Mesures par tour : (a) condensation correcte (jugement manuel O/N consigné), (b) recall du retrieval sur la question condensée, (c) fidélité de la réponse. `evaluate.py --mode conversation`.

## 8. Critères d'acceptation

Chaque fonctionnalité du §5.1/§5.2 est « faite » quand :

| # | Fonctionnalité | Critère objectif |
|---|---|---|
| F1 | Corpus | `python -m assistant_amu.ingestion.download` télécharge toutes les entrées de `sources.yaml` ; les échecs sont listés en fin de run sans interrompre le lot. |
| F2 | Ingestion | La commande d'ingestion traite tout `corpus/raw/` ; log final : documents traités, exclus (scannés), chunks produits. Une relance immédiate ajoute 0 doublon. Une commande de dump affiche N chunks aléatoires avec métadonnées pour inspection visuelle. |
| F3 | Indexation | La collection ChromaDB contient un nombre de chunks égal au log d'ingestion ; la métrique est cosinus (vérifiable dans les métadonnées de collection). |
| F4 | Retrieval | Pour la question de référence « Quelles sont les modalités de césure à AMU ? », le top-5 contient au moins un chunk du document attendu (test automatisé une fois le corpus figé). |
| F5 | Abstraction LLM | Les deux backends passent le même test d'intégration manuel ; `LLM_BACKEND` mal configuré → erreur explicite au démarrage, pas à la première requête. Backend éteint → `/ask` répond 503 avec cause. |
| F6 | Prompt RAG | Question hors corpus → la phrase de refus, vérifiée par comparaison normalisée (§7.6), 0 source citée. `prompts/CHANGELOG.md` contient ≥ 3 itérations motivées. |
| F7 | API | `/docs` fonctionnel ; les 3 endpoints respectent les contrats §7.5 (tests pytest avec backend LLM mocké) ; latence `/ask` mesurée et consignée dans le README pour chaque backend (ordres de grandeur attendus : secondes via API, dizaines de secondes à ~1-2 min en local selon machine — pas de seuil dur en V1). |
| F8 | Harnais | `python eval/evaluate.py --mode retrieval --method all` produit le rapport daté avec agrégats des trois méthodes (sémantique, BM25, RRF) et section désaccords ; la baseline est reportée dans le README avec ≥ 3 exemples de désaccord commentés. |
| F9 | Port LangChain | Branche `langchain-port` : `/ask` rend des réponses équivalentes ; le README contient un paragraphe « ce que LangChain abstrait » comparant les deux implémentations. |
| F10-12 | V2 | Scénario de référence (tour 1 : césure ; tour 2 : « Et pour un étudiant en droit ? ») → `condensed_question` contient « césure » et « droit », et le retrieval ramène des chunks césure. Requête sans `history` → comportement V1 strictement identique (test de non-régression). Rapport `--mode conversation` produit. |

## 9. Contraintes et risques

| Risque | Impact | Mitigation |
|---|---|---|
| **PDF AMU hétérogènes** (colonnes, tableaux, mises en page) — risque n°1 | Chunks incohérents → retrieval dégradé | Inspection visuelle systématique (commande de dump F2) ; escalade Docling par document (`extractor: docling`, §7.2) ; exclusion documentée des cas restants ; chaque escalade notée au JOURNAL |
| Scraping bloqué ou URLs instables | Corpus incomplet | `sources.yaml` accepte des chemins locaux ; téléchargement manuel en repli |
| Latence Ollama sur CPU | Itération pénible, démo risquée | Workflow : développer sur l'API Mistral, valider/démontrer en local ; latences mesurées à l'avance pour la démo |
| e5-small dilue les sigles | Retrieval raté sur requêtes lexicales | Précisément ce que le harnais mesure — y compris la fusion RRF dès la V1 ; comparaison avec `sentence-camembert-base` en Phase 5 ; bascule hybride en V2.1 si les chiffres la justifient |
| Sur-ingénierie par le développeur LLM | Budget temps consommé | Les non-objectifs §3 font foi ; règle §11 : demander avant tout ajout |
| Fuite de secrets | Rédhibitoire sur un dépôt public | `.gitignore` (incluant `.env`) **avant** le premier commit ; `.env.example` seul versionné |
| Dérive V2 pendant la V1 | MVP jamais fini | Interdiction d'implémenter quoi que ce soit de §7.7 avant validation de tous les critères F1-F9 |

## 10. Plan de développement par phases

Chaque phase se termine par un incrément démontrable, un commit propre et une entrée JOURNAL si un problème a été résolu. Unité : 1 j = 1 soirée de travail (~2-3 h) ; le total V1 (14-19 soirées) recouvre les « 3-4 semaines en soirées » du §1 à raison de 4-5 soirées par semaine.

- **Phase 0 — Squelette** (1 soirée) : structure §6.3, `.gitignore`, `.env.example`, `config.py`, `pyproject.toml`/`requirements.txt`, premier commit. *Sortie : `pytest` tourne (0 test), l'arborescence existe.*
- **Phase 1 — Corpus et ingestion** (2-3 j) : F1, F2. L'utilisateur constitue `sources.yaml` en parallèle et amorce `eval/questions.yaml` au fil de ses lectures. *Sortie : chunks inspectés visuellement.*
- **Phase 2 — Indexation et retrieval** (2-3 j) : F3, F4 + script de test manuel (question → top-5 affiché). *Sortie : pertinence vérifiée à l'œil sur 5 questions.*
- **Phase 3 — Génération** (3-4 j) : F5, F6. Itérations du prompt sur les 4 cas limites, chacune motivée au CHANGELOG. *Sortie : pipeline complet en ligne de commande.*
- **Phase 4 — API** (2-3 j) : F7, tests pytest (LLM mocké). *Sortie : démo via `/docs`.*
- **Phase 5 — Évaluation** (2-3 j) : F8 ; mesures de sensibilité consignées : 2 tailles de chunks, k ∈ {3, 5, 8}, comparaison des embeddeurs `e5-small` vs `sentence-camembert-base` (`--embedding-model`). *Sortie : baseline sémantique/BM25/RRF + désaccords + tableau des embeddeurs dans le README.*
- **Phase 6 — Port LangChain et finition** (2 j) : F9, README complet (architecture, choix justifiés, résultats, limites), relecture du JOURNAL. *Sortie : V1 taguée `v1.0`.*
- **Phase 7 — V2 multi-turn** (4-6 soirées) : F10-F12, dans l'ordre : contrat + condensation → non-régression single-turn → scénarios d'évaluation. *Sortie : tag `v2.0`.*
- **Bonus** (si temps) : `demo.py` Gradio, dans les limites du §5.4.

## 11. Instructions spécifiques pour Claude (développeur)

1. **Lire ce PRD en entier avant la première ligne de code.** Les non-objectifs (§3) et les plafonds (§5.4) sont contractuels : toute fonctionnalité non listée au §5 exige un accord explicite de l'utilisateur — poser la question, ne pas implémenter « au cas où ».
2. **Placeholders** : face à un `[À_PRÉCISER]`, s'arrêter et demander. Ne jamais inventer d'URL, de seuil ou de contenu de corpus.
3. **Ordre strict** : ne rien implémenter de la V2 (§7.7) tant que F1-F9 ne sont pas validés. Pas de LangChain hors de la branche `langchain-port`.
4. **Style** : Python ≥ 3.11, type hints partout, Pydantic v2 pour tout schéma d'API, fonctions courtes, docstrings concises. Code et docstrings en anglais ; README, JOURNAL et prompts en français.
5. **Erreurs** : exceptions métier dédiées (`LLMBackendError`, `IngestionError`), jamais de `except:` nu, messages actionnables (que faire, pas seulement quoi).
6. **Tests** : pytest ; fixtures de mini-documents pour l'ingestion ; `TestClient` FastAPI avec backend LLM mocké. Aucun test n'appelle un vrai LLM ou le réseau.
7. **Dépendances** : ne rien ajouter hors de la liste §6.1 sans une ligne de justification dans le JOURNAL.
8. **Commits** : atomiques, format conventional commits en anglais (`feat:`, `fix:`, `docs:`, `test:`), un commit ne mélange pas deux phases.
9. **JOURNAL.md** : à chaque problème non trivial rencontré : date, symptôme, diagnostic, solution. C'est un livrable, pas une option.
10. **Prompts** : toute modification de `prompts/*.md` s'accompagne d'une entrée CHANGELOG (raison + cas de test qui a motivé le changement).

---

## Hypothèses et points ouverts

- `[À_PRÉCISER]` **Liste des URLs du corpus** (Phase 1, à constituer par l'utilisateur — le développeur fournit format et script).
- `[À_PRÉCISER]` **Machine de développement** (RAM, GPU ?) : détermine le choix `mistral` (7B) vs `llama3.2` (3B) en local, et les latences de référence.
- `[À_PRÉCISER]` **Clé API Mistral** : compte La Plateforme créé ? (À faire par l'utilisateur — jamais par le développeur.)
- **Hypothèse** : dépôt GitHub public.
- **Hypothèse** : l'usage de documents publics AMU pour un projet personnel non commercial, sans redistribution des documents eux-mêmes (`corpus/raw/` non versionné), est acceptable. Point à garder en tête ; en cas de doute, ne pas publier le corpus.
- **Hypothèse** : les seuils de performance ne sont pas fixés a priori ; la baseline du premier run d'évaluation fait référence.

### Axes d'approfondissement suggérés

1. **Constituer ensemble `sources.yaml`** : une session dédiée pour sélectionner les 15-30 documents (équilibre règlements / guides / composantes) — c'est le fondement de tout le reste.
2. **Rédiger le jeu d'évaluation à quatre mains** : les 15-20 questions annotées gagnent à mêler votre connaissance du corpus et une revue systématique des deux régimes (lexical / sémantique).
3. **Après la baseline** : décider s'il faut fixer des seuils durs (recall@5 minimal) et si la recherche hybride RRF mérite de passer d'« évolution future » à « V2.1 » au vu des désaccords mesurés.

---

## Références état de l'art (sources vérifiées en juillet 2026)

*Sources ayant fondé les choix de ce PRD — à reprendre dans le README.*

- **Anthropic — Contextual Retrieval** (`https://www.anthropic.com/engineering/contextual-retrieval`) : article de référence de l'ingénierie du retrieval — contextual embeddings + contextual BM25 (−49 % d'échecs de retrieval, −67 % avec reranking) et arbitrage RAG vs long-contexte (seuil ~200k tokens avec prompt caching). Fonde le §2 (décision RAG) et le §5.3.1.
- **Claude Cookbook — Contextual Embeddings** (`https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide`) : implémentation officielle de référence, métrique Pass@k. Modèle d'inspiration directe pour le harnais §7.6.
- **RAGAS — documentation** (`https://docs.ragas.io`) : standard de l'évaluation RAG — *faithfulness*, *answer relevancy*, *context precision*, *context recall*. Vocabulaire adopté par le §7.6 ; automatisation en évolution §5.3.4.
- **RAGFlow** (`https://github.com/infiniflow/ragflow`) : moteur RAG open source de référence (de l'ordre de 70-85k étoiles en 2026), centré sur la compréhension profonde de documents et les réponses à citations traçables — l'étalon « produit » de ce qu'AssistantAMU réimplémente en version pédagogique.
- **kotaemon** (Cinnamon, open source) : application de QA documentaire reconnue pour ses citations détaillées avec prévisualisation des sources — référence d'UX de citation pour le format de réponse §7.5.
- **Docling** (IBM Research, open source) : parseur de documents à modèles de layout (DocLayNet) et de structure de tableaux (TableFormer), exécution locale, export Markdown — l'outil de l'escalade PDF §7.2.

**Positionnement** : AssistantAMU ne concurrence pas ces outils — il réimplémente leur cœur en quelques centaines de lignes pour pouvoir en expliquer chaque brique, ce que l'usage d'un moteur clé en main ne permettrait pas. Les références ci-dessus servent de vocabulaire commun et d'étalon, pas de dépendances.