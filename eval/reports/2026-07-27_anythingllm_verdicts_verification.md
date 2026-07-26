# Vérification des verdicts — comparaison AnythingLLM — 2026-07-27

Contrôle de substance du rapport `2026-07-26_anythingllm_vs_assistant-amu.md`. La
relecture du 26 juillet portait sur la **méthode** — corpus identique, modèle tenu
constant, cadrage annoncé. Elle ne disait rien du **contenu des verdicts**.

**Méthode.** Chacune des vingt lignes du rapport a été confrontée aux réponses
réellement produites par les deux systèmes, telles que versionnées dans
`anythingllm_raw_answers.json` et `assistant_amu_full_answers.json`. Aucun appel
de modèle, aucune nouvelle mesure : la vérification porte sur des données déjà
présentes au dépôt. Les quatre questions hors-corpus (q17-q20) ont été incluses
bien qu'elles ne fassent pas partie des seize verdicts : elles portent l'autre
chiffre de tête du rapport.

**Résultat d'ensemble.** Dix-sept lignes sur vingt sont étayées par les réponses
brutes. **Trois cellules du tableau de synthèse sont fausses**, et les trois vont
dans le même sens : elles surévaluent l'écart au détriment d'AnythingLLM.

---

## Ce qui est confirmé, et solidement

**q06 — le SMIC.** AnythingLLM écrit mot pour mot : « exonérés d'impôt sur le
revenu dans la limite de **3 fois le SMIC annuel** (soit environ 47 000 € en
2024) ». La règle réelle porte sur le SMIC **mensuel**, et assistant-amu la cite
correctement avec sa source. Erreur factuelle avérée, d'un facteur douze, sur une
question où un étudiant pourrait agir sur le chiffre. Verdict `incorrect`
**confirmé**.

**q11 — la compensation.** AnythingLLM contredit sa source sur deux points :
compensation « au sein d'un même semestre » là où la règle est **annuelle à
l'intérieur des BCC jumeaux**, et « seules les UE sont compensables (pas les
ECUE) » là où les ECUE se compensent entre eux à l'intérieur d'une UE. S'y
ajoutent un exemple chiffré et un « bonus par BCC (ex : +0,5) » sans existence
dans le corpus. Verdict `incorrect` **confirmé**.

> **Ce point mérite d'être isolé.** Sur q11, AnythingLLM avait cité le **bon
> document** — `15_droit-compensation-des-notes-par-bloc-de-connaissances-licen.pdf`,
> un PDF que son ingestion a traité sans difficulté. La défaillance n'est donc
> imputable ni au `queryRefusalResponse` non configuré, ni à l'échec du scraper
> sur le gabarit Drupal. Les deux causes structurelles avancées par le rapport
> sont réelles, mais elles **ne couvrent pas tout** : il subsiste un mode d'échec
> où la bonne source est récupérée et la réponse la contredit. Le même mécanisme
> se retrouve, atténué, sur q12 et q14.

Sont également confirmés sans réserve : q02, q03, q04, q05, q08, q09, q10, q13,
q14, q16, ainsi que q17, q19 et q20 côté hors-corpus. Les deux refus à tort
d'assistant-amu (q02, q16) sont réels — la réponse est bien le refus canonique
avec zéro source, alors que la question était répondable.

---

## Trois cellules qui ne tiennent pas

### 1. q01 — un refus compté comme une réponse substantiellement fausse

Le rapport classe q01 parmi les **3/16 « substantiellement fausses »**. La réponse
brute d'AnythingLLM est :

> « D'après les documents fournis, il n'y a pas d'information spécifique sur la
> procédure pour demander une césure à l'université. […] Pour obtenir cette
> information, je vous recommande de consulter directement le site web de votre
> université ou de contacter le service des études. »

Aucune affirmation fausse n'y figure. Le système **décline et redirige**. Et sa
déclaration est même exacte au regard de son propre index : la page « La césure à
AMU » y a été ingérée à **un seul mot**, comme le documente le rapport lui-même.

Le classement est d'autant moins tenable que le même comportement, côté
assistant-amu, reçoit une autre étiquette : q02 et q16 sont des refus sur
questions répondables, et sont comptés `refused_incorrectly` (⚠️), non
`incorrect` (❌). Une même conduite, deux barèmes.

L'anomalie se voit mieux en regardant q08, qui a la même forme — « il n'y a pas
d'information spécifique sur le RSE » — **suivie d'une définition générique
fabriquée**. q08 est plus grave que q01, et reçoit pourtant l'étiquette la plus
douce (`hallucinated_plausible`). Le barème le plus sévère a été appliqué au cas
le plus bénin.

**Correction :** q01 relève de `refused_incorrectly`.

### 2. q18 — un refus compté comme un échec de refus

Le rapport annonce **0/4** de refus corrects hors-corpus. La réponse brute sur la
météo est :

