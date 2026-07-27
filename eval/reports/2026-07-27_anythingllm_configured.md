# AnythingLLM une fois configuré — 2026-07-27

Le rapport du 26 juillet impute l'essentiel de l'écart entre les deux systèmes à
**deux réglages par défaut** d'AnythingLLM, et le dit explicitement : il mesure le
produit *out of the box*, non son plafond. Ce rapport corrige ces deux réglages et
repose les vingt questions. L'attribution n'est pas confirmée.

- **Expérience annexe**, hors périmètre du PRD, comme celle qu'elle prolonge.
- **Corpus, jeu de questions et backend identiques** au rapport du 26 juillet :
  19 sources, `eval/questions.yaml`, `mistral-small-latest` des deux côtés.
- **Instance** : AnythingLLM v1.15.0, workspace `corpus-amu`, mode de chat
  `query`, `topN = 4`, `similarityThreshold = 0,25`, embeddings natifs
  (`Xenova/all-MiniLM-L6-v2`), LanceDB — relevés par l'API au moment de la mesure.

## Ce qui a été changé

| | Changement | Origine |
|---|---|---|
| 1 | `queryRefusalResponse` passé de `null` à une phrase de refus | réglage par défaut du produit |
| 2 | Cinq pages du gabarit Drupal central réimportées en HTML brut | défaut du scraper du produit |
| 3 | Retrait de 24 documents : 10 coquilles vides et **14 doublons** | **défaut du harnais de ce dépôt** |

Le troisième changement n'était pas prévu et doit être nommé partout où une
différence avant/après est interprétée. Le workspace contenait chacune des
19 sources **en double** : un `topN = 4` ne rendait donc que **deux textes
distincts** et leurs copies. Vérifié sur les vingt questions — 2 textes distincts
avant, 4 après. Ce défaut vient de `anythingllm_compare.py ingest`, qui ajoute au
lieu de réconcilier et a été exécuté deux fois. Il ne relève pas du produit, et il
affectait **toute** la mesure du 26 juillet, y compris le 0/16 publié.

Effet du changement 2 sur l'extraction, relevé par l'API (`wordCount`) :

| Page | Défaut (scraper) | HTML brut réimporté |
|---|---|---|
| La césure à AMU | 1 | 18 028 |
| Régime spécial d'études (RSE) | 1 | 13 398 |
| Droits d'inscription et aides financières | 1 | 13 078 |
| Se loger — vie des campus | 1 | 14 315 |
| Mission handicap | 1 | 13 525 |

Ces décomptes incluent le balisage : le parseur de fichiers d'AnythingLLM ne
retire pas les balises HTML (voir « Ce que la réimportation a produit »).

## Protocole de jugement

Les **16 questions répondables** sont jugées sur le seul critère de l'ancrage, par
**8 juges indépendants** recevant deux questions chacun — le dispositif du
26 juillet et du rejugement du 27. Chaque juge reçoit la réponse *avant* et la
réponse *après* présentées comme systèmes **A et B**, attribuées par tirage à
graine fixe : le run configuré occupe la position A sur 11 des 16 questions. Un
juge informé qu'un côté suit un correctif a toute raison de le trouver meilleur.

Le bloc `<document_metadata>` est retiré des extraits : il porte la date
d'ingestion, qui ordonne les deux runs.

Les **4 questions hors-corpus** ne se jugent pas à l'ancrage mais au refus, mesuré
mécaniquement (`eval/configured_tally.py`) selon deux critères :

- **refus net** — la réponse est la phrase de refus configurée, et rien d'autre ;
- **refus sur le fond** — la réponse déclare que les documents ne portent pas
  l'information, puis répond tout de même par connaissances générales.

## Résultat 1 — le réglage du refus ne change rien

