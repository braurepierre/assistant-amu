"""Bring a standalone page inside the site, content and all.

The two pages under ``docs/`` are written to work alone: one HTML file, its own
stylesheet, its own script, no server. That is what makes them useful, and the
sources are never touched. But *published*, they must be pages of the site like
any other — same bar, same tree, same reading column — rather than a place the
reader falls into and where the view changes.

So the published copy is disassembled: the stylesheet is confined under a single
class so it cannot reach the site chrome, the bar and the section list they carry
are hidden — the site provides both — and what remains, opening, sections,
glossary drawer and script, becomes the body of a Pelican page.

The scoping is mechanical rather than a hand-picked list of selectors: every rule
is prefixed, so a rule added to those pages later cannot escape by accident.
"""

from __future__ import annotations

import re

# Their variables are declared on :root, their page frame on html/body. Under a
# scope, all three mean the wrapper.
_ROOT_SELECTORS = {":root", "html", "body", "html, body"}

# At-rules whose block holds selectors, and must therefore be walked into.
_NESTING_AT_RULES = ("@media", "@supports", "@document", "@layer", "@container")


def _block(css: str, opening: int) -> tuple[str, int]:
    """Inner text of the block opening at ``opening``, and the index after it."""
    depth, i = 0, opening
    while i < len(css):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[opening + 1 : i], i + 1
        i += 1
    return css[opening + 1 :], len(css)


def _split_selectors(prelude: str) -> list[str]:
    """Split on commas that separate selectors, not on those inside :not(...)."""
    parts, depth, current = [], 0, []
    for char in prelude:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _prefix(prelude: str, scope: str) -> str:
    scoped = []
    for selector in _split_selectors(prelude):
        bare = selector.strip()
        if not bare:
            continue
        if bare in _ROOT_SELECTORS:
            scoped.append(scope)
        elif bare.startswith(":root"):
            scoped.append(scope + bare[len(":root") :])
        elif bare.startswith("body"):
            scoped.append(scope + bare[len("body") :])
        else:
            scoped.append(f"{scope} {bare}")
    return ",".join(scoped)


def scope_css(css: str, scope: str) -> str:
    """Confine a stylesheet under one class, at-rules included."""
    out, i = [], 0
    while i < len(css):
        opening = css.find("{", i)
        if opening == -1:
            out.append(css[i:])
            break
        prelude = css[i:opening]
        stripped = prelude.strip()
        block, after = _block(css, opening)
        if stripped.startswith("@"):
            at_rule = stripped.split(None, 1)[0].lower()
            # @keyframes, @font-face: their block holds declarations or frame
            # selectors, neither of which may be prefixed.
            inner = scope_css(block, scope) if at_rule in _NESTING_AT_RULES else block
            out.append(f"{prelude}{{{inner}}}")
        else:
            out.append(f"{_prefix(prelude, scope)}{{{block}}}")
        i = after
    return "".join(out)


_STYLE = re.compile(r"<style>(?P<css>.*?)</style>", re.DOTALL)
_BODY = re.compile(r"<body[^>]*>(?P<body>.*)</body>", re.DOTALL)
_HEAD_ASSETS = re.compile(
    r'<(?:link|script)\b[^>]*(?:href|src)="https?://[^"]+"[^>]*>(?:</script>)?'
)

# The banner a standalone page opens on. Published, it gives way to the opening
# every prose page of the site has — the title at the top of the reading card —
# so that moving from "Mesures et évaluation" to the pedagogical page is not a
# change of genre. Its class is *dropped* rather than overridden: the rules the
# page writes for a dark banner stop matching, and the ones it writes for a light
# surface apply to the opening as they do to the sections below, dark scheme
# included. The source under docs/ is untouched and keeps its banner.
_HERO = re.compile(r'(<header[^>]*\sclass=")hero(")')

# What the site now provides, and which must therefore stop being drawn twice.
SUPERSEDED = """
/* The site carries the bar, the section list and the page frame. The reading
   card is the paper now, so the wrapper stops painting one under it. */
.embed #topbar,.embed #sidebar,.embed #sideOverlay{display:none}
.embed{background:none}
/* Freed of its navigation column, the content spans the reading card. The
   padding is dropped rather than kept: the card gives its own, and on a narrow
   screen the site styles a `.layout` of its own that this one answers to. */
.embed .layout{display:block;max-width:none;margin:0;padding:0}
.embed main{max-width:none;padding:0}
.embed>footer{margin-top:48px}
/* The opening, once the banner is gone: a title and a lead. The eyebrow and the
   animated strip belonged to the banner and go with it; the strip keeps its
   element, which the page's script writes into. */
.embed .page-open .in{max-width:none;margin:0}
.embed .page-open .eyebrow,.embed .page-open .hero-tokens{display:none}
.embed .page-open h1{margin:0 0 0.9rem}
.embed .page-open p.sub{max-width:none;margin:0}
"""


def embed(html: str) -> tuple[str, str]:
    """Return the confined stylesheet and the body to hand to Pelican."""
    styles = _STYLE.findall(html)
    if not styles:
        raise SystemExit("standalone page: no <style> block to confine")
    css = scope_css("\n".join(styles), ".embed") + SUPERSEDED

    match = _BODY.search(html)
    if not match:
        raise SystemExit("standalone page: no <body> to embed")
    body = _HERO.sub(r"\1page-open\2", _STYLE.sub("", match.group("body")))

    # Fonts, KaTeX, Cytoscape: kept, and moved with the content. Browsers accept
    # these tags in the body, and Pelican only ever hands us a body.
    assets = "\n".join(_HEAD_ASSETS.findall(html.split("</head>")[0]))
    return css, f'{assets}\n<div class="embed">\n{body}\n</div>'
