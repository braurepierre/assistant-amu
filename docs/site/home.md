# AssistantAMU

AssistantAMU interroge les documents publics d'Aix-Marseille Université —
règlements de scolarité, guides étudiants, pages des composantes — et répond en
français à partir du seul corpus indexé. Chaque réponse cite les passages qui la
fondent, et le système refuse de répondre lorsque l'information demandée est
absente de la base documentaire.

Ce site réunit la documentation du projet. Le code, les rapports d'évaluation
bruts et les branches d'expérimentation sont dans le dépôt.

## Parcours de lecture

Le sommaire range les pages par usage : **Prise en main** pour installer et
faire tourner le système, **Comprendre** pour son fonctionnement et ses
résultats, **Référence d'API** pour les signatures. Le tableau suit cet ordre,
qui est aussi celui de la navigation précédent/suivant.

| Page | Objet |
| :--- | :--- |
| [Présentation](presentation.html) | Architecture, installation, exécution, contrats d'API, périmètre et limites. Point d'entrée pour installer et faire tourner le système. |
| [Démonstration](demonstration.html) | Parcours de bout en bout avec des requêtes prêtes à l'emploi, y compris les cas de refus et le multi-tour. |
| [Page pédagogique](concepts-assistant-amu.html) | Le fonctionnement d'un système RAG brique par brique, avec des démonstrations manipulables et un glossaire relié aux fichiers du code. |
| [Organisation du code et chaînes de traitement](architecture-assistant-amu.html) | L'organisation du dépôt en cinq ensembles, la chaîne d'ingestion et la chaîne de réponse, en schémas à deux niveaux. |
| [Mesures et évaluation](mesures.html) | Tous les chiffres du projet : rappel par méthode de recherche, comparaison des encodeurs, contextualisation de l'index, latences, refus. Tables par question et limites de chaque étude. |
| [Référence d'API](api-noyau.html) | Signatures et docstrings des cinq ensembles du paquet, extraites du source par analyse statique. |

## Origine des chiffres

Les chiffres publiés proviennent des rapports datés du harnais d'évaluation,
versionnés dans `eval/reports/`. Chaque chiffre est accompagné de sa condition
de mesure — jeu de questions, profondeur de recherche, corpus.
