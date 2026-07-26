# docs/ — carte pédagogique du projet

`concepts-assistant-amu.html` est une page autonome (aucun serveur, aucune étape
de build) qui explique **ce que fait réellement AssistantAMU**, brique par brique,
avec des démos manipulables (chunking, requête RAG, réécriture) et un glossaire
relié aux fichiers du code. Ouvrir en double-cliquant.

Deux ressources sont chargées depuis un CDN — les polices et **KaTeX**, qui
compose les formules des blocs « En savoir plus ». Hors ligne, la page reste
entièrement lisible : les formules retombent sur leur source TeX en monospace
(repli géré dans `renderMath`).

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
   python docs/build_concepts.py --check   # échoue si la page est périmée
   ```

   > `--check` n'est pas exploitable tel quel en intégration continue : la page
   > enregistre le SHA du commit courant, si bien qu'un commit touchant la page la
   > rend aussitôt « périmée » vis-à-vis de HEAD. L'utiliser comme garde-fou
   > demanderait d'exclure `commit` et `updated` de la comparaison.

   Une valeur numérique s'affiche en score français (`0,94`) si son chemin figure
   dans `SCORE_PATH` (dans la page) ; les entiers restent bruts. D'où la
   convention : les scores d'une nouvelle rubrique vont sous une sous-clé
   `recall:`, les décomptes restent à côté.

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
   l'objet `G` ; elle apparaît automatiquement dans la puce du glossaire et dans
   les renvois « Termes liés ». Chaque fiche se lit en deux temps :

   | champ | rôle |
   | --- | --- |
   | `t` / `c` | intitulé et catégorie affichés en tête du tiroir |
   | `def[]` | **définition formelle** — le concept en lui-même, hors projet |
   | `math{}` | *facultatif* — bloc repliable « En savoir plus », marque l'entrée d'un `ƒ` |
   | `impl[]` | **mise en œuvre** — ce qu'AssistantAMU en fait, les contraintes rencontrées |
   | `f` | fichier réel du dépôt, affiché sous le bloc `impl[]` |
   | `r[]` / `x[]` | termes liés (clés de `G`) et lien externe |

   Le bloc `math{}` se compose dans l'ordre `intro → formula → note → h1 →
   worked → h2 → p2` ; tous les champs sont facultatifs. `formula` est du **TeX**
   rendu par KaTeX, `worked` un bloc monospace admettant `<span class="hl">` et
   `<span class="cm">` pour surligner et commenter. Le `ƒ` se réserve aux entrées
   portant réellement une formule — au-delà, la marque devient décorative.
4. **Chiffres** — si la rubrique affiche des mesures, les ajouter à
   `concepts.facts.yaml` (+ `data-stat="…"` dans le HTML) et régénérer.

Pour « e5 vs CamemBERT » précisément : la comparaison est déjà supportée
(`embedder.py` gère les deux familles ; `eval/evaluate.py --embedding-model
dangvantuan/sentence-camembert-base`). Une fois mesurée → un rapport daté dans
`eval/reports/` → nouvelle section + chiffres dans `concepts.facts.yaml`.
