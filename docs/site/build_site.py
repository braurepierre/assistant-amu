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
import re
import shutil
import subprocess
import sys
from pathlib import Path

import apiref

SITE_DIR = Path(__file__).resolve().parent
DOCS_DIR = SITE_DIR.parent
ROOT = DOCS_DIR.parent
SRC_DIR = ROOT / "src"
CONTENT_DIR = SITE_DIR / "content"
PAGES_DIR = CONTENT_DIR / "pages"
STATIC_DIR = CONTENT_DIR / "static"

REPO_URL = "https://github.com/braurepierre/assistant-amu"
BLOB_URL = f"{REPO_URL}/blob/main"

# Prose pages: (source file, slug, title, nav label). The title overrides the H1
# of the source file, which is stripped — the theme prints the title itself.
#
# ``home.md`` is the one page written for the site alone: a GitHub landing page
# and a documentation home want different things — install commands on one side,
# orientation and navigation on the other — and one file cannot be both. Every
# other page is a deliverable of the repository, staged here rather than copied.
PROSE_PAGES = [
    (SITE_DIR / "home.md", "index", "AssistantAMU", "Accueil"),
    (ROOT / "README.md", "presentation", "Présentation du projet", "Présentation"),
    (ROOT / "DEMO.md", "demonstration", "Guide de démonstration", "Démonstration"),
    (DOCS_DIR / "mesures.md", "mesures", "Mesures et évaluation", "Mesures"),
]

# Read by the reader at the top of every API page. It states how the reference
# is produced and why its body is in English, the code of this project being
# written in English while its documentation is in French.
API_LEAD = (
    "Référence extraite du source par analyse statique : les signatures et les "
    "docstrings sont lues telles quelles, sans importer le paquet ni exécuter "
    "de code. Elle suit donc le code au commit près. Les docstrings sont en "
    "anglais, comme le reste du code ; chaque module renvoie à son fichier "
    "dans le dépôt."
)

# API reference: (slug, title, nav label, package path relative to src/).
API_PAGES = [
    ("api-noyau", "Noyau du paquet", "Noyau", "assistant_amu"),
    ("api-ingestion", "Chaîne d'ingestion", "Ingestion", "assistant_amu/ingestion"),
    ("api-recherche", "Recherche et index", "Recherche", "assistant_amu/retrieval"),
    ("api-generation", "Génération de réponse", "Génération", "assistant_amu/generation"),
    ("api-http", "Interface HTTP", "Interface HTTP", "assistant_amu/api"),
]

# Standalone pages copied verbatim: they carry their own styles and scripts and
# must not go through Markdown. Kept under their original file name so the links
# already written in README.md keep working once rewritten to site root.
STANDALONE_PAGES = [
    DOCS_DIR / "concepts-assistant-amu.html",
    DOCS_DIR / "architecture-assistant-amu.html",
]

# Relative links found in the staged prose, mapped to their address on the site.
# Targets the site does not publish point back at the repository.
LINK_MAP = {
    "docs/concepts-assistant-amu.html": "concepts-assistant-amu.html",
    "docs/architecture-assistant-amu.html": "architecture-assistant-amu.html",
    "docs/mesures.md": "mesures.html",
    "DEMO.md": "demonstration.html",
    "README.md": "presentation.html",
    "docs/maintenance.md": f"{BLOB_URL}/docs/maintenance.md",
    "prompts/CHANGELOG.md": f"{BLOB_URL}/prompts/CHANGELOG.md",
    "eval/reports/": f"{REPO_URL}/tree/main/eval/reports",
}

_LINK = re.compile(r"\]\((?P<target>[^)#]+)(?P<anchor>#[^)]*)?\)")
_FIRST_H1 = re.compile(r"\A\s*#\s+[^\n]*\n+", re.MULTILINE)


def rewrite_links(text: str) -> str:
    """Point relative links at their address on the site, or at the repository."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        anchor = match.group("anchor") or ""
        return f"]({LINK_MAP.get(target, target)}{anchor})"

    return _LINK.sub(replace, text)


def front_matter(**fields: str) -> str:
    """Pelican reads Markdown metadata as ``key: value`` lines before the body.

    Keys are case-insensitive and reach the templates lowercased, so custom ones
    (``nav_label``, ``nav_group``, ``nav_order``) are read as page attributes.
    """
    return "".join(f"{key}: {value}\n" for key, value in fields.items())


def stage_prose() -> None:
    for order, (source, slug, title, nav_label) in enumerate(PROSE_PAGES, start=1):
        body = source.read_text(encoding="utf-8")
        body = _FIRST_H1.sub("", body, count=1)
        page = front_matter(
            title=title,
            slug=slug,
            nav_label=nav_label,
            nav_group="prose",
            nav_order=f"{order * 10:02d}",
        )
        page += "\n" + rewrite_links(body)
        (PAGES_DIR / f"{slug}.md").write_text(page, encoding="utf-8")


def stage_api_reference() -> None:
    for order, (slug, title, nav_label, package) in enumerate(API_PAGES, start=1):
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
            nav_order=f"{40 + order:02d}",
        )
        page += f"\n{API_LEAD}\n\n{body}"
        (PAGES_DIR / f"{slug}.md").write_text(page, encoding="utf-8")


def stage_standalone_pages() -> None:
    for source in STANDALONE_PAGES:
        shutil.copy2(source, STATIC_DIR / source.name)


def stage() -> None:
    """Rebuild ``content/`` from scratch, so a removed page never lingers."""
    if CONTENT_DIR.exists():
        shutil.rmtree(CONTENT_DIR)
    PAGES_DIR.mkdir(parents=True)
    STATIC_DIR.mkdir(parents=True)
    stage_prose()
    stage_api_reference()
    stage_standalone_pages()


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
    print(f"content staged: {len(list(PAGES_DIR.glob('*.md')))} pages")
    if args.stage_only:
        return 0
    return run_pelican(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
