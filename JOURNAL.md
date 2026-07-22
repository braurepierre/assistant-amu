# JOURNAL

Journal de bord du projet : chaque problème non trivial (symptôme → diagnostic →
solution, daté) et chaque décision notable. Livrable au même titre que le code
(PRD §11.9).

## 2026-07-22 — Phase 0 : squelette du projet

**Fait.** Mise en place de la structure §6.3 (packages `ingestion`, `retrieval`,
`generation`, `api` en stubs documentés), `config.py` avec chargement + validation
des variables d'environnement, `.gitignore` (posé **avant** le premier commit —
mitigation « fuite de secrets » §9), `.env.example`, `pyproject.toml`, prompts v0,
templates `sources.yaml` / `questions.yaml`, et un test de fumée sur la config.
`pytest` tourne au vert.

**Décision — `config.py` sans validation à l'import.** `config.py` expose
`load_settings()` (lecture + validation) et `get_settings()` (cache `lru_cache`).
La validation « fail-fast au démarrage » (F5) est portée par l'entrée applicative
(l'app FastAPI, Phase 4, appellera `get_settings()` à l'import), pas par l'import
de `config` lui-même : cela évite qu'un `.env` local incomplet casse la collecte
des tests, tout en conservant l'erreur explicite au lancement de l'app.

**Décision — dépendances hors liste §6.1 (justification requise par §11.7).**
- `pyyaml` : lecture de `corpus/sources.yaml` et des fichiers `eval/*.yaml` — ces
  formats sont imposés par le PRD (§7.1, §7.6), le parseur YAML est donc structurel.
- `python-multipart` : requis par FastAPI pour l'endpoint multipart `POST /ingest`
  (§7.5). Déclaré maintenant, utilisé en Phase 4.
- `docling` : placé en dépendance **optionnelle** (`[docling]`), car réservé à
  l'escalade PDF par document (§7.2) et lourd à installer.

**Environnement.** Python 3.14.3 détecté en local (le PRD exige ≥ 3.11).
Note de vigilance pour la Phase 1 : vérifier la disponibilité de roues (wheels)
pour `chromadb` / `sentence-transformers` / `docling` sous Python 3.14 ; à défaut,
créer l'environnement avec un interpréteur 3.11–3.12. Aucun blocage en Phase 0
(seuls `pytest` et `python-dotenv` sont installés à ce stade).

## 2026-07-22 — Environnement : pin Python 3.12 via uv

**Symptôme.** Seul Python 3.14.3 est installé sur la machine ; `torch` (tiré par
`sentence-transformers`) et `chromadb` n'ont pas encore de wheels pour 3.14.

**Diagnostic.** Python 3.14 est trop récent pour la pile ML au moment du projet.

**Solution.** `uv` (0.11.14) est disponible : `uv venv --python 3.12` provisionne
un CPython 3.12.13 autonome (dans le cache uv, non invasif) et `uv pip install -e
".[dev]"` installe toute la pile §6.1 sans erreur. Imports vérifiés : `chromadb`,
`sentence_transformers`, `pdfplumber`, `bs4`, `fastapi`, `rank_bm25`. `uv` est un
outil de dev, pas une dépendance runtime — aucun impact sur §6.1. Le `README`
documente les deux voies (uv et `python -m venv` + `pip`).

## 2026-07-22 — Phase 1 : corpus et ingestion (F1, F2)

**Fait.** Pipeline complet `download → extract → clean → chunk` avec métadonnées,
CLI d'ingestion (`stats`, `dump`), et 33 tests au vert (fixtures HTML + PDF réels).

**Décisions de conception.**
- *Compteur de tokens injectable* (`chunk.py`) : la production utilise le tokenizer
  e5 (`transformers.AutoTokenizer`, préfixe `passage: ` = 4 tokens) ; les tests
  injectent un simple compteur de mots — chunking testable sans charger de modèle.
- *Fusion de segments* : les blocs consécutifs de même `(page, section)` sont
  fusionnés avant découpe, pour que les paragraphes HTML forment des chunks de
  taille correcte au lieu d'un chunk minuscule par `<p>`.
- *`models.py`* (hors §6.3) : dataclasses partagées (`SourceDoc`, `TextBlock`,
  `Document`, `Chunk`) pour que `extract → clean → chunk → indexation` parlent le
  même vocabulaire. Organisation interne, aucune fonctionnalité §5 ajoutée.

