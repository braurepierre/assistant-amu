# AssistantAMU — branche `langchain-port`

> Cette branche ne porte qu'un travail comparatif. Pour le projet lui-même —
> architecture, installation, mesures de recherche, périmètre et limites — se
> reporter au `README.md` de la branche `main`, qui fait référence. Ce document
> ne décrit que ce qui est propre à la branche.

Le pipeline de requête mono-tour est réimplémenté avec **LangChain (LCEL)** dans
`src/assistant_amu/langchain_port/pipeline.py`. Cette réimplémentation réutilise
la **même collection ChromaDB** et le **même prompt système** que la version
écrite à la main : les réponses des deux implémentations sont donc directement
comparables.

Installation : `uv pip install -e ".[dev,langchain]"`.

## 1. Équivalence des deux implémentations

`eval/compare_pipelines.py` rejoue le même jeu de questions dans les deux
implémentations, au sein d'un même processus, à collection ChromaDB, prompt
système et backend identiques. La comparaison isole donc le **câblage**, et non
le modèle.

| Indicateur | Résultat |
| :--- | :--- |
| Parité des refus | **19/20** |
| Parité des citations `[S…]` | 15/20 |
| Recouvrement lexical moyen | 0,75 |

*20 questions, `mistral-small-latest` des deux côtés, k = 5.*

Un recouvrement inférieur à 1 est attendu : même contexte et même prompt, mais
deux formulations d'un modèle non déterministe. L'équivalence se lit sur la
parité des refus et des citations, non sur l'égalité mot à mot. L'unique
divergence de refus relève de la génération, non de l'agencement du pipeline.

Rapport détaillé, question par question :
`eval/reports/2026-07-23_pipeline_vs_langchain.md`.

## 2. Ce que LangChain abstrait

- **L'orchestration.** `{"context": retriever | format_docs, "question": passthrough}
  | prompt | llm | StrOutputParser()` remplace l'assemblage explicite du message
  et l'appel au backend. Le gain est réel, mais le flux de données devient
  implicite.
- **Le vectorstore et le retriever.** `Chroma(...).as_retriever(k=...)` masque la
  requête ChromaDB, la conversion distance → similarité et la sélection top-k.
- **Le modèle de chat.** `ChatOllama` et `ChatMistralAI` unifient les deux
  backends, à l'équivalent de l'abstraction `LLMBackend` du projet, mais avec une
  surface d'API et un graphe de dépendances sensiblement plus larges.

## 3. Ce que LangChain n'abstrait pas

- **Les préfixes E5.** `HuggingFaceEmbeddings` n'ajoute pas `query:` ni
  `passage:` par défaut. Une classe `Embeddings` propre au projet
  (`E5Embeddings`) reste nécessaire pour réutiliser correctement la collection
  existante.
- **La logique produit.** Fiabilisation des citations `[S1]`, détection de refus
  et mise à zéro des sources associées, traduction d'une erreur de backend en
  `503`, champ `condensed_question`. La chaîne LCEL renvoie une chaîne de
  caractères ; tout le contrat de `/ask` (`api/schemas.py`) reste à la charge du
  projet.

## 4. Bilan

LangChain fait gagner quelques lignes d'orchestration, au prix d'une dépendance
volumineuse et d'un contrôle moindre sur les points sensibles du pipeline —
préfixes d'encodeur, métrique cosinus, fenêtre de contexte Ollama — que
l'implémentation manuelle garde explicites.
