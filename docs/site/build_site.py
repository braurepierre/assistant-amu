"""Assemble the Pelican content tree, then build the documentation site.

The prose of this project lives where its readers expect it: ``README.md`` at
the root, ``DEMO.md`` next to it, ``docs/mesures.md`` in ``docs/``. Those files
are the deliverable and stay free of Pelican front matter, so this script
*stages* copies into ``content/pages/`` with the metadata added on the fly and
the relative links rewritten to their address on the site. Whatever the site
does not publish (the prompt changelog, the raw evaluation reports) is
redirected to the GitHub repository rather than left broken.

The home page is the exception: ``home.md`` next to this script exists for the
site alone, so that the README does not have to serve two audiences at once.

The API reference is produced by :mod:`apiref`, which reads the source with
``ast`` — the build server never installs the project's runtime dependencies.

Usage:
    python docs/site/build_site.py                     # build into docs/site/output
    python docs/site/build_site.py --output DIR        # build elsewhere (Read the Docs)
    python docs/site/build_site.py --stage-only        # stage content/, skip Pelican
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import apiref
import embed
from markdown.extensions.toc import slugify

SITE_DIR = Path(__file__).resolve().parent
DOCS_DIR = SITE_DIR.parent
ROOT = DOCS_DIR.parent

# docs/ holds build_glossaire.py, whose marker extraction is reused to package
# the glossary drawer for the prose pages (see stage_glossary_drawer).
sys.path.insert(0, str(DOCS_DIR))
import build_glossaire  # noqa: E402
SRC_DIR = ROOT / "src"
CONTENT_DIR = SITE_DIR / "content"
PAGES_DIR = CONTENT_DIR / "pages"
STATIC_DIR = CONTENT_DIR / "static"

REPO_URL = "https://github.com/braurepierre/assistant-amu"
BLOB_URL = f"{REPO_URL}/blob/main"

# Prose pages: (source file, slug, title, nav label, nav group, nav order). The
# title overrides the H1 of the source file, which is stripped — the theme
# prints the title itself.
#
# The group is the *kind* of document, not its subject: what a reader comes to
# do decides where they go first. ``nav_order`` is global rather than per group,
# so the sequence the sidebar draws is also the one previous/next follows, and
# the pages staged here interleave with the standalone ones below.
#
# ``home.md`` is the one page written for the site alone: a GitHub landing page
# and a documentation home want different things — install commands on one side,
# orientation and navigation on the other — and one file cannot be both. Every
# other page is a deliverable of the repository, staged here rather than copied.
# It stands in its own group, which the theme draws without a title: an entry
# point is not a category.
PROSE_PAGES = [
    (SITE_DIR / "home.md", "index", "AssistantAMU", "Accueil", "home", "10"),
    (ROOT / "README.md", "presentation", "Présentation du projet", "Présentation", "start", "20"),
    (ROOT / "DEMO.md", "demonstration", "Guide de démonstration", "Démonstration", "start", "30"),
    (DOCS_DIR / "mesures.md", "mesures", "Mesures et évaluation", "Mesures", "understand", "60"),
]

# Opening of every API page. It states how the reference is produced, and why its
# body is in English while the documentation around it is in French.
API_LEAD = (
    "Référence extraite du source par analyse statique : les signatures et les "
    "docstrings sont lues telles quelles, sans importer le paquet ni exécuter "
    "de code. Elle suit donc le code au commit près. Les docstrings sont en "
    "anglais, comme le reste du code ; chaque module renvoie à son fichier "
    "dans le dépôt."
)

# API reference: (slug, title, nav label, package path relative to src/, lead).
#
# The five titles are those the code map gives the five sets of the repository,
# to the letter: a reader who has seen the map must recognise the same names
# here. Each page opens on what its set does, in French, before handing over to
# docstrings written in English.
API_PAGES = [
    (
        "api-noyau",
        "Socle commun",
        "Socle commun",
        "assistant_amu",
        "Configuration, journalisation, modèles de données et erreurs. Cet "
        "ensemble ne dépend d'aucun autre, et tous les autres en dépendent.",
    ),
    (
        "api-ingestion",
        "Ingestion du corpus",
        "Ingestion",
        "assistant_amu/ingestion",
        "La chaîne hors ligne, du téléchargement des sources à l'indexation : "
        "extraction du texte, nettoyage, découpage en fragments, vectorisation.",
    ),
    (
        "api-recherche",
        "Recherche des passages",
        "Recherche",
        "assistant_amu/retrieval",
        "Vectorisation des textes, base vectorielle et index lexical BM25 — ce "
        "qui retrouve les fragments susceptibles de porter la réponse.",
    ),
    (
        "api-generation",
        "Génération de la réponse",
        "Génération",
        "assistant_amu/generation",
        "Construction du prompt, appel du modèle et restitution des sources, "
        "refus hors-corpus compris.",
    ),
    (
        "api-http",
        "Interface HTTP",
        "Interface HTTP",
        "assistant_amu/api",
        "Les trois points d'entrée du service et les schémas de leurs échanges.",
    ),
]

# Where the reader situates the set they are reading about.
API_MAP_LINK = (
    "Place de cet ensemble dans le dépôt : [Architecture du "
    "système](architecture-assistant-amu.html)."
)

# Standalone pages: they carry their own styles and scripts and must not go
# through Markdown. Kept under their original file name so the links already
# written in README.md keep working once rewritten to site root.
STANDALONE_PAGES = [
    DOCS_DIR / "concepts-assistant-amu.html",
    DOCS_DIR / "architecture-assistant-amu.html",
    DOCS_DIR / "glossaire-assistant-amu.html",
]

# Published as pages of the site, content and all: their body becomes the body
# of a Pelican page and their stylesheet is confined under one class, so that a
# reader never leaves the site to read them. See embed.py. The sources under
# docs/ are not touched — opened directly, they remain autonomous.
STANDALONE_META = {
    "concepts-assistant-amu.html": (
        "concepts-assistant-amu",
        "Page pédagogique",
        "Page pédagogique",
        "understand",
        "40",
    ),
    # The name became available when the presentation dropped its section of the
    # same name: the ASCII schema left the README for this page, which now
    # carries the architecture alone.
    "architecture-assistant-amu.html": (
        "architecture-assistant-amu",
        "Architecture du système",
        "Architecture du système",
        "understand",
        "50",
    ),
    # Last of its genre: the glossary closes "Comprendre" because it covers the
    # whole of it — the concepts of the pedagogical page as well as those the
    # measurements bring in.
    "glossaire-assistant-amu.html": (
        "glossaire-assistant-amu",
        "Glossaire",
        "Glossaire",
        "understand",
        "65",
    ),
}

# Relative links found in the staged prose, mapped to their address on the site.
# Targets the site does not publish point back at the repository.
LINK_MAP = {
    "docs/concepts-assistant-amu.html": "concepts-assistant-amu.html",
    "docs/architecture-assistant-amu.html": "architecture-assistant-amu.html",
    "docs/glossaire-assistant-amu.html": "glossaire-assistant-amu.html",
    "docs/mesures.md": "mesures.html",
    "DEMO.md": "demonstration.html",
    "README.md": "presentation.html",
    "docs/maintenance.md": f"{BLOB_URL}/docs/maintenance.md",
    "eval/reports/": f"{REPO_URL}/tree/main/eval/reports",
}

_LINK = re.compile(r"\]\((?P<target>[^)#]+)(?P<anchor>#[^)]*)?\)")
_FIRST_H1 = re.compile(r"\A\s*#\s+[^\n]*\n+", re.MULTILINE)

# A glossary term cited in the prose, as mesures.md writes it: a link to the
# sheet's address on the glossary page. On the site the sheet opens in place
# instead — the drawer of the pedagogical page is packaged as one static script
# (stage_glossary_drawer) and the link is given the class and attribute its
# delegated listener reacts to. Without JavaScript the link keeps navigating to
# the glossary page, whose own script opens the sheet from the hash.
_TERM_LINK = re.compile(
    r"\[(?P<label>[^\]]+)\]\(glossaire-assistant-amu\.html#(?P<key>[^)]+)\)"
)
GLOSSARY_SOURCE = DOCS_DIR / "concepts-assistant-amu.html"
DRAWER_SCRIPT = "glossary_drawer.js"


def upgrade_term_links(body: str) -> str:
    """Let a glossary term open its sheet in place, keeping the link as fallback."""

    def replace(match: re.Match[str]) -> str:
        key = match.group("key")
        return (
            f'<a class="term" data-term="{key}" '
            f'href="glossaire-assistant-amu.html#{key}">{match.group("label")}</a>'
        )

    return _TERM_LINK.sub(replace, body)


def stage_glossary_drawer() -> None:
    """Package the glossary drawer as a script a prose page can load.

    The three verbatim regions of the pedagogical page — the sheets (``G``),
    the drawer markup and the drawer script — travel with their stylesheet,
    confined under ``.embed`` exactly as :mod:`embed` confines the standalone
    pages. Everything is injected at run time, so a page whose JavaScript never
    runs keeps plain links and today's behaviour.
    """
    regions = build_glossaire.extract(GLOSSARY_SOURCE.read_text(encoding="utf-8"))
    sheet = regions["style"][len("<style>") : -len("</style>")]
    css = embed.scope_css(sheet, ".embed") + (
        # The wrapper only hosts the two fixed elements of the drawer; the page
        # frame the scoped sheet gives .embed would otherwise paint an empty
        # band at the foot of the page.
        "\n#glossary-embed{margin:0;padding:0;background:none}"
        # The look of a term in the prose. Applied by the same injected sheet,
        # so an unscripted page shows ordinary links.
        "\n.content a.term{color:var(--blue-2);text-decoration:none;"
        "border-bottom:1.5px dotted var(--blue-2)}"
    )
    markup = f'<div class="embed" id="glossary-embed">{regions["drawer_markup"]}</div>'
    bootstrap = (
        "(function () {\n"
        '  var style = document.createElement("style");\n'
        f"  style.textContent = {json.dumps(css)};\n"
        "  document.head.appendChild(style);\n"
        f'  document.body.insertAdjacentHTML("beforeend", {json.dumps(markup)});\n'
        "  /* The drawer script owns the delegated listener that opens the\n"
        "     sheet; this one only keeps the browser on the page, and only when\n"
        "     the sheet exists — an unknown key falls back on the glossary\n"
        "     page. */\n"
        '  document.addEventListener("click", function (event) {\n'
        '    var link = event.target.closest ? event.target.closest("a.term[data-term]") : null;\n'
        '    if (link && G[link.getAttribute("data-term")]) event.preventDefault();\n'
        "  });\n"
        "})();"
    )
    script = (
        "/* Built by build_site.py from the marked regions of "
        f"{GLOSSARY_SOURCE.name} — do not edit. */\n"
        f"{regions['terms']}\n\n{bootstrap}\n\n{regions['drawer_script']}\n"
    )
    (STATIC_DIR / DRAWER_SCRIPT).write_text(script, encoding="utf-8")

# Second-level headings, outside fenced code blocks — a "## " inside a shell
# sample is a comment, not a section.
_HEADING = re.compile(r"^##\s+(?P<text>\S[^\n]*?)\s*$", re.MULTILINE)
_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)

_INLINE_MARKS = re.compile(r"[`*]")

# The section list of a standalone page, read from the sidebar it already has.
_STANDALONE_ENTRY = re.compile(r'<a href="#(?P<id>[^"]+)" data-sec="[^"]*">(?P<label>[^<]+)</a>')

# The rank a standalone page prints beside its own section titles. It numbers a
# reading order inside one page, which the site tree does not show: there, the
# entry sits under its page among the entries of other pages, and a leading "07"
# would be read as a rank in the tree rather than in the page.
_SECTION_RANK = re.compile(r"^\s*\d+\s*[·.\-–—]\s*")

# Filled while staging, written next to this script and read back by
# pelicanconf.py: the templates need the sections of *every* page to draw the
# tree, not only those of the page being rendered.
NAV_SECTIONS: dict[str, list[dict[str, str]]] = {}
SECTIONS_FILE = SITE_DIR / "nav_sections.json"


def collect_sections(body: str) -> list[dict[str, str]]:
    """Second-level headings of a staged page, with the ids Markdown will give
    them. ``slugify`` is the very function the toc extension applies, so the
    anchors written here cannot drift from the ones rendered in the page."""
    return [
        {"id": slugify(text, "-"), "label": text}
        for text in (
            # Inline code and emphasis marks belong to the prose, not to a
            # navigation label. slugify discards them either way, so stripping
            # them here cannot make the anchor drift from the rendered one.
            _INLINE_MARKS.sub("", match.group("text").strip("#").strip())
            for match in _HEADING.finditer(_FENCE.sub("", body))
        )
    ]


def rewrite_links(text: str) -> str:
    """Point relative links at their address on the site, or at the repository."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        anchor = match.group("anchor") or ""
        return f"]({LINK_MAP.get(target, target)}{anchor})"

    return _LINK.sub(replace, text)


