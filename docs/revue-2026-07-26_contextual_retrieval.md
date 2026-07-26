# Revue du lot « Contextual Retrieval » — 2026-07-26

> **Traitée le 2026-07-27.** Les dix-neuf constats ont été corrigés. Ce document
> garde son texte d'origine — c'est un état des lieux daté — et signale ici les
> deux points où le correctif appliqué s'écarte de celui qui était proposé :
>
> - **Constat 7 (plafond de 25 mots).** Les contextes ne sont **pas** tronqués.
>   Couper une phrase nominale en son milieu l'abîmerait, et modifierait
>   silencieusement des contextes déjà mesurés et publiés. Le dépassement est
>   compté, remonté par le rapport de lot et affiché par la commande : l'écart
>   entre l'instruction et ce que le modèle produit devient visible au lieu
>   d'être absorbé.
> - **Constat 1.** Déjà corrigé le 2026-07-27 au cours de l'allègement du README,
>   avant l'ouverture de ce lot.
>
> S'y ajoute un constat postérieur à la revue : `corpus/contexts.jsonl` est exclu
> de git — ce que la section « Ce qui tient » relève comme correct — alors que
> les « Réserves de méthode » établissent qu'il est désormais le seul chemin de
> reproduction des deux rapports. Les deux sont vrais ; ensemble, ils signifient
> qu'un tiers ne peut pas rejouer les mesures. L'arbitrage est documenté dans
> `docs/mesures.md` et laissé ouvert.

Revue de cohérence du lot poussé entre `ea2c747` et `86a34a5` (14 commits,
30 fichiers, +3 232 lignes). Aucun fichier du dépôt n'a été modifié au cours de
cette revue.

