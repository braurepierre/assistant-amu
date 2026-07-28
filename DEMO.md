# AssistantAMU — Guide de démonstration

Exemples vérifiés sur le corpus réel (18 documents AMU, 316 fragments), backend
**Mistral**. Deux interfaces exposent les mêmes réponses au travers de la même API.

## Prérequis

Les trois premières étapes ne sont nécessaires qu'au premier lancement : l'index
vectoriel et le corpus téléchargé ne sont pas versionnés, ils se régénèrent
depuis `corpus/sources.yaml`.

```powershell
# Depuis la racine du dépôt
pip install -e ".[dev]"                                     # ou : uv pip install -e ".[dev]"
Copy-Item .env.example .env                                 # y renseigner MISTRAL_API_KEY
.venv\Scripts\python.exe -m assistant_amu.ingestion.download # téléchargement du corpus
.venv\Scripts\python.exe -m assistant_amu.ingestion index    # indexation (idempotent)
```

L'indexation télécharge le modèle d'embeddings au premier appel. Contrôle de
l'état une fois l'API lancée : `GET /health` doit renvoyer `documents: 18` et
`chunks: 316`.

## Lancement de l'API en local

```powershell
$env:LLM_BACKEND = "mistral"
.venv\Scripts\python.exe -m uvicorn assistant_amu.api.main:app --host 127.0.0.1 --port 8000
```

## Interfaces de démonstration

- **A. Interface conversationnelle (recommandée)** → **http://127.0.0.1:8000/**
  Interface aux couleurs AMU. Saisir la question dans le champ prévu : l'assistant
  répond en citant ses sources `[S1]`, et affiche en multi-tour la mention
  « ↳ compris comme : … » (condensation de la requête). Les questions des exemples ci-dessous
  se saisissent directement.
- **B. Panneau du site de documentation** → **http://127.0.0.1:8000/site/**
  Le bouton « Assistant » du bandeau ouvre un tiroir de conversation sur
  n'importe quelle page. Il faut avoir construit le site au préalable
  (`python docs/site/build_site.py`), et redémarrer l'API si le site n'existait
  pas encore à son démarrage. Le pied du panneau indique l'instance qui répond,
  ou l'absence d'instance.
- **C. API / Swagger** → **http://127.0.0.1:8000/docs**
  `POST /ask` → **Try it out** → coller l'un des corps JSON ci-dessous → **Execute**.

---

## 1. Questions simples (tour unique)

Paraphrase (la recherche sémantique retrouve la césure sans le mot exact) :

```json
{ "question": "Puis-je interrompre mes études un an puis les reprendre ?", "k": 5 }
```

Sigles et termes exacts :

```json
{ "question": "Qu'est-ce que le régime spécial d'études (RSE) ?", "k": 5 }
```

```json
{ "question": "Qu'est-ce que la CVEC ?", "k": 5 }
```

```json
{ "question": "Comment fonctionne la compensation des notes en licence ?", "k": 5 }
```

```json
{ "question": "Comment obtenir un duplicata de mon diplôme à l'IUT ?", "k": 5 }
```

> Réponse attendue : un texte **sourcé**, comportant des citations `[S1]`, `[S2]`…
> et la liste des extraits (titre, page, score). Le champ `condensed_question`
> vaut `null`.

---

## 2. Conversation multi-tour (condensation de requête)

> **Dans l'interface conversationnelle**, le multi-tour est **automatique** :
> saisir le tour 1 puis le tour 2 suffit — l'historique est géré par l'interface,
> et la mention « ↳ compris comme : … » s'affiche. Le champ `history` ci-dessous
> n'est utile que pour `/docs` ou un appel direct à l'API.

**Étape A — poser d'abord le tour 1 seul**, pour montrer `condensed_question: null` :

```json
{ "question": "Quelles sont les modalités de la césure ?", "k": 5 }
```

**Étape B — puis le tour 2 avec une question elliptique** (« Et à quelles dates… ? »)
accompagnée de l'historique :

```json
{
  "question": "Et à quelles dates faut-il déposer sa candidature ?",
  "k": 5,
  "history": [
    { "role": "user", "content": "Quelles sont les modalités de la césure ?" },
    { "role": "assistant", "content": "La césure permet de suspendre ses études un ou deux semestres pour réaliser un projet, avec maintien du statut étudiant." }
  ]
}
```

> Résultat : `condensed_question` se remplit — la question « Et à quelles dates… ? »
> est reformulée en *« À quelles dates faut-il déposer sa candidature pour une
> **césure** à Aix-Marseille Université ? »* — puis la réponse restitue les dates
> de dépôt, citées `[S1]`.
>
> Le contraste entre le tour 1 (`null`) et le tour 2 (condensé) montre la condensation.

---

## 3. Refus volontaire (garde-fou contre l'hallucination)

Question hors du corpus : le système refuse au lieu d'inventer.

```json
{ "question": "Quelle est la capitale de l'Australie ?", "k": 5 }
```

> Réponse attendue **exactement** :
> `Je ne trouve pas cette information dans les documents disponibles.`
> avec `"sources": []`.

---

## 4. Autres points d'entrée

- **`GET /health`** → état de ChromaDB, du backend LLM, nombre de documents et de fragments.
- **`POST /ingest`** (multipart) → ajoute un document (`file` + `title`) sans
  réindexer l'existant ; `409` si le document est déjà présent.

---

## Bascule sur le backend local Ollama

Lancer d'abord l'application **Ollama**, puis :

```powershell
$env:LLM_BACKEND = "ollama"; $env:OLLAMA_NUM_CTX = "4096"
.venv\Scripts\python.exe -m uvicorn assistant_amu.api.main:app --host 127.0.0.1 --port 8000
```

> Sur CPU, l'inférence Ollama est lente (de plusieurs dizaines de secondes à
> environ deux minutes par réponse) : conserver un `k` bas (par exemple `"k": 3`).
> Ce mode fonctionne sans service externe ; l'API Mistral reste le mode rapide.