| id | question | défaut | configuré |
|---|---|---|---|
| q17 | Quelle est la capitale de l'Australie ? | aucun refus | aucun refus |
| q18 | Quel temps fera-t-il demain à Marseille ? | sur le fond | sur le fond |
| q19 | Combien coûte un abonnement à un service de streaming vidéo ? | sur le fond | sur le fond |
| q20 | Peux-tu me donner une recette de ratatouille ? | aucun refus | aucun refus |

**Refus nets : 0/4 avant, 0/4 après.** Aucune des quatre réponses ne bouge de
catégorie. q17 répond toujours « La capitale de l'Australie est **Canberra** » et
q20 livre toujours la recette complète.

Le mécanisme explique l'absence d'effet. En mode `query`, la phrase de
`queryRefusalResponse` n'est rendue que lorsque la recherche ne remonte **aucun**
passage ; or elle en remonte quatre sur chacune de ces questions, pertinents ou
non — `similarityThreshold` vaut 0,25 et ne les écarte pas. Le réglage ne
gouverne donc pas le cas qu'on lui prêtait : il couvre le workspace vide, non la
question hors sujet.

Ce constat corrige le rapport du 26 juillet, qui écrivait « son paramètre
`queryRefusalResponse` est resté à `null` par défaut : à l'absence de source
pertinente, le modèle retombe sur ses connaissances générales au lieu de
refuser ». La première moitié de la phrase est exacte, la seconde suppose une
causalité que la mesure dément.

## Résultat 2 — l'ancrage se déplace sans progresser

| id | défaut | configuré | |
|---|---|---|---|
| q01 | refusé | non ancré | change de nature |
| q02 | non ancré | non ancré | = |
| q03 | partiellement ancré | partiellement ancré | = |
| q04 | non ancré | non ancré | = |
| q05 | partiellement ancré | partiellement ancré | = |
| q06 | incorrect | incorrect | = |
| q07 | non ancré | non ancré | = |
| q08 | non ancré | partiellement ancré | meilleur |
| q09 | non ancré | partiellement ancré | meilleur |
| q10 | correct et ancré | incorrect | moins bon |
| q11 | incorrect | incorrect | = |
| q12 | correct et ancré | partiellement ancré | moins bon |
| q13 | non ancré | non ancré | = |
| q14 | incorrect | partiellement ancré | meilleur |
| q15 | non ancré | incorrect | moins bon |
| q16 | partiellement ancré | partiellement ancré | = |

| Catégorie | défaut | configuré |
|---|---|---|
| correct et ancré | 2 | **0** |
| partiellement ancré | 3 | 7 |
| non ancré (plausible) | 7 | 5 |
| incorrect | 3 | 4 |
| refus | 1 | 0 |

Sept questions sur seize changent de catégorie : trois en mieux, trois en moins
bien, une change de nature — q01 cesse de refuser et produit une procédure de
césure entièrement inventée, alors que la page césure est désormais dans le
workspace. Les deux seules réponses pleinement ancrées du run par défaut ne
survivent pas au correctif.

La réponse moyenne passe de 1 166 à 3 658 caractères. Le produit configuré écrit
trois fois plus, sans qu'aucune réponse n'atteigne l'ancrage complet.

## Le témoin qui borne ces chiffres

Les seize réponses **du run par défaut** avaient déjà été jugées à l'aveugle le
27 juillet (`2026-07-27_blind_rejudge.md`). Le jury du présent rapport les a
rejugées sans le savoir, sur un matériel identique : **12 verdicts sur 16
coïncident**, les quatre divergences ne dépassant jamais une catégorie
(q05, q10, q11, q12).

C'est la mesure du bruit de la procédure de jugement elle-même, et elle borne
tout ce qui précède : **7 questions déplacées par le correctif, contre 4 déplacées
par le seul changement de jury.** L'écart entre les deux runs n'est donc pas
séparable du bruit question par question. Ce qui résiste à cette réserve, ce sont
les mouvements d'ensemble : la disparition des deux réponses pleinement ancrées,
et le report vers l'ancrage partiel (3 → 7).

