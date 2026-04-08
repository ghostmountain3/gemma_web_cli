import re


ROUTES = {
    "LOCAL_ONLY",
    "MEMORY_ONLY",
    "WEB_SEARCH",
    "WEB_SEARCH_AND_MEMORY",
    "CLARIFY",
}


FRESHNESS_TERMS = {
    "current", "currently", "latest", "today", "right now", "recent", "recently",
    "new", "newest", "news", "updated", "update", "happening", "happened",
    "price", "stock", "market", "score", "won", "release", "version",
    "bitcoin", "btc", "ethereum", "eth", "weather",
}

FOLLOW_UP_TERMS = {
    "earlier", "before", "previous", "previously", "those", "that source",
    "those sources", "what you read", "you read", "you found", "based on that",
    "based on those", "from earlier", "from before",
}

AMBIGUOUS_REFERENCES = {
    "that", "this", "it", "them", "those", "these",
}

STABLE_KNOWLEDGE_PATTERNS = [
    r"\bwhat is\b",
    r"\bexplain\b",
    r"\bhow does\b",
    r"\bhow do i\b",
    r"\bhelp me\b",
    r"\bwrite\b",
    r"\bdebug\b",
    r"\bsummarize\b",
    r"\bbrainstorm\b",
    r"\bcompare\b",
]

