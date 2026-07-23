"""Query rewriting for retrieval — shared by the eval harness and /ask.

Conversational/imperative formulations (« Parle-moi de… », « Dis-moi… »,
« Je voudrais des infos sur… ») push the query vector into noise and drop the
definitional source; raising k does NOT fix it (the fix is at the *query*). Three
strategies:

    raw    identity — the V1 default; the retrieval query is left untouched.
    strip  heuristic: drop the leading conversational/imperative opener.
    llm    the LLM backend rewrites into a short factual search query.

`strip` is deterministic and is the identity on definitional questions
(« Qu'est-ce que… », « Comment… », « Où… »), so it cannot regress them. `llm`
costs one extra backend call and is non-deterministic. The measured comparison
(recall@k on a hard vs. easy set) lives in ``eval/query_rewrite_experiment.py``
and its dated report in ``eval/reports/``. Wired into ``/ask`` as an opt-in
parameter (default ``raw`` ⇒ V1 behaviour unchanged).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid an import cycle; backend is used duck-typed at runtime
    from .llm import LLMBackend

STRATEGIES: tuple[str, ...] = ("raw", "strip", "llm")

# --- strip: pure heuristic -------------------------------------------------

# Conversational / imperative openers, anchored at the start (case-insensitive).
# Each may greedily consume its own trailing "des infos"-style filler.
_OPENERS = [
    r"parle[- ]?moi",
    r"parlez[- ]?moi",
    r"dis[- ]?moi",
    r"dites[- ]?moi",
    r"explique[- ]?moi",
    r"expliquez[- ]?moi",
    r"raconte[- ]?moi",
    r"racontez[- ]?moi",
    r"montre[- ]?moi",
    r"montrez[- ]?moi",
    r"donne[- ]?moi(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails|précisions))?",
    r"donnez[- ]?moi(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails|précisions))?",
    r"j['’]?\s*aimerais(?:\s+(?:bien|savoir|en\s+savoir\s+plus|avoir|obtenir))?(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails))?",
    r"je\s+voudrais(?:\s+(?:bien|savoir|avoir|obtenir))?(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails))?",
    r"je\s+souhaite(?:rais)?(?:\s+(?:savoir|avoir|obtenir))?(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails))?",
    r"je\s+cherche(?:\s+(?:des|quelques)?\s*(?:informations|infos|renseignements|détails))?",
    r"je\s+veux(?:\s+savoir)?",
    r"peux[- ]?tu(?:\s+m['’]?e?)?(?:\s+(?:parler|expliquer|dire|donner|renseigner|indiquer|en\s+dire\s+plus))?",
    r"pouvez[- ]?vous(?:\s+m['’]?e?)?(?:\s+(?:parler|expliquer|dire|donner|renseigner|indiquer))?",
    r"pourrais[- ]?tu(?:\s+m['’]?e?)?(?:\s+(?:parler|expliquer|dire|donner))?",
    r"as[- ]?tu\s+des\s+(?:informations|infos)(?:\s+sur)?",
    r"aurais[- ]?tu\s+des\s+(?:informations|infos)(?:\s+sur)?",
]
# Connective that may bridge opener -> topic ("parle-moi DES régimes" -> "régimes").
_CONNECTIVE = r"(?:\s+(?:sur|concernant|au\s+sujet\s+de|à\s+propos\s+de|de\s+la|de\s+l['’]|de|du|des|d['’]))?"
_OPENER_RE = re.compile(
    r"^\s*(?:" + "|".join(_OPENERS) + r")" + _CONNECTIVE + r"\b\s*",
    flags=re.IGNORECASE | re.UNICODE,
)
# A single leading article, dropped only after an opener was removed.
_LEAD_ARTICLE_RE = re.compile(
    r"^\s*(?:les|le|la|l['’]|un|une|des|du|de\s+la|de\s+l['’]|de|d['’])\s+",
    flags=re.IGNORECASE | re.UNICODE,
)


def strip_query(question: str) -> str:
    """Drop a leading conversational/imperative opener; keep the informative tail.

    Identity on definitional questions (« Qu'est-ce que… », « Comment… », « Où… »):
    they start with no opener, so nothing matches and the query is returned
    unchanged. This guarantees `strip` cannot regress such questions — it only
    ever edits the front of an imperative/conversational phrasing.
    """
    stripped = _OPENER_RE.sub("", question, count=1)
    if stripped == question:
        return question  # no opener matched: definitional questions stay byte-identical
    stripped = _LEAD_ARTICLE_RE.sub("", stripped, count=1)  # "la césure" -> "césure"
    stripped = stripped.strip().strip("?.!,;:").strip()
    return stripped or question  # never return an empty query


# --- llm: backend rewrite --------------------------------------------------

REWRITE_SYSTEM = """Tu reformules une requête d'utilisateur en une requête de recherche courte et factuelle, destinée à un moteur de recherche documentaire (embeddings).

Règles :
1. Supprime les formules conversationnelles/impératives (« parle-moi de », « dis-moi », « je voudrais des infos sur »…) et la politesse.
2. Conserve TOUS les termes porteurs de sens (sujets, sigles, entités) exactement ; n'ajoute AUCUN mot-clé absent de la requête.
3. Produis un groupe nominal court ou une question factuelle, sans verbe d'adresse.
4. Réponds uniquement par la requête reformulée, sur une seule ligne, sans guillemets ni commentaire."""


def _clean_llm(raw: str, fallback: str) -> str:
    first = raw.strip().splitlines()[0] if raw.strip() else ""
    cleaned = first.strip().strip("«»\"'").strip()
    return cleaned or fallback


def rewrite_query(
    question: str, strategy: str = "raw", backend: "LLMBackend | None" = None
) -> str:
    """Return the retrieval query for ``question`` under ``strategy``.

    ``raw`` is the identity (no backend call). ``strip`` is a pure heuristic.
    ``llm`` needs a backend; without one it degrades to the identity rather than
    failing, so a misconfigured call never breaks retrieval.
    """
    if strategy == "raw":
        return question
    if strategy == "strip":
        return strip_query(question)
    if strategy == "llm":
        if backend is None:
            return question
        return _clean_llm(backend.generate(REWRITE_SYSTEM, question), question)
    raise ValueError(f"unknown rewrite strategy: {strategy!r} (expected one of {STRATEGIES})")
