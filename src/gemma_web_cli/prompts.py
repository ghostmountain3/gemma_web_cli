SYSTEM_PROMPT = """You are Gemma running locally through Ollama.

Rules:
- If no external evidence is provided, answer normally.
- If web evidence or memory evidence is provided, use it as grounded context.
- Prefer provided evidence over guessing.
- If evidence is incomplete or conflicting, say so clearly.
- When you use evidence, end with a short Sources section.
- Be natural and clear.
"""


def build_web_context(user_query: str, search_results: list, page_reads: list, memory_hits: list) -> str:
    lines = []
    lines.append(f"User question: {user_query}")
    lines.append("")

    lines.append("Relevant memory hits:")
    if not memory_hits:
        lines.append("No memory hits found.")
    else:
        for i, hit in enumerate(memory_hits, start=1):
            lines.append(f"{i}. {hit['title']}")
            lines.append(f"   URL: {hit['url']}")
            lines.append(f"   Similarity: {hit['score']:.4f}")
            lines.append(f"   Chunk: {hit['text']}")
            lines.append("")

    lines.append("Search results:")
    if not search_results:
        lines.append("No search results found.")
    else:
        for i, item in enumerate(search_results, start=1):
            lines.append(f"{i}. {item['title']}")
            lines.append(f"   URL: {item['url']}")
            lines.append(f"   Snippet: {item['snippet']}")
            lines.append("")

    lines.append("Top chunks from freshly read pages:")
    if not page_reads:
        lines.append("No pages were successfully read.")
    else:
        for i, page in enumerate(page_reads, start=1):
            lines.append(f"{i}. URL: {page['url']}")
            for chunk in page.get("top_chunks", []):
                lines.append(f"   Score: {chunk['score']:.4f}")
                lines.append(f"   Chunk: {chunk['text']}")
            lines.append("")

    lines.append("Instructions:")
    lines.append("- Answer using the evidence above.")
    lines.append("- Prioritize the most relevant chunks.")
    lines.append("- Do not invent unsupported facts.")
    lines.append("- Mention uncertainty when needed.")
    lines.append("- Include a short Sources section when evidence was used.")

    return "\n".join(lines)