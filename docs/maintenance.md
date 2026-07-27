# Maintenance de la documentation

Guide destiné au contributeur : d'où viennent les chiffres publiés, comment les
régénérer, comment se construit le site, et ce qui périme chaque document. Il ne
présente pas le projet — cette fonction revient au `README.md` principal — et
n'est pas publié sur le site.

## Page pédagogique

`concepts-assistant-amu.html` est une page autonome (aucun serveur, aucune étape
de build) qui explique ce que fait AssistantAMU, brique par brique,
avec des démonstrations manipulables (chunking, requête RAG, réécriture) et un
glossaire relié aux fichiers du code. Elle s'ouvre directement dans un navigateur.

Deux ressources sont chargées depuis un CDN — les polices et **KaTeX**, qui
compose les formules des blocs « En savoir plus ». Hors ligne, la page reste
entièrement lisible : les formules retombent sur leur source TeX en monospace
(repli géré dans `renderMath`).

> Support pédagogique / de présentation — **hors périmètre produit**.
> Aucune dépendance runtime, non branché dans l'application.

## Organisation du code et chaînes de traitement

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
`src/`, et le contenu des deux pages autonomes. Rien n'y est rédigé en double —
ces fichiers restent la source, le site les compose.

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

**Intégration des pages autonomes.** Elles ne sont plus des pages à part : leur
**contenu** devient le corps d'une page du site, avec le bandeau, le sommaire en
arbre, le sommaire de page et la navigation précédent/suivant comme toutes les
autres. Le lecteur ne quitte plus le site pour les lire, et la vue ne change pas.

Le travail est fait par `docs/site/embed.py`, à la mise en scène :

| Étape | Traitement |
| :--- | :--- |
| Feuille de style | Confinée sous la classe `.embed`, règle par règle. `:root`, `html` et `body` deviennent le conteneur ; les blocs `@media` sont parcourus ; `@keyframes` est laissé intact |
| Bandeau et sommaire propres à la page | Masqués : le site les fournit. Les éléments restent dans le document, car leur script les interroge |
| Ressources externes | Polices, KaTeX, Cytoscape : conservées et déplacées avec le contenu |
| Corps | Bannière, sections, tiroir du glossaire et script deviennent le corps d'une page Pelican |

Le confinement est mécanique : toute règle est préfixée, donc une règle ajoutée
plus tard à ces pages ne peut pas s'échapper sur l'habillage du site.

**Les fichiers sources ne sont pas modifiés.** Ouverts directement depuis
`docs/`, ils restent des pages autonomes — un fichier, aucun serveur.

**Ce qu'il faut vérifier après une modification de ces pages** : que la bannière,
le tiroir du glossaire, les formules KaTeX et les schémas Cytoscape fonctionnent
toujours dans la page publiée. Un sélecteur d'élément nu ajouté à leur feuille de
style est confiné sans risque ; en revanche, un script qui interrogerait un
élément du bandeau du site échouerait, ces deux mondes restant distincts.

**Rangement par genre documentaire.** Le sommaire classe d'abord les pages par
ce que le lecteur vient faire, et non par sujet : « Prise en main » (présentation,
démonstration), « Comprendre » (page pédagogique, organisation du code, mesures),
« Référence d'API ». L'accueil reste hors groupe.

Les groupes sont déclarés dans `NAV_GROUPS` (`docs/site/pelicanconf.py`), qui
fixe leur ordre, leur intitulé et leur état d'ouverture ; chaque page porte sa
clé de groupe et son rang dans `PROSE_PAGES`, `STANDALONE_META` ou `API_PAGES`
(`docs/site/build_site.py`). Le rang `nav_order` est **global, non par groupe** :
le gabarit aplatit les groupes dans l'ordre de `NAV_GROUPS` pour en tirer la
navigation précédent/suivant, si bien que l'ordre de lecture proposé est par
construction celui qu'affiche l'arbre. Ajouter un groupe demande une ligne dans
`NAV_GROUPS` et sa clé sur les pages concernées ; un groupe vide n'est pas
dessiné, et un groupe sans intitulé est rendu comme une liste simple.

**Sommaire du site en arbre.** Toutes les pages, et pas seulement les deux
autonomes, sont des rubriques dépliables sur leurs titres de second niveau. Les
sections sont relevées à la mise en scène par `collect_sections`, qui applique la
**fonction `slugify` de l'extension `toc`** — celle-là même que Markdown emploie
pour poser les `id`. Les ancres écrites dans le sommaire ne peuvent donc pas
dériver de celles rendues dans la page ; en cas de doute, comparer le contenu de
`docs/site/nav_sections.json` aux `id` des pages construites.

Ce fichier est écrit par `build_site.py` à la fin de la mise en scène et relu par
`pelicanconf.py` : dessiner l'arbre demande les titres de **toutes** les pages,
que Pelican n'expose pas lorsqu'il en rend une. S'il manque, le sommaire reste
plat au lieu d'échouer.

La rubrique de la page courante est ouverte ; les autres suivent le dernier choix
du lecteur, conservé sous la clé `amu.rubrics`.

**Page d'accueil.** `docs/site/home.md` est le seul document rédigé pour le site
seul. Une vitrine GitHub et un accueil de documentation n'ont pas le même
objet : le `README.md` est publié comme page « Présentation », et l'accueil se
limite à orienter. Aucun chiffre de mesure ne figure sur l'accueil, pour ne pas
créer une copie à tenir à jour.

**Fonctions du navigateur.** `docs/site/theme/static/js/site.js` porte quatre
comportements, sans dépendance ni étape de construction :

