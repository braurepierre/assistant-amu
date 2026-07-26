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

> **Révisé le 2026-07-26** (voir l'entrée « Ce que le jeu élargi a aussi révélé
> sur la contextualisation »). Cette affirmation ne vaut que pour la recherche
> sémantique. Sur le jeu élargi à 50 questions, **BM25 se dégrade nettement à
> 440 tokens** (−4 questions à k=3, −3 à k=5) — un effet que 16 questions ne
> pouvaient pas montrer. Rapport et README ont été corrigés ; cette entrée garde
> son texte d'origine et porte ce renvoi.

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

> **Rectifié le 2026-07-27.** Les trois annotations sont q06 (« job »), q08
> (« régime spécial ») et q28 (FOAD) : **une seule est une question de sigle**,
> la dernière. La justification avancée ne couvrait donc pas les deux autres. Le
> marqueur de q08 est de surcroît celui que ce même fichier documente comme peu
> fiable pour q03.

**La baseline recule, et ce n'est pas une régression.** Recall@5 : sémantique
0,94 → **0,86**, BM25 0,81 → 0,84, RRF 0,88 → 0,86. Le repli sémantique n'est pas
un défaut du système : le nouveau jeu couvre des documents qui n'avaient encore
aucune question (règlement intérieur, droits d'inscription, sigles, Cadrage M3C
Master, Mission handicap) et des procédures propres à une composante plutôt que
génériques (la césure à l'IUT plutôt qu'au niveau central). Le jeu à 16 questions
sur-représentait les documents déjà faciles à trouver ; le jeu à 50 mesure une
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

## 2026-07-27 — Le README rendu lisible, la démo rendue reproductible, et un point de registre dont la prémisse était fausse

**Fait.** Une note de travail non versionnée réunissait sept demandes
d'allègement et de cohérence documentaire. Toutes sont traitées sauf une, qui
demandait un arbitrage. `README.md` passe de 295 à 243 lignes ; le détail des
mesures part dans `docs/mesures.md` (299 lignes). Sont également repris
`DEMO.md`, `docs/README.md`, `demo.html`, `CLAUDE.md`, plus un README et un
`.env.example` sur la branche `worktree-compare-anythingllm`.

**Ce que l'allègement déplace réellement.** Le README ne portait pas seulement
un volume de chiffres : il portait l'argumentation complète de cinq études —
tables par question, désaccords commentés, diagnostics de concurrence, triage
des bascules. Publier cela sous un fichier d'accueil revenait à demander au
lecteur de traverser une revue de mesures avant d'atteindre le mode d'emploi. Le
partage retenu : le README garde la table recall@k et une conclusion d'une ligne
par étude, `docs/mesures.md` reçoit l'argumentation **intégrale**, sans coupe.
S'y ajoute un index des rapports datés, qui n'existait nulle part. Une table
« Documentation du projet » en tête recense enfin les cinq entrées du dépôt — la
page pédagogique `docs/concepts-assistant-amu.html` n'était référencée depuis
aucun document.

**Problème → solution : la démo n'était pas reproductible, mais pas pour la
raison annoncée.** La note visait un chemin absolu personnel en tête de
`DEMO.md`. Le vrai obstacle était ailleurs : `chroma_db/` et `corpus/raw/` sont
gitignorés — à juste titre, ce sont des données dérivées — et `DEMO.md`
démarrait directement sur `uvicorn`. Un tiers clonant le dépôt lançait donc une
API sur un index vide. Les étapes de premier lancement (téléchargement,
indexation) sont désormais explicites, et le contrôle par `/health` est indiqué
avec les valeurs attendues. Vérification faite en exécutant réellement la
chaîne, non en la relisant : `/health` à 18 documents et 316 fragments, réponse
sourcée à 5 extraits, refus canonique à 0 source.

**Ce que le point sur le registre supposait, et ce qu'il en était.** La demande
annonçait une passe corrective sur les commentaires de code et le
conversationnel du CLI. Vérification faite, il n'y avait rien à y corriger : le
code est commenté en anglais, les libellés `argparse` sont neutres, et
`demo.html` est déjà en vouvoiement. La dérive réelle était dans les documents
français destinés au lecteur — tutoiement dans `docs/README.md` (« jamais tes
sections ») et `DEMO.md` (« Tape ta question », « géré pour toi »), tournures
d'oralité (« en 4 gestes », « ça ne se génère pas », « tout seuls »), et un
emoji ornemental dans le message d'accueil de l'interface. Je le consigne parce
que la prémisse était fausse dans une direction utile : le soupçon portait sur
la surface la plus visible, le défaut était sur celle qu'on relit le moins.

