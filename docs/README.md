# docs/ — carte pédagogique du projet

`concepts-assistant-amu.html` est une page autonome (aucune dépendance, aucun
serveur) qui explique **ce que fait réellement AssistantAMU**, brique par brique,
avec des démos manipulables (chunking, requête RAG, réécriture) et un glossaire
relié aux fichiers du code. Ouvrir en double-cliquant.

> Support pédagogique / de présentation — **hors périmètre produit** (PRD §5).
> Aucune dépendance runtime, non branché dans l'application.

## Tenir la page à jour

Les faits qui bougent (corpus, recall, latences, k, tests…) sont centralisés à
**un seul endroit** : le bloc `STATS` en tête du `<script>`, entre les marqueurs

```
/* STATS:START */ ... /* STATS:END */
```

Deux façons de le mettre à jour :

1. **À la main** — éditer les valeurs dans le bloc `STATS` (édition d'un seul
   endroit, 1 minute). Les `data-stat="…"` disséminés dans la page se
   re-remplissent tout seuls au chargement.

2. **Généré** (recommandé) — éditer `concepts.facts.yaml` puis lancer :

   ```bash
   python docs/build_concepts.py           # réécrit le bloc STATS
   python docs/build_concepts.py --check   # échoue si la page est périmée (CI)
   ```

   Le script relit **`config.py`** pour `k`, le modèle d'embedding et les noms de
   modèles backend (jamais dupliqués : le code fait foi), prend la **date du jour**
   et le **commit git court**, et signale toute dérive entre `concepts.facts.yaml`
   et `config.py`. Il ne touche **que** le bloc `STATS` — jamais tes sections.

D'où viennent les chiffres de `concepts.facts.yaml` : des **rapports datés** de
`eval/reports/` (recall, sensibilité à k, réécriture) et de
`python -m assistant_amu.ingestion stats` (corpus). On recopie depuis la mesure —
on n'invente pas.

## Ajouter une rubrique (ex. « e5 vs CamemBERT ») en 4 gestes

Le contenu conceptuel s'écrit à la main (ça ne se génère pas). Pour rester
cohérent avec le reste de la page :

1. **Section** — dupliquer un bloc `<section id="sN">` avec son `sec-num`, son
   titre et ses cartes. Réutiliser les classes existantes (`.card`, `.evalrow`,
   `.recall-chart`, `.grid2`…) pour garder l'unité visuelle.
2. **Sidebar** — ajouter `<a href="#sN" data-sec="sN">N · Titre</a>` dans le bon
   groupe. Le surlignage au défilement (scroll-spy) le prend en charge tout seul.
3. **Glossaire** — si la rubrique introduit un terme, ajouter une entrée dans
   l'objet `G` (`t/c/d/r/f`, `f` = fichier réel du dépôt) ; il apparaît
   automatiquement dans la puce du glossaire et dans les renvois « Termes liés ».
4. **Chiffres** — si la rubrique affiche des mesures, les ajouter à
   `concepts.facts.yaml` (+ `data-stat="…"` dans le HTML) et régénérer.

Pour « e5 vs CamemBERT » précisément : la comparaison est déjà supportée
(`embedder.py` gère les deux familles ; `eval/evaluate.py --embedding-model
dangvantuan/sentence-camembert-base`). Une fois mesurée → un rapport daté dans
`eval/reports/` → nouvelle section + chiffres dans `concepts.facts.yaml`.
