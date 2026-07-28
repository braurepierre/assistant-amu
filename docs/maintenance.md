# Maintenance de la documentation

Guide destiné au contributeur : d'où viennent les chiffres publiés, comment les
régénérer, comment se construit le site, et ce qui périme chaque document. Il ne
présente pas le projet — cette fonction revient au `README.md` principal — et
n'est pas publié sur le site.

## Page pédagogique

`concepts-assistant-amu.html` est une page autonome (aucun serveur, aucune étape
de build) qui explique ce que fait AssistantAMU, brique par brique,
avec des démonstrations manipulables (découpage en fragments, requête RAG,
réécriture). Chaque
terme souligné en pointillé y ouvre sa fiche de glossaire. Elle s'ouvre
directement dans un navigateur.

Deux ressources sont chargées depuis un CDN — les polices et **KaTeX**, qui
compose les formules des blocs « En savoir plus ». Hors ligne, la page reste
entièrement lisible : les formules retombent sur leur source TeX en monospace
(repli géré dans `renderMath`).

> Support pédagogique / de présentation — **hors périmètre produit**.
> Aucune dépendance runtime, non branché dans l'application.

## Architecture du système

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

## Glossaire

`glossaire-assistant-amu.html` réunit les fiches de toute la rubrique
« Comprendre » — celles des concepts du RAG comme celles qu'introduisent les
mesures — en un nuage que filtre un champ de recherche. Le filtre porte sur
l'intitulé **et** sur la catégorie, sans accents ni casse : « evaluation »
retrouve les sept fiches de cette famille, qu'aucun intitulé ne nomme.

**Cette page est produite, non rédigée.** Les fiches vivent dans
`concepts-assistant-amu.html`, où elles servent les termes soulignés du texte.
Deux copies dériveraient ; un fichier `.js` partagé coûterait aux deux pages ce
qui fait leur intérêt — être un fichier qui s'ouvre dans un navigateur, sans
serveur. `docs/build_glossaire.py` recopie donc **verbatim**, entre marqueurs,
quatre régions de la page pédagogique :

| Région | Marqueurs | Raison |
| :--- | :--- | :--- |
| Feuille de style | `<style>` … `</style>`, en entier | Les deux pages ne peuvent pas diverger d'aspect ; les règles inutilisées ne coûtent rien |
| Balisage du tiroir | `<!-- DRAWER:START -->` … `:END` | Une fiche s'ouvre de la même façon des deux côtés |
| Fiches | `/* GLOSSARY:START */` … `:END` | L'objet `G`, source unique |
| Script du tiroir | `/* DRAWER:START */` … `:END` | `openTerm`, `renderMath`, `toggleDeep` |

Le script n'écrit lui-même que ce que la page de glossaire a et que l'autre n'a
pas : sa bannière, son chapeau, le champ de recherche et le nuage.

```bash
python docs/build_glossaire.py            # écrire la page
python docs/build_glossaire.py --check    # sortie 1 si elle est périmée
```

Un marqueur supprimé à la main arrête le script au lieu de produire une demi-page.

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

**Intégration des pages autonomes.** Les trois — page pédagogique, architecture
du système, glossaire — ne sont plus des pages à part : leur **contenu** devient le
corps d'une page du site, avec le bandeau, le sommaire du genre, le sommaire de
page et la navigation précédent/suivant comme toutes les autres. Le lecteur ne
quitte plus le site pour les lire, et la vue ne change pas.

Le travail est fait par `docs/site/embed.py`, à la mise en scène :

| Étape | Traitement |
| :--- | :--- |
| Feuille de style | Confinée sous la classe `.embed`, règle par règle. `:root`, `html` et `body` deviennent le conteneur ; les blocs `@media` sont parcourus ; `@keyframes` est laissé intact |
| Bandeau et sommaire propres à la page | Masqués : le site les fournit. Les éléments restent dans le document, car leur script les interroge |
| Bannière d'ouverture | Sa classe `hero` est retirée, donc les règles qui la peignent en sombre cessent de s'appliquer : la page s'ouvre sur son titre et son chapeau dans la carte de lecture, comme les pages rédigées en Markdown. L'exergue et la frise animée, qui appartenaient à la bannière, ne sont plus affichés |
| Ressources externes | Polices, KaTeX, Cytoscape : conservées et déplacées avec le contenu |
| Corps | Ouverture, sections, tiroir du glossaire et script deviennent le corps d'une page Pelican |

