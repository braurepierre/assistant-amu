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
