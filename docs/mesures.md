# Mesures et évaluation — AssistantAMU

Cette page réunit les résultats détaillés et leur commentaire. Le `README.md`
principal n'en conserve qu'une synthèse chiffrée.

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur
équivalent au *context recall* du framework RAGAS) selon trois stratégies de
recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown
daté est généré dans `eval/reports/` à chaque exécution, incluant une section
« désaccords » recensant les questions pour lesquelles une seule méthode
identifie le fragment attendu.

Deux conventions valent pour toute la page. Les méthodes mesurées ici — fusion
RRF, réécriture de requête, *Contextual Retrieval* — ne sont pas intégrées au
pipeline `/ask`, qui reste purement sémantique. Un écart n'est retenu qu'à
partir de trois questions, seuil fixé avant les mesures (granularité du jeu de
50 questions : 1/50 = 0,02).

---

## Synthèse des résultats

Le détail, les tables par question et les limites de chaque étude suivent ce
résumé.

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

### 1. Corpus et chiffres de référence

*Corpus de test : 18 documents, 316 fragments, 50 questions d'évaluation, k=5.*

* **Rappel sémantique @5 :** 0,86
* **Rappel BM25 @5 :** 0,84
* **Rappel RRF @5 :** 0,86

### 2. Courbe recall@k

| Méthode | k=2 | k=3 | k=5 | k=8 |
|---|---|---|---|---|
| semantic | 0,80 | 0,82 | 0,86 | 0,86 |
| bm25 | 0,70 | 0,78 | 0,84 | 0,88 |
| rrf | 0,74 | 0,82 | 0,86 | **0,92** |

À k = 8, la fusion RRF dépasse le sémantique pur de 3 questions sur 50 (0,92
contre 0,86). `/ask` reste sémantique pur au k par défaut de 5, où les deux
méthodes sont à égalité ; ce résultat soutient une bascule vers la RRF si k
venait à être relevé, et se lit avec son contrepoids (voir « Sensibilité à la
taille du corpus ») : la RRF est aussi la seule méthode qu'un corpus élargi
dégrade, parce qu'elle fusionne un classement profond où les documents ajoutés
sont presque toujours présents.

### 3. Désaccords sémantique / BM25

| id | question | trouvé par | mécanisme |
|---|---|---|---|
| `q02` | « Puis-je interrompre mes études pendant un an puis les reprendre ? » | sémantique | paraphrase pure — la requête ne contient aucun terme du corpus (« césure »), seul le sens y conduit. |
| `q31` | « Auprès de qui se signaler pour bénéficier d'un régime spécial à la faculté de droit ? » | BM25 | le sémantique se laisse détourner vers le document IUT, structurellement proche ; BM25 accroche « signaler » au bon fragment. |
| `q52` | « Quelles pièces justificatives faut-il fournir lors de l'inscription en ligne ? » | BM25 | terme composé et rare (« pièces justificatives ») : le sémantique renvoie vers un document sans rapport (Régimes spéciaux). |
| `q53` | « Comment se connecter à la plateforme d'inscription administrative en ligne ? » | sémantique | la question paraphrase l'intitulé du document sans le citer : le sémantique le retrouve, BM25 disperse le score sur des termes trop génériques. |

Neuf désaccords sémantique/BM25 existent en tout à k=5 (voir
`eval/reports/2026-07-26_retrieval_all_k5.md`) ; ces quatre illustrent le
mécanisme récurrent — la paraphrase favorise le sémantique, le terme rare ou
exact favorise BM25 — qui motive la mesure de la fusion RRF.

---

## Analyse comparative des modèles d'embeddings

Rappel sémantique mesuré sur les mêmes 50 questions et les mêmes fragments. Le
pipeline `/ask` conserve le modèle d'embeddings de production.

| Modèle d'embeddings | @3 | @5 | @8 |
| :--- | :---: | :---: | :---: |
| `intfloat/multilingual-e5-small` (production, 384 dimensions) | **0,82** | **0,86** | 0,86 |
| `dangvantuan/sentence-camembert-base` (768 dimensions) | 0,66 | 0,76 | 0,86 |
| `hugorosen/flaubert_base_uncased-xnli-sts` (768 dimensions) | 0,68 | 0,76 | 0,86 |
| _BM25 (référence lexicale)_ | 0,78 | 0,84 | 0,88 |

