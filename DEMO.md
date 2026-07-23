# AssistantAMU — Guide de démonstration

Exemples testés sur le corpus réel (18 documents AMU, 316 chunks), backend **Mistral**.
Deux interfaces, mêmes réponses via la même API.

## Lancer l'API en local

```powershell
cd C:\Users\Pierre\Documents\projet_claude_code\assistant-amu
$env:LLM_BACKEND = "mistral"
.venv\Scripts\python.exe -m uvicorn assistant_amu.api.main:app --host 127.0.0.1 --port 8000
```

## Deux façons de démontrer

- **A. Chatbot (recommandé)** → **http://127.0.0.1:8000/**
  Interface conversationnelle aux couleurs AMU. Tape ta question : l'assistant répond
  en citant ses sources `[S1]`, et en multi-tour il affiche « ↳ compris comme : … »
  (condensation V2). Les questions des exemples ci-dessous se tapent directement dans
  le champ.
- **B. API / Swagger** → **http://127.0.0.1:8000/docs**
  `POST /ask` → **Try it out** → coller un corps JSON ci-dessous → **Execute**.

---

## 1. Questions simples (single-turn)

Paraphrase (le sémantique retrouve la césure sans le mot exact) :

```json
{ "question": "Puis-je interrompre mes études un an puis les reprendre ?", "k": 5 }
```

Sigles / termes exacts :

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

> Réponse attendue : un texte **sourcé** avec des citations `[S1]`, `[S2]`… et la
> liste des extraits (titre, page, score). `condensed_question` vaut `null`.

---

## 2. Conversation multi-tour (V2 — condensation de requête)

> **Dans le chatbot**, le multi-tour est **automatique** : tape simplement le tour 1
> puis le tour 2 — l'historique est géré pour toi, et « ↳ compris comme : … » s'affiche.
> Le champ `history` ci-dessous n'est utile que pour `/docs` ou un appel direct à l'API.

**Étape A — pose d'abord le tour 1 seul** pour montrer `condensed_question: null` :

```json
{ "question": "Quelles sont les modalités de la césure ?", "k": 5 }
```

**Étape B — puis le tour 2 avec une question elliptique** (« Et à quelles dates… ? »)
et l'historique :

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
> **césure** à Aix-Marseille Université ? »* — puis la réponse donne les vraies
> dates de dépôt, citées `[S1]`.
>
> **Le contraste tour 1 (`null`) → tour 2 (condensé) rend la V2 évidente.**

---

## 3. Refus volontaire (garde-fou anti-hallucination)

Question hors du corpus → le système refuse au lieu d'inventer :

```json
{ "question": "Quelle est la capitale de l'Australie ?", "k": 5 }
```

> Réponse attendue **exactement** :
> `Je ne trouve pas cette information dans les documents disponibles.`
> avec `"sources": []`.

---

## 4. Autres endpoints

- **`GET /health`** → état de ChromaDB, du backend LLM, nombre de documents/chunks.
- **`POST /ingest`** (multipart) → ajoute un document (`file` + `title`) sans
  réindexer l'existant ; `409` si le document est déjà présent.

---

## Basculer sur le backend local Ollama (souverain)

Lancer d'abord l'application **Ollama**, puis :

```powershell
$env:LLM_BACKEND = "ollama"; $env:OLLAMA_NUM_CTX = "4096"
.venv\Scripts\python.exe -m uvicorn assistant_amu.api.main:app --host 127.0.0.1 --port 8000
```

> Sur CPU, Ollama est lent (dizaines de secondes à ~2 min/réponse) : garder `k` bas
> (ex. `"k": 3`). Idéal pour démontrer la **souveraineté** ; l'API Mistral reste le
> mode rapide pour itérer.
