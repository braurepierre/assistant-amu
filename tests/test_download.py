"""Tests for the downloader: robots, failures, dedup (PRD §7.1). No real network."""

from __future__ import annotations

import httpx
import pytest

from assistant_amu.ingestion.download import download_all
from assistant_amu.models import SourceDoc


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _remote(title="Doc", url="https://example.org/doc.pdf"):
    return SourceDoc(title=title, category="composante", type="pdf", url=url)


def test_remote_download_writes_file(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"%PDF-fake-bytes")

    results = download_all([_remote()], raw_dir=tmp_path, delay_s=0, client=_client(handler))
    assert results[0].status == "downloaded"
    assert results[0].path.exists()
    assert results[0].path.read_bytes() == b"%PDF-fake-bytes"


def test_rerun_skips_existing(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"data")

    src = [_remote()]
    download_all(src, raw_dir=tmp_path, delay_s=0, client=_client(handler))
    results = download_all(src, raw_dir=tmp_path, delay_s=0, client=_client(handler))
    assert results[0].status == "skipped-exists"


def test_robots_disallow_blocks(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return httpx.Response(200, content=b"should-not-be-fetched")

    results = download_all([_remote()], raw_dir=tmp_path, delay_s=0, client=_client(handler))
    assert results[0].status == "blocked-robots"


def test_http_error_is_failure_not_abort(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(500)

    sources = [_remote("A", "https://example.org/a.pdf"), _remote("B", "https://example.org/b.pdf")]

    def handler2(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/a.pdf":
            return httpx.Response(500)
        return httpx.Response(200, content=b"ok")

    results = download_all(sources, raw_dir=tmp_path, delay_s=0, client=_client(handler2))
    assert results[0].status == "failed"  # first failed
    assert results[1].status == "downloaded"  # batch continued


def test_local_path_source(tmp_path):
    local = tmp_path / "local.pdf"
    local.write_bytes(b"local")
    src = SourceDoc(title="Local", category="composante", type="pdf", path=str(local))
    results = download_all([src], raw_dir=tmp_path, delay_s=0)
    assert results[0].status == "local"
    assert results[0].path == local
