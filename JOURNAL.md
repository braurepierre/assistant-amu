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
visé porte effectivement le sujet. Aucune question n'a été retouchée **au vu des
résultats** — ajuster le banc à sa réponse le viderait de son sens.

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
0,48 — son gain passe de +0,37 à +0,24. Surtout, **`llm` passe devant** (0,84 à
k=3) : elle traite les tournures que l'expression régulière ne sait pas retirer.
Elle reste écartée, mais pour une raison désormais chiffrée et non plus supposée —
elle casse trois questions définitionnelles qui fonctionnaient (q01, q02, q03),
n'est pas déterministe et coûte un appel par requête. `strip` demeure la meilleure
stratégie **parmi celles qui ne coûtent aucune question**.

**Une conclusion s'inverse.** Sur 8 questions, la contextualisation (§5.3.1)
paraissait échanger 3 réussites contre 2 — un arbitrage équilibré, donc décevant.
Sur 25, l'écart devient lisible : **+8 questions gagnées contre 2 perdues**
(recall@3 du jeu dur 0,48 → 0,80), et le contrôle à 440 tokens confirme le sens
(+4 contre 2). La méthode gagne nettement plus qu'elle ne perd. Ce n'est pas la
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

**Reprise de formulation, après relecture.** Sept questions du régime B
employaient l'élision parlée (« il existe des aides ? », « ça marche comment ? »).
Corrigées en français bien formé — inversion (« existe-t-il », « peuvent-elles »),
« si j'échoue » plutôt que « si je rate ». Ce qui rend une question difficile ici,
c'est sa **forme** — préambule personnel, tournure indirecte, et surtout l'absence
du vocabulaire du document visé —, pas une grammaire relâchée. La reprise étant
intervenue **après** une première mesure, tout a été rejoué : la baseline monte
légèrement (recall@5 du jeu dur 0,68 → 0,72, ces formulations étant un peu plus
proches du régime définitionnel), `strip` passe à 0,88 et le gain de la
contextualisation revient de +9 à +8 questions. **Aucune conclusion ne bouge** —
ce qui est en soi le résultat intéressant : elle résiste à une reformulation de
sept questions sur vingt-cinq. Les huit questions d'origine restent intactes, pour
que les rapports datés du 23 juillet demeurent comparables.

**Reste à faire.** Le jeu principal (16 questions définitionnelles) n'a pas bougé :
sa granularité reste de 0,062, et c'est lui qui porte l'arbitrage e5/CamemBERT —
lequel se joue sur **une** question à k=8. La question de l'encodeur restera donc
indécidable tant que ce jeu-là n'aura pas été élargi à son tour.

## 2026-07-26 — Le jeu principal passe de 16 à 50 questions : la baseline recule, deux verdicts s'inversent

