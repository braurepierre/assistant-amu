"""Re-test AnythingLLM once its two default settings are corrected.

The 2026-07-26 report attributes almost the whole gap to two defaults, and says
so explicitly — it measures the product *out of the box*, not its ceiling:

1. ``queryRefusalResponse`` left at ``null``, so the model falls back on general
   knowledge instead of refusing (0/4 on the out-of-corpus questions);
2. the default web scraper failing on AMU's central Drupal template — five of the
   nine web pages were ingested as a **single word**, which is the direct cause
   of the hallucinations on césure, RSE, logement and handicap.

A THIRD CHANGE, WHICH IS OURS AND NOT THE PRODUCT'S. ``apply`` also removes the
duplicate copy of every source (see ``cmd_apply``): the workspace held each of
the 19 sources twice, which turned ``topN=4`` into two distinct texts. That one
is a defect of this repository's harness, not a default of AnythingLLM, and it
affected all 20 questions of the 2026-07-26 measurement — so it must be named
wherever a before/after difference is attributed.

``ask --all`` covers the 20 questions, so the "configured" column is measured
under a single regime. Without it, only the ten questions the two defaults bear
on are asked.

WHAT IS UPLOADED, AND WHY IT IS FAIR. The five pages are re-ingested as their
**raw HTML**, straight from ``corpus/raw/`` — the very bytes the scraper choked
on — so AnythingLLM parses them with its own document parser instead of its web
connector. Uploading assistant-amu's *extracted* text would hand it the answer
and measure nothing. Switching ingestion route is ordinary product usage;
borrowing another system's extraction is not.

The word count reported by the API is persisted this time: the 2026-07-26 report
carried its central evidence — the table of extracted words — only in a terminal
scroll, which the review flagged.

Usage:
    python eval/anythingllm_retest_configured.py plan        # what would change, no write
    python eval/anythingllm_retest_configured.py apply       # refusal setting + re-ingest
    python eval/anythingllm_retest_configured.py ask         # the 10 affected questions
    python eval/anythingllm_retest_configured.py ask --all   # the full 20-question set
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from assistant_amu.evaluation import load_questions
from assistant_amu.ingestion.download import load_sources, target_filename

# Anchored on this file, not on ``config.PROJECT_ROOT``: the package is installed
# editable from the main checkout, so PROJECT_ROOT points there whatever worktree
# the script runs from — which silently wrote this branch's reports into main.
REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_RAW = REPO_ROOT / "corpus" / "raw"
SOURCES_YAML = REPO_ROOT / "corpus" / "sources.yaml"
REPORTS = REPO_ROOT / "eval" / "reports"
RESULTS = REPORTS / "anythingllm_configured_answers.json"
INGEST_LOG = REPORTS / "anythingllm_configured_ingest.json"

# The five pages the default scraper reduced to one word, all on the central
# Drupal template, plus the questions whose failure the report imputes to them.
BROKEN_URLS = (
    "https://www.univ-amu.fr/fr/cesure",
    "https://www.univ-amu.fr/fr/regime-special-detudes",
    "https://www.univ-amu.fr/fr/droits-dinscription-aides-financieres",
    "https://www.univ-amu.fr/fr/vie-des-campus/vivre-amu/se-loger",
    "https://www.univ-amu.fr/fr/mission-handicap",
)
AFFECTED = ("q01", "q02", "q03", "q04", "q05", "q08")  # scraper failures
OUT_OF_CORPUS = ("q17", "q18", "q19", "q20")  # refusal setting

REFUSAL = "Je ne trouve pas cette information dans les documents disponibles."


def _config() -> dict:
    missing = [
        name
        for name in ("ANYTHINGLLM_BASE_URL", "ANYTHINGLLM_API_KEY", "ANYTHINGLLM_WORKSPACE_SLUG")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "Variables manquantes dans l'environnement : "
            + ", ".join(missing)
            + "\nLes renseigner dans .env (voir .env.example)."
        )
    return {
        "base": os.environ["ANYTHINGLLM_BASE_URL"].rstrip("/"),
        "key": os.environ["ANYTHINGLLM_API_KEY"],
        "slug": os.environ["ANYTHINGLLM_WORKSPACE_SLUG"],
    }


def _client(cfg: dict) -> httpx.Client:
    return httpx.Client(
        base_url=cfg["base"], headers={"Authorization": f"Bearer {cfg['key']}"}, timeout=180
    )


def _raw_path(url: str) -> Path:
    """The local file the downloader wrote for this source URL."""
    for index, source in enumerate(load_sources(SOURCES_YAML)):
        if source.url == url:
            return CORPUS_RAW / target_filename(source, index)
    raise SystemExit(f"URL absente de corpus/sources.yaml : {url}")


def _workspace_documents(client: httpx.Client, slug: str) -> list[dict]:
    """What is actually EMBEDDED in the workspace, with its word count.

    The workspace endpoint is authoritative here: ``/api/v1/documents`` lists
    everything the instance has ever parsed, embedded or not. Each entry carries
    ``docpath`` — the identifier ``update-embeddings`` expects — and a
    ``metadata`` JSON string holding the title, source URL and word count.
    """
    resp = client.get(f"/api/v1/workspace/{slug}")
    resp.raise_for_status()
    payload = resp.json().get("workspace") or []
    if not payload:
        raise SystemExit(f"Workspace introuvable : {slug!r}")

    out = []
    for doc in payload[0].get("documents") or []:
        try:
            meta = json.loads(doc.get("metadata") or "{}")
        except json.JSONDecodeError:
            meta = {}
        out.append(
            {
                "title": meta.get("title") or doc.get("filename"),
                "url": meta.get("chunkSource") or meta.get("url") or "",
                "location": doc.get("docpath"),
                "wordCount": meta.get("wordCount"),
            }
        )
    return sorted(out, key=lambda d: (d["wordCount"] if d["wordCount"] is not None else -1))


def _refusal_setting(client: httpx.Client, slug: str):
    resp = client.get(f"/api/v1/workspace/{slug}")
    resp.raise_for_status()
    payload = resp.json().get("workspace") or [{}]
    return payload[0].get("queryRefusalResponse")


def cmd_plan(args: argparse.Namespace) -> int:
    cfg = _config()
    with _client(cfg) as client:
        docs = _workspace_documents(client, cfg["slug"])
        refusal = _refusal_setting(client, cfg["slug"])
    starved = [d for d in docs if (d["wordCount"] or 0) <= 5]
    print(f"queryRefusalResponse actuel : {refusal!r}")
    print(f"{len(docs)} documents embarqués dans le workspace, {len(starved)} à 5 mots ou moins :\n")
    for d in starved:
        print(f"  {d['wordCount']:>6} mots  {d['title']}")
    print("\nSeraient réimportés en HTML brut :")
    for url in BROKEN_URLS:
        path = _raw_path(url)
        print(f"  {'OK ' if path.exists() else 'ABSENT'} {path.name}")
    print(f"\nQuestions rejouées : {', '.join(AFFECTED + OUT_OF_CORPUS)}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    cfg = _config()
    log: dict = {"refusal": None, "uploaded": [], "removed": []}
    with _client(cfg) as client:
        # 1. The one-line fix the report says would probably have corrected 0/4.
        resp = client.post(
            f"/api/v1/workspace/{cfg['slug']}/update",
            json={"queryRefusalResponse": REFUSAL},
        )
        resp.raise_for_status()
        log["refusal"] = REFUSAL
        print(f"[refus] queryRefusalResponse = {REFUSAL!r}")

        # 2. Two removals, for two different reasons.
        #
        #    (a) The starved copies of the five Drupal pages — the scraper defect
        #        the report names.
        #    (b) EVERY duplicate. The workspace held each of the 19 sources
        #        exactly twice, so a topN=4 retrieval returned two distinct texts
        #        and their copies: an effective topN of 2, verified on all 20
        #        questions of the stored answers. That one is ours, not the
        #        product's — `anythingllm_compare.py ingest` appends instead of
        #        reconciling, and it was run twice. Leaving it in place would
        #        keep measuring our own harness.
        docs = _workspace_documents(client, cfg["slug"])
        starved = [d for d in docs if (d["wordCount"] or 0) <= 5]
        seen: set[str] = set()
        duplicates = []
        for doc in docs:
            if doc in starved:
                continue
            title = str(doc["title"])
            if title in seen:
                duplicates.append(doc)
            else:
                seen.add(title)

        to_delete = starved + duplicates
        if to_delete:
            resp = client.post(
                f"/api/v1/workspace/{cfg['slug']}/update-embeddings",
                json={"adds": [], "deletes": [d["location"] for d in to_delete]},
            )
            resp.raise_for_status()
            log["removed"] = to_delete
            log["removed_starved"] = len(starved)
            log["removed_duplicates"] = len(duplicates)
            print(
                f"[retrait] {len(starved)} documents faméliques + {len(duplicates)} "
                f"doublons retirés du workspace"
            )

        # 3. Re-ingest them as raw HTML, parsed by AnythingLLM's own file parser.
        locations = []
        for url in BROKEN_URLS:
            path = _raw_path(url)
            with open(path, "rb") as handle:
                resp = client.post(
                    "/api/v1/document/upload", files={"file": (path.name, handle, "text/html")}
                )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print(f"  ECHEC {path.name}: {data.get('error')}")
                continue
            doc = data["documents"][0]
            locations.append(doc["location"])
            entry = {"file": path.name, "url": url, "wordCount": doc.get("wordCount")}
            log["uploaded"].append(entry)
            print(f"  ok ({entry['wordCount']} mots) : {path.name}")

        if locations:
            resp = client.post(
                f"/api/v1/workspace/{cfg['slug']}/update-embeddings",
                json={"adds": locations, "deletes": []},
            )
            resp.raise_for_status()

    # 4. State the resulting workspace, so the measurement that follows is not
    #    taken on trust.
    with _client(cfg) as client:
        after = _workspace_documents(client, cfg["slug"])
        log["refusal_after"] = _refusal_setting(client, cfg["slug"])
    titles = [d["title"] for d in after]
    log["after"] = {
        "documents": len(after),
        "distinct_titles": len(set(titles)),
        "still_starved": sum(1 for d in after if (d["wordCount"] or 0) <= 5),
    }
    print(
        f"\n[état] {log['after']['documents']} documents, "
        f"{log['after']['distinct_titles']} titres distincts, "
        f"{log['after']['still_starved']} encore à 5 mots ou moins"
    )

    INGEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    INGEST_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] journal d'ingestion -> {INGEST_LOG}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    cfg = _config()
    questions = load_questions(Path(args.questions))
    if not args.all:
        wanted = set(AFFECTED + OUT_OF_CORPUS)
        questions = [q for q in questions if q.id in wanted]

    # Answers already stored are kept rather than re-asked. This is only sound
    # while the workspace has not moved since: ``plan`` restates the document
    # count, the distinct-title count and the refusal setting, and they must
    # match ``after`` in the ingestion log before this path is trusted.
    stored: dict[str, dict] = {}
    if RESULTS.exists() and not args.refresh:
        stored = {r["id"]: r for r in json.loads(RESULTS.read_text(encoding="utf-8"))}

    results = []
    with _client(cfg) as client:
        for q in questions:
            if q.id in stored:
                results.append(stored[q.id])
                print(f"  {q.id}: conservée (déjà mesurée)")
                continue
            resp = client.post(
                f"/api/v1/workspace/{cfg['slug']}/chat",
                json={"message": q.question, "mode": "query"},
            )
            resp.raise_for_status()
            data = resp.json()
            sources = data.get("sources") or []
            results.append(
                {
                    "id": q.id,
                    "question": q.question,
                    "answerable": q.answerable,
                    "answer": data.get("textResponse", ""),
                    "num_sources": len(sources),
                    "sources": [
                        {
                            "title": s.get("title"),
                            "wordCount": s.get("wordCount"),
                            "text": s.get("text", ""),
                        }
                        for s in sources
                    ],
                }
            )
            print(f"  {q.id}: {len(sources)} source(s)")

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ask] {len(results)} questions -> {RESULTS}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="montre ce qui changerait, sans rien écrire")
    sub.add_parser("apply", help="règle le refus et réimporte les cinq pages")
    p_ask = sub.add_parser("ask", help="rejoue les dix questions concernées")
    p_ask.add_argument("--questions", default=str(REPO_ROOT / "eval" / "questions.yaml"))
    p_ask.add_argument(
        "--all",
        action="store_true",
        help="rejoue les vingt questions, et non les seules dix que les deux "
        "réglages concernent",
    )
    p_ask.add_argument(
        "--refresh",
        action="store_true",
        help="repose les questions déjà stockées au lieu de conserver leur réponse",
    )

    args = parser.parse_args(argv)
    return {"plan": cmd_plan, "apply": cmd_apply, "ask": cmd_ask}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
