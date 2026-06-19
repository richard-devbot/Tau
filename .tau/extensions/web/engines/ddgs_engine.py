"""DuckDuckGo engine (via the ``ddgs`` package). No API key required."""
from __future__ import annotations

from .base import BaseSearchEngine, SearchMode, result


class DDGSearchEngine(BaseSearchEngine):
    name = "ddgs"
    supported_modes = frozenset({
        SearchMode.text, SearchMode.news, SearchMode.images,
        SearchMode.videos, SearchMode.books,
    })

    def __init__(self, region: str = "us-en", safesearch: str = "off") -> None:
        self._region = region or "us-en"
        self._safesearch = safesearch or "off"

    def search(self, query: str, mode: SearchMode, max_results: int) -> list[dict]:
        from ddgs import DDGS
        d = DDGS()
        region, safe = self._region, self._safesearch
        match mode:
            case SearchMode.text:
                raw = d.text(query, region=region, safesearch=safe, max_results=max_results) or []
                return [result(title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")) for r in raw]
            case SearchMode.news:
                raw = d.news(query, region=region, safesearch=safe, max_results=max_results) or []
                return [result(
                    title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("body", ""),
                    source=r.get("source", ""), date=r.get("date", ""),
                ) for r in raw]
            case SearchMode.images:
                raw = d.images(query, region=region, safesearch=safe, max_results=max_results) or []
                return [result(title=r.get("title", ""), url=r.get("url", ""), image=r.get("image", "")) for r in raw]
            case SearchMode.videos:
                raw = d.videos(query, region=region, safesearch=safe, max_results=max_results) or []
                return [result(
                    title=r.get("title", ""), url=r.get("content", ""),
                    snippet=r.get("description", ""), duration=r.get("duration", ""),
                ) for r in raw]
            case SearchMode.books:
                raw = d.books(query, max_results=max_results) or []
                return [result(
                    title=r.get("title", ""), url=r.get("url", ""), author=r.get("author", ""),
                    publisher=r.get("publisher", ""), info=r.get("info", ""),
                ) for r in raw]

    def fetch(self, url: str, timeout: int) -> str:
        from ddgs import DDGS
        ddgs = DDGS(timeout=timeout)
        res = ddgs.extract(url)
        raw = res.get("content", "") or ""
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
