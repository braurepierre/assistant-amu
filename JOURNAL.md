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

## 2026-07-22 — Phase 7 : V2 multi-turn par condensation (F10-F12)

**Fait.** Champ `history` optionnel dans `/ask` (rétrocompatible : absence =
comportement V1 strictement identique, testé), condensation de requête
(`RagPipeline._condense` avec `prompts/condense_system.md`), `condensed_question`
renvoyé dans la réponse, mode `--mode conversation` du harnais + `scenarios.yaml`.
9 tests supplémentaires. Total : 90 tests. Tag `v2.0`.

**Décisions.**
- *Ordre contractuel (§11.3).* La V2 n'aurait dû démarrer qu'après validation
  chiffrée de F1-F9. L'utilisateur a explicitement demandé « tout le PRD » ; la
  V2 est donc **codée**, mais la validation terrain de la V1 reste due (corpus +
  backend). Noté ici et au README pour transparence.
- *Troncature de l'historique* : au-delà de ~6 tours (`MAX_HISTORY_MESSAGES=12`),
  les messages anciens sont retirés avant condensation (§7.7).
- *Stateless* : aucun stockage serveur, le client renvoie l'historique.

**En attente utilisateur.** F10-F12 : validation des scénarios (condensation
correcte, recall par tour, fidélité) avec un backend LLM réel — le harnais
`--mode conversation` est prêt, `eval/scenarios.yaml` reste à peupler.

## 2026-07-23 — Corpus réel constitué + F1-F4 validés sur le terrain

**Fait (session à deux, via l'extension Chrome + WebFetch).** Constitution de
`corpus/sources.yaml` avec **17 documents AMU réels** (browsing de `univ-amu.fr`).
Découverte : le domaine du PRD « amu.fr » est une **entreprise sans rapport** ; le
vrai site est **`www.univ-amu.fr`** (corrigé dans sources.yaml). Beaucoup de docs
facultaires (règlement/MCC) sont derrière l'ENT/intranet → le corpus public
s'appuie sur le central + ALLSH + Droit (accès libre) + Sciences/IUT.

**Validation terrain.**
- **F1** : `download` → 16/17 OK, 1 lien 404 (page IUT périmée) loggé sans casser
  le lot ; corrigé, 2ᵉ run idempotent (16 skipped-exists).
- **F2** : `stats` → 16 docs, **269 chunks**, 1 exclusion **correcte** : le
  calendrier 2026-2027 (PDF) n'a pas de couche texte exploitable (pdfplumber sort
  des avertissements FontBBox) → exclu sans OCR (§7.2).
- **F3/F4** : `index` → 269 chunks en collection (16 docs distincts) ; une requête
  paraphrasée sur la césure ramène des passages pertinents (score ~0.86).

**Méthode.** WebFetch (rapide, extraction de liens) > extension Chrome (fiable
mais lente) pour récupérer des URLs. WebSearch inutilisable ici (US-only → mauvais
« amu.fr »).

**Candidat Docling (§7.2).** Le calendrier scanné est le cas d'escalade type : si
`docling` est installé, ajouter `extractor: docling` à son entrée pourrait le
récupérer. Non fait (dépendance optionnelle non installée).

**Reste dû.** `eval/questions.yaml` (baseline chiffrée) et un backend LLM
(Ollama/Mistral) pour `/ask` et l'end-to-end.

## 2026-07-23 — Backends LLM réels : F5, F6, F7 validés sur le terrain

**Fait (session à deux).** Les deux backends branchés sur le corpus réel.
- **Mistral API** : première réponse `/ask` **sourcée et fidèle** sur la césure
  (5 chunks, citations [S1]-[S4], dates/webinaires tirés des extraits). End-to-end
  20 questions : **refus 4/4** sur les hors-corpus (F6). ~3 s/question.
- **Ollama local** (`mistral` 7B) : fonctionne mais lent sur CPU.

