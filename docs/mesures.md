# Mesures et évaluation — AssistantAMU

Cette page réunit les résultats détaillés et leur commentaire. Le `README.md`
principal n'en conserve qu'une synthèse chiffrée.

Le harnais d'évaluation mesure le taux de rappel (**recall@k**, indicateur
équivalent au *context recall* du framework RAGAS) selon trois stratégies de
recherche : sémantique, lexicale (BM25) et hybride (RRF). Un rapport Markdown
daté est automatiquement généré dans `eval/reports/`, incluant une section
« désaccords » recensant les questions pour lesquelles une seule méthode
identifie le fragment attendu.

**Une convention gouverne l'ensemble de ces mesures : mesurer n'est pas
brancher** (§40 du PRD). La fusion RRF, la réécriture de requête, le *Contextual
Retrieval* et le lot de distracteurs sont mesurés, documentés et **non intégrés**
au pipeline `/ask`, qui demeure purement sémantique en V1.

---

## Résultats de référence (2026-07-26)

*Corpus de test : 18 documents, 316 fragments, 50 questions d'évaluation
(portées de 16 à 50 le 2026-07-26), k=5.*

* **Rappel sémantique @5 :** 0,86
* **Rappel BM25 @5 :** 0,84
* **Rappel RRF @5 :** 0,86

La baseline du 23 juillet (0,94 / 0,81 / 0,88 sur 16 questions) est supplantée
par celle-ci, mesurée sur un jeu 3 fois plus grand : elle en reste l'historique,
pas la référence. Le repli du rappel sémantique (0,94 → 0,86) n'est pas une
régression du système — c'est le corpus d'évaluation qui couvre désormais des
documents et des tournures qu'il ne testait pas encore (règlement intérieur,
droits d'inscription, sigles, procédures propres à une composante…).

### Courbe recall@k (k ∈ {2, 3, 5, 8}) — un résultat nouveau à k = 8

| Méthode | k=2 | k=3 | k=5 | k=8 |
|---|---|---|---|---|
| semantic | 0,80 | 0,82 | 0,86 | 0,86 |
| bm25 | 0,70 | 0,78 | 0,84 | 0,88 |
| rrf | 0,74 | 0,82 | 0,86 | **0,92** |

À k = 8, **la fusion RRF dépasse le sémantique pur de 3 questions sur 50**
(0,92 contre 0,86) — un écart supérieur à la granularité du jeu (1/50 = 0,02),
donc significatif. Sur l'ancien jeu de 16 questions, RRF plafonnait à égalité
avec le sémantique (0,88 chacun) : l'écart existait peut-être déjà, mais un jeu
trop petit ne pouvait pas le voir. `/ask` reste sémantique pur en V1 (k par
défaut = 5, où RRF et sémantique sont encore à égalité) ; ce résultat renforce,
sans la trancher, la piste d'une bascule vers RRF documentée en §5.3 si k venait
à être relevé en production. **Cet argument est à lire avec son contrepoids**,
mesuré depuis (voir « Sensibilité à la taille du corpus ») : la RRF est aussi la
seule méthode qu'un corpus élargi dégrade, et pour une raison structurelle —
elle fusionne un classement profond, où les documents ajoutés sont presque
toujours présents.

### Désaccords sémantique / BM25 (k=5), commentés

| id | question | trouvé par | mécanisme |
|---|---|---|---|
| `q02` | « Puis-je interrompre mes études pendant un an puis les reprendre ? » | sémantique | paraphrase pure — la requête ne contient aucun terme du corpus (« césure »), seul le sens y conduit. |
| `q31` | « Auprès de qui se signaler pour bénéficier d'un régime spécial à la faculté de droit ? » | BM25 | le sémantique se laisse détourner vers le document IUT, structurellement proche ; BM25 accroche « signaler » au bon fragment. |
| `q52` | « Quelles pièces justificatives faut-il fournir lors de l'inscription en ligne ? » | BM25 | terme composé et rare (« pièces justificatives ») : le sémantique renvoie vers un document sans rapport (Régimes spéciaux). |
| `q53` | « Comment se connecter à la plateforme d'inscription administrative en ligne ? » | sémantique | la question paraphrase l'intitulé du document sans le citer : le sémantique le retrouve, BM25 disperse le score sur des termes trop génériques. |