**Périmètre.** `ea2c747` (module d'ingestion, prompt, commande, tests) ·
`dd7c82b` (expérience et deux rapports) · `a264e78` (en-tête du cache) ·
`fb2d16d` (README, JOURNAL, page pédagogique, `facts.yaml`), puis les quatre
commits qui rejouent et republient les mêmes mesures sur les jeux de questions
élargis : `473d328`, `105033e`, `e6c6157`, `a862f48`, `86a34a5`. Le commit
`72a8cfc` (conteneurisation et intégration continue, §5.3.6), intercalé dans le
lot, n'a été examiné qu'en survol.

**Méthode.** Deux passes indépendantes, la seconde conduite sans connaissance des
conclusions de la première :

1. lecture du code, recoupement des chiffres entre rapports, README,
   `concepts.facts.yaml` et le bloc `STATS` de la page, exécution de la suite de
   tests ;
2. reproduction intégrale des deux rapports hors ligne : store ChromaDB
   reconstruit hors du dépôt à partir de `corpus/contexts.jsonl`, backend factice
   programmé pour échouer en l'absence de cache — donc aucun appel d'API —
   puis comparaison cellule par cellule.

Dix-neuf constats, classés ci-dessous par gravité. La première passe en a établi
huit, la seconde les huit mêmes plus dix, et un dernier est propre à la première.

---

## Ce qui tient

- **Les deux rapports se reproduisent à l'identique** : 24 cellules de recall,
  12 écarts strict/naïf, statistiques de fenêtre (`0/498/0` contre
  `23/7 %/537/229` ; `0/438` contre `0/475`), statistiques de contexte
  (`316/316` et `332/332`, 25,2 mots, maximum 44 et 45), phrases d'exemple
  médianes, listes complètes des questions gagnées et perdues, rangs de la
  question phare. Les chiffres publiés sont donc bien ceux que le code produit.
- **La clé de cache adressée par le contenu fonctionne comme annoncé** : les
  436 entrées de `corpus/contexts.jsonl` ont servi `316/316` puis `332/332`
  fragments sans un seul appel de modèle, ce qui confirme au passage que le
  découpage est reproductible aux deux budgets.
- **La validité de mesure est correctement câblée.** Dans `_build_methods`
  (`eval/contextual_retrieval_experiment.py:98-113`), la fusion RRF porte bien
  sur les classements *contextuels* et ne substitue que les objets rendus :
  l'ordre des lignes 110 et 112 est volontaire et juste. Le comptage strict est
  sain par construction, le texte d'origine étant un sous-ensemble du texte
  contextualisé.
- **Le diagnostic de fenêtre est fiable** : `default_token_counter`
  (`src/assistant_amu/ingestion/chunk.py:33-42`) emploie `tokenizer.encode()`,
  qui inclut les tokens spéciaux ; la comparaison à `max_seq_length = 512` est
  donc exacte et non optimiste de deux tokens.
- **Les dénominateurs sont cohérents** : `evaluate_retrieval` divise par le
  nombre de questions *répondables* (25 pour le jeu dur, 50 sur 60 pour le jeu
  facile) et `_delta` remultiplie par ce même nombre. Les écarts exprimés en
  questions sont exacts.
- **La propagation des chiffres est intègre** de bout en bout : rapports →
  `concepts.facts.yaml` → README → bloc `STATS` de la page. Les baselines du jeu
  dur (0,48 et 0,72) et du jeu facile (0,82 et 0,86) concordent également entre
  le rapport de contextualisation et celui de réécriture de requête.
- **Les annotations d'évaluation résolvent toutes** vers un unique titre indexé,
  aux exceptions M3C déclarées près (h04, h21) ; les 75 annotations sont
  satisfiables. Le double régime de `eval/hard_questions.yaml:16-22` est
  exactement vrai : `strip_query` modifie h01 à h14 et laisse h15 à h25
  identiques au caractère près.
- **`MAX_DOC_CHARS = 60_000` n'a tronqué aucun document** : le plus long compte
  40 144 caractères pour 9 587 tokens, ce qui rend exact le commentaire
  « ~10k tokens » de `contextualize.py:52`.
- **142 tests passent**, conformément à `concepts.facts.yaml`. Les règles 4 et 5
  du prompt (aucune formule d'auto-description, aucun guillemet d'encadrement)
  sont respectées sur 433 contextes sur 433.
- `corpus/contexts.jsonl` est exclu de git comme de l'image ; `prompts/CHANGELOG.md`
  documente les versions v1 et v2 ainsi que leur couplage à `PROMPT_VERSION`.

---

## Constats graves

Ces quatre constats portent sur des conclusions destinées à un lecteur tiers.

### 1. Le README affirme deux verdicts opposés à trente-quatre lignes d'écart

`README.md:197` — « À 500 tokens, la contextualisation **gagne nettement plus
qu'elle ne perd** ».
`README.md:231` — « la contextualisation systématique de l'index constitue **un
arbitrage défavorable** sur ce corpus ».

La seconde ligne date de `fb2d16d`, lorsque le verdict mesuré était encore un
échange équilibré. Les commits `105033e` et `86a34a5` ont retouché la section de
mesure sans revenir à la liste des perspectives V2+ — c'est-à-dire la section que
lira quiconque cherche la suite à donner.

**Correctif.** Réécrire la perspective n° 1 pour l'aligner sur le verdict mesuré :
la contextualisation systématique constitue un arbitrage favorable en recherche
sémantique et neutre à favorable en fusion RRF, la piste subsistante étant la
contextualisation sélective.

### 2. Le générateur affirme un dégât là où le chiffre n'en montre aucun

`eval/reports/2026-07-26_contextual_retrieval_440.md:130` publie : « **Ce qu'elle
casse** : les formulations définitionnelles — jeu « facile », `semantic` à k=5,
**+0.00 (+0 questions)**. Ces questions fonctionnaient déjà ; le préfixe déplace
le vecteur du fragment vers le sujet du *document* et l'éloigne de son contenu
propre. »

`eval/contextual_retrieval_experiment.py:479-482` code ce récit en dur sur `ew_*`,
le pire écart du jeu facile, quel qu'en soit le signe. À 440 tokens ce pire écart
vaut zéro : le rapport explique une perte inexistante. Il aggrave l'effet en
reléguant la perte réelle de cette configuration — BM25, jeu dur, −4 questions à
k=3 — à la puce suivante, présentée comme un écart secondaire.

Cette classe de défaut est précisément celle que `JOURNAL.md:553-558` déclare
corrigée : le verdict principal a été rendu conditionnel, ces deux puces ne l'ont
pas été. Le symétrique vaut pour « Ce qu'elle répare » si le meilleur écart du jeu
dur devenait négatif.

**Correctif.** Rendre les deux puces conditionnelles au signe de l'écart, et
sélectionner la perte à commenter sur l'ensemble des deux jeux plutôt que sur le
seul jeu facile.

### 3. Le verdict oppose un maximum à un minimum tirés de cellules non comparables

`eval/contextual_retrieval_experiment.py:432-462` : `best_gain = max(hb_q, eb_q)`
et `worst_loss = -min(hw_q, ew_q)` prennent l'extremum sur douze cellules
— deux jeux, trois méthodes, deux valeurs de k — puis les opposent comme un
solde. Concrètement :

- `eval/reports/2026-07-26_contextual_retrieval.md:124` : « gagne nettement plus
  qu'elle ne perd (8 questions contre 2) » oppose *jeu dur / semantic / k=3* à
  *jeu facile / semantic / k=5* — deux jeux et deux valeurs de k différents ;
- `…_440.md:128` : « **échange** des réussites contre d'autres (4 gagnées,
  4 perdues) » oppose *semantic / k=3*, qui gagne 4, à *bm25 / k=3*, qui en perd
  4 — deux moteurs distincts. Rien n'est échangé.

