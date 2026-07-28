# Mesures et évaluation — AssistantAMU

Cette page réunit les résultats détaillés et leur commentaire. Le `README.md`
principal n'en conserve qu'une synthèse chiffrée.

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur
équivalent au *context recall* du framework RAGAS) selon trois stratégies de
recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown
daté est généré dans `eval/reports/` à chaque exécution ; les tables par
question s'y lisent.

Deux conventions valent pour toute la page. Les méthodes mesurées ici — fusion
RRF, réécriture de requête,
[*Contextual Retrieval*](glossaire-assistant-amu.html#contextuel) — ne sont pas
intégrées au pipeline `/ask`, qui reste purement sémantique. Un écart n'est
retenu qu'à partir de trois questions,
[seuil](glossaire-assistant-amu.html#seuil) fixé avant les mesures (granularité
du jeu de 50 questions : 1/50 = 0,02).

---

## Synthèse des résultats

* **La recherche sémantique seule suffit à k = 5.** 0,86 de rappel, à égalité
  avec la fusion RRF : `/ask` reste purement sémantique.
* **La fusion RRF gagne en profondeur et perd à l'échelle.** Elle devance le
  sémantique de 3 questions à k = 8, mais elle est la seule méthode à reculer
  quand le corpus passe de 18 à 28 documents. La brancher demanderait de
  trancher entre ces deux mesures.
* **Le choix de l'encodeur est tranché.** `e5-small` devance CamemBERT et
  FlauBERT de 16 et 10 points à k = 3 et k = 5, pour une empreinte mémoire deux
  fois moindre.
* **La contextualisation des fragments aide les formulations
  conversationnelles** — au mieux 8 questions gagnées — sans que le solde
  justifie son intégration.
* **Le retrait de l'ouverture conversationnelle améliore la recherche.** Sur des
  formulations parlées, le rappel passe de 0,48 à 0,72 à k = 3 par simple
  retrait heuristique, sans appel de modèle.
* **Le refus tient.** 100 % des questions hors-corpus sont refusées, sur les
  deux backends, y compris le backend local dans sa configuration de repli.
* **La limite connue porte sur la recherche, pas sur la génération.** En
  multi-tour, la page institutionnelle attendue se fait évincer par une page de
  composante, et 11,7 % de l'index est constitué de fragments de moins de
  50 caractères qui captent les requêtes courtes.

---

## Résultats de référence

*Corpus de test : 18 documents, 316 fragments, 50 questions d'évaluation.*

| Méthode | k=2 | k=3 | k=5 | k=8 |
|---|---|---|---|---|
| semantic | 0,80 | 0,82 | 0,86 | 0,86 |
| bm25 | 0,70 | 0,78 | 0,84 | 0,88 |
| rrf | 0,74 | 0,82 | 0,86 | **0,92** |

À k = 8, la fusion RRF dépasse le sémantique pur de 3 questions sur 50 (0,92
contre 0,86). `/ask` reste sémantique pur au k par défaut de 5, où les deux
méthodes sont à égalité ; une bascule vers la RRF si k était relevé se lit avec
son contrepoids (voir « Sensibilité à la taille du corpus ») : la RRF est aussi
la seule méthode qu'un corpus élargi dégrade.

### Désaccords sémantique / BM25

| id | question | trouvé par | mécanisme |
|---|---|---|---|
| `q02` | « Puis-je interrompre mes études pendant un an puis les reprendre ? » | sémantique | paraphrase pure — la requête ne contient aucun terme du corpus (« césure »), seul le sens y conduit. |
| `q31` | « Auprès de qui se signaler pour bénéficier d'un régime spécial à la faculté de droit ? » | BM25 | le sémantique se laisse détourner vers le document IUT, structurellement proche ; BM25 accroche « signaler » au bon fragment. |
| `q52` | « Quelles pièces justificatives faut-il fournir lors de l'inscription en ligne ? » | BM25 | terme composé et rare (« pièces justificatives ») : le sémantique renvoie vers un document sans rapport. |
| `q53` | « Comment se connecter à la plateforme d'inscription administrative en ligne ? » | sémantique | la question paraphrase l'intitulé du document sans le citer ; BM25 disperse le score sur des termes trop génériques. |

Neuf désaccords existent en tout à k=5 (`eval/reports/2026-07-26_retrieval_all_k5.md`) ;
le mécanisme récurrent — la paraphrase favorise le sémantique, le terme rare ou
exact favorise BM25 — motive la mesure de la fusion RRF.

---

## Analyse comparative des modèles d'embeddings

Rappel sémantique sur les mêmes 50 questions et les mêmes fragments ; `/ask`
conserve le modèle de production.

| Modèle d'embeddings | @3 | @5 | @8 |
| :--- | :---: | :---: | :---: |
| `intfloat/multilingual-e5-small` (production, 384 dimensions) | **0,82** | **0,86** | 0,86 |
| `dangvantuan/sentence-camembert-base` (768 dimensions) | 0,66 | 0,76 | 0,86 |
| `hugorosen/flaubert_base_uncased-xnli-sts` (768 dimensions) | 0,68 | 0,76 | 0,86 |
| _BM25 (référence lexicale)_ | 0,78 | 0,84 | 0,88 |

e5 domine à k = 3 et k = 5 (+16 et +10 points sur CamemBERT), les trois modèles
se rejoignent à k = 8 : e5 reste le modèle retenu, pour une empreinte mémoire
deux fois moindre. FlauBERT échoue en particulier sur les sigles et les
définitions (RSE, CVEC, LANSAD, FOAD) ; sa variante *cased*
(`Lajavaness/sentence-flaubert-base`) ne s'initialise pas sous
`sentence-transformers` 5.6.1, d'où le recours à l'*uncased*.

Script : `eval/embedder_comparison.py` ; rapport :
`eval/reports/2026-07-26_embedder_comparison.md`.

---

## Contextual Retrieval — index contextuel comparé à la référence

Chaque fragment est préfixé, avant l'embedding et l'indexation BM25, d'une
phrase générée par le LLM le situant dans son document (méthode Anthropic,
septembre 2024 — [fiche du
glossaire](glossaire-assistant-amu.html#contextuel)). L'index est constitué dans
une collection parallèle ; mesures sur les deux
[jeux de questions](glossaire-assistant-amu.html#jeux), le jeu « dur »
réunissant les formulations conversationnelles.

| Jeu de questions | Méthode | Référence | Index contextuel |
| :--- | :--- | :---: | :---: |
| **Dur** (25 questions, k=3) | sémantique | 0,48 | **0,80** |
| **Dur** (25 questions, k=5) | BM25 | **0,84** | 0,80 |
| **Facile** (50 questions, k=5) | sémantique | **0,86** | 0,82 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,94** |

À 500 tokens de budget de découpage, la contextualisation améliore la
recherche : meilleur gain +8 questions (jeu dur, sémantique à k=3 — le mode
d'échec visé), pire perte −2 (jeu facile, sémantique à k=5, sous le seuil).
Sur les douze cellules mesurées (2 jeux × 3 méthodes × 2 valeurs de k), la
somme des écarts vaut **+18 questions** : huit cellules gagnantes, trois
perdantes, une inchangée. Le mécanisme : le préfixe rapproche le vecteur du
fragment du sujet de son document, ce qui sert les requêtes vagues et dessert
les requêtes précises en sémantique seul ; la fusion RRF gagne sur les deux
jeux (+2 sur le dur à k=3, +4 sur le facile à k=5), la composante BM25
compensant ce que le sémantique cède.

Trois réserves bornent ces chiffres :

* **Comptage.** Le jeu « facile » exige des mots-clés dans le fragment
  récupéré, or un contexte généré nomme presque toujours son sujet. Le texte
  d'origine est restauré après classement — le contexte sert à trouver le
  fragment, pas à valider la réussite ; l'artefact ainsi évité atteint trois
  questions de rappel.
* **Budget de découpage.** Le préfixe faisait sortir 23 fragments (7 %) de la
  fenêtre d'encodeur de 512 tokens. Rejouée à 440 tokens, sans débordement,
  l'expérience conserve le gain sémantique (+4 sur le jeu dur à k=3, contre +8
  à 500) ; la réponse de BM25 dépend en revanche du budget — quasi neutre à
  500, dégradée à 440 (−4 à k=3, −3 à k=5) — comportement à comprendre avant de
  généraliser.
* **Échelle.** Les chiffres publiés par Anthropic (−49 % d'échecs de recherche)
  portent sur des corpus de plusieurs milliers de fragments ; 25 et 50
  questions ne peuvent ni les confirmer ni les infirmer.

Rapports : `eval/reports/2026-07-26_contextual_retrieval.md` et `…_440.md`.
`eval/repro_contextual_retrieval.py` reconstruit les quatre collections depuis
le cache `corpus/contexts.jsonl` — versionné par exception, seul chemin de
reproduction des deux rapports (143 Ko contre environ 316 appels de modèle) —
et retrouve les chiffres publiés sans appel de modèle.

---

## Réécriture de requête — deux stratégies comparées

Une question conversationnelle (« Parle-moi des régimes spéciaux ») recherche
mal : l'ouverture occupe une part du vecteur sans porter de sens. Deux
stratégies sont comparées à la requête brute — `strip`, retrait heuristique de
l'ouverture, déterministe et sans appel de modèle ; `llm`, reformulation
factuelle par le backend, un appel par requête — sur le jeu dur de 25
formulations parlées, le jeu de 50 servant de contrôle de non-régression.

| Stratégie | Jeu dur @3 | Jeu dur @5 | Jeu de 50 @3 | Jeu de 50 @5 |
| :--- | :---: | :---: | :---: | :---: |
| requête brute | 0,48 | 0,72 | 0,82 | 0,86 |
| `strip` | 0,72 | **0,88** | 0,82 | 0,86 |
| `llm` | **0,84** | **0,88** | 0,80 | 0,88 |

Le retrait de l'ouverture fait passer le rappel de 0,48 à 0,72 à k = 3 :
« Parle-moi des régimes spéciaux » ne remonte pas la page « Régime spécial
d'études », qui apparaît au rang 4 dès que la requête est ramenée à « régimes
spéciaux ». La réécriture par le modèle gagne 3 questions de plus sur le jeu
dur mais en perd une sur le jeu de 50 — en reformulant « interrompre mes études
pendant un an », elle efface le lien lexical vers « césure ». À k = 5, les deux
stratégies sont à égalité (0,88) : l'arbitrage porte sur le coût, `llm`
demandant un appel de modèle supplémentaire et non déterministe. Aucune des
deux n'est branchée dans `/ask`.

Script : `eval/query_rewrite_experiment.py` ; rapport :
`eval/reports/2026-07-26_query_rewrite.md`.

---

## Sensibilité à la taille du corpus — 18 documents comparés à 28

Retrouver le bon document parmi dix-huit est intrinsèquement facile : une part
du rappel de référence pouvait venir de là. Un lot de dix pages distractrices
(`corpus/sources_distractors.yaml`) porte le corpus de 18 à 28 documents
indexés (316 → 378 fragments), à jeu de questions inchangé ; index reconstruits
dans le même passage, même encodeur, même découpage, sans appel LLM ni
écriture dans la collection de production.

| Jeu de questions | Méthode | 18 documents | 28 documents |
| :--- | :--- | :---: | :---: |
| **Facile** (50 questions, k=5) | sémantique | 0,86 | 0,86 |
| **Facile** (50 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,88** |
| **Dur** (25 questions, k=5) | sémantique | 0,72 | 0,72 |
| **Dur** (25 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Dur** (25 questions, k=5) | RRF | 0,88 | **0,80** |

Le sémantique et BM25 ne perdent aucune question sur 75 questions et trois
valeurs de k : les arbitrages retenus — e5, k = 5 — résistent à un corpus
élargi de moitié. Les distracteurs pèsent réellement sur les classements — ils
atteignent le top-8 sur 14 des 50 questions faciles en sémantique (12 des 25
dures en BM25) et le rang 1 dans les quatre configurations — l'immobilité du
rappel ne tient donc pas à un lot resté trop bas. La RRF est la seule méthode à
céder (−2 questions sur le jeu dur, sous le seuil) : pour `h01`, la page
attendue passe du rang 4 au rang 6, chassée par un catalogue de services sans
rapport — défaillance ; pour `h20`, du rang 3 au rang 7, chassée par une page
de compte étudiant qui traite bien des identifiants — déplacement partiellement
légitime. Le rang du document attendu dans le classement sémantique ne bouge
pas : la sensibilité est une propriété de la RRF, non de l'encodeur.

Réserve : le lot est voisin par le vocabulaire mais disjoint par le contenu —
il teste la dilution, non l'ambiguïté entre deux documents qui répondent tous
les deux. Le document le plus adverse disponible (le règlement intérieur des
bibliothèques universitaires) a été écarté parce que son titre serait compté
comme source attendue par le harnais ; l'instruire supposerait de resserrer six
annotations, au prix de la comparabilité avec les rapports antérieurs.

Script : `eval/distractor_experiment.py` ; rapport :
`eval/reports/2026-07-26_corpus_scaling.md`.

---

## Performances d'inférence et latence

*Mesures effectuées sur le corpus de référence :*

| Backend LLM | Latence moyenne (`/ask`) | Taux de rejet contextuel (hors-corpus) |
| :--- | :--- | :--- |
| **Mistral API** (`mistral-small-latest`) | ~3,0 s / requête | **100 % (4/4)** des requêtes hors-corpus rejetées |
| **Ollama local** (`mistral` 7B, CPU) | > 120 s à `num_ctx=8192` / `k=5` (dépassement de délai intercepté) ; ~190 s modèle déjà chargé, avec repli `num_ctx=4096` / `k=3` | **100 % (4/4)** des requêtes hors-corpus rejetées |

Le rejet du backend local est mesuré sur les quatre requêtes hors-corpus de
`eval/questions.yaml` (q17 à q20), en configuration de repli `num_ctx=4096` /
`k=3`, le modèle étant déjà chargé en mémoire ; les quatre réponses
reproduisent le refus canonique, sans source, verdict établi par `is_refusal()`
sur comparaison normalisée. La latence propre à ces refus (31 à 135 s, moyenne
103 s) n'est pas comparable à celle d'une réponse complète — un refus ne génère
qu'une douzaine de tokens. Le chargement initial du modèle en mémoire, exclu de
ces mesures, a requis 306 s à lui seul : Ollama décharge le modèle après un
temps d'inactivité, et le premier appel suivant paie ce rechargement. Le repli documenté pour
l'inférence CPU est `num_ctx=4096`, `k ≤ 5` ; les dépassements de délai
remontent `LLMBackendError(timeout)`, traduite en HTTP `503`.

Rapport détaillé : `eval/reports/2026-07-23_end-to-end_k5.md`.

---

## Évaluation conversationnelle multi-tour

Le rapport `eval/reports/2026-07-23_conversation_k5.md` mesure un rappel de
**3/6** sur les tours annotés comme répondables. La cause principale est une
limite de la recherche : sur la requête relative à la césure, les cinq
fragments retournés proviennent tous du document « IUT — Services de la
scolarité », la page institutionnelle « La césure à AMU », qui porte la
réponse, restant absente du top-5 — le même mécanisme d'éviction que sur la
requête RSE. Deux facteurs s'y ajoutent : 11,7 % de l'index est constitué de
fragments de moins de 50 caractères (`FAQ`, `Césure`, `Bonus` — éléments de
navigation devenus unités indexées, contre une médiane de 786 caractères), qui
obtiennent des scores de similarité élevés sur les requêtes courtes et évincent
du contenu substantiel ; et un tour annoté `answerable` produit un refus
correct (le corpus ne contient aucune règle de césure propre à la filière
droit), refus qui vide la liste des sources et se comptabilise mécaniquement
comme un échec de recherche.

---

## Index des rapports datés

Tous les rapports sont générés par le harnais et versionnés dans
`eval/reports/`.

| Rapport | Objet |
| :--- | :--- |
| `2026-07-26_retrieval_all_k{2,3,5,8}.md` | Rappel des trois méthodes, courbe recall@k |
| `2026-07-26_recall_sensitivity_k.md` | Sensibilité au paramètre k |
| `2026-07-26_embedder_comparison.md` | e5 / CamemBERT / FlauBERT |
| `2026-07-26_contextual_retrieval.md`, `…_440.md` | Index contextuel, aux deux budgets de découpage |
| `2026-07-26_corpus_scaling.md` | Lot de distracteurs, 18 → 28 documents |
| `2026-07-26_query_rewrite.md` | Réécriture de requête |
| `2026-07-23_end-to-end_k5.md` | Latences `/ask` et refus hors-corpus |
| `2026-07-23_conversation_k5.md` | Évaluation conversationnelle multi-tour |

Les rapports les plus anciens portent sur le jeu de 16 à 20 questions antérieur
à la référence courante ; leurs noms de fichiers gardent leur date, qui les
ordonne.
