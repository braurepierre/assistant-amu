# Maintenance de la documentation

Guide destiné au contributeur : d'où viennent les chiffres publiés, comment les
régénérer, comment se construit le site, et ce qui périme chaque document. Il ne
présente pas le projet — cette fonction revient au `README.md` principal — et
n'est pas publié sur le site.

## Page pédagogique

`concepts-assistant-amu.html` est une page autonome (aucun serveur, aucune étape
de build) qui explique **ce que fait réellement AssistantAMU**, brique par brique,
avec des démonstrations manipulables (chunking, requête RAG, réécriture) et un
glossaire relié aux fichiers du code. Elle s'ouvre directement dans un navigateur.

Deux ressources sont chargées depuis un CDN — les polices et **KaTeX**, qui
compose les formules des blocs « En savoir plus ». Hors ligne, la page reste
entièrement lisible : les formules retombent sur leur source TeX en monospace
(repli géré dans `renderMath`).

> Support pédagogique / de présentation — **hors périmètre produit**.
> Aucune dépendance runtime, non branché dans l'application.

## Carte du code

`architecture-assistant-amu.html` répond à une autre question que la page
pédagogique : non pas ce qu'est un système RAG, mais comment ce dépôt est
organisé. Trois sections — l'organisation du code en cinq ensembles, la chaîne
d'ingestion, la chaîne de réponse — s'en tiennent aux traitements principaux.
Le détail d'implémentation ne charge pas les schémas : survoler un bloc en
donne le rôle et le fichier.

La page se lit à **deux niveaux**. Sept blocs, signalés par un contour plus
marqué, ouvrent au clic le schéma du fonctionnement interne du script qu'ils
désignent : extraction, découpage, vectorisation, base vectorielle,
construction du prompt. Un fil d'Ariane ramène au schéma de départ, la touche
Échap également. Les cinq schémas de second niveau sont ceux dont la logique
mérite d'être vue — un fichier qui ne fait qu'enchaîner deux appels n'en a
pas.

Les schémas sont rendus par **Cytoscape**, chargé depuis un CDN. Hors ligne,
chaque schéma retombe sur la liste ordonnée de ses étapes, écrite en clair dans
le HTML.

Cette page ne porte **aucun chiffre de mesure** : elle n'a donc pas de bloc
`STATS` et ne dépend pas de `build_concepts.py`. Ce qui la périme, c'est un
changement de structure — un module déplacé, une dépendance ajoutée, une
responsabilité transférée d'une classe à une autre.

## Site de documentation

`site/` construit un site à partir des documents qui existent déjà dans le
dépôt : `README.md`, `DEMO.md`, `mesures.md`, une référence d'API extraite de
`src/`, et les deux pages autonomes recopiées telles quelles. Rien n'y est
rédigé en double — ces fichiers restent la source, le site les compose.

Construction locale :

```bash
uv run --no-project --with-requirements docs/site/requirements.txt \
    python docs/site/build_site.py
# le site est écrit dans docs/site/output/, à ouvrir dans un navigateur
```

Le script assemble d'abord `docs/site/content/` — métadonnées Pelican ajoutées
à la volée, titre de premier niveau retiré, liens relatifs réécrits vers leur
adresse sur le site ou vers le dépôt quand la cible n'est pas publiée — puis
lance Pelican. Les deux répertoires produits, `content/` et `output/`, ne sont
pas versionnés : ils sont reconstruits à chaque appel.

**Page d'accueil.** `docs/site/home.md` est le seul document rédigé pour le site
seul. Une vitrine GitHub et un accueil de documentation n'ont pas le même
objet — commandes d'installation d'un côté, orientation et navigation de
l'autre — et un fichier unique ne peut pas remplir les deux fonctions sans en
sacrifier une. Le `README.md` est donc publié comme page « Présentation », et
l'accueil se limite à orienter. Conséquence à retenir en écrivant : **aucun
chiffre de mesure ne figure sur l'accueil**, pour ne pas créer une copie de plus
à tenir à jour.

**Référence d'API.** Elle est extraite du source par analyse statique
(`apiref.py`, module `ast`) : rien n'est importé ni exécuté, donc aucune
dépendance d'exécution du projet n'est installée sur le serveur de
construction. Le corollaire est qu'un membre construit dynamiquement serait
invisible ; le paquet déclare aujourd'hui toute son API dans le source.

**Publication.** `.readthedocs.yaml`, à la racine, appelle le même script.
Pelican n'étant ni Sphinx ni MkDocs, la construction passe par
`build.commands`, qui remplace les étapes prédéfinies de Read the Docs et écrit
le résultat dans `$READTHEDOCS_OUTPUT/html`.

## Unité graphique du site et des pages autonomes

Le site et les deux pages autonomes partagent une même palette (encre `#0F1F4D`,
fond `#F4F6FB`, accent `#143b8f`), un même rayon d'arrondi et une même
typographie — *Sora* pour les titres, *Public Sans* pour le texte, *IBM Plex
Mono* pour le code. Les valeurs de référence sont celles déclarées dans le
`:root` des pages autonomes ; `docs/site/theme/static/css/site.css` les reprend.
Modifier l'une des deux surfaces suppose donc de reporter le changement sur
l'autre.

Les polices sont chargées depuis le même CDN par les deux surfaces, avec repli
sur la pile système : hors ligne, la mise en page et les couleurs tiennent, seule
la fonte change.

**Écart résiduel assumé.** Le site suit le thème sombre du système, les pages
autonomes non — leur mise en forme est en clair dans quelques milliers de lignes
de HTML, et leur ajouter un thème sombre exposerait les schémas Cytoscape, les
graphiques et KaTeX à des régressions sans rapport avec l'objet de ces pages. En
thème sombre, passer du site à une page autonome change donc de fond.

## Mise à jour de la page pédagogique

Les faits qui bougent (corpus, recall, latences, k, tests…) sont centralisés à
**un seul endroit** : le bloc `STATS` en tête du `<script>`, entre les marqueurs

```
/* STATS:START */ ... /* STATS:END */
```

Deux façons de le mettre à jour :

1. **À la main** — éditer les valeurs dans le bloc `STATS` : un seul endroit à
   modifier. Les `data-stat="…"` disséminés dans la page sont renseignés
   automatiquement au chargement.

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
   et `config.py`. Il ne modifie **que** le bloc `STATS` — jamais les sections
   rédigées.

D'où viennent les chiffres de `concepts.facts.yaml` : des **rapports datés** de
`eval/reports/` (recall, sensibilité à k, réécriture) et de
`python -m assistant_amu.ingestion stats` (corpus). Les valeurs sont recopiées
depuis la mesure, jamais estimées.

## Ajout d'une rubrique à la page pédagogique

Le contenu conceptuel est rédigé à la main : il ne se génère pas. Pour rester
cohérent avec le reste de la page :

1. **Section** — dupliquer un bloc `<section id="sN">` avec son `sec-num`, son
   titre et ses cartes. Réutiliser les classes existantes (`.card`, `.evalrow`,
   `.recall-chart`, `.grid2`…) pour conserver l'unité visuelle.
2. **Sidebar** — ajouter `<a href="#sN" data-sec="sN">N · Titre</a>` dans le bon
   groupe. Le surlignage au défilement (scroll-spy) s'en charge automatiquement.
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