La règle ignore par ailleurs le **nombre** de cellules perdantes : un lot perdant
trois questions dans onze cellules et gagnant huit dans une seule serait encore
déclaré « gagne nettement plus qu'elle ne perd ». Le verdict actuel n'est pas faux
pour autant — la somme des écarts vaut +18 à 500 tokens et +8 à 440 — mais
`JOURNAL.md:557` revendique que « les conclusions se déduisent maintenant des
écarts, y compris leur rapport de grandeur », et la déduction ignore la
dispersion.

La portée est large : cette phrase est reprise telle quelle dans `README.md:197`
et `docs/concepts-assistant-amu.html:471`. Le README nomme, lui, les deux
populations et reste donc honnête ; le rapport présente le même couple comme un
solde unique.

**Correctif.** Nommer la configuration dont chaque chiffre est tiré, et adjoindre
au verdict une ligne de dispersion : somme des écarts, nombre de cellules
gagnantes et perdantes.

Un précédent existe désormais dans le dépôt, postérieur au périmètre de cette
revue : `eval/reports/2026-07-26_corpus_scaling.md:9` **fixe son seuil de
signification à trois questions avant de mesurer**, et le déclare (« Seuil, fixé
avant la mesure »). Le générateur de la contextualisation tranche, lui, à deux
questions et après coup. Aligner le second sur le premier réglerait le constat par
la même occasion.

### 4. Le chiffre mis en avant n'est traçable dans aucun document

« +8 questions » se lit à **k=3**, alors que les seules tables par question des
deux rapports sont produites à **k=5** — la valeur est codée en dur à
`eval/contextual_retrieval_experiment.py:201-202` — où le solde n'est que de +2.
Aucun document du dépôt ne permet donc de savoir *quelles* huit questions
composent le chiffre porté par le README et par la page.

**Correctif.** Produire les tables par question pour chaque valeur de `KS` plutôt
que pour la seule valeur 5.

---

## Constats moyens

### 5. Le garde-fou de troncature ne peut jamais se déclencher

