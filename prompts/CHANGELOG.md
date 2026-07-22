# Changelog des prompts

Chaque modification d'un prompt (`prompts/*.md`) est consignée ici : date,
version, résumé du changement, **raison** et **cas de test** qui l'a motivé
(PRD §11.10). Le format v0 est le point de départ ; les itérations de la Phase 3
viennent l'enrichir.

## rag_system.md

### v0 — 2026-07-22 — version initiale
- Contenu repris tel quel du PRD §7.4 (prompt RAG v0).
- Structure : règles en message système ; les sources balisées en XML et la
  question sont assemblées côté `rag.py` dans le message utilisateur, question
  en fin de prompt.
- Raison : point de départ du pipeline de génération, à itérer en Phase 3 sur
  les quatre cas limites (hors corpus, contradictions, hors sujet, ambiguïté).
- Cas de test : à couvrir en Phase 3 (F6 — refus vérifié par comparaison
  normalisée, ≥ 3 itérations motivées).

## condense_system.md

### v0 — 2026-07-22 — version initiale (V2)
- Contenu repris tel quel du PRD §7.7 (prompt de condensation v0).
- Fichier posé dès le squelette (structure §6.3) ; **non branché** au code tant
  que la V1 n'est pas validée (F1-F9, PRD §11.3). Sera activé en Phase 7.
