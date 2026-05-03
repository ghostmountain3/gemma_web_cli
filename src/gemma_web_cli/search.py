from ddgs import DDGS
from .config import SEARCH_MAX_RESULTS
from urllib.parse import urlparse


def _domain(url: str) -> str:
    return urlparse(url or "").netloc.lower()


def _normalize_result(item: dict, rank: int, provider: str = "ddgs") -> dict:
    url = (item.get("href") or item.get("url") or "").strip()
    return {
        "title": (item.get("title") or "").strip(),
        "url": url,
        "snippet": (item.get("body") or item.get("snippet") or "").strip(),
        "source": _domain(url),
        "domain": _domain(url),
        "rank": rank,
        "date": str(item.get("date") or item.get("published") or ""),
        "provider": provider,
    }


def search_web(query: str, max_results: int = SEARCH_MAX_RESULTS):
    results = []
    with DDGS() as ddgs:
        for rank, r in enumerate(ddgs.text(query, max_results=max_results), start=1):
            results.append(_normalize_result(r, rank))
    return results


def search_news(query: str, max_results: int = SEARCH_MAX_RESULTS):
    results = []
    with DDGS() as ddgs:
        for rank, r in enumerate(ddgs.news(query, max_results=max_results), start=1):
            results.append(_normalize_result(r, rank))
    return results


def search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> dict:
    try:
        results = search_web(query, max_results=max_results)
        return {"success": True, "query": query, "provider": "ddgs", "results": results, "error_message": ""}
    except Exception as exc:
        return {"success": False, "query": query, "provider": "ddgs", "results": [], "error_message": str(exc)}