Le confinement est mécanique : toute règle est préfixée, donc une règle ajoutée
plus tard à ces pages ne peut pas s'échapper sur l'habillage du site.

**Les fichiers sources ne sont pas modifiés.** Ouverts directement depuis
`docs/`, ils restent des pages autonomes — un fichier, aucun serveur.

**Fiches de glossaire sur la page Mesures.** Dans `mesures.md`, un terme de
glossaire est un lien vers `glossaire-assistant-amu.html#terme` ; le fichier
source n'en dit pas plus. À la mise en scène, `stage_glossary_drawer`
(`build_site.py`) empaquette le tiroir de la page pédagogique — fiches, balisage
et script, recopiés entre les mêmes marqueurs que pour la page de glossaire,
feuille confinée sous `.embed` comme le fait `embed.py` — dans
`static/glossary_drawer.js`, et la page qui cite un terme charge ce script : la
fiche s'ouvre alors sur place, sans changement de page. Sans JavaScript, les
liens gardent leur comportement d'origine et mènent à la page de glossaire, dont
le script ouvre la fiche depuis l'ancre.

**Le rang que ces pages impriment devant leurs propres titres de section est
retiré du sommaire du site** (`_SECTION_RANK` dans `build_site.py`). Il numérote
un ordre de lecture *à l'intérieur* d'une page ; dans l'arbre, l'entrée voisine
celles d'autres pages, et un « 07 » de tête s'y lirait comme un rang de l'arbre.

**Vérifications après une modification de ces pages** : la bannière, le tiroir
du glossaire, les formules KaTeX et les schémas Cytoscape doivent continuer de
fonctionner dans la page publiée. Un sélecteur d'élément nu ajouté à leur feuille de
style est confiné sans risque ; en revanche, un script qui interrogerait un
élément du bandeau du site échouerait, ces deux mondes restant distincts.

## Panneau de l'assistant

Le bandeau porte, sur toutes les pages, un bouton « Assistant » qui ouvre un
tiroir de conversation. Le site documente un assistant : le lecteur doit pouvoir
l'essayer là où l'affirmation est faite.

**Origine unique.** Le panneau interroge `/prepare` puis `/ask` sur l'origine
depuis laquelle la page est servie. L'application monte le site construit sous
`/site` (`SITE_OUTPUT` dans `api/main.py`), de sorte que la page et l'API
partagent cette origine :

    python docs/site/build_site.py
    python -m uvicorn assistant_amu.api.main:app --host 127.0.0.1 --port 8000
    # → http://127.0.0.1:8000/site/

C'est ce qui dispense l'API d'une configuration CORS, et le navigateur des règles
de réseau privé qu'il applique à une page HTTPS appelant une adresse locale. Le
montage n'a lieu que si le répertoire existe, et il est lu au démarrage : un site
reconstruit pendant que le serveur tourne est servi tel quel, un site construit
après le démarrage demande un redémarrage. Pour viser une autre instance,
renseigner `ASSISTANT_API_URL` dans `pelicanconf.py` — l'API visée doit alors
autoriser l'origine du site, ce qu'elle ne fait pas aujourd'hui.

**Dégradation.** Le bouton et le panneau sont rendus masqués et révélés par
`site.js` : une page dont le script ne s'exécute pas n'affiche pas une commande
sans effet. À l'ouverture, le panneau appelle `/health` ; si rien ne répond, il
l'annonce en pied et désactive la saisie, et il réessaie à l'ouverture suivante.
Le site publié sans API — sur Read the Docs, ou ouvert depuis le système de
fichiers — se comporte ainsi sans rien casser.