La règle correspondante est ajoutée à `CLAUDE.md`, avec deux exceptions
nommées — les fichiers de `prompts/`, qui tutoient le modèle par convention
d'ingénierie de prompt, et ce journal, qui garde son registre d'analyse à la
première personne. Un troisième point a été précisé après coup : la règle
proscrivait les emoji, ce qui aurait condamné `🔎` et `⚠️` dans `demo.html`. Ces
deux-là signalent — requête réellement recherchée, erreur — là où le `👋`
d'accueil ornait. La règle distingue désormais les deux.

**Une correction faite en avance, et pourquoi.** Le constat n°1 de la revue du
26 juillet — `README.md` affirmant à la fois que la contextualisation « gagne
nettement plus qu'elle ne perd » et qu'elle « constitue un arbitrage
défavorable » — a été corrigé ici, hors de son lot. Recopier dans un fichier
neuf une phrase que la même page contredit n'était pas défendable : le
déplacement aurait pérennisé l'erreur au lieu de la laisser visible. La
justification de non-intégration s'appuie désormais sur le principe « mesurer
n'est pas brancher » (§40) plutôt que sur un verdict de mesure défavorable —
ce que la revue reprochait par ailleurs aux deux rapports.

**Un constat incident, à verser au lot revue.** `corpus/contexts.jsonl` est
gitignoré, au même titre que les autres données dérivées du corpus. Or
`eval/repro_contextual_retrieval.py`, dont l'entrée précédente signalait qu'il
rend la reprise des rapports gratuite, reconstruit les collections **depuis ce
fichier**. La gratuité annoncée ne vaut donc que sur ce poste : un tiers qui
clone le dépôt ne peut pas rejouer les rapports sans repayer les 316 appels.

**Sur la branche AnythingLLM.** Le renvoi depuis `main` pointait un fichier de
rapport, faute de page d'accueil. La branche a désormais un README aligné sur
celui de `langchain-port` : cadrage hors PRD, ce qui est tenu constant et ce qui
ne l'est pas, résultats, les deux causes structurelles, quatre limites énoncées,
procédure de reprise et inventaire des fichiers. Les trois variables
`ANYTHINGLLM_*` rejoignent `.env.example` de la branche — le README décrivait
une reprise que rien n'outillait, c'était la quatrième réserve de l'entrée
précédente.

**Ce que ça vaut.** Trois des sept demandes reposaient sur un diagnostic
partiellement inexact : le registre du code, le chemin absolu de la démo, et
l'idée qu'un README de branche existait déjà côté AnythingLLM. Les traiter
supposait de vérifier la prémisse avant d'appliquer le correctif — ce qui a
chaque fois déplacé le travail vers un défaut réel et plus profond que celui
signalé. C'est la valeur d'une note de travail : elle désigne l'endroit, pas
nécessairement la cause.

**Décision.** La reprise de la comparaison AnythingLLM sur le corpus courant
(28 documents, 50 questions) est **différée**. Elle suppose de relancer WSL2 et
Docker, de reconfigurer le produit à la main et de payer des appels de part et
d'autre — pour produire un second chiffre dont la substance ne serait pas plus
établie que celle du premier.

**Reste à faire.** La confrontation des seize verdicts aux réponses brutes
versionnées, priorité retenue : elle ne coûte rien, elle porte sur des données
déjà présentes, et elle conditionne toute reprise de mesure. Puis le lot revue,
augmenté du constat sur `corpus/contexts.jsonl`.

## 2026-07-27 — Les verdicts AnythingLLM instruits : trois cellules fausses, toutes du même côté

**Fait.** Les vingt lignes du rapport de comparaison ont été confrontées aux
réponses réellement produites par les deux systèmes, telles que versionnées la
veille. Aucun appel de modèle : la vérification ne porte que sur des données déjà
au dépôt. Rapport
`eval/reports/2026-07-27_anythingllm_verdicts_verification.md` sur la branche.
Dix-sept lignes tiennent. Trois cellules du tableau de synthèse sont fausses.
Les quatre questions hors-corpus ont été incluses bien qu'elles ne fassent pas
partie des seize verdicts : elles portent l'autre chiffre de tête.