**Problème → diagnostic → solution (Ollama).**
- *Symptôme 1* : `ollama` introuvable dans bash → `command not found`. *Cause* :
  l'exe (`%LOCALAPPDATA%/Programs/Ollama/ollama.exe`) n'est pas dans le PATH de Git
  Bash. *Solution* : l'appeler par chemin absolu ; le serveur :11434 tourne à part.
- *Symptôme 2* : premier `/ask` Ollama → **timeout à 120 s** (149 s réels). *Cause* :
  chargement à froid du 7B en RAM + prompt ~3000 tk à `num_ctx=8192` sur CPU.
  *Solution* : repli **machine modeste** du PRD — `num_ctx=4096`, `k=3`, modèle
  gardé chaud → réponse en ~190 s. Le timeout remonte proprement en
  `LLMBackendError(timeout)` (F5). Latences consignées au README.

**Bilan V1.** F1-F8 validés **en conditions réelles** ; F9 (port LangChain) est
code+tests. Reste : peupler `eval/scenarios.yaml` pour la validation
conversationnelle V2 (F10-F12), et raffiner 3 annotations d'éval (q03, q04, q10).

## 2026-07-23 — V2 condensation validée en direct (F10)

**Fait.** Scénario de référence du PRD testé avec Mistral : tour 1 « césure »
(condensed_question = None, V1) ; tour 2 elliptique « Et pour un étudiant en
droit ? » → condensé en « Un étudiant en droit peut-il bénéficier des modalités
de la césure à AMU ? » — contient bien **césure** ET **droit** (critère F10). Le
modèle refuse ensuite (pas de règles de césure propres au droit dans le corpus) :
garde-fou anti-hallucination **fonctionnel en multi-tour**. `eval/scenarios.yaml`
peuplé de 3 scénarios réels (dont celui-ci) à raffiner.

**Note d'éval conversationnelle.** `evaluate_conversation` calcule le recall par
tour depuis `result.sources` ; or un refus vide `sources` (F6). Sur un tour où le
retrieval réussit mais la réponse refuse (cas s1 tour 2), le recall par tour peut
donc afficher un « miss » alors que le retrieval a ramené les bons chunks —
limite connue, à affiner (mesurer le recall avant le drop de refus) si besoin.

## 2026-07-23 — Bonus : interface Gradio (demo.py, §5.4)

