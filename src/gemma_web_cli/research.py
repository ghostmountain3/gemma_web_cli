import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .config import RESEARCH_CACHE_DIR, RESEARCH_CACHE_TTL_SECONDS, RESEARCH_FETCH_TOP, SEARCH_MAX_RESULTS
from .reader import extract as extract_page
from .reader import fetch as fetch_page
from .search import search as search_query


TREND_TERMS = ("trending", "latest", "current", "popular", "rising", "viral", "news", "what people are talking about")
SEARCH_RESULT_TERMS = (
    "show links",
    "give me links",
    "list results",
    "top results",
    "top 5 results",
    "websites about",
    "sources only",
    "raw search",
    "search results only",
    "links only",
)
RESEARCH_ANSWER_TERMS = (
    "what is happening",
    "explain",
    "new developments",
    "compare sources",
    "summarize news",
    "look up and explain",
    "what do people say",
    "find out whether",
    "is true",
    "research",
)
STOPWORDS = {"the", "is", "a", "an", "and", "or", "to", "of", "in", "for", "with", "what", "are", "about", "how"}
CONTEXT_CLUES = {
    "technology": {"software", "ai", "llm", "agent", "agents", "model", "models", "api", "python", "github", "docs", "library", "package", "ollama"},
    "finance": {"stock", "crypto", "market", "price", "bank", "fund", "revenue", "earnings"},
    "health": {"health", "medical", "drug", "disease", "symptom", "nutrition", "food", "fda"},
    "government": {"law", "policy", "government", "election", "court", "regulation", "agency"},
    "entertainment": {"movie", "game", "music", "show", "celebrity", "streaming", "anime"},
}