**Les deux verdicts les plus lourds tiennent, et l'un d'eux plus fortement
qu'annoncé.** Sur q06, AnythingLLM écrit mot pour mot « 3 fois le SMIC **annuel**
(soit environ 47 000 €) » là où la règle porte sur le SMIC mensuel — une erreur
d'un facteur douze, sur un chiffre qu'un étudiant pourrait utiliser. Sur q11, il
contredit sa source sur deux points (compensation par semestre au lieu de
l'annuelle à l'intérieur des BCC jumeaux ; ECUE déclarés non compensables) et
ajoute un bonus et un exemple chiffré qui n'existent pas. Ce second cas est le
plus instructif du lot : **le bon document avait été récupéré**, un PDF que
l'ingestion avait traité sans difficulté. La défaillance n'est donc imputable ni
au `queryRefusalResponse` non configuré, ni à l'échec du scraper. Les deux causes
structurelles avancées par le rapport sont réelles, mais elles ne couvrent pas
tout : subsiste un mode d'échec où la bonne source est là et la réponse la
contredit. On le retrouve, atténué, sur q12 et q14.

**Problème → solution : le barème n'était pas le même des deux côtés.** q01 était
comptée parmi les « substantiellement fausses ». Or la réponse ne contient aucune
affirmation fausse : elle décline et redirige vers le service de scolarité. Elle
est même exacte au regard de l'index d'AnythingLLM, où la page césure avait été
ingérée à un seul mot. C'est un refus — le même comportement que q02 et q16 côté
assistant-amu, qui sont comptés `refused_incorrectly`, pas `incorrect`. Une même
conduite, deux étiquettes. L'anomalie se lit encore mieux en regardant q08, de
forme identique — « il n'y a pas d'information sur le RSE » — mais **suivie d'une
définition fabriquée** : plus grave que q01, et pourtant classée dans la
catégorie la plus douce. Le barème le plus sévère avait été appliqué au cas le
plus bénin.

**Même mécanisme sur le second chiffre de tête.** Le 0/4 de refus hors-corpus
comptait q18 comme un échec. La réponse dit ne pas pouvoir répondre faute
d'information dans les documents et ne fabrique aucune prévision : sur le fond,
elle refuse. Le rapport la qualifiait de « pas un refus net ». Le défaut n'est
pas ce jugement, c'est l'**instrument** : dans la même case de tableau, le 4/4
d'assistant-amu est établi par `is_refusal()` — comparaison normalisée à la
chaîne canonique — et le 0/4 d'AnythingLLM par lecture. q18 tombe dans l'écart
entre les deux. Les trois autres ne refusent pas et le confirment par contraste :
q17 affirme « Canberra » sans réserve, q19 reconnaît l'absence d'information puis
publie sept tarifs, q20 livre une recette complète.

**Ce que ça change, et ce que ça ne change pas.** Refus hors-corpus 0/4 → **1/4**,
refus à tort 0/16 → **1/16**, substantiellement fausses 3/16 → **2/16**. La
colonne assistant-amu est inchangée. Le sens du résultat ne bouge pas : 4/4
contre 1/4, 14/16 contre 0/16 sur l'ancrage — l'écart reste massif. Ce qui bouge
est la précision, et un point de méthode qui pèse davantage que les chiffres.

**Ce que ça vaut.** Les trois erreurs vont dans le même sens : aucune ne joue en
faveur d'AnythingLLM. C'est exactement le biais que l'entrée du 26 juillet avait
identifié en principe — les juges nommaient les deux systèmes dans leurs notes,
devant un écart annoncé de 14/16 à 0/16 — sans pouvoir le mesurer. Il l'est
maintenant : sur vingt lignes, trois glissements, tous du même côté. Nommer un
biais ne suffit donc pas à le neutraliser, et un jury qui ignore l'identité des
systèmes n'est pas une précaution de forme. À noter aussi, dans l'autre sens :
deux verdicts étaient **sous-évalués** — le « timbre fiscal de 20-30 € » inventé
en q07 est une condition administrative fabriquée, pas une généralité plausible,
et la précision ajoutée en q12 contredit sa source au lieu de la dépasser. La
dérive du barème n'est pas unidirectionnelle dans le détail ; elle l'est dans ses
effets sur les chiffres publiés.

**Une incohérence mineure, sans effet.** Le champ
`anythingllm_self_flagged_uncertain` vaut `false` pour q03 et q05, dont les deux
réponses se terminent pourtant par la formule « Adapté des contextes fournis »
qui vaut `true` ailleurs. Le champ n'alimente aucun chiffre publié ; les notes
rédigées, elles, décrivent correctement ces réponses.