def meta_tags(**fields: str) -> str:
    """Pelican reads the metadata of an HTML page from its ``<meta>`` tags."""
    return "".join(f'<meta name="{key}" content="{value}">' for key, value in fields.items())


def front_matter(**fields: str) -> str:
    """Pelican reads Markdown metadata as ``key: value`` lines before the body.

    Keys are case-insensitive and reach the templates lowercased, so custom ones
    (``nav_label``, ``nav_group``, ``nav_order``) are read as page attributes.
    """
    return "".join(f"{key}: {value}\n" for key, value in fields.items())


def stage_prose() -> None:
    for source, slug, title, nav_label, nav_group, nav_order in PROSE_PAGES:
        body = source.read_text(encoding="utf-8")
        body = _FIRST_H1.sub("", body, count=1)
        linked = upgrade_term_links(body)
        page = front_matter(
            title=title,
            slug=slug,
            nav_label=nav_label,
            nav_group=nav_group,
            nav_order=nav_order,
        )
        page += "\n" + rewrite_links(linked)
        if linked != body:
            page += f'\n\n<script src="static/{DRAWER_SCRIPT}" defer></script>\n'
        (PAGES_DIR / f"{slug}.md").write_text(page, encoding="utf-8")
        NAV_SECTIONS[slug] = collect_sections(body)