**Dépendance hors §6.1 (justif. §11.7).** `fpdf2` en dépendance **de test** (extra
`dev`) : génère à la volée des PDF de fixture (dont un scanné = page sans texte)
pour tester extraction et exclusion, sans versionner de binaires (§7.1). Piège
rencontré : `multi_cell` de fpdf2 2.8 laisse le curseur à la marge droite —
`new_x=XPos.LMARGIN, new_y=YPos.NEXT` pour revenir à la marge gauche.

**En attente utilisateur.** F1/F4 ne seront *validés* qu'avec de vraies URLs dans
`corpus/sources.yaml` (`[À_PRÉCISER]`, §11.2). Le code et les tests sont prêts.

## 2026-07-22 — Phase 2 : indexation et retrieval (F3, F4)

**Fait.** `embedder.py` (préfixes E5 par famille, modèle injectable),
`vector_store.py` (ChromaDB persistant, espace cosinus, dédoublonnage par
`chunk_id` + `doc_id`, score = 1 − distance ∈ [0, 1]), commandes CLI `index` /
`search`. 12 tests supplémentaires (faux embedder déterministe, aucun
téléchargement de modèle). Total : 45 tests au vert.

**Smoke test réel** (e5-small téléchargé une fois, corpus synthétique local de
2 documents) : la requête paraphrasée « comment interrompre mes etudes pendant un
an » (sans le mot « césure ») ramène le chunk césure en tête (score 0.841) —
exactement le régime sémantique visé. Réindexation → +0 chunk (dédoublonnage F2
vérifié). Métadonnée `section` (chemin de titres) correctement capturée.