**Décision.** Le rapport du 26 juillet garde ses valeurs d'origine — c'est un
artefact daté — avec un renvoi en tête et une marque ⚠ sur les trois cellules
concernées. Le README de la branche, lui, publie les chiffres corrigés : c'est la
page d'accueil, elle ne doit pas propager les anciens.

**Reste à faire.** Les réponses d'assistant-amu jugées « correctes et ancrées »
n'ont pas été revérifiées contre le corpus lui-même : la vérification établit la
cohérence entre verdicts et réponses, pas entre réponses et documents sources.
Le rejugement à l'aveugle reste entier — constater un biais par ses effets ne le
supprime pas. Enfin le lot revue, augmenté du constat sur
`corpus/contexts.jsonl`.

## 2026-07-27 — Rejugement à l'aveugle : le 14/16 tient, deux de mes conclusions du matin tombent

**Fait.** Les deux angles morts de l'entrée précédente sont traités ensemble,
parce que le second a besoin du premier. `eval/serialize_retrieved_sources.py`
récupère les passages qu'assistant-amu avait réellement lus ; huit juges
indépendants, ignorant l'identité des systèmes, rejugent les seize questions avec
ces passages en main. Rapport `eval/reports/2026-07-27_blind_rejudge.md` sur la
branche, verdicts versionnés. Je n'ai pas jugé moi-même : ayant tout lu, je suis
le juge le moins aveugle disponible.

**La récupération des passages ne coûte rien, et c'est le point à retenir.** Sans
historique et avec `rewrite="raw"`, la requête de recherche est la question
verbatim (`rag.py:154-158`) : rejouer `store.query()` reproduit exactement les
fragments qui ont servi aux réponses stockées. Aucun appel de modèle, aucune
réponse régénérée — donc les verdicts existants restent comparables, ce qu'une
reprise complète aurait détruit. Contrôle sur six questions témoins : les chaînes
distinctives des réponses (« eCandidat », « attestation sur l'honneur », « BCC
jumeaux », « sesame.univ-amu.fr ») se retrouvent toutes dans les passages
récupérés.

**Le chiffre qui n'avait jamais été instruit tient.** 14/16 correctes et ancrées,
2 refus : identique au rapport d'origine, mais établi cette fois par des juges
disposant des fragments effectivement lus, là où le jury de départ ne disposait
que de la réponse et de ses marqueurs `[S1]`. L'ancrage d'assistant-amu n'est plus
inféré, il est vérifié. Côté AnythingLLM, accord sur 12 verdicts sur 16.

**Le biais est confirmé, et borné.** Les quatre écarts : q01 (`incorrect` →
`refused`), q03 et q11 adoucis, et **q14 durci** — le juge aveugle relève que le
délai de quinze jours porte sur la convocation et non sur la publication des
sujets, ce que le jury d'origine n'avait pas vu. Trois écarts en faveur
d'AnythingLLM, un contre : le déséquilibre est réel, il n'est pas systématique.
Sur q01, le juge aveugle va plus loin que ma correction du matin : il note que le
refus était *correctement motivé*, ses passages ne contenant effectivement rien
sur la césure.

**Un résultat défavorable à assistant-amu, à ne pas escamoter.** Le juge relève
que le refus q02 portait sur une question à laquelle ses propres passages
répondaient explicitement (« souhaitez suspendre vos études pour un ou deux
semestres… La césure est faite pour vous ! »). Ce n'est pas un refus de prudence
sur une question limite, c'est un refus alors que le contexte fourni répondait.

**Deux de mes conclusions du matin sont fausses.** La reclassification que je
proposais pour q15 : le juge, qui a lu les passages, constate qu'ils portent sur
les examens, le doctorat et le plagiat, et ne soutiennent pas la section
« Droits » — le verdict d'origine était juste. Et le « troisième mode d'échec »
que j'annonçais sur q11 : les passages remontés du bon PDF ne contenaient que la
structure (BCC, UE, ECTS) et une mention de bonus, **pas la règle de
compensation**. Le bon document, pas le bon fragment — défaut de recherche, non
mode d'échec inédit. La réponse d'AnythingLLM reste factuellement fausse ; c'est
ma conclusion sur les causes qui tombe.