def stage_api_reference() -> None:
    for order, (slug, title, nav_label, package, lead) in enumerate(API_PAGES, start=1):
        package_dir = SRC_DIR / package
        package_name = package.replace("/", ".")
        modules = apiref.iter_modules(package_dir, package_name)
        body = apiref.render_page(
            modules, source_root=SRC_DIR, source_url=f"{BLOB_URL}/src"
        )
        page = front_matter(
            title=title,
            slug=slug,
            nav_label=nav_label,
            nav_group="api",
            nav_order=f"{70 + order:02d}",
        )
        page += f"\n{lead}\n\n{API_LEAD}\n\n{API_MAP_LINK}\n\n{body}"
        (PAGES_DIR / f"{slug}.md").write_text(page, encoding="utf-8")
        NAV_SECTIONS[slug] = collect_sections(body)


def stage_standalone_pages() -> None:
    """Turn each standalone page into a page of the site."""
    for source in STANDALONE_PAGES:
        html = source.read_text(encoding="utf-8")
        slug, title, nav_label, nav_group, order = STANDALONE_META[source.name]

        # Their sections come from the summary they carry, so the site tree and
        # the page can never list different things.
        NAV_SECTIONS[slug] = [
            {"id": match.group("id"), "label": _SECTION_RANK.sub("", match.group("label")).strip()}
            for match in _STANDALONE_ENTRY.finditer(html)
        ]

        css, body = embed.embed(html)
        page = meta_tags(
            title=title,
            slug=slug,
            nav_label=nav_label,
            nav_group=nav_group,
            nav_order=order,
            # The page opens on its own banner, which already carries its title.
            hide_title="true",
            embedded="true",
        )
        (PAGES_DIR / f"{slug}.html").write_text(
            f"<html><head>{page}</head><body>\n"
            f"<style>{css}</style>\n{body}\n</body></html>",
            encoding="utf-8",
        )


def stage() -> None:
    """Rebuild ``content/`` from scratch, so a removed page never lingers."""
    if CONTENT_DIR.exists():
        shutil.rmtree(CONTENT_DIR)
    PAGES_DIR.mkdir(parents=True)
    STATIC_DIR.mkdir(parents=True)
    NAV_SECTIONS.clear()
    stage_glossary_drawer()
    stage_prose()
    stage_api_reference()
    stage_standalone_pages()
    SECTIONS_FILE.write_text(
        json.dumps(NAV_SECTIONS, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def run_pelican(output: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "pelican",
        str(CONTENT_DIR),
        "--settings",
        str(SITE_DIR / "pelicanconf.py"),
        "--output",
        str(output),
        "--delete-output-directory",
    ]
    return subprocess.call(command, cwd=SITE_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=SITE_DIR / "output",
        help="directory the built site is written to (default: docs/site/output)",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="only rebuild content/, do not run Pelican",
    )
    args = parser.parse_args()

    stage()
    staged = len(list(PAGES_DIR.glob("*.md"))) + len(list(PAGES_DIR.glob("*.html")))
    print(f"content staged: {staged} pages")
    if args.stage_only:
        return 0
    return run_pelican(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