**Ce que le panneau montre, et pourquoi.** Les marques `[S1]` sont surlignées
dans la phrase qu'elles appuient, et le dépliant « Sources citées » donne pour
chacune son document, sa page, son score et son extrait. C'est la démonstration
elle-même : rattacher une affirmation à un passage, non à une page. La ligne
« compris comme » n'apparaît que si la condensation d'une question de suite en
change le texte ; une ligne qui répète la question apprend à ne plus la lire.

**Ce que le panneau ne porte pas.** Les réglages `k` et « réécriture » de
`demo.html` sont des instruments de mesure et restent dans la page de
démonstration. Aucun échange n'est enregistré : la mention correspondante ne sera
écrite que lorsqu'un enregistrement existera.

**Rangement par genre documentaire.** Le site classe d'abord les pages par ce que
le lecteur vient faire, et non par sujet : « Prise en main » (présentation,
démonstration), « Comprendre » (page pédagogique, architecture du système, mesures),
« Référence d'API ». « Accueil » est un genre à lui seul, qui ne contient que le
point d'entrée.

**Les genres sont les onglets du bandeau, et le sommaire ne liste que l'onglet
ouvert.** L'onglet mène à la première page de son genre, celle que son rang place
en tête : le lecteur n'est jamais déposé au milieu. Un genre dont le sommaire
tiendrait en une seule entrée est dessiné sans sommaire du tout — c'est le cas de
l'accueil, où le texte occupe alors toute la largeur.

Les genres sont déclarés dans `NAV_GROUPS` (`docs/site/pelicanconf.py`), qui fixe
leur ordre et leur intitulé ; chaque page porte sa clé de genre et son rang dans
`PROSE_PAGES`, `STANDALONE_META` ou `API_PAGES` (`docs/site/build_site.py`). Le
rang `nav_order` est **global, non par genre** : le gabarit aplatit les genres
dans l'ordre de `NAV_GROUPS` pour en tirer la navigation précédent/suivant, qui
**traverse donc les onglets** — l'ordre de lecture proposé reste continu d'un
bout à l'autre du site. Ajouter un genre demande une ligne dans `NAV_GROUPS` et
sa clé sur les pages concernées ; un genre vide n'est pas dessiné.

**Sommaire du genre en arbre.** Toutes les pages, et pas seulement les deux
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

**Fonctions du navigateur.** `docs/site/theme/static/js/site.js` porte cinq
comportements, sans dépendance ni étape de construction :

| Fonction | Détail |
| :--- | :--- |
| Hauteur du bandeau | Mesurée et reportée dans `--topbar`, dont tout ce qui colle sous la barre tire sa position. La valeur déclarée dans la feuille est celle d'un bandeau sur une ligne ; sous 56 rem les onglets en prennent une seconde et la barre grandit |
| Bascule de thème | Bouton au pinceau dans la gouttière ; préférence conservée sous la clé `amu.theme`, appliquée avant le chargement de la feuille par le script en ligne du `<head>` du gabarit |
| Sommaire du genre rétractable | Bouton posé dans la page à l'aplomb du sommaire, collant au défilement ; préférence conservée sous la clé `amu.nav`. Sous 56 rem, le sommaire devient un tiroir refermé par défaut, par le bouton, par le voile ou par la touche Échap |
| Sommaire de la page | Construit à partir des `h2`/`h3`, rétractable (clé `amu.toc`), avec suivi de la position de lecture. Omis en dessous de trois titres, masqué sous 78 rem. **Un titre qui n'est qu'une signature de fonction en est écarté** : sur une page d'API, les lister toutes reproduirait la page au lieu de la résumer — modules et classes en portent la structure, les fonctions se lisent à l'intérieur |
| Copie des blocs de code | Bouton révélé au survol de chaque bloc. Hors contexte sécurisé, repli sur `execCommand` |
| Ancres de titre | Rendues à la construction par l'extension `toc` de Markdown, pas par le script |