> « Je ne peux pas fournir de prévisions météo précises, car les documents
> fournis ne contiennent pas d'informations météorologiques. »

Suit une redirection vers Météo France. Le système ne fabrique aucune prévision :
sur le fond, il refuse. Le rapport le qualifie de « pas un refus net ».

Le problème n'est pas ce jugement mais l'**instrument** : sur cette même ligne,
le 4/4 d'assistant-amu est établi par `is_refusal()`, une comparaison normalisée
à la chaîne de refus canonique, tandis que le 0/4 d'AnythingLLM est établi par
lecture. Deux mesures différentes dans une même case de tableau comparatif. q18
tombe exactement dans l'écart entre les deux.

La distinction se voit en comparant aux trois autres : q17 affirme « La capitale
de l'Australie est Canberra » sans la moindre réserve ; q19 reconnaît l'absence
d'information **puis publie un tableau de sept tarifs** ; q20 livre une recette
complète. Ces trois-là ne refusent pas. q18 refuse.

**Correction :** refus hors-corpus **1/4**, non 0/4.

### 3. q15 — une réponse partiellement ancrée classée en hallucination

q15 est classée `hallucinated_plausible`, soit sans ancrage. Or AnythingLLM cite
bien `01_charte-des-tudiants-et-stagiaires-d-amu.pdf`, et son contenu sur les
libertés individuelles et collectives, la neutralité et la laïcité correspond à
de la matière démontrablement présente au corpus — ce sont les passages mêmes que
sa recherche avait remontés sur q01. La réponse reste générique et sans citation
précise, mais elle n'est pas hors-sol. `partially_grounded` convient mieux.

Cette correction ne déplace aucun chiffre de tête : les deux catégories sont
agrégées sur la même ligne du tableau de synthèse.

---

## Deux verdicts exacts mais sous-évalués

- **q07 (duplicata).** Classé `hallucinated_plausible`. La réponse invente un
  **« timbre fiscal (environ 20-30 €) »** présenté comme généralement requis. Ce
  n'est pas une généralité plausible, c'est une condition administrative
  fabriquée, sur laquelle un usager agirait. La procédure réelle, que
  assistant-amu cite avec sa source, ne comporte aucun frais.
- **q12 (sigle BCC).** Classé `partially_grounded` au motif de « précisions non
  confirmées ». L'une de ces précisions — les BCC « contribuent à la validation
  des **semestres** » — reprend l'erreur semestre/année qui vaut à q11 son
  classement en `incorrect`. Elle ne dépasse pas la source, elle la contredit.

---

## Une incohérence dans les données du jury

Le champ `anythingllm_self_flagged_uncertain` vaut `false` pour q03 et q05, alors
que les deux réponses se terminent par « *(Source : Adapté des contextes
fournis…)* » — la formule même qui vaut `true` ailleurs. Le champ n'est pas
fiable ; les notes rédigées, elles, décrivent correctement ces deux réponses. Le
champ n'alimente aucun chiffre publié.

---

## Ce que ça change au tableau de synthèse

| | rapport du 26/07 | après vérification |
|---|---|---|
| Refus hors-corpus (AnythingLLM) | 0/4 | **1/4** |
| Répondables — correcte et ancrée (AnythingLLM) | 0/16 | 0/16 |
| Répondables — refus à tort (AnythingLLM) | 0/16 | **1/16** |
| Répondables — substantiellement fausse (AnythingLLM) | 3/16 | **2/16** |
| Colonne assistant-amu (4/4, 14/16, 2/16 refus à tort) | inchangée | inchangée |

**Le sens du résultat ne change pas.** 4/4 contre 1/4 sur les refus, 14/16 contre
0/16 sur l'ancrage : l'écart reste massif, et les deux causes structurelles
avancées restent établies. Ce qui change est la **précision** des chiffres, et un
point de méthode qui pèse plus que les chiffres eux-mêmes.

**Les trois erreurs vont dans le même sens.** Aucune ne joue en faveur
d'AnythingLLM. C'est précisément le biais que la relecture du 26 juillet avait
identifié en principe — les juges nommaient les deux systèmes dans leurs notes,
devant un écart annoncé de 14/16 à 0/16 — et qu'elle ne pouvait pas mesurer.
Il est maintenant mesuré : sur vingt lignes, trois glissements, tous du même côté.

---

## Ce que cette vérification ne couvre pas

- Elle établit que chaque verdict est **cohérent avec les réponses brutes**. Elle
  ne vérifie pas que les réponses d'assistant-amu jugées « correctes et ancrées »
  le sont au regard du **corpus** : cela supposerait de rouvrir les documents
  sources, question par question.
- Elle ne rejuge pas à l'aveugle de l'identité des systèmes. Elle constate le
  biais par ses effets, elle ne le supprime pas.
- Elle ne dit rien de la performance d'AnythingLLM correctement configuré, qui
  reste le principal angle mort du rapport.
