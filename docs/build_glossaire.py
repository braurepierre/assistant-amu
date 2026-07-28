"""Produce the glossary page from the pedagogical page, which holds its source.

The 35-odd term sheets serve two surfaces at once: inside
``docs/concepts-assistant-amu.html`` every underlined term opens one, and the
glossary page lists them all. Two copies of that data would drift within a
month, and a shared ``.js`` file would cost both pages what makes them useful —
being one file that opens in a browser with no server.

So the pedagogical page stays the single source and this script derives the
other, the way ``build_concepts.py`` derives the numbers block of the same page.
Four regions are copied *verbatim* between markers, never rewritten:

    <style>…</style>                        the whole stylesheet, so the two
                                            pages cannot diverge in appearance
    <!-- DRAWER:START --> … :END            markup of the term drawer
    /* GLOSSARY:START */ … :END             ``var G = {…}``, the sheets
    /* DRAWER:START */ … :END               script that opens a sheet

What this script writes itself is only what the glossary page has and the other
does not: its banner, its lead, the search field and the cloud of terms below it.

Usage:
    python docs/build_glossaire.py            # write the page
    python docs/build_glossaire.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

DOCS_DIR = Path(__file__).resolve().parent
SOURCE_PATH = DOCS_DIR / "concepts-assistant-amu.html"
TARGET_PATH = DOCS_DIR / "glossaire-assistant-amu.html"

# Each region, and the message printed when the markers are gone — a marker
# deleted by hand must stop the build rather than produce half a page.
REGIONS = {
    "style": (re.compile(r"<style>.*?</style>", re.DOTALL), "bloc <style>"),
    "drawer_markup": (
        re.compile(r"<!-- DRAWER:START.*?<!-- DRAWER:END -->", re.DOTALL),
        "marqueurs DRAWER du corps",
    ),
    "terms": (
        re.compile(r"/\* GLOSSARY:START \*/.*?/\* GLOSSARY:END \*/", re.DOTALL),
        "marqueurs GLOSSARY",
    ),
    # An opening marker may carry a note after its name; only the name matters.
    "drawer_script": (
        re.compile(r"/\* DRAWER:START\b.*?/\* DRAWER:END \*/", re.DOTALL),
        "marqueurs DRAWER du script",
    ),
}

PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AssistantAMU — glossaire</title>
<!-- Page produite par docs/build_glossaire.py depuis
     docs/concepts-assistant-amu.html. Ne pas modifier à la main : les fiches,
     la feuille de style et le tiroir sont recopiés de cette page-là. -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500&display=swap" rel="stylesheet">
<!-- KaTeX : rendu des formules des blocs « En savoir plus ». Hors ligne, la
     source TeX s'affiche en monospace (repli géré dans renderMath). -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
{style}
<style>
/* Propre à cette page. La feuille reprise ci-dessus dessine une colonne de
   navigation que cette page n'a pas : sans elle, le texte se recentre. */
.layout>main{{margin:0 auto}}
#s0{{margin-top:36px}}
/* Le champ de recherche, posé au-dessus du nuage. */
.finder{{position:relative;max-width:420px;margin:0 0 22px}}
.finder input{{padding-left:38px}}
.finder .glass{{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none;display:flex}}
.finder input:focus+.glass{{color:var(--blue-2)}}
.chip[hidden]{{display:none}}
.tally{{margin:16px 0 0;font-size:13px;color:var(--muted)}}
/* Porté par le balisage, jamais dessiné : lu par un lecteur d'écran. */
.sr-only{{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}}
</style>
</head>
<body>

<div id="topbar">
  <span class="brand"><span class="logo">am<b>U</b></span> AssistantAMU — glossaire</span>
  <span class="repo mono">assistant-amu · pipeline RAG</span>
</div>

<header class="hero">
  <div class="in">
    <p class="eyebrow">Assistant documentaire RAG · corpus public d'Aix-Marseille Université</p>
    <h1>Glossaire</h1>
    <p class="sub">Les termes employés par la documentation du projet, de l'architecture du système jusqu'aux mesures. Chaque fiche sépare la <b>définition</b> du concept de sa <b>mise en œuvre</b> dans le dépôt, rattachée au fichier correspondant. Les entrées marquées <span class="mono" style="color:#E9A088">ƒ</span> offrent en outre un approfondissement mathématique.</p>
  </div>
</header>

<div class="layout">
<main>

<section id="s0">
  <div class="finder">
    <label class="sr-only" for="finder">Filtrer les termes</label>
    <input type="text" id="finder" placeholder="Filtrer les termes…" autocomplete="off"
           spellcheck="false" aria-describedby="tally">
    <span class="glass" aria-hidden="true">
      <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor"
           stroke-width="1.7" stroke-linecap="round">
        <circle cx="7" cy="7" r="4.5"/><path d="M10.4 10.4 14 14"/>
      </svg>
    </span>
  </div>
  <div class="chips" id="chips"></div>
  <p class="tally" id="tally" role="status"></p>
</section>

</main>
</div>

<footer>
  Glossaire du projet <b>AssistantAMU</b> · produit depuis la page pédagogique, qui en est la source.
</footer>

{drawer_markup}

<script>
{terms}

{drawer_script}

/* ---------- nuage de termes et filtre ----------
   Le filtre porte sur l'intitulé et sur la catégorie : « évaluation » retrouve
   ainsi les cinq fiches de cette famille, qu'aucun intitulé ne nomme. La
   comparaison est faite sans accents ni casse — « requete » trouve « requête ».
*/
function fold(s){{
  s=String(s).toLowerCase();
  return s.normalize?s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,''):s;
}}
var KEYS=Object.keys(G);
document.getElementById('chips').innerHTML=KEYS.map(function(k){{
  return '<button class="chip" data-find="'+fold(G[k].t+' '+G[k].c)
       + '" onclick="openTerm(\\''+k+'\\')">'+G[k].t+fx(G[k])+'</button>';
}}).join('');

var chips=[].slice.call(document.querySelectorAll('#chips .chip'));
var tally=document.getElementById('tally');
function filter(){{
  var q=fold(document.getElementById('finder').value.trim());
  var shown=0;
  chips.forEach(function(c){{
    var hit=!q||c.getAttribute('data-find').indexOf(q)!==-1;
    c.hidden=!hit;
    if(hit)shown++;
  }});
  tally.textContent=!q
    ? shown+' termes'
    : (shown===0?'Aucun terme ne correspond à « '+document.getElementById('finder').value.trim()+' »'
                :shown+' terme'+(shown>1?'s':'')+' sur '+chips.length);
}}
document.getElementById('finder').addEventListener('input',filter);

/* Une fiche s'appelle par l'adresse — glossaire-assistant-amu.html#contextuel —
   ce qui permet à un autre document de renvoyer à un terme précis plutôt qu'au
   nuage entier. La clé inconnue est ignorée : la page reste celle du nuage. */
function openFromHash(){{
  var k=decodeURIComponent(location.hash.replace(/^#/,''));
  if(k&&G[k])openTerm(k);
}}
window.addEventListener('hashchange',openFromHash);
openFromHash();
/* Échap vide le champ avant de fermer le tiroir, qui est déjà fermé. */
document.getElementById('finder').addEventListener('keydown',function(e){{
  if(e.key==='Escape'&&this.value){{e.stopPropagation();this.value='';filter();}}
}});
filter();
</script>
</body>
</html>
"""


def extract(html: str) -> dict[str, str]:
    """The four regions the glossary page borrows, verbatim."""
    found = {}
    for name, (pattern, label) in REGIONS.items():
        match = pattern.search(html)
        if not match:
            raise SystemExit(f"{SOURCE_PATH.name} : {label} introuvable")
        found[name] = match.group(0)
    return found


def render(html: str) -> str:
    return PAGE.format(**extract(html))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the page is stale")
    args = parser.parse_args()

    if not SOURCE_PATH.exists():
        print(f"introuvable : {SOURCE_PATH}", file=sys.stderr)
        return 2

    page = render(SOURCE_PATH.read_text(encoding="utf-8"))
    current = TARGET_PATH.read_text(encoding="utf-8") if TARGET_PATH.exists() else None

    if args.check:
        stale = current != page
        print("STALE : lancer `python docs/build_glossaire.py`" if stale else "à jour ✓")
        return 1 if stale else 0

    if current == page:
        print("glossaire déjà à jour — rien à écrire.")
        return 0

    TARGET_PATH.write_text(page, encoding="utf-8")
    terms = page.count('c:"')
    print(f"{TARGET_PATH.name} régénéré ({terms} fiches).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
