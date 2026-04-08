from ddgs import DDGS
from .config import SEARCH_MAX_RESULTS


def search_web(query: str, max_results: int = SEARCH_MAX_RESULTS):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", "").strip(),
                "url": r.get("href", "").strip(),
                "snippet": r.get("body", "").strip(),
            })
    return results


def search_news(query: str, max_results: int = SEARCH_MAX_RESULTS):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.news(query, max_results=max_results):
            results.append({
                "title": r.get("title", "").strip(),
                "url": r.get("url", "").strip(),
                "snippet": r.get("body", "").strip(),
            })
    return results