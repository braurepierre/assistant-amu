# Accord inter-juges — comparaison AnythingLLM — 2026-07-27

Dernière faiblesse méthodologique des deux séries de verdicts : chaque question
n'avait été jugée **qu'une fois**. Un verdict erroné n'avait rien pour le
rattraper. Trois passes couvrent désormais les mêmes seize questions.

## Méthode — pourquoi pas trois fois le même prompt

Rejouer trois fois des instructions identiques mesurerait le déterminisme du
modèle, pas la solidité du jugement. Chaque passe change donc une condition, à
matériel constant :

| Passe | Ce qui change | Ce que ça teste |
| :--- | :--- | :--- |
| **base** | la série à l'aveugle du 27/07 | référence |
| **swap** | les étiquettes A et B sont échangées | **biais de position** — le verdict tient-il si la même réponse change de place ? |
| **shift** | la liste de questions est décalée avant l'appariement | l'appariement est un contexte partagé : deux verdicts censés être indépendants ne doivent pas le devenir parce qu'ils viennent du même juge |

Vingt-quatre juges au total (huit par passe, deux questions chacun), chacun avec
son propre dossier, dans un répertoire distinct des clés. Aucun appel de modèle
aux systèmes comparés : les réponses et les passages sont ceux déjà versionnés.

## Résultats

**Accord sur 29 des 32 couples (question, système), soit 91 %.**

| | unanimes | catégories distinctes |
| :--- | :---: | :---: |
| assistant-amu | **16/16** | 2 |
| AnythingLLM | **13/16** | 4 |

**Le biais de position est nul, ou presque.** Entre la passe de référence et la
passe où A et B sont échangés, **31 verdicts sur 32 sont identiques**. Le seul
qui bouge (q05, AnythingLLM) passe de « non ancrée » à « partiellement ancrée » —
deux catégories voisines.

**Les trois désaccords sont tous d'un cran, et tous du même côté.**

| | votes | majorité |
| :--- | :--- | :--- |
| q05 AnythingLLM | non ancrée · partiellement · partiellement | partiellement ancrée |
| q09 AnythingLLM | non ancrée · non ancrée · incorrecte | non ancrée |
| q12 AnythingLLM | partiellement · partiellement · correcte | partiellement ancrée |

Aucun ne franchit plus d'une catégorie, et aucun ne concerne assistant-amu.

## Ce que ça change aux chiffres publiés

| Verdict (AnythingLLM) | passe unique (27/07) | **majorité des 3 passes** |
| :--- | :---: | :---: |
| `correct_grounded` | 0/16 | **0/16** |
| `partially_grounded` | 4/16 | **5/16** |
| non ancrée mais plausible | 9/16 | **8/16** |
| `incorrect` | 2/16 | **2/16** |
| `refused` | 1/16 | **1/16** |

Côté assistant-amu, **14 correctes et ancrées, 2 refus** — inchangé.

Le seul mouvement est q05, qui glisse d'une catégorie à sa voisine. Or les deux
sont **agrégées sur la même ligne** du tableau de synthèse du rapport
(« plausible mais non ancrée, ou partiellement ancrée » : 13/16 dans les deux
cas). **Aucun chiffre publié ne bouge.**

## Ce que ce résultat vaut, et ce qu'il ne vaut pas

**Le 16/16 d'assistant-amu est un accord bon marché.** Quatorze de ses seize
verdicts tombent dans la même catégorie : s'entendre sur une distribution quasi
constante ne demande pas grand-chose. Le chiffre qui porte de l'information est
le **13/16 d'AnythingLLM**, dont les verdicts se répartissent sur quatre
catégories — c'est là que les juges avaient une vraie occasion de diverger, et
ils l'ont fait trois fois, jamais de plus d'un cran.

**Ce n'est pas un accord entre juges différents.** Les trois passes emploient le
même modèle et le même barème ; ce qui est mesuré est la stabilité d'un verdict
quand la présentation change, pas la convergence de points de vue indépendants.
Un juge humain, ou un modèle d'une autre famille, reste à faire — et c'est la
seule manière de savoir si le barème lui-même n'oriente pas les verdicts.

**Ce que ça referme.** Les deux séries reposaient sur une notation unique.
Elles reposent maintenant sur trois notations concordantes à 91 %, dont l'écart
résiduel ne déplace aucun chiffre publié. La stabilité des verdicts n'est plus
une hypothèse.