Neuf désaccords sémantique/BM25 existent en tout à k=5 (voir
`eval/reports/2026-07-26_retrieval_all_k5.md`) ; ces quatre illustrent le
mécanisme récurrent — la paraphrase favorise le sémantique, le terme rare ou
exact favorise BM25 — qui justifie de mesurer la fusion RRF plutôt que de
trancher a priori entre les deux.

---

## Analyse comparative des modèles d'embeddings

Mesures de rappel sémantique effectuées sur les mêmes 50 questions et les mêmes
fragments. Cette comparaison relève d'une démarche d'évaluation : le pipeline
`/ask` conserve le modèle d'embeddings de production.

| Modèle d'embeddings | @3 | @5 | @8 |
| :--- | :---: | :---: | :---: |
| `intfloat/multilingual-e5-small` (production, 384 dimensions) | **0,82** | **0,86** | 0,86 |
| `dangvantuan/sentence-camembert-base` (768 dimensions) | 0,66 | 0,76 | 0,86 |
| `hugorosen/flaubert_base_uncased-xnli-sts` (768 dimensions) | 0,68 | 0,76 | 0,86 |
| _BM25 (référence lexicale)_ | 0,78 | 0,84 | 0,88 |

**Ce résultat corrige une lecture antérieure.** Sur le jeu de 16 questions du
23 juillet, CamemBERT atteignait 1,00 à k = 8 contre 0,94 pour e5 — un seul
écart de question, à la limite de la granularité de mesure (1/16 ≈ 0,06), déjà
interprété avec prudence à l'époque. Sur 50 questions (granularité
1/50 = 0,02), l'écart s'inverse et se creuse : **e5 domine nettement à k = 3 et
k = 5** (+16 et +10 points), et les trois modèles se rejoignent seulement à
k = 8 (0,86 chacun) — CamemBERT n'y prend plus l'avantage, il rattrape son
retard. e5 reste donc le meilleur choix, pour une empreinte mémoire deux fois
moindre (384 contre 768 dimensions) et sans qu'aucune bascule ne soit justifiée.
FlauBERT se situe en retrait à k = 3/5, en particulier sur les sigles et les
définitions (échecs sur RSE, CVEC, LANSAD, FOAD). Le modèle *cased*
`Lajavaness/sentence-flaubert-base` ne s'initialise pas sous
`sentence-transformers` 5.6.1 (tokenizer Moses dépourvu de `basic_tokenizer`),
d'où le recours à la variante *uncased*.

Script d'évaluation : `eval/embedder_comparison.py` ; rapport :
`eval/reports/2026-07-26_embedder_comparison.md`.

---

## Contextual Retrieval — index contextuel comparé à la référence

Chaque fragment a été préfixé, avant l'embedding **et** l'indexation BM25, d'une
phrase générée par le LLM le situant dans son document (méthode Anthropic,
septembre 2024 ; §5.3.1 du PRD). L'index correspondant est constitué dans une
collection parallèle : le pipeline `/ask` n'est pas modifié. Mesures effectuées
sur les deux jeux de questions, le jeu « dur » réunissant les formulations
conversationnelles.

| Jeu de questions | Méthode | Référence | Index contextuel |
| :--- | :--- | :---: | :---: |
| **Dur** (25 questions, k=3) | sémantique | 0,48 | **0,80** |
| **Dur** (25 questions, k=5) | BM25 | **0,84** | 0,80 |
| **Facile** (50 questions, k=5) | sémantique | **0,86** | 0,82 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,94** |