def cache_dir() -> Path:
    path = Path(RESEARCH_CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(kind: str, key: str) -> Path:
    digest = hashlib.sha256(f"{kind}:{key}".encode("utf-8")).hexdigest()
    return cache_dir() / f"{digest}.json"


def read_cache(kind: str, key: str):
    path = cache_path(kind, key)
    if not path.exists() or time.time() - path.stat().st_mtime > RESEARCH_CACHE_TTL_SECONDS:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["cached"] = True
        return data
    except Exception:
        return None


def write_cache(kind: str, key: str, data: dict) -> None:
    payload = {**data, "cached": False, "cache_kind": kind, "cached_at": datetime.now().isoformat(timespec="seconds")}
    cache_path(kind, key).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def cache_status() -> dict:
    directory = cache_dir()
    files = list(directory.glob("*.json"))
    return {"cache_dir": str(directory), "entries": len(files), "bytes": sum(path.stat().st_size for path in files), "ttl_seconds": RESEARCH_CACHE_TTL_SECONDS}


def cache_clear() -> int:
    count = 0
    for path in cache_dir().glob("*.json"):
        path.unlink()
        count += 1
    return count


def normalized_url(url: str) -> str:
    parsed = urlparse(url or "")
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def domain(url: str) -> str:
    return urlparse(url or "").netloc.lower()


def query_terms(query: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", query.lower()) if token not in STOPWORDS and len(token) > 2}


def choose_response_mode(query: str, requested: str = "auto") -> str:
    if requested in {"search_results", "research_answer"}:
        return requested
    lowered = query.lower()
    if any(term in lowered for term in SEARCH_RESULT_TERMS):
        return "search_results"
    if query.strip().endswith("?") or any(term in lowered for term in RESEARCH_ANSWER_TERMS) or any(term in lowered for term in TREND_TERMS):
        return "research_answer"
    return "research_answer"


def infer_topic_profile(query: str, context: str = "") -> dict:
    terms = query_terms(f"{query} {context}")
    domains = {name for name, clues in CONTEXT_CLUES.items() if terms & clues}
    return {"terms": terms, "domains": domains}


def _topic_alignment(profile: dict, item: dict) -> float:
    title = item.get("title", "")
    snippet = item.get("snippet", "") or item.get("body", "")
    source = item.get("source", "")
    haystack = f"{title} {snippet} {source} {domain(item.get('url', ''))}".lower()
    terms = profile.get("terms", set())
    if not terms:
        return 0.0
    term_score = sum(1 for term in terms if term in haystack) / max(1, len(terms))
    domain_score = 0.0
    for name in profile.get("domains", set()):
        clues = CONTEXT_CLUES.get(name, set())
        if any(clue in haystack for clue in clues):
            domain_score = max(domain_score, 0.2)
    return round(min(1.0, term_score + domain_score), 3)


def classify_source_type(url: str, title: str = "") -> str:
    host = domain(url)
    text = f"{host} {title}".lower()
    if "github.com" in host:
        return "github"
    if any(marker in text for marker in ("docs.", "/docs", "documentation", "developer.", "api.")):
        return "docs"
    if any(marker in host for marker in ("reddit.com", "stackoverflow.com", "forum", "discourse")):
        return "forum"
    if any(marker in host for marker in ("news", "reuters", "apnews", "bbc", "cnn", "theverge", "techcrunch")):
        return "news"
    if any(marker in host for marker in ("medium.com", "substack.com", "blog")):
        return "blog"
    if host.endswith((".gov", ".edu")) or any(marker in host for marker in ("docs.", "developer.", "official")):
        return "official"
    return "unknown"


def credibility_score(source_type: str) -> float:
    return {"official": 0.95, "docs": 0.9, "github": 0.78, "news": 0.7, "blog": 0.55, "forum": 0.45}.get(source_type, 0.5)


def relevance_score(query: str, title: str, snippet: str, text: str = "") -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0
    haystack = f"{title} {snippet} {text[:2000]}".lower()
    matched = sum(1 for term in terms if term in haystack)
    return round(matched / max(1, len(terms)), 3)


def dedupe_results(results: list[dict]) -> list[dict]:
    seen_urls = set()
    seen_titles = set()
    deduped = []
    for item in results:
        url_key = normalized_url(item.get("url", ""))
        title_key = re.sub(r"\W+", " ", item.get("title", "").lower()).strip()
        if not url_key or url_key in seen_urls or (title_key and title_key in seen_titles):
            continue
        seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(item)
    return deduped


def trend_query_variants(query: str) -> list[str]:
    lowered = query.lower()
    if not any(term in lowered for term in TREND_TERMS):
        return [query]
    variants = [query, f"{query} latest", f"{query} trends", f"{query} news"]
    if "reddit" in lowered or "people" in lowered or "community" in lowered:
        variants.append(f"{query} reddit")
    return list(dict.fromkeys(variants))


def query_variants(query: str, max_searches: int = 4) -> list[str]:
    lowered = query.lower()
    if any(term in lowered for term in TREND_TERMS):
        variants = trend_query_variants(query)
    else:
        variants = [query]
        if not any(term in lowered for term in ("latest", "current", "news", "docs", "official")):
            variants.append(f"{query} latest")
        if any(term in lowered for term in ("docs", "documentation", "api", "library", "package", "software")):
            variants.append(f"{query} official docs")
        elif any(term in lowered for term in ("news", "happening", "development", "trending")):
            variants.append(f"{query} news")
        else:
            variants.append(f"{query} official")
    return list(dict.fromkeys(variants))[: max(1, max_searches)]


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def summarize_source(query: str, extracted_source: dict) -> dict:
    text = extracted_source.get("main_text") or extracted_source.get("text") or ""
    terms = query_terms(query)
    sentences = split_sentences(text)
    scored = []
    for sentence in sentences[:80]:
        lowered = sentence.lower()
        score = sum(1 for term in terms if term in lowered)
        if score:
            scored.append((score, sentence))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    key_sentences = [sentence for _, sentence in scored[:4]] or sentences[:3]
    headings = extracted_source.get("headings", [])[:5]
    key_points = []
    for heading in headings[:3]:
        key_points.append(heading)
    for sentence in key_sentences:
        if sentence not in key_points:
            key_points.append(sentence[:300])
        if len(key_points) >= 5:
            break
    return {
        "summary": " ".join(key_sentences)[:900],
        "key_points": key_points,
        "matched_query_terms": sorted(term for term in terms if term in text.lower()),
        "headings": headings,
        "important_snippets": key_sentences[:3],
    }


def rank_candidates(query: str, results: list[dict]) -> list[dict]:
    profile = infer_topic_profile(query)
    ranked = []
    for item in dedupe_results(results):
        source_type = classify_source_type(item.get("url", ""), item.get("title", ""))
        rel = relevance_score(query, item.get("title", ""), item.get("snippet", ""))
        alignment = _topic_alignment(profile, item)
        rank_score = max(0.0, 1.0 - (float(item.get("rank") or 1) - 1) * 0.08)
        score = round((rel * 0.42) + (alignment * 0.23) + (credibility_score(source_type) * 0.20) + (rank_score * 0.15), 3)
        ranked.append({**item, "source_type": source_type, "relevance_score": score, "topic_alignment": alignment, "credibility_score": credibility_score(source_type)})
    ranked.sort(key=lambda item: item.get("relevance_score", 0), reverse=True)
    return ranked


def filter_irrelevant_results(query: str, candidates: list[dict], minimum_score: float = 0.22) -> tuple[list[dict], list[dict]]:
    terms = query_terms(query)
    profile = infer_topic_profile(query)
    kept = []
    filtered = []
    for item in candidates:
        haystack = f"{item.get('title', '')} {item.get('snippet', '')} {domain(item.get('url', ''))}".lower()
        direct_matches = sum(1 for term in terms if term in haystack)
        domain_mismatch = bool(profile.get("domains")) and item.get("source_type") == "unknown" and item.get("topic_alignment", 0) < 0.6 and direct_matches < 2
        keep = item.get("relevance_score", 0) >= minimum_score and not domain_mismatch and (direct_matches > 0 or item.get("topic_alignment", 0) > 0)
        if keep:
            kept.append(item)
        else:
            filtered.append({"title": item.get("title", ""), "url": item.get("url", ""), "reason": "low topic relevance", "relevance_score": item.get("relevance_score", 0)})
    if not kept and candidates:
        return candidates[:3], filtered
    return kept, filtered


def _select_diverse(candidates: list[dict], limit: int) -> list[dict]:
    selected = []
    seen_domains = set()
    for item in candidates:
        host = domain(item.get("url", ""))
        if host in seen_domains and len(selected) < limit - 1:
            continue
        selected.append(item)
        seen_domains.add(host)
        if len(selected) >= limit:
            break
    for item in candidates:
        if len(selected) >= limit:
            break
        if item not in selected:
            selected.append(item)
    return selected


def _outline(query: str, sources: list[dict]) -> dict:
    points = []
    for source in sources:
        points.extend(source.get("key_points", [])[:2])
    unique = list(dict.fromkeys(point for point in points if point))
    fetched = [source for source in sources if source.get("fetched") and source.get("extraction_success")]
    return {
        "main_findings": unique[:5],
        "consensus": unique[:3],
        "disagreements_or_uncertainty": ["Source coverage may be incomplete; some pages can block automated fetching."] if len(fetched) < max(1, len(sources) // 2) else [],
        "opportunities_or_implications": [],
    }


def synthesize_answer(query: str, sources: list[dict], limitations: list[str]) -> str:
    fetched_sources = [source for source in sources if source.get("fetched") and source.get("extraction_success")]
    source_pool = fetched_sources or sources
    findings = []
    for source in source_pool:
        for point in source.get("key_points", [])[:2]:
            point = str(point).strip()
            if point and point not in findings:
                findings.append(point)
        if len(findings) >= 5:
            break
    if not findings:
        findings = [str(source.get("summary", "")).strip() for source in source_pool if source.get("summary")]
    findings = [item for item in findings if item][:5]
    snippet_only_count = sum(1 for source in sources if source.get("snippet_only"))
    lines = [f"Short answer: I checked recent results for \"{query}\". "]
    if findings:
        lines[0] += findings[0]
    else:
        lines[0] += "there was not enough readable source text to make a strong synthesized claim."
    if len(findings) > 1:
        lines.append("")
        lines.append("Key findings:")
        lines.extend(f"- {finding}" for finding in findings[1:5])
    lines.append("")
    lines.append("Interpretation:")
    if fetched_sources:
        lines.append("The most relevant updates point in the same general direction, with the clearest details coming from readable pages.")
    else:
        lines.append("The results were thin, so the answer should be treated as a quick read rather than a complete research pass.")
    lines.append("")
    lines.append("Uncertainty or limitations:")
    if limitations or snippet_only_count:
        for item in limitations[:3]:
            lines.append(f"- {item}")
        if snippet_only_count:
            lines.append(f"- {snippet_only_count} source(s) were snippet-only, so avoid treating those details as confirmed.")
    else:
        lines.append("- Source coverage may still be incomplete, and search ranking can be noisy.")
    lines.append("")
    lines.append("Sources:")
    for source in sources[:5]:
        status = "fetched" if source.get("fetched") and source.get("extraction_success") else "snippet-only"
        lines.append(f"- {source.get('title', '')} ({source.get('domain', '')}) - {source.get('url', '')} [{status}]")
    return "\n".join(lines)


def research(
    query: str,
    max_results: int = SEARCH_MAX_RESULTS,
    fetch_top: int = RESEARCH_FETCH_TOP,
    no_cache: bool = False,
    response_mode: str = "auto",
    max_searches: int = 4,
) -> dict:
    selected_mode = choose_response_mode(query, response_mode)
    cache_key = f"{query}:{max_results}:{fetch_top}:{selected_mode}:{max_searches}"
    if not no_cache:
        cached = read_cache("research", cache_key)
        if cached:
            return cached
    searched_at = datetime.now().isoformat(timespec="seconds")
    searches = []
    all_results = []
    limitations = []
    variants = [query] if selected_mode == "search_results" else query_variants(query, max_searches=max_searches)
    for variant in variants:
        result = search_query(variant, max_results=max_results)
        searches.append(result)
        if result.get("success"):
            all_results.extend(result.get("results", []))
        else:
            limitations.append(result.get("error_message", "search failed"))
    candidates, filtered_out = filter_irrelevant_results(query, rank_candidates(query, all_results))
    selected = _select_diverse(candidates, fetch_top)
    sources = []
    for item in selected:
        fetched = fetch_page(item.get("url", "")) if selected_mode == "research_answer" else {"success": False, "error_message": "not fetched in search_results mode"}
        extracted = extract_page(fetched.get("final_url") or item.get("url", ""), fetched.get("html", "")) if fetched.get("success") else {}
        summary = summarize_source(query, extracted) if extracted.get("extraction_success") else {"summary": item.get("snippet", ""), "key_points": [item.get("snippet", "")] if item.get("snippet") else [], "matched_query_terms": [], "headings": [], "important_snippets": []}
        rel = relevance_score(query, item.get("title", ""), item.get("snippet", ""), extracted.get("main_text", ""))
        snippet_only = not (fetched.get("success") and extracted.get("extraction_success"))
        sources.append(
            {
                "title": extracted.get("title") or item.get("title", ""),
                "url": item.get("url", ""),
                "domain": domain(item.get("url", "")),
                "source_type": item.get("source_type") or classify_source_type(item.get("url", ""), item.get("title", "")),
                "fetched": bool(fetched.get("success")),
                "fetched_at": fetched.get("fetched_at", ""),
                "extraction_success": bool(extracted.get("extraction_success")),
                "snippet_only": snippet_only,
                "summary": summary.get("summary", ""),
                "key_points": summary.get("key_points", []),
                "matched_query_terms": summary.get("matched_query_terms", []),
                "relevance_score": round(max(float(item.get("relevance_score", 0)), rel), 3),
                "credibility_score": item.get("credibility_score", 0.5),
                "error_message": None if fetched.get("success") and extracted.get("extraction_success") else (fetched.get("error_message") or extracted.get("error_message") or "not fetched"),
            }
        )
    if any(term in query.lower() for term in TREND_TERMS):
        limitations.append("Trend/current queries use multiple search variants, but freshness depends on search provider results and fetched page availability.")
    if sources and all(source.get("snippet_only") for source in sources):
        limitations.append("All selected sources were snippet-only or failed extraction; answer confidence is limited.")
    outline = _outline(query, sources)
    synthesized = synthesize_answer(query, sources, list(dict.fromkeys(item for item in limitations if item))) if selected_mode == "research_answer" else ""
    result = {
        "success": bool(searches) and any(search.get("success") for search in searches),
        "query": query,
        "mode": "research",
        "response_mode": selected_mode,
        "searched_at": searched_at,
        "provider": "ddgs",
        "query_variants": variants,
        "searches": searches,
        "filtered_out": filtered_out,
        "sources": sources,
        "answer_outline": outline,
        "synthesized_answer": synthesized,
        "limitations": list(dict.fromkeys(item for item in limitations if item)),
    }
    write_cache("research", cache_key, result)
    return result


__all__ = [
    "cache_clear",
    "cache_status",
    "choose_response_mode",
    "classify_source_type",
    "dedupe_results",
    "domain",
    "filter_irrelevant_results",
    "query_variants",
    "rank_candidates",
    "research",
    "synthesize_answer",
    "summarize_source",
    "trend_query_variants",
]
