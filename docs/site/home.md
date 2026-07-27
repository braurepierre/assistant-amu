# AssistantAMU

AssistantAMU interroge les documents publics d'Aix-Marseille Université —
règlements de scolarité, guides étudiants, pages des composantes — et répond en
français à partir du seul corpus indexé. Chaque réponse cite les passages qui la
fondent, et le système refuse de répondre lorsque l'information demandée est
absente de la base documentaire.

Ce site réunit la documentation du projet. Le code, les rapports d'évaluation
bruts et les branches d'expérimentation sont dans le dépôt.

## Parcours de lecture

| Page | Ce qu'elle apporte |
| :--- | :--- |
| [Présentation](presentation.html) | Architecture, installation, exécution, contrats d'API, périmètre et limites. Point d'entrée pour installer et faire tourner le système. |
| [Démonstration](demonstration.html) | Parcours de bout en bout avec des requêtes prêtes à l'emploi, y compris les cas de refus et le multi-tour. |
| [Mesures et évaluation](mesures.html) | Tous les chiffres du projet : rappel par méthode de recherche, comparaison des encodeurs, contextualisation de l'index, latences, refus. Tables par question et limites de chaque étude. |
| [Référence d'API](api-noyau.html) | Signatures et docstrings des cinq ensembles du paquet, extraites du source par analyse statique. |
| [Page pédagogique](concepts-assistant-amu.html) | Le fonctionnement d'un système RAG brique par brique, avec des démonstrations manipulables et un glossaire relié aux fichiers du code. |
| [Organisation du code et chaînes de traitement](architecture-assistant-amu.html) | L'organisation du dépôt en cinq ensembles, la chaîne d'ingestion et la chaîne de réponse, en schémas à deux niveaux. |

## Convention de mesure

Une règle explique la forme de la page *Mesures* et mérite d'être connue avant
de la lire : **mesurer n'est pas brancher**. La fusion RRF, la réécriture de
requête et la contextualisation de l'index sont mesurées et documentées sans
être intégrées au pipeline de production, qui reste purement sémantique. Un
résultat favorable n'entraîne donc pas de bascule tant que ses limites ne sont
pas instruites.

## Emplacement des chiffres

Les chiffres publiés ici proviennent des rapports datés du harnais d'évaluation,
versionnés dans `eval/reports/`. Ils sont recopiés depuis la mesure, jamais
estimés. Ce qui distingue deux mesures est leur condition — le jeu de questions,
la profondeur de recherche, le corpus — et cette condition accompagne chaque
chiffre.
