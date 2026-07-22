"""Download corpus documents listed in ``corpus/sources.yaml`` into ``corpus/raw/``.

PRD §7.1 / Phase 1 (F1). Identifiable User-Agent, robots.txt respected, >= 1 s
delay between requests, per-URL failures logged without aborting the batch.

Run with: ``python -m assistant_amu.ingestion.download``.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import yaml

from ..config import PROJECT_ROOT
from ..models import KNOWN_CATEGORIES, SUPPORTED_TYPES, SourceDoc
from . import IngestionError

USER_AGENT = "AssistantAMU-corpus-builder/0.1 (projet etudiant)"
DEFAULT_DELAY_S = 1.0
SOURCES_YAML = PROJECT_ROOT / "corpus" / "sources.yaml"
RAW_DIR = PROJECT_ROOT / "corpus" / "raw"

# Download outcome, one per source entry.
Status = str  # "downloaded" | "local" | "skipped-exists" | "blocked-robots" | "failed"


@dataclass(frozen=True, slots=True)
class DownloadResult:
    source: SourceDoc
    status: Status
    path: Path | None = None
    error: str | None = None


def load_sources(path: Path | str = SOURCES_YAML) -> list[SourceDoc]:
    """Parse and validate ``sources.yaml`` into a list of :class:`SourceDoc`.

    Raises:
        IngestionError: if the file is missing, malformed, or an entry is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise IngestionError(
            f"Sources file not found: {path}. Create it from the template "
            "(PRD §7.1) and list the corpus documents."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise IngestionError(f"Invalid YAML in {path}: {exc}") from exc

    entries = data.get("documents")
    if entries is None:
        raise IngestionError(
            f"{path} must contain a top-level 'documents:' list (may be empty)."
        )
    if not isinstance(entries, list):
        raise IngestionError(f"'documents' in {path} must be a list, got {type(entries).__name__}.")

    sources: list[SourceDoc] = []
    for i, entry in enumerate(entries):
        sources.append(_parse_entry(entry, index=i, path=path))
    return sources


def _parse_entry(entry: object, *, index: int, path: Path) -> SourceDoc:
    where = f"{path} entry #{index + 1}"
    if not isinstance(entry, dict):
        raise IngestionError(f"{where}: each document must be a mapping.")
    for required in ("title", "category", "type"):
        if not entry.get(required):
            raise IngestionError(f"{where}: missing required field '{required}'.")

    url, local_path = entry.get("url"), entry.get("path")
    if bool(url) == bool(local_path):
        raise IngestionError(
            f"{where} ('{entry['title']}'): provide exactly one of 'url' or 'path'."
        )

    doc_type = str(entry["type"]).lower()
    if doc_type not in SUPPORTED_TYPES:
        raise IngestionError(
            f"{where}: type '{doc_type}' unsupported (expected one of {SUPPORTED_TYPES})."
        )
    category = str(entry["category"])
    if category not in KNOWN_CATEGORIES:
        print(f"  warning: {where}: unknown category '{category}' (not in {KNOWN_CATEGORIES}).")

    return SourceDoc(
        title=str(entry["title"]),
        category=category,
        type=doc_type,
        url=str(url) if url else None,
        path=str(local_path) if local_path else None,
        extractor=str(entry["extractor"]) if entry.get("extractor") else None,
    )


def _slugify(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:max_len] or "document"


def target_filename(source: SourceDoc, index: int) -> str:
    """Stable, human-readable filename for a downloaded source."""
    return f"{index:02d}_{_slugify(source.title)}.{source.type}"


class _RobotsCache:
    """Per-host robots.txt cache. Fail-open if robots.txt is unreachable."""

    def __init__(self, client: httpx.Client, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._parsers:
            self._parsers[host] = self._load(host)
        parser = self._parsers[host]
        return True if parser is None else parser.can_fetch(self._user_agent, url)

    def _load(self, host: str) -> RobotFileParser | None:
        robots_url = urljoin(host, "/robots.txt")
        try:
            resp = self._client.get(robots_url)
        except httpx.HTTPError:
            return None  # unreachable -> assume allowed
        if resp.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser


def download_all(
    sources: list[SourceDoc],
    *,
    raw_dir: Path | str = RAW_DIR,
    delay_s: float = DEFAULT_DELAY_S,
    user_agent: str = USER_AGENT,
    overwrite: bool = False,
    client: httpx.Client | None = None,
) -> list[DownloadResult]:
    """Download every remote source; verify local ones. Never abort on one failure.

    Returns one :class:`DownloadResult` per source, in input order.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": user_agent}, follow_redirects=True, timeout=30.0
    )
    robots = _RobotsCache(client, user_agent)
    results: list[DownloadResult] = []
    try:
        for index, source in enumerate(sources):
            results.append(
                _fetch_one(source, index, raw_dir, robots, client, overwrite, delay_s)
            )
    finally:
        if owns_client:
            client.close()
    return results


def _fetch_one(
    source: SourceDoc,
    index: int,
    raw_dir: Path,
    robots: _RobotsCache,
    client: httpx.Client,
    overwrite: bool,
    delay_s: float,
) -> DownloadResult:
    if source.path:  # local file — verify, don't download
        local = Path(source.path)
        if not local.is_absolute():
            local = PROJECT_ROOT / local
        if local.exists():
            return DownloadResult(source, "local", path=local)
        return DownloadResult(source, "failed", error=f"local path not found: {local}")

    assert source.url is not None
    dest = raw_dir / target_filename(source, index)
    if dest.exists() and not overwrite:
        return DownloadResult(source, "skipped-exists", path=dest)

    if not robots.allowed(source.url):
        return DownloadResult(source, "blocked-robots", error=f"robots.txt disallows {source.url}")

    try:
        resp = client.get(source.url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return DownloadResult(source, "failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        time.sleep(delay_s)  # politeness delay, even on failure

    dest.write_bytes(resp.content)
    return DownloadResult(source, "downloaded", path=dest)


def _print_summary(results: list[DownloadResult]) -> int:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print("\n=== Download summary ===")
    for status, n in sorted(counts.items()):
        print(f"  {status:16s}: {n}")
    failures = [r for r in results if r.status in ("failed", "blocked-robots")]
    if failures:
        print("\nFailures (batch continued):")
        for r in failures:
            print(f"  - {r.source.title}: {r.error}")
    return len(failures)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download corpus documents (PRD F1).")
    parser.add_argument("--sources", default=str(SOURCES_YAML), help="Path to sources.yaml")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Destination directory")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S, help="Delay between requests (s)")
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")
    args = parser.parse_args(argv)

    sources = load_sources(args.sources)
    if not sources:
        print("No documents listed in sources.yaml yet (see PRD §7.1).")
        return 0
    print(f"Downloading {len(sources)} source(s) to {args.raw_dir} ...")
    results = download_all(
        sources, raw_dir=args.raw_dir, delay_s=args.delay, overwrite=args.overwrite
    )
    _print_summary(results)
    return 0  # per F1, per-item failures do not fail the batch


if __name__ == "__main__":
    sys.exit(main())