**Fait.** `eval/questions.yaml` compte désormais **50 questions répondables** (contre
16) et **10 hors corpus** (contre 4). Même méthode que pour le jeu « dur » : avant
d'écrire une annotation, vérification par programme que le marqueur choisi
apparaît dans plusieurs fragments du document visé (`expected_keywords` doit
matcher *le fragment récupéré*, pas seulement le document — piège déjà rencontré
sur q03). Huit marqueurs candidats se sont révélés trop rares (1 seul fragment,
parfois 0) et ont été remplacés ; trois questions « hors corpus » que j'avais
envisagées portaient en réalité sur des sujets présents dans le corpus (Erasmus,
mobilité internationale) et ont été écartées avant d'être écrites. Un script de
vérification (`chunk_matches` appliqué à chaque annotation contre l'index réel)
confirme les 50 annotations satisfiables, dont 3 ne tiennent qu'à un seul
fragment — acceptable pour des questions de sigle, à surveiller sinon.

**La baseline recule, et ce n'est pas une régression.** Recall@5 : sémantique
0,94 → **0,86**, BM25 0,81 → 0,84, RRF 0,88 → 0,86. Le repli sémantique n'est pas
un défaut du système : le nouveau jeu couvre des documents qui n'avaient encore
aucune question (règlement intérieur, droits d'inscription, sigles, Cadrage M3C
Master, Mission handicap) et des procédures propres à une composante plutôt que
génériques (la césure à l'IUT plutôt qu'au niveau central). Le jeu à 16 questions
sur-représentait les documents déjà faciles à trouver ; le jeu à 50 measure une
tâche plus proche de ce qu'un vrai corpus de 18 documents impose.

**Deux conclusions s'inversent.**

1. **CamemBERT.** La question posée directement : « CamemBERT à 1,00 avec k=8 »
   était réelle sur 16 questions (0,94 pour e5) mais tenait à **un seul écart de
   question** — la granularité même du jeu (1/16 ≈ 0,06), déjà signalée avec
   prudence à l'époque. Sur 50 questions (granularité 1/50 = 0,02), l'écart
   s'**inverse et se creuse** : e5 domine nettement à k=3 (0,82 contre 0,66, soit
   16 points) et à k=5 (0,86 contre 0,76) ; les trois modèles ne se rejoignent
   qu'à k=8, à 0,86 chacun — CamemBERT n'y prend plus l'avantage, il **rattrape**
   son retard. e5 reste le choix de production, cette fois avec une mesure qui
   tranche plutôt qu'un chiffre à la limite du bruit.

2. **Recall@k : la RRF dépasse le sémantique pur à k=8.** Nouveau sur ce jeu :
   0,92 contre 0,86, soit 3 questions sur 50 — au-dessus de la granularité, donc
   significatif. Sur l'ancien jeu, RRF plafonnait à égalité (0,88 chacun) ; huit
   questions plus tard, l'écart existait peut-être déjà mais restait invisible.
   `/ask` reste sémantique pur à k=5 (où RRF et sémantique sont encore à égalité) ;
   ce résultat ne tranche rien pour la V1 mais renforce l'argument d'une bascule
   RRF si k était un jour relevé en production (§5.3).

**Ce que le jeu élargi a aussi révélé sur la contextualisation — une nuance, pas
seulement une confirmation.** Rejouée sur le jeu facile élargi (16 → 50
questions), la contextualisation à 500 tokens confirme le sens déjà mesuré : gain
net sur le jeu dur (8 gagnées / 2 perdues en sémantique pur), et surtout **la
fusion RRF ne perd plus rien** — elle gagne désormais sur les deux jeux (+4
questions sur le facile à k=5, la composante BM25 compensant ce que le sémantique
seul cède). Mais le contrôle à 440 tokens, qui « confirmait sans réserve » sur
l'ancien jeu de 25×16 questions, se nuance sur 25×50 : le gain sémantique **résiste**
(jeu dur k=3 : +4 questions à 440 contre +8 à 500 — même sens, ampleur moindre),
mais **BM25 se dégrade nettement à 440 sur le jeu dur** (−4 questions à k=3, −3 à
k=5), un effet resté invisible tant que le jeu facile ne comptait que 16
questions. Ce n'est plus un artefact de troncature à écarter par un simple
contrôle : c'est un comportement propre à BM25, sensible au budget de découpage,
qui reste à comprendre avant de généraliser la méthode. Rapport et README ont été
corrigés pour ne plus affirmer que « les conclusions sont inchangées » entre 500
et 440 tokens — elles le sont pour le sémantique, pas pour BM25.

**Un problème d'infrastructure, au passage.** `eval/query_rewrite_experiment.py`
n'avait aucune reprise sur erreur : un run coûtant ~75 appels Mistral (25+50
questions, stratégie `llm`) a heurté un `429 Too Many Requests` après la plupart
des appels déjà payés, perdant tout le run. Ajout d'un mécanisme de reprise avec
attente progressive (5s/15s/45s) sur les causes transitoires (`quota`, `timeout`,
`connection`) — même logique que celle déjà en place dans
`ingestion/contextualize.py`, gardée hors de l'abstraction LLM elle-même (PRD
§7.4 : « pas de reprise élaborée » au niveau du backend, la résilience de lot vit
dans le script qui l'utilise).