À 500 tokens, la contextualisation **améliore** la recherche. Son meilleur gain
est de **8 questions** sur les formulations conversationnelles, en recherche
sémantique à k=3 — le mode d'échec qu'elle vise ; sa pire perte, **2 questions**
sur les formulations définitionnelles en sémantique à k=5, reste sous le seuil
de signification de 3 questions fixé avant la mesure.

**Ces deux chiffres sont des extrema tirés de configurations différentes, non un
solde.** Les opposer comme un bilan reviendrait à ignorer la dispersion : un jeu
gagnant huit questions dans une cellule et en perdant trois dans onze autres
donnerait le même couple. La mise en perspective est la suivante — sur les douze
cellules mesurées (2 jeux × 3 méthodes × 2 valeurs de k), la somme des écarts
vaut **+18 questions**, avec huit cellules gagnantes, trois perdantes et une
inchangée.

Le préfixe rapproche le vecteur du fragment du sujet de son *document*, ce qui
sert les requêtes vagues et dessert les requêtes précises quand elles s'appuient
sur la recherche sémantique seule. **La fusion RRF, elle, ne perd rien** sur le
jeu élargi : elle gagne sur les deux jeux (+2 questions sur le dur à k=3, **+4
questions sur le facile à k=5**), la composante BM25 compensant ce que le
sémantique cède.

Deux précautions déterminent la validité de ces chiffres :

1. **Comptage strict.** Le jeu « facile » exige la présence de mots-clés dans le
   fragment récupéré, or un contexte généré nomme presque toujours le sujet du
   fragment qu'il préfixe. Le texte d'origine est donc conservé et restauré
   après classement : le contexte sert à *trouver* le fragment, jamais à
   *prouver* la réussite. Le rapport chiffre l'artefact ainsi évité (jusqu'à
   trois questions de rappel sur le jeu élargi).
2. **Troncature contrôlée, avec un résultat plus nuancé qu'annoncé.** Le
   découpage vise 500 tokens contre une fenêtre d'encodeur de 512 : le préfixe
   faisait sortir 23 fragments (7 %) de cette fenêtre. L'expérience a été
   rejouée sur un corpus redécoupé à 440 tokens, où aucun fragment ne déborde.
   Le gain sémantique **résiste** au redécoupage (jeu dur k=3 : +4 questions,
   contre +8 à 500 tokens — même sens, ampleur moindre). Mais élargir le jeu
   facile à 50 questions a révélé un effet invisible jusqu'ici : **la réponse de
   BM25 à la contextualisation dépend du budget de découpage** — quasi neutre à
   500 tokens, elle se dégrade nettement à 440 sur le jeu dur (−4 questions à
   k=3, −3 à k=5). Ce n'est plus un simple artefact de troncature à écarter :
   c'est un comportement propre à BM25 qui reste à comprendre avant de
   généraliser la méthode.