**Fait.** `demo.py` (**55 lignes** ≤ 60), pur client HTTP de l'API : champ question
+ slider k → appelle `POST /ask` → rend réponse + sources en Markdown. Zéro logique
métier (le RAG reste dans l'API). Réalisé après validation V1 (contrainte §5.4).

**Dépendance hors §6.1 (justif. §11.7).** `gradio` en extra **optionnel** `[demo]`
(uniquement pour le bonus). Non requis par le cœur du produit.

## 2026-07-23 — Raffinage d'éval diagnostiqué : recall@5 0.81 → 0.94

**Méthode (anti-triche).** Avant de toucher aux annotations, **inspection des vrais
chunks** pour distinguer problème d'annotation vs problème de données.
- **q03 (RSE)** : le doc RSE central *était* retrouvé (rang 2-3), mais mon mot-clé
  `["régime spécial"]` ne figure que dans le chunk d'intro (hors top-5) ; les
  chunks retrouvés disent « RSE ». → **annotation** trop stricte → `["RSE"]`.
- **q10 (M3C)** : la page M3C *était* parfaitement retrouvée, mais son contenu est
  un **index de liens** (« M3C Licence X 2025-2026 »), sans les règles. → **données**
  → ajout des PDF « Cadrage M3C » (Licence + Master), le vrai contenu MCC.

**Résultat.** semantic 0.81→**0.94**, bm25 0.75→0.81, rrf 0.81→0.88 (corpus 18 docs
/ 316 chunks). q03 ✅ (annotation), q10 ✅ (données).

**Arrêt assumé (intégrité).** La dernière question ratée par le sémantique (q04,
logement) est **récupérée par la RRF** ; je ne la « corrige » pas — ce serait
gonfler le score, et c'est l'illustration vivante de l'intérêt de l'hybride. Un
0.94 honnête vaut mieux qu'un 1.00 suspect ; le plafond restant reflète un vrai
cas, pas un bug.

## 2026-07-23 — UI : swap Gradio → chatbot HTML vanilla (charte AMU)

**Décision (accord utilisateur).** Remplacement du bonus Gradio par une
`demo.html` **autonome, zéro dépendance**, servie par l'API sur `GET /`
(même origine → pas de CORS). Reste un **pur client HTTP** de `/ask` (esprit §5.4).
Avantages : dépendance `gradio` retirée (projet plus léger), look **charte AMU**
(bleu #143b8f / jaune #f6e400), et surtout **format chatbot conversationnel** qui
exploite `history` → met en scène la **condensation V2** (affichage « compris
comme : … »). `demo.py` et l'extra `[demo]` supprimés (une seule UI). Réversible.

## 2026-07-23 — Comparaisons : embeddeurs (Phase 5) & pipeline vs LangChain (F9)

**Fait.** Deux comparaisons *mesure seule* demandées par l'utilisateur, lancées en
parallèle (worktree dédiée pour la branche `langchain-port`).
- **Embeddeurs** (`eval/embedder_comparison.py`, sur `main`) : recall@k sémantique
  d'e5-small / CamemBERT / FlauBERT sur les **mêmes** chunks (ré-embarqués dans des
  collections éphémères, supprimées ensuite ; `amu_docs` intacte). Résultat : e5 et
  CamemBERT à égalité en moyenne (0.92 ; CamemBERT parfait à k=8), FlauBERT en
  retrait sur les sigles (rate RSE, CVEC). Tableau reporté au README. `/ask` garde
  e5 : les écarts (1-2 questions ≈ granularité 0.06) ne le justifient pas.
- **Pipeline manuel vs port LangChain** (`eval/compare_pipelines.py`, sur
  `langchain-port`) : mêmes questions, même collection, même prompt, backend
  Mistral. Parité de refus **19/20**, citations 15/20, recouvrement lexical 0.75 →
  F9 « réponses équivalentes » vérifié. Piège : les deux pipelines ouvrant un client
  Chroma sur le même dossier dans un seul process, il faut aligner leurs réglages
  (télémétrie) et injecter le retriever LangChain.

**Dépendance hors §6.1 (justif. §11.7).** `sacremoses` en extra **optionnel**
`[eval-flaubert]` : le tokenizer Moses de FlauBERT en a besoin pour se charger
(sentence-transformers). Réservé à la comparaison d'embeddeurs (Phase 5), hors du
cœur produit — `/ask` reste sur e5. À noter : le modèle FlauBERT *cased*
`Lajavaness/sentence-flaubert-base` ne charge pas sous sentence-transformers 5.6.1
(son `FlaubertTokenizer` Moses n'a pas `basic_tokenizer`, que le module Transformer
suppose) ; la variante *uncased* `hugorosen/flaubert_base_uncased-xnli-sts` est
utilisée à la place.

## 2026-07-23 — F12 : rapport conversationnel produit + diagnostic d'annotations

**Fait.** `--mode conversation` lancé sur les 3 scénarios (Mistral, k=5) →
`eval/reports/2026-07-23_conversation_k5.md`. C'était le dernier livrable de la
feuille de route à n'avoir jamais été produit. Recall **3/6** sur les tours
answerable.

**Diagnostic — première lecture erronée, corrigée après examen du contenu.**
Premier réflexe : « annotation trop stricte », comme q03. **C'était faux**, et la
correction vaut d'être consignée. Vérifié sur `s1_cesure_droit` tour 1 : le
pipeline ne refuse pas et rend 5 chunks qui parlent bien de césure — mais tous
issus de « IUT — Services de la scolarité », c'est-à-dire la césure vue par *une*
composante. La page institutionnelle « La césure à AMU », qui porte la réponse
(« Les formalités administratives… précise les modalités »), est **absente du
top-5**. L'annotation encode donc une intention **défendable** — à une question
générique, répondre par la source institutionnelle et non par les règles d'une
composante, sous peine d'induire en erreur un étudiant non-IUT — et c'est le
**retrieval** qui échoue. Même motif d'éviction de la page centrale que celui déjà
relevé sur le RSE (cf. `eval/query_rewrite_experiment.py`).

**Cause aggravante, mesurée : micro-chunks parasites.** 37 chunks sur 316
(**11.7 %**) font moins de 50 caractères — `FAQ` (3 car.), `Top !` (5), `Bonus`
(5), `Césure` (6), `Scolarité` (9) : des fragments de navigation HTML et des titres
orphelins devenus unités indexées, contre une médiane de corpus à 786 caractères.
Un chunk ultra-court quasi identique à une requête courte obtient une similarité
cosinus très élevée — aucun contenu ne dilue le signal. Ici, `Césure` (6
caractères, zéro information) score **0.860** et occupe la place n°2 du top-5,
pendant que la page institutionnelle reste dehors.

**Reste dû (arbitrage utilisateur requis : touche le cœur produit, §11.3).**
- Filtre de longueur minimale au chunking, ré-ingestion et re-mesure : on saurait
  alors ce que ces 11.7 % de déchets coûtent réellement en recall.
- L'éviction de la page centrale par les pages de composante : problème de fond,
  relevant des pistes V2.1 (réécriture de requête, bascule hybride/RRF, Contextual
  Retrieval).
- Le second biais du 3/6, lui, relève bien de l'annotation et reste valide : le
  tour 2 de s1 est marqué `answerable` alors qu'il **refuse correctement** (le
  corpus n'a pas de règle de césure propre au droit) ; or un refus vide les sources
  (F6), donc il compte mécaniquement comme un raté de recall.

## 2026-07-26 — F6 sur le backend local : la case vide de la table des backends

**Fait.** Le taux de refus hors corpus n'avait jamais été mesuré sur Ollama : depuis
le 23 juillet, la table des backends (README et page pédagogique) affichait `4/4`
pour Mistral et `—` pour le local. Seules la latence et la remontée propre du
timeout (F5) avaient été vérifiées côté Ollama. Mesure faite sur les 4 questions
`answerable: false` de `eval/questions.yaml` (q17-q20), repli **num_ctx=4096, k=3**,
modèle gardé chaud, verdict rendu par `is_refusal()` du projet — comparaison
normalisée, pas un jugement à l'œil. Résultat : **4/4**, les quatre réponses
reproduisant le refus canonique au mot près, avec `sources` vide dans les quatre cas.

**Problème → solution : le timeout par défaut rendait la mesure impossible.**
`OLLAMA_TIMEOUT_S` vaut **120 s** par défaut (`config.py`), soit *moins* que la
latence de ce backend telle qu'elle est documentée (~190 s à chaud). Toute mesure
un peu longue se serait donc soldée par un `LLMBackendError(timeout)` — non pas un
échec du garde-fou, mais un artefact de configuration qu'on aurait pu prendre pour
tel. Relevé à 600 s **pour la durée de la mesure uniquement** ; `.env` n'est pas
touché, le défaut reste volontairement bas pour que l'API échoue vite en usage réel.

**Latences — deux chiffres à ne pas confondre.** Préchauffage : **306 s**, ce qui
confirme le coût du chargement à froid du 7B déjà relevé le 23 juillet. Refus, à
chaud : 120 s, 126 s, 135 s et 31 s, soit une moyenne de **103 s**. Cette moyenne
n'infirme pas les ~190 s consignés pour ce backend : un refus ne génère qu'une
douzaine de tokens là où une vraie réponse en génère plusieurs centaines — les deux
mesures ne portent pas sur la même charge de génération. La ligne de latence de la
table reste donc inchangée. Le cas q20 (31 s) sort du lot et n'est pas expliqué à ce
stade ; à regarder si la question revient.

**Ce que ça vaut.** Le garde-fou anti-hallucination ne dépend pas du fournisseur :
il tient sur un 7B local exactement comme sur l'API. C'est cohérent avec sa
conception — la règle vit dans le prompt système et la détection dans une
comparaison normalisée, pas dans les capacités d'un modèle particulier. La colonne
est désormais renseignée dans `concepts.facts.yaml`, la page et le README.

**Au passage.** `tests: 90` dans `concepts.facts.yaml` était périmé : `pytest -q`
en compte **119**. Corrigé et régénéré.

## 2026-07-26 — Conteneurisation et intégration continue : deux surprises de packaging

**Fait.** L'image Docker et la CI GitHub Actions du §5.3.6 sont posées. L'image
sert l'API par uvicorn, embarque le modèle d'embeddings et laisse l'index
vectoriel dans un volume — il se régénère depuis le corpus, il n'a rien à faire
dans une image. La CI lance `pytest` puis **construit l'image réelle** et
interroge `/health` sur le conteneur démarré. Aucun secret n'est nécessaire : les
tests moquent le backend, et `/health` rend 200 même sans index ni backend
joignable, puisque c'est précisément leur état qu'il rapporte.

**Problème → solution : le lock épingle une variante CUDA de torch.** `uv.lock`
résout pour toutes les plateformes ; côté Linux, cela signifie la variante CUDA de
torch et **16 roues `nvidia-*`/`triton`, soit environ 2,5 Go** — pour un projet
dont toutes les latences documentées sont mesurées sur CPU. Trois options se
présentaient : accepter l'image obèse, modifier `pyproject.toml` pour déclarer un
index PyTorch dédié (ce qui reverrouille tout le projet pour un besoin
d'empaquetage), ou retirer ces roues de l'export et installer la roue CPU de la
**même version** depuis l'index PyTorch. La troisième a été retenue : l'épinglage
du lock est conservé, la version de torch est extraite de l'export lui-même (elle
ne peut donc pas diverger), et le contrat de dépendances du §6.1 n'est pas touché.

**Problème → solution : installer le paquet aurait cassé la résolution des
chemins.** `config.py` déduit la racine du projet de son propre emplacement
(`parents[2]`). Installé dans `site-packages`, ce calcul désigne le répertoire de
Python, et `prompts/`, `demo.html` et `corpus/` deviennent introuvables. L'image
conserve donc l'arborescence des sources et la rend importable par `PYTHONPATH`,
exactement comme `pythonpath = ["src"]` le fait pour pytest en local.

**Ce que ça vaut — et sa limite.** Docker n'est pas installé sur la machine de
développement : l'image n'a **pas** été construite localement. C'est la CI qui en
fait foi, et c'est aussi pourquoi elle construit l'artefact réel, préchargement du
modèle compris, plutôt qu'une variante allégée qui aurait été plus rapide sans
rien prouver.

**Au passage.** `docs/build_concepts.py --check` ne peut pas servir de garde-fou
en CI en l'état : la page enregistre le SHA du commit courant, si bien qu'un
commit touchant la page la rend aussitôt « périmée » vis-à-vis de HEAD. La CI se
limite donc aux tests et à l'image. Rendre ce contrôle exploitable demanderait
d'exclure `commit` et `updated` de la comparaison.

## 2026-07-26 — Contextual Retrieval (§5.3.1) : un arbitrage, pas un gain

**Fait.** La candidate n°1 du PRD est mesurée. Chaque fragment est préfixé d'une
phrase générée par le LLM qui le situe dans son document — « Charte des étudiants
et stagiaires d'AMU, partie « II. ENGAGEMENT DE L'USAGER SIGNATAIRE » : respect
des personnes et lutte contre le harcèlement » — avant l'embedding **et**
l'indexation BM25, dans une collection parallèle. 316 fragments, 316 contextes,
25 mots en moyenne, environ 1,7 M tokens d'entrée sur `mistral-small-latest`.

**Résultat : la méthode échange des réussites contre d'autres.** Elle répare
exactement le mode d'échec qu'elle vise — les formulations conversationnelles en
recherche sémantique, recall@3 du jeu « dur » **0,38 → 0,75** — et dégrade les
formulations définitionnelles, recall@5 du jeu « facile » **0,94 → 0,81**. Le
préfixe déplace le vecteur du fragment vers le sujet de son *document* : cela
sert les questions vagues et dessert les questions précises. Sur BM25 le bilan
est franchement négatif (jeu « dur » à k=5 : 1,00 → 0,88).

**Problème → solution : la mesure était d'abord confondue avec une troncature.**
Le découpage vise 500 tokens par fragment, préfixe `passage: ` compris, contre
une fenêtre d'encodeur de 512 : douze tokens de marge, où un contexte de 25 mots
n'entre pas. Mesure faite : **23 fragments (7 %) sortaient de la fenêtre après
contextualisation, contre 0 avant** — l'encodeur les tronquait en silence, le
contexte lu et la fin du fragment perdue. L'expérience a donc été rejouée sur un
corpus redécoupé à 440 tokens, où plus aucun fragment ne déborde (le plus long
atteint 475). **Les conclusions ne bougent pas** : l'arbitrage tient à la méthode,
pas à la marge.

**Problème → solution : le comptage risquait de se donner raison tout seul.** Le
jeu « facile » exige la présence de mots-clés *dans le fragment récupéré*, et un
contexte généré nomme presque toujours le sujet du fragment qu'il préfixe.
Compter sur le texte contextualisé aurait validé « la phrase de contexte dit
*césure* » comme une réussite de recherche — un gain gratuit, invisible dans les
tableaux. Le texte d'origine est donc conservé (`metadata["text_raw"]`) et
restauré après classement : le contexte sert à **trouver** le fragment, jamais à
**prouver** qu'on l'a trouvé. Le rapport chiffre l'artefact ainsi évité : jusqu'à
une question de recall créditée pour rien.

**Problème → solution : le cache rejouait des contextes écrits pour d'autres
textes.** Le cache disque était d'abord indexé sur `chunk_id`. Or `chunk_id` vaut
`hash(doc_id, index)` — il désigne une **position**, pas un contenu. En
redécoupant à 440 tokens, la première exécution a donc annoncé « 316 contextes
depuis le cache » sur 332 fragments dont le texte avait pourtant changé : des
contextes écrits pour d'autres portions, servis sans un mot. Détecté à ce compteur
anormalement élevé. La clé est désormais l'adresse du contenu,
`hash(doc_id, texte)` ; les entrées de l'ancien format sont ignorées plutôt que
crues. Le second passage à 440 tokens a alors régénéré 117 fragments et n'en a
rejoué que 215 — ceux dont le texte est réellement identique d'un découpage à
l'autre, ce qui est le comportement attendu.

**Ce que ça vaut.** Trois précautions valent ici plus que le chiffre lui-même :
contrôler la troncature, refuser un comptage qui se donne raison, et ne pas faire
confiance à une clé de cache qui ne parle pas du contenu. Les chiffres d'Anthropic
(−49 % d'échecs) portent sur des corpus de plusieurs milliers de fragments : huit
et seize questions ne les infirment pas. Ce qui est établi, c'est que sur **ce**
corpus la méthode ne s'applique pas telle quelle. La suite naturelle serait de ne
contextualiser que les fragments réellement décontextualisés — ceux dont le texte
ne nomme ni son document ni son sujet — plutôt que tout l'index.

**Décision.** `/ask` reste sur la collection de production, comme la RRF et la
réécriture avant lui : mesuré, documenté, non branché.

## 2026-07-26 — Le jeu « dur » passe de 8 à 25 questions, et une conclusion s'inverse

**Fait.** `eval/hard_questions.yaml` compte désormais **25 formulations** au lieu de
8. Chaque annotation a été vérifiée par programme avant d'être écrite : la
sous-chaîne attendue résout vers exactement un des 18 titres indexés (sauf h04 et
h21, qui acceptent délibérément les trois documents M3C d'ALLSH), et le document
visé porte effectivement le sujet. Les questions n'ont **pas** été retouchées au vu
des résultats — ajuster le banc à sa réponse le viderait de son sens.

**Problème → solution : le jeu mesurait l'heuristique dans son propre miroir.** Les
8 questions d'origine s'ouvraient toutes par une tournure que `strip` sait retirer
(« Parle-moi de… », « Je voudrais des infos sur… »). Un jeu élargi avec les mêmes
tournures aurait confirmé `strip` par construction. Le jeu comporte donc deux
régimes explicites : les ouvertures que l'heuristique traite (h01-h14) et des
formulations qu'elle **ne touche pas** — cadrage personnel (« Je suis en licence
et… »), question indirecte (« ça marche comment ? »), préambule narratif
(h15-h25). Le champ `regime` documente l'appartenance ; le harnais l'ignore.

**Ce que ça change, chiffres à l'appui.** La réécriture `strip` recule, comme
prévu : recall@3 du jeu dur **0,75 → 0,72** alors que la baseline monte de 0,38 à
0,48 — son gain passe de +0,37 à +0,24. Surtout, **`llm` passe devant** (0,80 à
k=3) : elle traite les tournures que l'expression régulière ne sait pas retirer.
Elle reste écartée, mais pour une raison désormais chiffrée et non plus supposée —
elle casse trois questions définitionnelles qui fonctionnaient (q01, q02, q03),
n'est pas déterministe et coûte un appel par requête. `strip` demeure la meilleure
stratégie **parmi celles qui ne coûtent aucune question**.

**Une conclusion s'inverse.** Sur 8 questions, la contextualisation (§5.3.1)
paraissait échanger 3 réussites contre 2 — un arbitrage équilibré, donc décevant.
Sur 25, l'écart devient lisible : **+9 questions gagnées contre 2 perdues**
(recall@3 du jeu dur 0,48 → 0,84), et le contrôle à 440 tokens confirme le sens
(+6 contre 3). La méthode gagne nettement plus qu'elle ne perd. Ce n'est pas la
mesure qui a changé, c'est sa résolution : à 8 questions, un cran valait 0,125 et
l'écart se confondait avec le bruit.

**Ce que ça vaut.** Un jeu d'évaluation trop petit ne se contente pas d'être
imprécis — **il peut désigner la mauvaise conclusion**, et le faire avec l'aplomb
d'un tableau chiffré. Les deux verdicts codés en dur dans les générateurs de
rapport ont d'ailleurs dû être réécrits, car ils avaient été rédigés pour l'ancien
résultat et le contredisaient une fois les nouveaux chiffres calculés : celui de la
réécriture affirmait encore « `llm` écartée » dans le paragraphe même où le calcul
la désignait gagnante. Les conclusions se déduisent maintenant des écarts, y
compris leur rapport de grandeur.

**Reste à faire.** Le jeu principal (16 questions définitionnelles) n'a pas bougé :
sa granularité reste de 0,062, et c'est lui qui porte l'arbitrage e5/CamemBERT —
lequel se joue sur **une** question à k=8. La question de l'encodeur restera donc
indécidable tant que ce jeu-là n'aura pas été élargi à son tour.