`src/assistant_amu/ingestion/contextualize.py:51-53` annonce : « A local backend
at `num_ctx=8192` would silently drop the document tail instead — **hence the
warning**. » L'avertissement correspondant (`__main__.py:107-108`) est piloté par
`MAX_DOC_CHARS = 60_000`, soit environ 14 000 tokens ; le plus long document du
corpus fait 40 144 caractères pour 9 587 tokens. Le seuil ne sera donc jamais
franchi.

Or `README.md:107` propose la commande sans variable d'environnement, et le
défaut est `LLM_BACKEND=ollama` à `OLLAMA_NUM_CTX=8192` : le plus gros document
serait tronqué par Ollama sans un mot — exactement le piège que `README.md:40`
documente par ailleurs. Les chiffres publiés ne sont pas concernés, les 436
entrées du cache portant toutes `mistral/mistral-small-latest`.

**Correctif.** Fonder l'avertissement sur la fenêtre effective du backend plutôt
que sur une constante de caractères, ou à défaut mentionner `LLM_BACKEND=mistral`
dans la commande du README, comme le fait déjà l'en-tête de l'expérience.

### 6. L'aide de la commande annonce un réglage que rien ne lit

`src/assistant_amu/ingestion/__main__.py:33` : `help="chunk budget in tokens
(default: CHUNK_MAX_TOKENS from the settings)"`. Or aucun chemin de production
suivi par git ne lit `settings.chunk_max_tokens` : les seules occurrences sont sa
déclaration (`config.py:88`), sa lecture d'environnement (`config.py:131`) et un
test (`tests/test_config.py:43`). Le défaut réel est le littéral
`max_tokens: int = 500` de `chunk.py:47`. Poser `CHUNK_MAX_TOKENS=440` dans
`.env` n'aurait donc aucun effet, et le contrôle à 440 tokens ne tient qu'au
passage explicite de `--max-tokens`. Même situation pour `chunk_overlap`.

**Correctif.** Soit brancher `settings.chunk_max_tokens` comme défaut réel de
`_chunking`, soit corriger l'aide pour désigner le littéral.

### 7. Le plafond de vingt-cinq mots du prompt est violé par la moitié des contextes

`prompts/context_system.md:4` impose « UNE seule phrase nominale, **de 25 mots au
maximum** ». Mesure sur les 433 entrées en version 2 de `corpus/contexts.jsonl` :

```
moyenne = 25,61  ·  médiane = 25  ·  maximum = 45  ·  au-dessus de 25 : 206/433 (48 %)
```

Aucun code ne contrôle ni ne signale le plafond — `clean_context`
(`contextualize.py:172-178`) ne tronque rien — et la documentation l'a converti en
moyenne : « 25.2 mots en moyenne (maximum 44) » dans les rapports, « Une phrase de
25 mots en moyenne » à `docs/concepts-assistant-amu.html:462`. Le plafond censé
garantir que le préfixe entre dans le budget de tokens est ainsi devenu la
moyenne, ce qui est le mécanisme même des 23 fragments hors fenêtre que le lot
documente par ailleurs.

**Correctif.** Faire respecter le plafond dans `clean_context`, ou le porter dans
le prompt à une valeur tenable et recalculer la marge de découpage en
conséquence. Dans les deux cas, signaler les dépassements dans le rapport.

### 8. La moitié de la précaution centrale n'est pas testée

`RawTextRetriever` et `_build_methods(strict=…)`
(`eval/contextual_retrieval_experiment.py:78-113`) portent ce que le rapport
appelle « le résultat méthodologique de cette expérience ». La moitié ingestion
est testée trois fois — `text_raw` **écrit**, à `tests/test_contextualize.py:111`,
`:200` et `:211` — mais sa **restauration avant comptage** ne l'est pas. Une
régression y inverserait silencieusement le sens des chiffres publiés.

Aucun script de `eval/` n'est couvert par des tests, ce qui relève d'une
convention du projet plutôt que d'une lacune propre à ce lot ; c'est l'asymétrie
entre les deux moitiés d'une même précaution qui mérite d'être relevée.