Les chiffres publiés par Anthropic (−49 % d'échecs de recherche) portent sur des
corpus de plusieurs milliers de fragments ; 25 et 50 questions ne sauraient les
confirmer ni les infirmer. Ce qui est établi ici, c'est le sens de l'arbitrage
pour la recherche sémantique sur ce corpus, et un signal encourageant pour son
usage combiné à la RRF. Reste à trancher laquelle des populations de requêtes
`/ask` doit servir en priorité, à comprendre la sensibilité de BM25 au budget de
découpage, et si une contextualisation *sélective* — limitée aux fragments
réellement décontextualisés — ne prendrait pas le meilleur des deux mondes.

Rapports : `eval/reports/2026-07-26_contextual_retrieval.md` et `…_440.md`.

**Reprise hors ligne**, sans appel de modèle : `eval/repro_contextual_retrieval.py`
reconstruit les quatre collections depuis le cache de contextes et retrouve les
chiffres publiés à l'identique, avec un backend factice qui **lève** sur tout
appel — un défaut de cache échoue au lieu de coûter.

> **Portée de cette gratuité.** Elle suppose `corpus/contexts.jsonl`, qui n'est
> **pas versionné** : donnée dérivée, au même titre que `chroma_db/` (§5.3.1).
> Les collections d'origine ayant par ailleurs disparu, ce fichier est
> aujourd'hui le **seul** chemin de reproduction des deux rapports. Sur ce
> poste, la reprise ne coûte rien ; sur un clone neuf, elle suppose de
> régénérer le cache — environ 316 appels de modèle. C'est un arbitrage ouvert :
> versionner 143 Ko rendrait les rapports reproductibles par un tiers, au prix
> d'une exception à la règle « les données dérivées ne sont pas versionnées ».

---

## Sensibilité à la taille du corpus — 18 documents comparés à 28

Retrouver le bon document parmi dix-huit est intrinsèquement facile : une part
du rappel de référence pouvait venir de là plutôt que de la qualité de la
recherche. Un lot de dix pages distractrices
(`corpus/sources_distractors.yaml`) porte donc le corpus mesuré de 18 à
**28 documents indexés** (+62 fragments, 316 → 378), **à jeu de questions
inchangé** : c'est la botte de foin qui grossit, pas la mesure. Les deux index
sont reconstruits dans le même passage, même encodeur et même découpage ; la
collection de production n'est jamais ouverte en écriture. Aucun appel LLM.

| Jeu de questions | Méthode | 18 documents | 28 documents |
| :--- | :--- | :---: | :---: |
| **Facile** (50 questions, k=5) | sémantique | 0,86 | 0,86 |
| **Facile** (50 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Facile** (50 questions, k=5) | RRF | 0,86 | **0,88** |
| **Dur** (25 questions, k=5) | sémantique | 0,72 | 0,72 |
| **Dur** (25 questions, k=5) | BM25 | 0,84 | 0,84 |
| **Dur** (25 questions, k=5) | RRF | 0,88 | **0,80** |

**Le sémantique et BM25 ne perdent aucune question**, sur 75 questions et trois
valeurs de k. Les arbitrages du 26 juillet — e5 plutôt que CamemBERT, k = 5 —
résistent donc à un corpus élargi de moitié. Ce zéro n'a de valeur que vérifié :
une immobilité totale pourrait tout aussi bien signifier que le lot n'est jamais
monté assez haut pour gêner. Un diagnostic tranche, et il écarte cette lecture —
les distracteurs atteignent le top-8 sur **14 des 50 questions faciles** en
sémantique (12 des 25 questions dures en BM25) et le **rang 1** dans les quatre
configurations. Un tiers du top-8 peut donc être constitué de matière nouvelle
sans que le document attendu perde sa place.

**La RRF est la seule méthode à céder** : −2 questions sur le jeu dur à k = 3 et
k = 5, +1 sur le jeu facile — sous le seuil de 3 questions fixé avant la mesure,
donc non retenu, mais le sens compte. Les deux bascules ont été instruites :
pour `h01` (« Parle-moi des régimes spéciaux »), la page attendue passe du rang
4 au rang 6, chassée par un catalogue de services numériques sans rapport avec
le sujet — **vraie défaillance** ; pour `h20` (réinscription en ligne), du rang
3 au rang 7, chassée par une page de compte étudiant qui traite bien des
identifiants — **déplacement partiellement légitime**. Dans les deux cas, le
rang du document attendu **dans le classement sémantique ne bouge pas** : ce qui
change est la composition du top-8 qui alimente la fusion. La sensibilité
mesurée est donc une propriété de la RRF, non de l'encodeur — le risque « e5
dilue les sigles » (§9 du PRD) n'est ni confirmé ni infirmé par ce test.

Ce que la mesure ne couvre pas : le lot est voisin par le vocabulaire mais
**disjoint par le contenu**, ce qui teste la dilution et non l'ambiguïté entre
deux documents qui répondent tous les deux. Le document le plus adverse
disponible — le règlement intérieur des bibliothèques universitaires, un second
règlement intérieur face à six questions — a été écarté parce que son titre
serait compté comme source attendue par le harnais ; l'instruire suppose de
resserrer ces six annotations, au prix de la comparabilité avec les rapports du
23 juillet.

Script : `eval/distractor_experiment.py` ; rapport :
`eval/reports/2026-07-26_corpus_scaling.md`.

---

## Performances d'inférence et latence

*Mesures effectuées le 2026-07-23 sur le corpus de référence :*

| Backend LLM | Latence moyenne (`/ask`) | Taux de rejet contextuel (hors-corpus) |
| :--- | :--- | :--- |
| **Mistral API** (`mistral-small-latest`) | ~3,0 s / requête | **100 % (4/4)** des requêtes hors-corpus rejetées |
| **Ollama local** (`mistral` 7B, CPU) | > 120 s à `num_ctx=8192` / `k=5` (dépassement de délai intercepté) ; ~190 s à chaud avec repli `num_ctx=4096` / `k=3` | **100 % (4/4)** des requêtes hors-corpus rejetées *(mesure du 2026-07-26)* |

Le taux de rejet du backend local a été mesuré le 2026-07-26 sur les quatre
requêtes hors-corpus de `eval/questions.yaml` (q17 à q20), dans la configuration
de repli `num_ctx=4096` / `k=3`, modèle maintenu chaud. Les quatre réponses
reproduisent le refus canonique à l'identique, sans source associée ; le verdict
est établi par la fonction `is_refusal()` du projet, sur comparaison normalisée.
La latence propre à ces refus (31 à 135 s, moyenne 103 s) n'est pas comparable
aux valeurs de la colonne précédente : un refus ne génère qu'une douzaine de
tokens, contre plusieurs centaines pour une réponse complète. Le préchauffage du
modèle a requis 306 s, ce qui confirme le coût du chargement à froid documenté
pour ce backend.

*Note sur l'exécution locale :* l'inférence du modèle local en environnement CPU
présente des latences élevées. Ce comportement est conforme aux arbitrages du
PRD (*développement sur API, démonstration en local*) ainsi qu'au repli
documenté `num_ctx=4096`, `k ≤ 5`. Les dépassements de délai sont interceptés et
remontent une exception `LLMBackendError(timeout)`, traduite par un code HTTP
`503` (F5).

Rapport détaillé : `eval/reports/2026-07-23_end-to-end_k5.md`.

---

## Évaluation conversationnelle V2 (F12)

Le rapport `eval/reports/2026-07-23_conversation_k5.md` fait état d'un rappel de
**3/6** sur les tours de conversation annotés comme répondables. L'analyse
diagnostique (détaillée dans `JOURNAL.md`) attribue ce résultat à une
**limitation avérée de la recherche**, et non à un défaut d'annotation. Sur la
requête relative à la césure, les cinq fragments retournés proviennent tous du
document « IUT — Services de la scolarité », soit le traitement de la césure par
une composante unique, tandis que la page institutionnelle « La césure à AMU »,
qui porte la réponse attendue, est **absente du top-5** : il s'agit du même
mécanisme d'éviction de la page centrale que celui déjà observé sur la requête
RSE.

Un facteur aggravant a été quantifié : **11,7 % de l'index est constitué de
fragments de moins de 50 caractères** (`FAQ`, `Césure`, `Bonus`, etc. — éléments
de navigation devenus unités indexées), contre une médiane de 786 caractères. Un
fragment très court et quasi identique à une requête courte obtient un score de
similarité élevé, occupe une position du top-k et évince du contenu substantiel.
Un second biais, de nature différente, relève effectivement de l'annotation : un
tour annoté `answerable` **produit un refus correct** (le corpus ne contient
aucune règle de césure propre à la filière droit), or un refus vide la liste des
sources (F6) et se comptabilise donc mécaniquement comme un échec de recherche.

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
| `2026-07-23_conversation_k5.md` | Évaluation conversationnelle V2 |

Les rapports datés du 23 juillet portent sur le jeu de 16 à 20 questions
antérieur : ils constituent l'historique des mesures, non la référence courante.