**Ce que ça vaut, et c'est inconfortable.** Mes deux erreurs ont la même origine :
j'ai jugé la qualité de la recherche sur les **titres** des documents remontés
sans ouvrir le texte des passages — alors que ce texte était dans le fichier que
je lisais. C'est exactement le raccourci que je reprochais au rapport du
26 juillet, qui inférait l'ancrage d'assistant-amu de ses marqueurs `[S1]` sans
ouvrir les fragments. Même erreur, un étage plus haut, commise dans le geste même
qui la dénonçait. La leçon n'est pas « vérifier davantage » : c'est qu'une
étiquette — un titre de document, un marqueur de citation — n'est jamais une
preuve du contenu qu'elle désigne, et que je m'en suis contenté au moment
précis où je démontrais qu'il ne fallait pas.

**Un défaut de mon anonymisation, déclaré.** Pour empêcher l'identification des
systèmes, j'ai retiré les titres et URL de source des passages : les deux
systèmes nomment leurs documents différemment, ce qui aurait trahi l'identité. Or
le pipeline **fournit ces titres au modèle** en production (`rag.py:83-87`). Les
juges ont donc évalué assistant-amu sur moins de matière qu'il n'en avait. Sans
effet sur les questions de contenu, mais le `answer_was_available: false` du
verdict q16 n'est pas fiable — le refus q16, lui, reste bien un refus à tort,
la page attendue figurant au top-5.

**Décision.** Le rapport du matin conserve son texte, avec un renvoi en tête et
une marque ⚠ sur les deux passages réfutés ; le README de la branche publie l'état
consolidé. Même régime que pour le rapport du 26 : un artefact daté ne se
réécrit pas, il s'annote.

**Reste à faire.** Chaque question reste jugée une seule fois dans les deux
séries : aucun accord inter-juges n'est mesurable, et c'est désormais la
faiblesse méthodologique dominante. La performance d'AnythingLLM correctement
configuré demeure l'angle mort principal. Enfin le lot revue, augmenté du constat
sur `corpus/contexts.jsonl`.

## 2026-07-27 — Le lot revue traité : dix-neuf constats corrigés, dont un garde-fou qui ne pouvait pas se déclencher

**Fait.** Les dix-neuf constats de `docs/revue-2026-07-26_contextual_retrieval.md`
sont corrigés. La suite de tests passe de **142 à 161** cas. Les deux rapports
ont été rejoués hors ligne avant et après : les chiffres publiés se reproduisent
à l'identique aux deux budgets de découpage, ce qui établit que les correctifs
n'ont pas touché la mesure. Le document de revue garde son texte et porte un
en-tête signalant les deux points où le correctif s'écarte de celui proposé.

**Ce que la correction du générateur change vraiment.** Les constats 2 à 4
tenaient tous au même mécanisme : le rapport tirait des extrema de douze cellules
non comparables, puis les présentait comme un solde. À 500 tokens, « gagne
nettement plus qu'elle ne perd (8 contre 2) » opposait *jeu dur / semantic / k=3*
à *jeu facile / semantic / k=5* ; à 440, « échange 4 contre 4 » opposait le
sémantique à BM25 — rien n'était échangé. Trois changements y répondent : le
seuil de signification est désormais **fixé à trois questions et déclaré dans le
rapport** (la barre du rapport de sensibilité au corpus, qui la déclarait déjà
avant de mesurer, là où le générateur tranchait à deux après coup) ; chaque
chiffre **nomme sa configuration** ; et une ligne de **dispersion** donne la somme
des écarts et le décompte des cellules gagnantes et perdantes. Résultat, à
500 tokens : « améliore la recherche — au mieux 8 questions (jeu dur, semantic,
k=3), aucune perte n'atteignant le seuil », avec +18 questions sur douze cellules,
huit gagnantes, trois perdantes. À 440 : « gagne et perd selon la configuration »,
les deux extrema nommés.

**Les puces du verdict ne racontent plus une histoire indépendante du signe.** « Ce
qu'elle casse » était codé en dur sur le pire écart du *jeu facile*, quel qu'en
soit le signe : à 440 tokens ce pire écart valait zéro, et le rapport expliquait
donc une perte inexistante tout en reléguant la perte réelle — BM25, jeu dur,
−4 questions — à la puce suivante. Les deux puces sont maintenant conditionnelles
au signe, la perte est choisie sur **les deux jeux**, et son explication suit la
**méthode** concernée : le déplacement du vecteur pour le sémantique, et pour BM25
l'hypothèse de l'effondrement de l'IDF des termes de titre — celle que l'annexe de
la revue proposait pour la « sensibilité au budget de découpage » restée à
comprendre. Enfin, les tables par question sont produites **à chaque valeur de k**
et non plus au seul k=5 : le chiffre de tête se lit à k=3, et aucun document ne
disait de quelles huit questions il s'agissait.