**Correctif.** Extraire `_with_raw_text` et le comptage strict vers
`src/assistant_amu/evaluation.py`, où ils deviennent testables sans corpus.

### 9. Le cache perd son contenu entier sur un enregistrement amputé

`src/assistant_amu/ingestion/contextualize.py:135` : `self._entries[key] =
record["context"]` est placé **hors** du `try`, alors que le commentaire de la
ligne 134 promet qu'« a truncated last line must not lose the whole cache ». Une
ligne de JSON valide dépourvue de la clé `context` fait donc échouer tout le
chargement. Vérifié :

```
RAISED: KeyError 'context' -> the whole cache is lost
```

Le test `test_cache_survives_a_truncated_last_line`
(`tests/test_contextualize.py:164`) ne couvre que le JSON malformé, cas qui passe
bien par `JSONDecodeError`.

**Correctif.** Déplacer la lecture de `record["context"]` dans le `try` et
étendre le test à ce cas.

### 10. La reprise sur erreur est dupliquée et divergente

`contextualize.py:74-75` : `RETRY_DELAYS = (2.0, 5.0, 15.0)`, fonction `sleep`
injectable, trois tests.
`eval/query_rewrite_experiment.py:65-66` : `RETRY_DELAYS = (5.0, 15.0, 45.0)`,
`time.sleep` en dur, aucun test.

Le message de `a862f48` annonce « même logique que celle déjà en place dans
`ingestion/contextualize.py` ». La logique est bien la même, mais les délais sont
deux fois et demie plus longs et la seconde copie n'est pas testable sans horloge
réelle.

**Correctif.** Extraire la reprise dans un utilitaire partagé, avec `sleep`
injectable et un jeu de délais unique.

---

## Constats faibles

### 11. Accord en nombre non géré dans le générateur

`eval/contextual_retrieval_experiment.py:483-485` et `:498-500` codent
« question » au singulier. Les rapports publient donc « (+4 question) »
(`…_contextual_retrieval.md:127`), « (+3 question) » (`:129`) et
« (−4 question) » (`…_440.md:131`). Le défaut était invisible tant que les écarts
valaient une question ; `_delta` y échappe en abrégeant en « q ».

### 12. Deux documents du même commit se contredisent sur `--check`

`docs/build_concepts.py:23` annonce `--check    # exit 1 if the page is stale
(CI-friendly)`, alors que `docs/README.md:38`, écrit dans le même commit
`fb2d16d`, énonce l'inverse : « `--check` n'est pas exploitable tel quel en
intégration continue ».

### 13. La page retouche une sortie de modèle qu'elle présente comme réelle

`docs/concepts-assistant-amu.html:460` affiche « partie « Engagement de l'usager
signataire » », là où la sortie effective — cache et `prompts/CHANGELOG.md:85-87`
— est « partie « **II. ENGAGEMENT DE L'USAGER SIGNATAIRE** » ». Sur une page qui
présente l'exemple comme un avant/après authentique, la normalisation de casse
n'est pas neutre.

### 14. La progression reste muette sur un lot entièrement servi par le cache

`contextualize.py:279-280` : l'appel `progress(...)` est placé dans la branche de
génération, après les `continue` des fragments cachés et échoués. Un lot
entièrement caché n'imprime donc rien, et la ligne finale
(`index == len(chunks)`) ne se déclenche pas si le dernier fragment est caché.

### 15. En-tête périmé du jeu de questions principal

`eval/questions.yaml:3` : « First draft written from the real corpus
(2026-07-23), to refine together » décrit un jeu qui compte désormais 60 questions
dont 50 répondables, chacune vérifiée par programme. Contrairement à
`eval/hard_questions.yaml`, l'en-tête ne documente ni l'élargissement, ni la
méthode de vérification, ni l'exception q10, dont l'`expected_source` « M3C »
résout vers trois titres — la même exception que celle explicitée pour h04 et h21.