e5 domine à k = 3 et k = 5 (+16 et +10 points sur CamemBERT) ; les trois
modèles se rejoignent à k = 8 (0,86 chacun). e5 reste le modèle retenu, pour
une empreinte mémoire deux fois moindre (384 contre 768 dimensions). FlauBERT
est en retrait à k = 3 et k = 5, en particulier sur les sigles et les
définitions (échecs sur RSE, CVEC, LANSAD, FOAD). Le modèle *cased*
`Lajavaness/sentence-flaubert-base` ne s'initialise pas sous
`sentence-transformers` 5.6.1 (tokenizer Moses dépourvu de `basic_tokenizer`),
d'où le recours à la variante *uncased*.

Script d'évaluation : `eval/embedder_comparison.py` ; rapport :
`eval/reports/2026-07-26_embedder_comparison.md`.

---

## Contextual Retrieval — index contextuel comparé à la référence

### 1. Protocole

Chaque fragment a été préfixé, avant l'embedding **et** l'indexation BM25, d'une
phrase générée par le LLM le situant dans son document (méthode Anthropic,
septembre 2024). L'index correspondant est constitué dans une collection
parallèle : le pipeline `/ask` n'est pas modifié. Mesures effectuées sur les
deux jeux de questions, le jeu « dur » réunissant les formulations
conversationnelles.

### 2. Résultats

| Jeu de questions | Méthode | Référence | Index contextuel |
| :--- | :--- | :---: | :---: |
| **Dur** (25 questions, k=3) | sémantique | 0,48 | **0,80** |
| **Dur** (25 questions, k=5) | BM25 | **0,84** | 0,80 |
| **Facile** (50 questions, k=5) | sémantique | **0,86** | 0,82 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,94** |

À 500 tokens de budget de découpage, la contextualisation améliore la
recherche. Son meilleur gain est de 8 questions, sur les formulations
conversationnelles en recherche sémantique à k=3 — le mode d'échec qu'elle
vise ; sa pire perte, 2 questions sur les formulations définitionnelles en
sémantique à k=5, reste sous le seuil de trois questions. Ces deux chiffres
sont des extrema tirés de configurations différentes ; sur les douze cellules
mesurées (2 jeux × 3 méthodes × 2 valeurs de k), la somme des écarts vaut
**+18 questions**, avec huit cellules gagnantes, trois perdantes et une
inchangée.

### 3. Mécanisme

Le préfixe rapproche le vecteur du fragment du sujet de son *document* : il
sert les requêtes vagues et dessert les requêtes précises quand elles s'appuient
sur la recherche sémantique seule. La fusion RRF gagne sur les deux jeux
(+2 questions sur le dur à k=3, +4 sur le facile à k=5), la composante BM25
compensant ce que le sémantique cède.

### 4. Méthode de comptage

Le jeu « facile » exige la présence de mots-clés dans le fragment récupéré, or
un contexte généré nomme presque toujours le sujet du fragment qu'il préfixe.
Le texte d'origine est donc conservé et restauré après classement : le contexte
sert à trouver le fragment, pas à valider la réussite. Le rapport chiffre
l'artefact ainsi évité (jusqu'à trois questions de rappel sur le jeu élargi).

### 5. Budget de découpage

Le préfixe faisait sortir 23 fragments (7 %) de la fenêtre d'encodeur de
512 tokens. Rejouée sur un corpus redécoupé à 440 tokens, sans débordement,
l'expérience conserve le gain sémantique : +4 questions sur le jeu dur à k=3,
contre +8 à 500 tokens. La réponse de BM25 à la contextualisation dépend en
revanche du budget de découpage — quasi neutre à 500 tokens, elle se dégrade à
440 sur le jeu dur (−4 questions à k=3, −3 à k=5). Ce comportement reste à
comprendre avant de généraliser la méthode.

### 6. Limites