**Ce que ça vaut.** Deux fois dans cette phase de mesure, un jeu d'évaluation
trop petit a produit une conclusion plausible mais fausse — l'échange équilibré
de la contextualisation sur 8 questions, la supériorité de CamemBERT sur 16.
Ce n'est pas la même erreur répétée : c'est le même mécanisme (résolution
insuffisante d'un jeu de test) qui produit des conclusions différentes selon
l'endroit où on l'applique. La leçon générale se confirme : la taille d'un jeu
d'évaluation n'est pas un détail de rigueur, c'est ce qui décide si une
conclusion est vraie.

## 2026-07-26 — Le corpus passe de 18 à 28 documents indexés : la recherche ne cède rien, la fusion RRF cède la première

**Fait.** Un lot de dix pages distractrices (`corpus/sources_distractors.yaml`)
porte le corpus mesuré de 18 à 28 documents indexés, soit +62 fragments
(316 → 378). Le jeu de questions ne bouge pas : c'est la botte de foin qui
grossit, pas la mesure. Objet du test : le recall@5 de 0,86 établi le matin sur
18 documents doit-il une part de son niveau à la facilité intrinsèque de
retrouver le bon document parmi dix-huit ? Le risque n°1 documenté pour
l'encodeur (§9, « e5-small dilue les sigles ») était de fait presque intestable à
cette échelle. Nouveau script `eval/distractor_experiment.py`, rapport
`eval/reports/2026-07-26_corpus_scaling.md`. Aucun appel LLM : retrieval pur,
rejouable gratuitement. `corpus/sources.yaml` reste à 19 entrées et `amu_docs`
n'a jamais été ouverte en écriture.

**Le résultat principal, et il est net.** Le sémantique et BM25 ne perdent
**aucune question**, sur 75 questions et trois valeurs de k. Recall@5 du jeu
facile : 0,86 → 0,86 en sémantique, 0,84 → 0,84 en BM25 ; jeu dur : 0,72 → 0,72
et 0,84 → 0,84. Les décisions du matin (e5 plutôt que CamemBERT, k=5) résistent
donc à un corpus élargi de moitié.

**Problème → solution : le lot pouvait faire *monter* le recall pour de faux
motifs.** `chunk_matches` reconnaît un `expected_source` comme sous-chaîne du
titre. Un distracteur dont le titre contient l'une des **21 sous-chaînes**
réservées par les deux jeux aurait été compté comme source attendue. Et quatre
questions de sigle (q09 CVEC, q12 BCC, q27 LANSAD, q28 FOAD) n'ont pas
d'`expected_source` : n'importe quel fragment portant le token y compte comme
réussite. Les deux garde-fous sont donc exécutés **avant** toute mesure et
arrêtent le script s'ils cèdent. Ils ont servi : deux candidates ont été écartées
pour la seule raison qu'elles décrivent l'emploi de la CVEC (« La culture à amU »,
« Bouger, découvrir et s'engager »). Sans ce contrôle, l'expérience aurait produit
une amélioration apparente du recall en ajoutant du bruit.

**Problème → solution : un zéro n'est pas lisible tel quel.** Une immobilité
totale admet deux lectures opposées — la recherche résiste, ou le lot n'est jamais
monté assez haut pour la gêner. La seconde était plausible : la RRF, seule méthode
à bouger, fusionne à profondeur 50, ce qui suggérait des distracteurs confinés au
classement profond. Un diagnostic a été ajouté au rapport pour trancher, et il a
**réfuté ce soupçon** : le lot atteint le top-8 sur 14 des 50 questions faciles en
sémantique (15 en BM25) et sur 12 des 25 questions dures en BM25 (5 en
sémantique), et il atteint le **rang 1** dans les quatre configurations. Le zéro
mesure donc une vraie résistance, pas une absence de
concurrence : un tiers du top-8 peut être constitué de matière nouvelle sans que
le document annoté perde sa place.

**Ce que ça nuance, chiffres à l'appui.** La RRF est la **seule** méthode que
l'élargissement dégrade : −2 questions sur le jeu dur à k=3 (0,80 → 0,72) et à
k=5 (0,88 → 0,80), +1 sur le jeu facile. Sous le seuil de 3 questions fixé avant
la mesure — la même barre que celle utilisée le matin pour retenir l'avantage de
la RRF à k=8 —, donc aucun écart retenu. Mais le sens compte : la conclusion du
matin voyait dans l'avance de la RRF à k=8 « un argument pour une bascule RRF si k
était un jour relevé en production ». Ce test lui oppose un contrepoids. Ce qui
fait la force de la RRF sur un corpus figé — fusionner un classement large — est
exactement ce qui l'expose quand le corpus grossit : sur le jeu facile, les
distracteurs sont présents dans le top-50 sur 46 à 48 questions sur 50, contre 14
à 15 dans le top-8. L'argument de bascule tient toujours, il n'est plus gratuit.

**Triage des deux bascules, parce qu'un recall qui baisse ne dit pas qu'une
mauvaise réponse serait produite.** Les deux questions perdues ont été instruites
en lisant les classements de part et d'autre.

- **h01** (« Parle-moi des régimes spéciaux », la question phare de l'expérience
  de réécriture) : la page RSE centrale passe du rang 4 au rang 6. L'intrus qui
  prend sa place est le « Catalogue des services numériques AMU », sans aucun
  rapport avec le sujet — **vraie défaillance**. La question était déjà marginale
  à 18 documents : elle tenait au dernier rang du top-5, avec un seul cran de
  marge, et le distracteur l'a pris.
- **h20** (réinscription en ligne) : le guide IA web passe du rang 3 au rang 7.
  Trois fragments distracteurs s'installent aux rangs 2 à 4 — « Votre compte
  étudiant AMU » d'une part, deux fois le catalogue numérique d'autre part.
  **Déplacement partiellement légitime** : la page de compte étudiant traite bien
  des identifiants et de l'activation, et sert plausiblement un étudiant qui
  demande comment se réinscrire en ligne ; le catalogue, non.

**Le mécanisme, et il déplace la responsabilité.** Dans les deux cas, le rang du
document attendu **dans le classement sémantique ne bouge pas** (rang 12 pour
h01, rang 4 pour h20, à l'identique avant et après). Ce qui change, c'est la
*composition* du top-8 qui alimente la fusion. e5 ne confond donc pas les
nouveaux documents avec les anciens : la sensibilité mesurée est une propriété de
la RRF, pas de l'encodeur. Le risque n°1 du PRD n'est pas confirmé par ce test —
il n'est pas infirmé non plus, faute de concurrence sur le même sujet.

**Un document se distingue.** Le « Catalogue des services numériques AMU » est
l'intrus des deux bascules. Long, dense en sigles, il remonte sur des requêtes
qui ne le concernent pas. C'est un type de document — le catalogue fourre-tout —
plus qu'un cas particulier, et c'est lui qu'il faudrait surveiller si le corpus
réel s'élargissait.

**Ce que ça vaut.** Deux garde-fous méthodologiques ont été posés avant de
regarder les chiffres, et les deux ont servi à quelque chose. Le seuil fixé
d'avance a empêché de présenter −2 questions comme une dégradation ; le
diagnostic de concurrence a empêché de présenter un zéro comme une robustesse
sans l'avoir vérifié. Sur ce second point, la vérification a désavoué mon propre
soupçon — c'est le cas où elle vaut le plus cher. À noter également, sans
l'enjoliver : la liste de trois questions que j'avais annoncée comme « à trier en
priorité » (q53, q06, q29) n'a rien prédit. Le mécanisme anticipé pour q53 — la
page de compte étudiant déplaçant une question d'inscription en ligne — s'est bien
produit, mais sur h20. Le bon document, la mauvaise question.

**Décision.** Le corpus de production reste à 19 entrées : mesuré, documenté, non
branché, même régime que la RRF, la réécriture et la contextualisation. Le lot de
distracteurs est versionné comme instrument de mesure, pas comme corpus.

**Reste à faire.** Ce test mesure la dilution, pas l'ambiguïté entre deux
documents qui répondent tous les deux. Le document le plus adverse disponible — le
règlement intérieur des bibliothèques universitaires, un second règlement
intérieur face aux six questions q21-q24/h11/h24 — a été **disqualifié par le
contrat d'annotation lui-même** : son titre serait compté comme source attendue.
L'instruire suppose de resserrer ces six annotations (« Règlement intérieur
d'Aix-Marseille »), au prix de la comparabilité avec les rapports datés du
23 juillet. C'est l'arbitrage qui reste ouvert, et il ne se tranche pas sans
décider ce qui compte le plus : la continuité des mesures ou la couverture du
dernier mode d'échec non testé.

## 2026-07-26 — Comparaison avec AnythingLLM : le résultat existe, son instruction reste à faire

**Fait.** Une expérience annexe, hors périmètre du PRD, confronte le pipeline
maison à AnythingLLM v1.15.0 en déploiement Docker par défaut : corpus
strictement identique (les 19 sources de `corpus/sources.yaml`), backend LLM tenu
constant des deux côtés (`mistral-small-latest`), configurations par défaut
conservées de part et d'autre (k=5 ici, topN=4 là), mode de chat `query`
mono-tour. Le travail a été conduit dans un worktree séparé, les verdicts de
fidélité étant posés par huit agents indépendants, une paire de questions
chacun. Il était **entièrement non commité** : six fichiers non suivis, sur une
branche à zéro commit et quatre commits de retard sur `main`. Il est désormais
sécurisé en un commit (`bdb9860`, branche `worktree-compare-anythingllm`) —
script de pilotage, rapport, verdicts du jury, réponses brutes des deux
systèmes. Ces derniers JSON sont versionnés sans précédent dans le dépôt, où
seuls les rapports `.md` l'étaient, parce qu'ils sont la seule base probante des
verdicts.

**Ce que le rapport avance.** Refus hors-corpus : 4/4 contre 0/4. Questions
répondables : 14/16 correctes et ancrées contre 0/16, avec 13/16 réponses non
ancrées ou partiellement ancrées et 3/16 substantiellement fausses côté
AnythingLLM, contre 2/16 refus par excès de prudence côté assistant-amu. La
cause avancée n'est pas une infériorité générale du produit mais deux défauts de
configuration par défaut : `queryRefusalResponse` laissé à `null`, et l'échec du
scraper sur le gabarit Drupal central d'AMU — cinq des neuf pages web extraites à
un seul mot. Le cadrage *out-of-the-box* est annoncé d'emblée, le LLM est tenu
constant, et le rapport énonce ce qu'il ne montre pas. Sur la méthode déclarée,
c'est propre.

**Quatre réserves relevées à la relecture, aucune tranchée.**

- **Le jeu de questions est celui de 20 entrées**, antérieur au passage à 50 du
  même jour, et le corpus mesuré n'a pas les dix distracteurs. La colonne
  assistant-amu (14/16, 4/4) n'est donc pas recoupable avec les chiffres de tête
  actuels. Le rapport est daté et sa configuration épinglée, ce qui borne le
  malentendu sans le lever.
- **La preuve centrale n'est pas persistée.** Le tableau des mots extraits porte
  tout l'argument de la cause structurelle, et `cmd_ingest` imprime `wordCount`
  sur la sortie standard sans jamais l'écrire. Il n'existe que dans le
  défilement d'un terminal. Une ligne de sérialisation le rendrait rejouable.
- **Le jury n'est pas aveugle au sens attendu.** « À l'aveugle de ma propre
  lecture » est exact et ne dit pas que les juges ignoraient quel système
  répondait : les notes de verdict nomment les deux. Devant un écart de 14/16 à
  0/16, c'est un biais à nommer. Chaque question n'a par ailleurs été jugée
  qu'une fois — aucun accord inter-juges n'est mesurable.
- **L'expérience n'est pas rejouable par un tiers.** Aucune mention
  d'AnythingLLM dans `README.md`, `docs/` ni ce journal avant la présente
  entrée ; les trois variables requises (`ANYTHINGLLM_BASE_URL`, `_API_KEY`,
  `_WORKSPACE_SLUG`) ne figurent pas dans `.env.example` ; et la configuration
  initiale du produit — choix du fournisseur, création du workspace — n'a pas
  d'API et reste manuelle, après activation de WSL2.

**Décision.** Le travail reste sur sa branche, non fusionné dans `main`, et n'est
répercuté ni dans le README ni dans les documents de concepts. Même régime que
les autres expériences du dépôt — mesuré, documenté, non branché — avec une
raison de plus ici : c'est une comparaison contre un produit tiers sous une
configuration par défaut dont le rapport dit lui-même qu'un réglage d'une ligne
aurait probablement corrigé le 0/4 sur les refus.

**Reste à faire — étude de fond.** Rien de ce qui précède ne vérifie les verdicts
eux-mêmes : la relecture a porté sur la méthode, pas sur la substance. L'étude à
mener est la confrontation ligne à ligne des seize verdicts aux réponses brutes
désormais versionnées, pour établir que chaque case du tableau est étayée par ce
que les deux systèmes ont réellement produit — en particulier les trois verdicts
« substantiellement fausses » (q06, le SMIC annuel avancé pour le SMIC mensuel ;
q11, un mécanisme de compensation inventé ; q01, le déni d'une information
présente au corpus), qui sont les plus chargés et les plus faciles à
surinterpréter. Restent ensuite deux arbitrages qui ne se tranchent pas sans
décider ce qu'on attend du résultat : rejouer sur les 50 questions et le corpus à
28 documents (coût : un cycle complet des deux côtés, avec appels à l'API Mistral
de part et d'autre), et refaire juger à l'aveugle de l'identité des systèmes.

## 2026-07-26 — Revue de cohérence du lot Contextual Retrieval : fil ouvert

**Fait.** Le lot §5.3.1 — `ea2c747` à `86a34a5`, 14 commits, 30 fichiers — a été
relu de bout en bout, en deux passes indépendantes, la seconde conduite sans
connaissance des conclusions de la première. Dix-neuf constats, classés par
gravité dans `docs/revue-2026-07-26_contextual_retrieval.md`, chacun avec sa
référence `fichier:ligne`, sa preuve et son correctif proposé. **Rien n'a été
modifié** : la revue constate, elle ne corrige pas. Cette entrée tient le fil
ouvert pour une session ultérieure.

**Ce qui tient, et comment on le sait.** Les deux rapports ont été rejoués
intégralement hors ligne et se reproduisent cellule par cellule : 24 cellules de
recall, 12 écarts strict/naïf, statistiques de fenêtre, listes complètes des
questions gagnées et perdues, rangs de la question phare. La validité de mesure
est correctement câblée — la fusion RRF porte bien sur les classements
contextuels et ne substitue que les objets rendus — et le diagnostic de fenêtre
est exact, `tokenizer.encode()` comptant les tokens spéciaux.

**Ce que la revue débloque : reprendre un rapport ne coûte plus rien.** Le faire
imposait jusqu'ici de repayer environ 316 appels de modèle, les collections
contextuelles ayant disparu de `chroma_db/` — seule `amu_docs` subsiste.
`eval/repro_contextual_retrieval.py` les reconstruit depuis
`corpus/contexts.jsonl` avec un stub qui **lève** sur tout appel : zéro dépense,
et un défaut de cache échoue au lieu de coûter. Exécuté, il retrouve les chiffres
publiés à l'identique. Quatre des dix-neuf constats portent sur le générateur de
rapports : ils sont désormais corrigibles et vérifiables gratuitement, d'un seul
lot.

**À traiter en premier — un lecteur est trompé en l'état.**

1. `README.md:197` affirme que la contextualisation « gagne nettement plus qu'elle
   ne perd » ; `README.md:231` la qualifie d'« arbitrage défavorable ». La seconde
   ligne date de `fb2d16d` et n'a pas suivi l'inversion de `86a34a5`.
2. `eval/reports/2026-07-26_contextual_retrieval_440.md:130` publie « **Ce qu'elle
   casse** […] +0.00 (+0 questions) », puis explique la perte. Le générateur
   (`eval/contextual_retrieval_experiment.py:479-482`) code ce récit en dur sans
   regarder le signe de l'écart, et relègue la perte réelle de cette
   configuration — BM25, jeu dur, −4 questions à k=3 — à la puce suivante. C'est
   la classe de défaut que l'entrée du jeu élargi déclare corrigée : le verdict
   principal a été rendu conditionnel, ces deux puces ne l'ont pas été.

**Un piège à désamorcer.** Le garde-fou censé prévenir la troncature silencieuse
d'un document trop long (`MAX_DOC_CHARS = 60_000`, soit environ 14k tokens) ne
peut pas se déclencher : le plus long document du corpus fait 9 587 tokens. Or
`README.md:107` propose la commande sans variable d'environnement, et le défaut
est `ollama` à `num_ctx=8192` — le document serait coupé sans un mot, exactement
le piège que `README.md:40` documente par ailleurs. Les chiffres publiés ne sont
pas concernés : les 436 entrées du cache portent toutes
`mistral/mistral-small-latest`.

**Ce qui n'est pas une correction, mais mérite d'être su.** Les deux rapports
justifient la non-intégration sur des bases de mesure — artefact de troncature,
arbitrage entre populations de requêtes — et concluent qu'il « reste à trancher »
laquelle `/ask` doit servir en priorité. Aucun ne cite le §5.3, qui range le
Contextual Retrieval parmi les évolutions « documentées, non implémentées », ni le
§40 (« mesurer n'est pas brancher », V1 *et* V2). La décision est juste, mais
adossée à une raison plus faible que la vraie : formulée ainsi, elle laisse croire
qu'une mesure plus favorable suffirait à brancher la méthode.

**Reste à faire.** Les deux corrections ci-dessus, puis le fichier de revue par
lots : le plafond de 25 mots du prompt, violé par 48 % des contextes et contrôlé
par rien ; le chiffre de tête « +8 questions », qui se lit à k=3 alors que les
seules tables par question sont produites à k=5, si bien qu'aucun document ne dit
de quelles huit questions il s'agit ; la restauration du texte d'origine avant
comptage, que nul test ne couvre alors qu'elle porte la validité de l'expérience ;
enfin les points de propreté. Le constat sur le verdict a désormais son précédent
dans le dépôt : `eval/reports/2026-07-26_corpus_scaling.md:9` fixe son seuil de
signification à trois questions **avant** de mesurer, et le déclare — là où le
générateur de la contextualisation tranche à deux, après coup.

**En annexe de la revue, une piste gratuite.** La « sensibilité de BM25 au budget
de découpage », que le README laisse « à comprendre », s'explique
mécaniquement : le préfixe place l'intitulé du document en tête de chaque
fragment, si bien que les termes de titre passent d'une fréquence documentaire de
quelques fragments à la quasi-totalité de ceux du document — leur IDF s'effondre —
tandis que `avgdl` croît d'environ 25 tokens. Vérifiable sans nouvelle dépense, en
comparant l'IDF des termes de titre entre les deux collections, ou en mesurant le
recall BM25 sur un index bâti depuis `metadata["text_raw"]`.
