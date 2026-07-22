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
