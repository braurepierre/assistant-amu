# Changelog des prompts

Chaque modification d'un prompt (`prompts/*.md`) est consignée ici : date,
version, résumé du changement, **raison** et **cas de test** qui l'a motivé
(PRD §11.10). Le format v0 est le point de départ ; les itérations de la Phase 3
viennent l'enrichir.

## rag_system.md

> Les itérations v1–v3 sont des améliorations **raisonnées**, ciblant les quatre
> cas limites du §7.4 (hors corpus, contradiction, hors sujet, ambiguïté). La v1
> est en outre motivée empiriquement (bug de retour à la ligne repéré en écrivant
> le test de refus). La validation chiffrée sur `eval/questions.yaml` (taux de
> refus correct, fidélité) est à faire dès qu'un backend LLM + un corpus figé sont
> disponibles (F6, §7.6).

### v3 — 2026-07-22 — quotes-first léger + concision
- **Diff** : ajout d'une section « Méthode » demandant de repérer d'abord les
  passages pertinents et de n'en rien extrapoler (variante *quotes-first* du §7.4,
  sans bloc `<citations>` en sortie pour garder la réponse propre) ; règle 5 :
  concision, pas de préambule.
- **Raison** : améliorer la *fidélité* (RAGAS faithfulness) et couper les
  généralités hors sources.
- **Cas visé** : réponse verbeuse ajoutant du hors-source « pour bien faire ».

### v2 — 2026-07-22 — ambiguïté + discipline de citation
- **Diff** : nouvelle règle 4 (question ambiguë entre plusieurs composantes/
  régimes → présenter chaque cas séparément) ; règle 2 renforcée (chaque
  affirmation citée, jamais d'identifiant non utilisé) ; règle 3 explicitée.
- **Raison** : éviter qu'une question ambiguë reçoive une réponse arbitraire, et
  fiabiliser les citations.
- **Cas visé** : « Quelles sont les modalités d'examen ? » alors que les extraits
  couvrent deux composantes distinctes.

### v1 — 2026-07-22 — phrase de refus sur une ligne + hors-sujet explicite
- **Diff** : la phrase de refus, auparavant coupée sur deux lignes, est mise sur
  une seule ligne ; la règle 1 couvre désormais explicitement les questions **hors
  sujet** (et pas seulement l'information absente).
- **Raison (empirique)** : en câblant la détection de refus par comparaison
  normalisée (§7.6), le retour à la ligne de la v0 rendait le « mot pour mot »
  ambigu — un modèle pouvait reproduire ou non la coupure. Une ligne unique lève
  l'ambiguïté.
- **Cas visé** : « Quelle heure est-il ? » → doit produire exactement la phrase de
  refus, 0 source citée (F6).

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
- Fichier posé dès le squelette (structure §6.3), **branché en Phase 7** :
  `RagPipeline._condense` l'utilise comme message système quand `history` est
  fourni. Non modifié depuis v0 ; toute itération future viendra ici (§11.10).