| Fonction | Détail |
| :--- | :--- |
| Sommaire du site rétractable | Bouton du bandeau ; préférence conservée sous la clé `amu.nav`. Sous 56 rem, le sommaire devient un tiroir refermé par défaut, par le voile ou par la touche Échap |
| Groupes du sommaire rétractables | Chaque groupe se replie d'un bloc, pour que le reste de l'arbre reste visible. « Référence d'API » s'ouvre replié — cinq pages qui chasseraient le reste — les autres ouverts. Le groupe de la page courante est ouvert d'office ; les autres suivent le dernier choix du lecteur, dans les deux sens (clé `amu.group.groupe-<clé du groupe>`) |
| Sommaire de la page | Construit à partir des `h2`/`h3`, rétractable (clé `amu.toc`), avec suivi de la position de lecture. Omis en dessous de trois titres, masqué sous 78 rem. **Un titre qui n'est qu'une signature de fonction en est écarté** : sur une page d'API, les lister toutes reproduirait la page au lieu de la résumer — modules et classes en portent la structure, les fonctions se lisent à l'intérieur |
| Copie des blocs de code | Bouton révélé au survol de chaque bloc. Hors contexte sécurisé, repli sur `execCommand` |
| Ancres de titre | Rendues à la construction par l'extension `toc` de Markdown, pas par le script |

Ce qui subsiste sans JavaScript : le sommaire du site déployé, les ancres de
titre, la navigation précédent/suivant — rendue par le gabarit à partir de
`nav_order` — et la totalité du texte. Seuls disparaissent le sommaire de page,
qui n'apparaît alors pas plutôt que d'apparaître vide, et les boutons de copie.

Le site n'a pas de recherche : il compte onze pages, toutes visibles
simultanément dans le sommaire.

**Référence d'API.** Ses cinq rubriques portent **les noms que la page « Organisation du code et
chaînes de traitement » donne aux cinq ensembles** du dépôt — socle commun, ingestion du corpus,
recherche des passages, génération de la réponse, interface HTTP. Un lecteur qui
a vu la carte doit retrouver les mêmes intitulés ici ; renommer d'un côté oblige
à renommer de l'autre. Chaque page s'ouvre sur ce que fait son ensemble, en
français, avant de passer la main aux docstrings, qui restent en anglais comme le
reste du code.

**Les citations du PRD sont retirées au rendu.** Les docstrings rattachent chaque
module à la section de la spécification qui l'a prescrit. Ce renvoi est juste
dans le source — le PRD fait autorité sur le périmètre — mais le PRD n'est pas
publié avec le code : sur le site, il enverrait le lecteur vers un document qu'il
n'a pas. `drop_spec_references` dans `apiref.py` les supprime donc à la
construction, sans toucher au source. Trois formes sont traitées : la parenthèse
qui n'est qu'une citation, la citation en fin de parenthèse plus longue avec la
ponctuation qui l'introduit, et la phrase entière qui renvoie à la
spécification. Après modification des docstrings, vérifier qu'aucun « § » ni
« PRD » ne subsiste dans `docs/site/output/`.

**Référence d'API.** Elle est extraite du source par analyse statique
(`apiref.py`, module `ast`) : rien n'est importé ni exécuté, donc aucune
dépendance d'exécution du projet n'est installée sur le serveur de
construction. Le corollaire est qu'un membre construit dynamiquement serait
invisible ; le paquet déclare aujourd'hui toute son API dans le source.

**Publication.** `.readthedocs.yaml`, à la racine, appelle le même script.
Pelican n'étant ni Sphinx ni MkDocs, la construction passe par
`build.commands`, qui remplace les étapes prédéfinies de Read the Docs et écrit
le résultat dans `$READTHEDOCS_OUTPUT/html`.

## Thème AMU

Le site et les deux pages autonomes partagent un seul thème. Les valeurs de
référence sont celles déclarées dans le `:root` des pages autonomes ;
`docs/site/theme/static/css/site.css` les reprend **sous les mêmes noms**, de
sorte que la correspondance se vérifie terme à terme. Modifier l'une des deux
surfaces suppose de reporter le changement sur l'autre.

| Élément | Valeur |
| :--- | :--- |
| Encre, encre atténuée | `--ink` `#0F1F4D`, `--ink-soft` `#33406B` |
| Fond de page, carte | `--paper` `#F4F6FB`, `--card` `#FFFFFF` |
| Bleu, bleu de lien, bleu de fond | `--blue` `#143b8f`, `--blue-2` `#2c6ecb`, `--blue-bg` `#E9EEFA` |
| Jaune AMU | `--yellow` `#f6e400` |
| Filets, texte atténué, arrondi | `--line` `#E1E5F0`, `--muted` `#6B7290`, `--radius` `12px` |
| Titres, texte, code | *Sora*, *Public Sans*, *IBM Plex Mono* |

Le bandeau reprend celui des pages autonomes : fond bleu, marque `amU` en pastille
blanche, filet jaune en fermeture. Le jaune ne sert qu'à ce filet.

Les polices sont chargées depuis le même CDN par les deux surfaces, ce qui leur
fait partager une entrée de cache, avec repli sur la pile système : hors ligne,
la mise en page et les couleurs tiennent, seule la fonte change.

**Le site est en thème clair uniquement**, comme les pages autonomes. La bascule
sombre a été retirée : elle donnait une documentation dont la prose suivait le
thème du système et dont les schémas ne le suivaient pas. Rétablir un thème
sombre supposerait de le porter d'abord sur les deux pages autonomes, ce qui
exposerait les schémas Cytoscape, les graphiques et KaTeX à des régressions sans
rapport avec l'objet de ces pages.

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
depuis ces rapports.

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