### 16. Qualification inexacte des annotations fragiles

`JOURNAL.md:591-592` : « dont 3 ne tiennent qu'à un seul fragment — acceptable
pour des questions de sigle ». Il s'agit de q06 (« job »), q08 (« régime
spécial ») et q28 (FOAD) : seule la dernière est une question de sigle. Le
marqueur de q08 est de surcroît celui que `eval/questions.yaml` documente comme
peu fiable pour q03.

### 17. L'entrée de journal corrigée ailleurs ne porte pas de renvoi

`JOURNAL.md:479` affirme encore sans réserve, à propos du contrôle à 440 tokens,
« **Les conclusions ne bougent pas** : l'arbitrage tient à la méthode, pas à la
marge » — ce que les jeux élargis ont démenti pour BM25. `JOURNAL.md:637` annonce
que « Rapport et README ont été corrigés » ; c'est exact, mais l'entrée d'origine
ne porte aucun renvoi vers celle qui la révise. La convention chronologique du
journal l'excuse en partie, le projet marquant toutefois ailleurs ses lectures
dépassées (`README.md:184`).

### 18. Coquille dans le changelog des prompts

`prompts/CHANGELOG.md:70` : « une itération **du prompte** invalide les contextes »
→ « du prompt ».

### 19. Coquille dans le journal

`JOURNAL.md:600` : « le jeu à 50 **measure** une tâche plus proche » → « mesure ».

---

## Annexe — une hypothèse pour la question laissée ouverte

`README.md:202` et la page pédagogique laissent ouverte la « sensibilité de BM25
au budget de découpage », qualifiée de comportement « qui reste à comprendre ».
Un mécanisme simple l'explique.

`src/assistant_amu/retrieval/bm25_store.py:31` construit `BM25Okapi` sur les
textes **contextualisés**, dont chacun commence par l'intitulé de son document.
Les termes du titre et des sections passent donc d'une fréquence documentaire de
quelques fragments à la quasi-totalité des fragments du document : leur IDF
s'effondre. La longueur moyenne `avgdl` augmente par ailleurs d'environ 25
tokens, ce qui pénalise la normalisation de longueur. Le préfixe rend ainsi les
termes de titre — précisément ceux qui distinguaient un document d'un autre en
recherche lexicale — presque sans pouvoir discriminant.

Cette hypothèse se vérifie sans nouvelle dépense d'API : il suffit de comparer
l'IDF des termes de titre entre les deux collections, ou de mesurer le recall
BM25 sur un index construit à partir de `metadata["text_raw"]`, qui isole l'effet
du préfixe sur la seule composante lexicale.

---

## Réserves de méthode

- **La construction de l'image Docker et l'appel `/health` en conteneur** n'ont
  pas été rejoués : Docker est absent de la machine. L'intégration continue en
  fait foi.
- **Les collections d'origine ont disparu.** `chroma_db/` ne contient plus que
  `amu_docs` ; `amu_docs_ctx`, `amu_docs_440` et `amu_docs_440_ctx` n'existent
  plus. Les quatre collections ont donc été reconstruites hors du dépôt depuis le
  cache de contextes. La reproduction exacte de l'ensemble des chiffres rend
  cette substitution sans conséquence, mais les rapports ne sont aujourd'hui
  reproductibles que par `corpus/contexts.jsonl`.
- **Le décompte de tokens d'entrée** (environ 1,73 M, à comparer au « environ
  1,7 M » de `JOURNAL.md:462`) emploie le tokenizer e5 du projet, non celui de
  `mistral-small-latest` : l'ordre de grandeur est confirmé, pas la valeur exacte.
- **Les sorties de la version 1 du prompt** ne sont pas contrôlables : trois
  entrées seulement subsistent en `prompt_version: 1` dans le cache.
- **La qualité des contextes générés** et la question laissée ouverte à
  `eval/hard_questions.yaml:43-44` relèvent du jugement humain.