Ce qui subsiste sans JavaScript : les onglets du bandeau et le sommaire du genre,
tous deux rendus à la construction, les ancres de titre, la navigation
précédent/suivant — rendue par le gabarit à partir de `nav_order` — et la
totalité du texte. Seuls disparaissent le sommaire de page, qui n'apparaît alors
pas plutôt que d'apparaître vide, les boutons de copie et la bascule de thème —
le site reste alors clair ; sous 56 rem, le tiroir s'ouvre alors quelques pixels
trop haut, la hauteur du bandeau n'étant plus mesurée.

Le site n'a pas de recherche : il compte onze pages, dont l'accueil donne le
tableau complet, et aucun genre n'en dépasse cinq.

**Référence d'API.** Ses cinq rubriques portent **les noms que la page « Architecture
du système » donne aux cinq ensembles** du dépôt — socle commun, ingestion du corpus,
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

Le bandeau reprend celui des pages autonomes : fond bleu, filet jaune en
fermeture. Le jaune ne sert qu'à ce filet — l'onglet ouvert est souligné de
blanc, à l'intérieur de la barre. Le bandeau porte le nom
du site, les onglets de genre, le sous-titre, et la marque GitHub qui renvoie au
dépôt — seul endroit où le site nomme son source, raison pour laquelle le sommaire
ne porte plus de rubrique « Dépôt ». La marque garde un `title` et un libellé hors
écran : une icône seule ne dit rien à un lecteur d'écran.

**Sous 56 rem, le bandeau tient sur deux lignes** : le nom et la marque GitHub,
puis les onglets, qui défilent latéralement plutôt que de passer à la ligne. Le
sous-titre est retiré — une troisième ligne de barre prendrait l'écran que le
texte réclame, et la page dit ce qu'est le site.

**Les icônes sont dessinées, non composées.** Le bouton du sommaire et le chevron
des trois sommaires — groupe, rubrique, page — sont des `svg` en ligne, tracés en
`currentColor` : un caractère `▸` ou `☰` serait rendu par la police que le système
substitue, à une taille et une graisse que la page ne contrôle pas. Le chevron est
un seul dessin, pointé à droite quand ce qu'il ouvre est replié et tourné d'un
quart de tour quand il est ouvert.

**Le bouton du sommaire est dans la page, non dans le bandeau.** Il commande la
surface de lecture ; le bandeau nomme le site et ne le commande pas. Il se tient
donc dans la gouttière entre l'arbre et le texte, à hauteur de la première ligne,
et colle au défilement — l'arbre se reprend à n'importe quel endroit d'une page
longue. Sommaire replié, l'arbre quitte sa colonne et le bouton en prend la place
au bord gauche, là où le lecteur vient de le voir. Le gabarit l'écrit **avant**
le sommaire et la feuille de style ordonne les quatre colonnes (`order`) : au
clavier, on l'atteint sans traverser l'arbre entier. Le bouton de thème se tient
sous lui, dans la même pile (`.nav-float`) ; une page sans sommaire garde la
pile, réduite à ce seul bouton.

**Coloration des blocs de code.** L'extension `codehilite` pose les classes de
Pygments ; la feuille du site n'habille que ce qui porte du sens — commentaire,
chaîne, mot-clé, littéral — sous quatre variables propres au site : `--code-comment`
`#6B7290`, `--code-string` `#17624A`, `--code-keyword` `#143b8f`, `--code-literal`
`#8A4B12`. Ponctuation et noms ordinaires gardent la couleur du texte. La classe
`err`, que Pygments pose sur ce que son analyseur n'attendait pas — un fragment de
commande coupé —, est neutralisée : c'est du texte lisible, non une faute à
signaler.

Les polices sont chargées depuis le même CDN par les deux surfaces, ce qui leur
fait partager une entrée de cache, avec repli sur la pile système : hors ligne,
la mise en page et les couleurs tiennent, seule la fonte change.

**Le site porte un thème sombre débrayable.** Le bouton au pinceau, posé sous le
bouton du sommaire dans la gouttière — et seul à cet emplacement sur une page
sans sommaire —, bascule entre les deux thèmes ; le défaut est le clair. La
préférence est conservée sous la clé `amu.theme`, et un script en ligne dans le
`<head>` du gabarit pose `data-theme="dark"` sur `<html>` avant le chargement de
la feuille de style — aucun éclair de thème au chargement.