Les chiffres publiés par Anthropic (−49 % d'échecs de recherche) portent sur des
corpus de plusieurs milliers de fragments ; 25 et 50 questions ne sauraient les
confirmer ni les infirmer. Restent à trancher : la population de requêtes que
`/ask` doit servir en priorité, la sensibilité de BM25 au budget de découpage,
et l'intérêt d'une contextualisation *sélective*, limitée aux fragments
réellement décontextualisés.

### 7. Reproduction

Rapports : `eval/reports/2026-07-26_contextual_retrieval.md` et `…_440.md`.

`eval/repro_contextual_retrieval.py` reconstruit les quatre collections depuis
le cache de contextes `corpus/contexts.jsonl` et retrouve les chiffres publiés,
sans appel de modèle : le backend factice lève sur tout appel, un défaut de
cache échoue au lieu de coûter. Ce cache est versionné, par exception à la
règle qui écarte les données dérivées : il est le seul chemin de reproduction
des deux rapports (143 Ko, contre environ 316 appels de modèle à repayer).

---

## Réécriture de requête — deux stratégies comparées

### 1. Protocole

Une question posée de façon conversationnelle (« Parle-moi des régimes
spéciaux ») recherche mal : l'ouverture occupe une part du vecteur sans porter de
sens. Deux stratégies ont été comparées à la requête brute, sur un jeu « dur » de
25 formulations impératives ou parlées, avec le jeu de 50 questions en contrôle
de non-régression.

* **`strip`** — retrait heuristique de l'ouverture conversationnelle.
  Déterministe, sans appel au modèle.
* **`llm`** — reformulation en requête factuelle par le backend. Un appel de
  modèle par requête, résultat non déterministe.

### 2. Résultats

| Stratégie | Jeu dur @3 | Jeu dur @5 | Jeu de 50 @3 | Jeu de 50 @5 |
| :--- | :---: | :---: | :---: | :---: |
| requête brute | 0,48 | 0,72 | 0,82 | 0,86 |
| `strip` | 0,72 | **0,88** | 0,82 | 0,86 |
| `llm` | **0,84** | **0,88** | 0,80 | 0,88 |

Sur les formulations conversationnelles, le retrait de l'ouverture fait passer
le rappel de 0,48 à 0,72 à k = 3, sans appel de modèle. « Parle-moi des régimes
spéciaux » ne remonte pas la page définitionnelle « Régime spécial d'études »,
qui apparaît au rang 4 dès que la requête est ramenée à « régimes spéciaux ».

La réécriture par le modèle va plus loin, mais elle paraphrase : elle gagne
3 questions de plus à k = 3 sur le jeu dur, et en perd une sur le jeu de 50 —
en reformulant « interrompre mes études pendant un an », elle efface le lien
lexical vers « césure ». `strip` ne touche jamais ces questions.

### 3. Arbitrage

À k = 5, les deux stratégies sont à égalité (0,88). L'arbitrage ne porte donc
pas sur le rappel mais sur le coût : `llm` demande un appel de modèle
supplémentaire et ne rend pas deux fois le même résultat. Aucune des deux n'est
branchée dans `/ask`.

### 4. Reproduction

Script : `eval/query_rewrite_experiment.py` ; rapport :
`eval/reports/2026-07-26_query_rewrite.md`.

---

## Sensibilité à la taille du corpus — 18 documents comparés à 28

### 1. Protocole

Retrouver le bon document parmi dix-huit est intrinsèquement facile : une part
du rappel de référence pouvait venir de là plutôt que de la qualité de la
recherche. Un lot de dix pages distractrices
(`corpus/sources_distractors.yaml`) porte donc le corpus mesuré de 18 à
**28 documents indexés** (+62 fragments, 316 → 378), à jeu de questions
inchangé. Les deux index sont reconstruits dans le même passage, même encodeur
et même découpage ; la collection de production n'est jamais ouverte en
écriture. Aucun appel LLM.

### 2. Résultats

| Jeu de questions | Méthode | 18 documents | 28 documents |
| :--- | :--- | :---: | :---: |
| **Facile** (50 questions, k=5) | sémantique | 0,86 | 0,86 |
| **Facile** (50 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,88** |
| **Dur** (25 questions, k=5) | sémantique | 0,72 | 0,72 |
| **Dur** (25 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Dur** (25 questions, k=5) | RRF | 0,88 | **0,80** |

Le sémantique et BM25 ne perdent aucune question, sur 75 questions et trois
valeurs de k : les arbitrages retenus — e5 plutôt que CamemBERT, k = 5 —
résistent à un corpus élargi de moitié. Les distracteurs pèsent réellement sur
les classements : ils atteignent le top-8 sur 14 des 50 questions faciles en
sémantique (12 des 25 questions dures en BM25) et le rang 1 dans les quatre
configurations. L'immobilité du rappel ne tient donc pas à un lot resté trop
bas dans les classements.

### 3. Diagnostic des deux régressions RRF

La RRF est la seule méthode à céder : −2 questions sur le jeu dur à k = 3 et
k = 5, +1 sur le jeu facile — sous le seuil de trois questions. Les deux
bascules ont été instruites : pour `h01` (« Parle-moi des régimes spéciaux »),
la page attendue passe du rang 4 au rang 6, chassée par un catalogue de
services numériques sans rapport avec le sujet — défaillance ; pour `h20`
(réinscription en ligne), du rang 3 au rang 7, chassée par une page de compte
étudiant qui traite bien des identifiants — déplacement partiellement légitime.
Dans les deux cas, le rang du document attendu dans le classement sémantique ne
bouge pas : ce qui change est la composition du top-8 qui alimente la fusion.
La sensibilité mesurée est une propriété de la RRF, non de l'encodeur.

### 4. Limites

Le lot est voisin par le vocabulaire mais disjoint par le contenu : il teste la
dilution, non l'ambiguïté entre deux documents qui répondent tous les deux. Le
document le plus adverse disponible — le règlement intérieur des bibliothèques
universitaires, un second règlement intérieur face à six questions — a été
écarté parce que son titre serait compté comme source attendue par le harnais ;
l'instruire supposerait de resserrer ces six annotations, au prix de la
comparabilité avec les rapports antérieurs.

### 5. Reproduction

Script : `eval/distractor_experiment.py` ; rapport :
`eval/reports/2026-07-26_corpus_scaling.md`.

---

## Performances d'inférence et latence

*Mesures effectuées sur le corpus de référence :*

| Backend LLM | Latence moyenne (`/ask`) | Taux de rejet contextuel (hors-corpus) |
| :--- | :--- | :--- |
| **Mistral API** (`mistral-small-latest`) | ~3,0 s / requête | **100 % (4/4)** des requêtes hors-corpus rejetées |
| **Ollama local** (`mistral` 7B, CPU) | > 120 s à `num_ctx=8192` / `k=5` (dépassement de délai intercepté) ; ~190 s à chaud avec repli `num_ctx=4096` / `k=3` | **100 % (4/4)** des requêtes hors-corpus rejetées |

Le taux de rejet du backend local est mesuré séparément, sur les quatre
requêtes hors-corpus de `eval/questions.yaml` (q17 à q20), dans la
configuration de repli `num_ctx=4096` / `k=3`, modèle maintenu chaud. Les
quatre réponses reproduisent le refus canonique à l'identique, sans source
associée ; le verdict est établi par la fonction `is_refusal()` du projet, sur
comparaison normalisée. La latence propre à ces refus (31 à 135 s, moyenne
103 s) n'est pas comparable aux valeurs de la colonne précédente : un refus ne
génère qu'une douzaine de tokens, contre plusieurs centaines pour une réponse
complète. Le préchauffage du modèle a requis 306 s.

L'inférence locale sur CPU présente des latences élevées ; le repli documenté
est `num_ctx=4096`, `k ≤ 5`. Les dépassements de délai sont interceptés et
remontent une exception `LLMBackendError(timeout)`, traduite par un code HTTP
`503`.

Rapport détaillé : `eval/reports/2026-07-23_end-to-end_k5.md`.

---

## Évaluation conversationnelle multi-tour

Le rapport `eval/reports/2026-07-23_conversation_k5.md` mesure un rappel de
**3/6** sur les tours de conversation annotés comme répondables. La cause
principale est une limite de la recherche : sur la requête relative à la
césure, les cinq fragments retournés proviennent tous du document « IUT —
Services de la scolarité », tandis que la page institutionnelle « La césure à
AMU », qui porte la réponse attendue, est absente du top-5 — le même mécanisme
d'éviction de la page centrale que celui observé sur la requête RSE.

Deux facteurs s'y ajoutent. **11,7 % de l'index est constitué de fragments de
moins de 50 caractères** (`FAQ`, `Césure`, `Bonus` — éléments de navigation
devenus unités indexées), contre une médiane de 786 caractères : un fragment
très court et quasi identique à une requête courte obtient un score de
similarité élevé, occupe une position du top-k et évince du contenu
substantiel. Enfin, un tour annoté `answerable` produit un refus correct (le
corpus ne contient aucune règle de césure propre à la filière droit) ; le refus
vide la liste des sources et se comptabilise mécaniquement comme un échec de
recherche.

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