**Décisions.**
- *Embeddings gérés à la main* (pas d'`embedding_function` Chroma) : c'est le seul
  moyen d'appliquer `query: ` aux questions et `passage: ` aux chunks (piège n°1).
- *Sanitisation des métadonnées* : Chroma refuse les valeurs `None` → les clés
  nulles (page HTML, section absente) sont retirées avant insertion.
- *Vecteurs normalisés* (`normalize_embeddings=True`) pour un cosinus propre.

## 2026-07-22 — Phase 3 : génération (F5, F6)

**Fait.** `llm.py` (Protocol `LLMBackend`, `OllamaBackend`/`MistralBackend`,
`LLMBackendError` à cause normalisée, `build_backend`), `rag.py` (assemblage du
prompt — sources XML puis question, détection de refus par comparaison
normalisée, pipeline `RagPipeline`), CLI `generation ask`. 17 tests (backends via
`httpx.MockTransport`, pipeline avec faux store/backend). Total : 62 tests.

**Itérations de prompt (F6).** `prompts/rag_system.md` porté de v0 à v3, trois
entrées motivées au `CHANGELOG` :
- v1 : **bug empirique** — la phrase de refus était coupée sur deux lignes ; le
  « mot pour mot » demandé au modèle devenait ambigu (repéré en écrivant le test
  de refus). Mise sur une seule ligne + hors-sujet explicite.
- v2 : ambiguïté entre composantes + discipline de citation.
- v3 : *quotes-first* léger (fidélité) + concision.

**Décision.** Sur refus détecté, le pipeline renvoie `sources=[]` (F6 : 0 source
citée) ; sur retrieval vide, refus immédiat sans appel LLM (économie + robustesse).

**En attente utilisateur / environnement.** (1) Test d'intégration manuel des
deux backends (F5) : nécessite un Ollama lancé en local et/ou une clé Mistral —
non disponibles ici. (2) Validation *chiffrée* des itérations de prompt sur le
jeu d'éval : nécessite un backend LLM + un corpus figé. Le code et les tests
mockés sont prêts ; ces deux points sont des vérifications à faire côté
utilisateur, documentées ici et au CHANGELOG.

## 2026-07-22 — Phase 4 : API FastAPI (F7)

**Fait.** `schemas.py` (Pydantic v2, contrats §7.5), `main.py` (`POST /ask`,
`POST /ingest`, `GET /health`, `/docs`). Store et backend en dépendances
(singletons `lru_cache`) surchargeables en test. 12 tests via `TestClient` :
`/ask` (réponse sourcée, refus sans sources, 422 de validation, 503 sur
`LLMBackendError`), `/health`, `/ingest` (succès + manifeste, 409 doublon, 422
type non géré). Total : 74 tests.

**Décisions.**
- *Validation au démarrage* : `get_settings()` est appelé à l'import de `main.py`
  → un `LLM_BACKEND` invalide fait échouer le lancement uvicorn, pas la première
  requête (F5, vérifié).
- *Tests hermétiques* : `/ask` utilise un backend mocké ; `/ingest` monkeypatche
  `default_token_counter` (compteur de mots, aucun modèle chargé) et
  `INGESTED_MANIFEST` (fichier temporaire, le manifeste du dépôt n'est pas touché).
- *503* : `LLMBackendError` → `503 {"detail": "LLM backend unavailable: <cause>"}`
  conforme au §7.5.

**En attente utilisateur.** Latences `/ask` par backend (F7) : à mesurer et
consigner au README avec un vrai backend (Ollama local / API Mistral).

## 2026-07-22 — Phase 5 : harnais d'évaluation (F8)

**Fait.** `bm25_store.py` (BM25Okapi sur les chunks stockés, tokenisation simple),
`evaluation.py` (matching chunk attendu, fusion RRF, recall@k, section désaccords,
rendu Markdown, mode end-to-end), `eval/evaluate.py` (CLI : `--mode
retrieval|end-to-end`, `--method semantic|bm25|rrf|all`, `--k`, `--embedding-model`
sur collection éphémère, `--chunk-report`, `--questions`). 20 tests
supplémentaires. Total : 82 tests.

**Smoke test réel** (corpus synthétique) : `--mode retrieval --method all --k 3`
produit un rapport daté correct (recall@k sémantique/BM25/RRF, détail par
question, section désaccords). Sur ce corpus trivial, les trois méthodes sont à
1.00 — la baseline chiffrée intéressante viendra du vrai corpus AMU.

**Décisions.**
- *`evaluation.py` dans le package* (logique pure, testable) + `eval/evaluate.py`
  fin (câblage des vrais retrievers/pipeline) — mêmes raisons que `models.py`.
- *`--embedding-model` / `--chunk-report`* opèrent sur des collections ChromaDB
  éphémères suffixées, supprimées en `finally` : la collection de production
  `amu_docs` n'est **jamais** modifiée (§7.6).
- *RRF mesuré seulement* : le pipeline `/ask` reste sémantique pur en V1 (§5.1.8).

**En attente utilisateur.** La **baseline** chiffrée (F8) et le tableau de
sensibilité (2 tailles de chunks, k ∈ {3,5,8}, e5 vs camembert) exigent le vrai
corpus + `eval/questions.yaml` renseigné. Le harnais est prêt à les produire en
une commande.

## 2026-07-22 — Phase 6 : finition V1 + port LangChain (F9)

**Fait.** README complet (motivation RAG vs long-contexte, architecture, pièges,
usage, contrats API, méthodologie d'éval, limites, feuille de route, références).
Port LangChain du pipeline de requête sur la branche **`langchain-port`** (isolée,
§11.3) avec un paragraphe README « ce que LangChain abstrait ». Tag `v1.0` posé
sur la ligne principale (F1-F8 + finition ; F9 vit sur la branche de comparaison).

**Rappel de statut.** F1-F9 sont **codés et testés** mais leur *validation
chiffrée* (recall réel, latences, équivalence des réponses du port) dépend du
corpus AMU et d'un backend LLM. Le tag `v1.0` marque donc la complétude *du code*
V1, pas encore la validation terrain — explicitement noté au README.

**Dépendances LangChain (branche uniquement, §11.7).** `langchain-core`,
`langchain-chroma`, `langchain-ollama`, `langchain-mistralai`,
`langchain-huggingface` sont déclarées dans l'extra **optionnel** `[langchain]`,
installées seulement sur cette branche. Elles n'existent pas sur `main` : le port
est un exercice de comparaison isolé (§3, §5.1.9). Constat clé documenté au README
de la branche : LangChain n'ajoute pas les préfixes E5 (piège n°1) → une classe
`Embeddings` maison reste nécessaire, et tout le contrat produit de `/ask`
(citations, refus, 503) reste à écrire à la main.