Le jeu sombre est déclaré dans `site.css` sous `[data-theme="dark"]`, sous les
mêmes noms de variables : encre `#DCE2F2`, fond de page `#0F1524`, carte
`#171E33`, filets `#2B3554`, bleu de texte `#9DB8F2`, bleu de lien `#7DA6EC`,
texte atténué `#8B95B6`, filet jaune inchangé. Le bandeau conserve son bleu par
la variable `--brand` (`#143b8f` en clair, `#122C66` en sombre), séparée de
`--blue` parce que celle-ci encre aussi du texte et s'éclaircit en sombre. Les
couleurs Pygments ont leur pendant sombre sous les variables `--code-*`.

**Le contenu embarqué suit le thème par des surcharges de `site.css`**
(`[data-theme="dark"] .embed …`) : le jeu de variables des pages autonomes y est
redéclaré, plus les encres que ces pages écrivent en dur. Chaque surcharge
reprend le sélecteur de la page, préfixé — la spécificité suffit, sans
`!important`. Les sources sous `docs/` ne portent aucune règle sombre :
ouvertes directement, elles restent claires, le bouton appartenant au site.

**Trois surfaces restent claires en thème sombre**, leurs couleurs étant fixées
par les scripts des pages et non par la feuille : les schémas Cytoscape — les
valeurs claires sont redéclarées sur `.figure`, qui devient un panneau clair
encadré, bulle et fil d'Ariane compris —, les graphiques — courbe de rappel sur
fond blanc encadré, pistes claires des barres de mesure et de similarité — et
les formules KaTeX — bloc `.formula` sur fond blanc, encre foncée épinglée. Le
cadre, l'arrondi et la marge donnent chacune à lire comme un choix, non comme
un défaut d'affichage.

## Mise à jour de la page pédagogique

Les faits volatils (corpus, rappel, latences, k, tests…) sont centralisés à
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

Provenance des chiffres de `concepts.facts.yaml` : les **rapports datés** de
`eval/reports/` (rappel, sensibilité à k, réécriture) et
`python -m assistant_amu.ingestion stats` (corpus). Les valeurs sont recopiées
depuis ces rapports.

## Ajout d'une rubrique à la page pédagogique

Le contenu conceptuel est rédigé à la main ; il n'est pas généré. Pour rester
cohérent avec le reste de la page :

1. **Section** — dupliquer un bloc `<section id="sN">` avec son en-tête
   `<div class="sec-head"><h2>Titre</h2></div>` et ses cartes. Réutiliser les
   classes existantes (`.card`, `.evalrow`, `.recall-chart`, `.grid2`…) pour
   conserver l'unité visuelle ; le `<span class="tag">` en fin de titre est
   facultatif et signale une rubrique adossée à une mesure.
2. **Sommaire latéral** — ajouter `<a href="#sN" data-sec="sN">Titre</a>` dans le bon
   groupe. Le surlignage au défilement (scroll-spy) s'en charge automatiquement.
   Les entrées ne sont pas numérotées.
3. **Glossaire** — si la rubrique introduit un terme, ajouter une entrée dans
   l'objet `G`, entre les marqueurs `GLOSSARY`. Elle apparaît d'elle-même dans
   les renvois « Termes liés » ; **relancer ensuite `python
   docs/build_glossaire.py`** pour qu'elle rejoigne le nuage de la page de
   glossaire. La même règle vaut pour un terme qu'introduisent les mesures et
   non cette page : `G` couvre la rubrique « Comprendre » entière. Chaque fiche
   se lit en deux temps :

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

Pour la comparaison « e5 / CamemBERT » précisément : elle est déjà prise en
charge (`embedder.py` gère les deux familles ; `eval/evaluate.py
--embedding-model dangvantuan/sentence-camembert-base`). Une fois la mesure
effectuée, un rapport daté est déposé dans `eval/reports/`, puis une nouvelle
section et ses chiffres sont ajoutés à `concepts.facts.yaml`.