**Problème → solution : un garde-fou qui ne pouvait pas se déclencher.**
`MAX_DOC_CHARS = 60 000` (~14k tokens) devait prévenir la troncature silencieuse
d'un document trop long pour la fenêtre du backend. Le plus long document du
corpus fait 40 144 caractères pour 9 587 tokens : le seuil était inatteignable.
Pendant ce temps, la commande proposée par le README tourne par défaut sur Ollama
à `num_ctx=8192`, où ce document serait coupé sans un mot. Les backends publient
désormais leur fenêtre réelle (`context_window`), et le budget en caractères en
est **dérivé** : 8192 tokens donnent environ 24 500 caractères, donc l'avertissement
se déclenche là où il devait le faire. Un test fixe la propriété par les deux
bouts — le document de 40 144 caractères doit dépasser le budget local et tenir
dans celui de l'API.

**Problème → solution : la précaution centrale n'était pas testable.**
`RawTextRetriever` et la restauration du texte d'origine avant comptage portent la
validité de toute l'expérience — sans elles, une phrase de contexte citant un
mot-clé attendu fabrique une réussite de recherche. Elles vivaient dans un script
de `eval/`, que nul test n'atteint, tandis que la moitié ingestion était couverte
trois fois. Elles rejoignent `evaluation.py` et sont couvertes par huit cas, dont
la propriété elle-même énoncée comme une assertion exécutable : sur un fragment
dont seul le contexte mentionne « césure », le comptage naïf réussit et le
comptage strict échoue. Une régression inverserait désormais un test au lieu
d'inverser silencieusement les conclusions publiées.

**Un défaut de cache vérifié, et une option qui ne servait à rien.** La lecture de
`record["context"]` était placée hors du `try` censé garantir qu'« une dernière
ligne tronquée ne fait pas perdre tout le cache » : un enregistrement JSON valide
mais privé de cette clé faisait échouer le chargement entier. Corrigé, avec le
test correspondant. Par ailleurs l'aide de `--max-tokens` annonçait
`CHUNK_MAX_TOKENS` depuis l'origine, alors qu'aucun chemin de production ne lisait
`settings.chunk_max_tokens` — poser la variable dans `.env` n'avait **aucun
effet**. Elle est maintenant branchée comme défaut réel, le drapeau gardant la
priorité.

**Ce que je n'ai pas fait, et pourquoi.** Le plafond de vingt-cinq mots du prompt,
violé par 48 % des contextes, n'est **pas** imposé par troncature. Couper une
phrase nominale en son milieu l'abîmerait, et modifierait silencieusement des
contextes déjà mesurés et publiés — j'aurais échangé un défaut invisible contre un
autre. Le dépassement est compté, porté par le rapport de lot et affiché par la
commande. C'est la moitié de la recommandation, assumée : rendre l'écart visible
plutôt que le résorber en abîmant la donnée.

**Ce que ça vaut.** Sur les dix-neuf constats, deux classes se dégagent. Les
défauts de *récit* — un verdict codé en dur, des extrema présentés comme un solde,
un chiffre de tête non traçable — venaient tous du même endroit : un générateur qui
sait produire une phrase mais pas vérifier qu'elle décrit ses propres chiffres. Les
défauts de *garde-fou* — le seuil de troncature inatteignable, le plafond de mots
non contrôlé, l'option jamais lue, le `try` mal placé — ont en commun d'avoir été
écrits comme des protections et de n'en être plus que la trace : un commentaire
promettait, le code ne tenait pas. Aucun des deux groupes n'a jamais fait échouer
quoi que ce soit, et c'est précisément pourquoi ils ont survécu à quatorze commits.

**Reste à faire.** `corpus/contexts.jsonl` est exclu de git — hygiène correcte pour
une donnée dérivée — alors qu'il est aujourd'hui le seul chemin de reproduction des
deux rapports, les collections d'origine ayant disparu. Sur ce poste la reprise ne
coûte rien ; sur un clone neuf elle suppose de repayer environ 316 appels.
Versionner 143 Ko lèverait l'obstacle au prix d'une exception à la règle. Arbitrage
documenté dans `docs/mesures.md`, non tranché. Restent par ailleurs, côté
AnythingLLM, l'absence d'accord inter-juges mesurable et la performance du produit
correctement configuré.