LIVE_DATA_PATTERNS = [
    r"\bcurrent price of\b",
    r"\blatest\b",
    r"\btoday('?s)?\b",
    r"\bright now\b",
    r"\bnews\b",
    r"\bwhat happened\b",
    r"\bwhat changed\b",
    r"\bupdate on\b",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def contains_any_phrase(text: str, phrases: set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def matches_any_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def detect_follow_up(text: str) -> bool:
    return contains_any_phrase(text, FOLLOW_UP_TERMS)


def detect_freshness_need(text: str) -> bool:
    return contains_any_phrase(text, FRESHNESS_TERMS) or matches_any_pattern(text, LIVE_DATA_PATTERNS)


def detect_stable_knowledge(text: str) -> bool:
    return matches_any_pattern(text, STABLE_KNOWLEDGE_PATTERNS)


def detect_ambiguity(text: str) -> bool:
    words = text.split()
    if len(words) <= 3 and contains_any_phrase(text, AMBIGUOUS_REFERENCES):
        return True

    very_ambiguous_patterns = [
        r"^what about (it|that|those|this)$",
        r"^look that up$",
        r"^search that$",
        r"^did it change$",
        r"^what changed\??$",
        r"^check that$",
    ]
    return matches_any_pattern(text, very_ambiguous_patterns)


def memory_strength(memory_hits: list) -> float:
    if not memory_hits:
        return 0.0

    top_score = memory_hits[0].get("score", 0.0)
    if top_score >= 0.85:
        return 1.0
    if top_score >= 0.75:
        return 0.8
    if top_score >= 0.65:
        return 0.55
    if top_score >= 0.55:
        return 0.3
    return 0.1


def build_search_query(user_text: str) -> str:
    text = user_text.strip()

    cleanup_prefixes = [
        "look up ",
        "search for ",
        "search ",
        "find ",
        "check ",
        "tell me about ",
    ]

    lowered = text.lower()
    for prefix in cleanup_prefixes:
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()

    return text


def clamp_confidence(value: float) -> float:
    return max(0.0, min(0.99, round(value, 2)))


def quick_route(user_text: str, memory_hits: list, history: list) -> dict:
    text = normalize_text(user_text)

    freshness = detect_freshness_need(text)
    follow_up = detect_follow_up(text)
    stable_knowledge = detect_stable_knowledge(text)
    ambiguous = detect_ambiguity(text)
    mem_strength = memory_strength(memory_hits)

    freshness_score = 0.0
    memory_score = 0.0
    local_score = 0.0
    clarify_score = 0.0

    if freshness:
        freshness_score += 0.85

    if follow_up:
        memory_score += 0.70

    if mem_strength > 0:
        memory_score += mem_strength

    if stable_knowledge:
        local_score += 0.75

    if ambiguous:
        clarify_score += 0.90

    if follow_up and mem_strength >= 0.55:
        memory_score += 0.25

    if freshness and mem_strength >= 0.55:
        freshness_score += 0.15
        memory_score += 0.20

    if stable_knowledge and not freshness:
        local_score += 0.20

    if not freshness and not follow_up and not ambiguous and not stable_knowledge:
        local_score += 0.35

    if ambiguous and mem_strength < 0.55 and not freshness:
        clarify_score += 0.10

    scores = {
        "LOCAL_ONLY": local_score,
        "MEMORY_ONLY": memory_score,
        "WEB_SEARCH": freshness_score,
        "WEB_SEARCH_AND_MEMORY": min(freshness_score, memory_score) + (0.35 if freshness and mem_strength >= 0.55 else 0.0),
        "CLARIFY": clarify_score,
    }

    best_route = max(scores, key=scores.get)
    best_score = scores[best_route]

    reason_parts = []
    if freshness:
        reason_parts.append("fresh/current info likely needed")
    if follow_up:
        reason_parts.append("looks like a follow-up to prior evidence")
    if mem_strength >= 0.55:
        reason_parts.append(f"memory hits are reasonably strong ({mem_strength:.2f})")
    elif mem_strength > 0:
        reason_parts.append(f"memory hits are weak ({mem_strength:.2f})")
    if stable_knowledge:
        reason_parts.append("looks like stable knowledge or general help")
    if ambiguous:
        reason_parts.append("request is ambiguous")

    if best_route == "WEB_SEARCH_AND_MEMORY" and scores["WEB_SEARCH_AND_MEMORY"] >= max(scores["WEB_SEARCH"], scores["MEMORY_ONLY"]) - 0.05:
        best_route = "WEB_SEARCH_AND_MEMORY"

    if best_route == "MEMORY_ONLY" and freshness and mem_strength < 0.75:
        best_route = "WEB_SEARCH_AND_MEMORY"
        reason_parts.append("freshness requested, so memory alone may be stale")

    if best_route == "LOCAL_ONLY" and freshness:
        best_route = "WEB_SEARCH"
        reason_parts.append("freshness overrides local-only")

    if best_route == "CLARIFY" and mem_strength >= 0.75:
        best_route = "MEMORY_ONLY"
        reason_parts.append("strong memory reduces need to clarify")

    return {
        "route": best_route,
        "search_query": build_search_query(user_text),
        "needs_freshness": freshness,
        "needs_citation": freshness or best_route in {"MEMORY_ONLY", "WEB_SEARCH", "WEB_SEARCH_AND_MEMORY"},
        "use_memory": best_route in {"MEMORY_ONLY", "WEB_SEARCH_AND_MEMORY"},
        "is_follow_up": follow_up,
        "confidence": clamp_confidence(best_score),
        "reason": "; ".join(reason_parts) if reason_parts else "default routing",
        "scores": {k: round(v, 3) for k, v in scores.items()},
    }


def validate_route(route_result: dict) -> dict:
    if route_result.get("route") not in ROUTES:
        route_result["route"] = "LOCAL_ONLY"

    if "search_query" not in route_result or not route_result["search_query"]:
        route_result["search_query"] = ""

    if "confidence" not in route_result:
        route_result["confidence"] = 0.5

    if "reason" not in route_result:
        route_result["reason"] = "no reason provided"

    if "needs_freshness" not in route_result:
        route_result["needs_freshness"] = False

    if "needs_citation" not in route_result:
        route_result["needs_citation"] = False

    if "use_memory" not in route_result:
        route_result["use_memory"] = False

    if "is_follow_up" not in route_result:
        route_result["is_follow_up"] = False

    if "scores" not in route_result:
        route_result["scores"] = {}

    return route_result


def route_request(user_text: str, memory_hits: list, history: list) -> dict:
    result = quick_route(user_text, memory_hits, history)
    return validate_route(result)