## Ce que la réimportation en HTML brut a produit

Le parseur de fichiers d'AnythingLLM conserve le balisage. Les fragments récupérés
contiennent `<li>`, `<a class="cta--link" href=…>`, `<div class="col paragraph
paragraph--type--texte…">` — d'où des `wordCount` de 13 000 à 18 000 mots pour des
pages dont le contenu utile est bien moindre.

La conséquence se lit dans la recherche, et elle est inversée. Sur les 80 extraits
récupérés pour les vingt questions, 17 proviennent des cinq pages réparées, mais
leur répartition ne correspond pas à ce que le correctif visait :

| Questions | Extraits issus des 5 pages réparées |
|---|---|
| Les 6 questions que ces pages devaient réparer (q01-q05, q08) | **2 / 24** |
| Les 4 questions hors-corpus | **10 / 16** |
| Les 10 autres questions | 5 / 40 |

q01 ne récupère toujours pas la page césure, q02, q03 et q05 non plus. En
revanche, la question sur la capitale de l'Australie récupère la page césure et la
page des droits d'inscription. Le balisage produit des fragments qui ne
ressemblent à rien de particulier, et qui remontent donc là où rien ne
correspond.

## Ce que ce rapport ne mesure pas

- **Un seul des chemins de correction possibles.** Réimporter en HTML brut confie
  la page au parseur de fichiers du produit ; ce n'est pas la seule voie, et le
  résultat ci-dessus suggère qu'elle n'est pas la bonne. Ce que ferait le produit
  avec un scraper correctement configuré, ou avec ces pages fournies en texte,
  reste inconnu. Fournir l'extraction d'assistant-amu a été écarté : cela
  reviendrait à mesurer l'extracteur de l'un dans le pipeline de l'autre.
- **Trois changements simultanés, dont un qui nous appartient.** Le retrait des
  doublons double la profondeur de recherche effective. Aucune différence
  avant/après ne peut être imputée aux deux seuls réglages du produit.
- **Des juges d'une seule famille de modèles, un seul barème.** Comme pour les
  séries précédentes, ce qui est établi est la stabilité d'un verdict, non la
  convergence de points de vue indépendants.
- **Le rapport du 26 juillet reste un artefact daté.** Ses chiffres ne sont pas
  corrigés ici ; ils ont été mesurés à profondeur de recherche effectivement
  divisée par deux, ce que le présent rapport documente sans les rejouer.

## Conclusion

L'hypothèse centrale du rapport du 26 juillet — « l'essentiel de l'écart tient à
deux réglages par défaut » — **n'est pas confirmée** sur ce corpus et ce jeu de
questions.

- Le réglage du refus est sans effet mesurable : 0/4 refus nets avant comme après,
  et pas une réponse ne change de catégorie.
- Le défaut d'extraction était bien réel — cinq pages sur neuf réduites à un mot —
  mais le réparer par cette voie ne produit aucune réponse pleinement ancrée, et
  fait perdre les deux qui l'étaient.
- Le seul écart dont l'ampleur dépasse clairement le bruit de jugement est
  imputable au **défaut de doublons du harnais de ce dépôt**, pas au produit.

Ce que la comparaison du 26 juillet établissait de la fiabilité d'assistant-amu
n'est pas remis en cause : ses chiffres à lui n'entrent pas dans cette mesure.
Ce qui tombe, c'est l'explication en deux réglages — plus commode que vérifiée.

## Fichiers

- `eval/anythingllm_retest_configured.py` — réglage, réimportation, `ask --all`
- `eval/configured_bundle.py` — dossiers de jugement à l'aveugle avant/après
- `eval/configured_tally.py` — levée de l'aveugle, décomptes, critères de refus
- `eval/reports/anythingllm_configured_ingest.json` — journal d'ingestion
- `eval/reports/anythingllm_configured_answers.json` — les 20 réponses brutes
- `eval/reports/configured_rejudge/` — dossiers, clé, verdicts
