import json
import argparse
import traceback
import requests

from .config import OLLAMA_URL, MODEL, READ_TOP_N, SHOW_DEBUG_STATUS, TOP_K_MEMORY
from .prompts import SYSTEM_PROMPT, build_web_context
from .router import route_request
from .search import search_web
from .reader import read_url
from .memory import search_memory, save_page, ensure_data_files, rank_chunks_for_query
from .reader import fetch as fetch_url, extract as extract_html
from .research import cache_clear, cache_status, research


def print_json(data: dict | list) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def run_noninteractive(argv: list[str]) -> bool:
    parser = argparse.ArgumentParser(prog="gemma-web")
    subparsers = parser.add_subparsers(dest="command")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--json", action="store_true")
    search_parser.add_argument("--limit", "--max-results", dest="max_results", type=int, default=5)

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("url")
    fetch_parser.add_argument("--json", action="store_true")

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("url")
    extract_parser.add_argument("--json", action="store_true")
    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("url")
    read_parser.add_argument("--json", action="store_true")

    research_parser = subparsers.add_parser("research")
    research_parser.add_argument("query")
    research_parser.add_argument("--json", action="store_true")
    research_parser.add_argument("--limit", "--max-results", dest="max_results", type=int, default=5)
    research_parser.add_argument("--fetch-top", type=int, default=3)
    research_parser.add_argument("--mode", choices=["auto", "search_results", "research_answer"], default="auto")
    research_parser.add_argument("--max-searches", type=int, default=4)
    research_parser.add_argument("--no-cache", action="store_true")

    cache_parser = subparsers.add_parser("cache")
    cache_parser.add_argument("cache_command", choices=["status", "clear"])

    if not argv:
        return False
    args = parser.parse_args(argv)
    if args.command == "search":
        from .search import search

        result = search(args.query, max_results=args.max_results)
        print_json(result) if args.json else print(result)
        return True
    if args.command == "fetch":
        result = fetch_url(args.url)
        print_json(result) if args.json else print(result.get("text") or result.get("error_message", ""))
        return True
    if args.command in {"extract", "read"}:
        fetched = fetch_url(args.url)
        result = extract_html(fetched.get("final_url") or args.url, fetched.get("html", "")) if fetched.get("success") else {"url": args.url, "extraction_success": False, "error_message": fetched.get("error_message", "fetch failed")}
        print_json(result) if args.json else print(result.get("main_text") or result.get("error_message", ""))
        return True
    if args.command == "research":
        result = research(args.query, max_results=args.max_results, fetch_top=args.fetch_top, no_cache=args.no_cache, response_mode=args.mode, max_searches=args.max_searches)
        text = result.get("synthesized_answer") or "\n".join(result.get("answer_outline", {}).get("main_findings", []))
        print_json(result) if args.json else print(text)
        return True
    if args.command == "cache":
        print_json(cache_status() if args.cache_command == "status" else {"cleared": cache_clear()})
        return True
    return False


def chat_with_ollama(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def chat_with_ollama_stream(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True
    }

    full_text = []
    printed_header = False

    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=300) as response:
            response.raise_for_status()

            print("\nassistant> ", end="", flush=True)
            printed_header = True

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                try:
                    data = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                message = data.get("message", {})
                content = message.get("content", "")

                if content:
                    print(content, end="", flush=True)
                    full_text.append(content)

                if data.get("done", False):
                    break

            print("\n")
            return "".join(full_text)

    except requests.exceptions.RequestException:
        if printed_header:
            print("\n[stream interrupted, retrying without streaming...]\n")
        else:
            print("\nassistant> [stream interrupted, retrying without streaming...]\n")

        answer = chat_with_ollama(messages)
        print(f"assistant> {answer}\n")
        return answer


def print_status(text: str):
    if SHOW_DEBUG_STATUS:
        print(text)


def main(argv=None):
    import sys

    if run_noninteractive(sys.argv[1:] if argv is None else argv):
        return
    ensure_data_files()

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"Connected model: {MODEL}")
    print("Normal chat is enabled.")
    print("Web search and memory retrieval happen automatically when needed.")
    print("Type /quit to exit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user_input:
            continue

        if user_input.lower() in {"/quit", "/exit"}:
            print("bye")
            break

        try:
            memory_hits = search_memory(user_input, top_k=TOP_K_MEMORY)
            route = route_request(user_input, memory_hits, history)

            #print_status(f"[router] route={route['route']} confidence={route['confidence']}")
            #print_status(f"[router] reason={route['reason']}")
            #if route.get("scores"):
                #print_status(f"[router] scores={route['scores']}")

            if route["route"] == "CLARIFY":
                answer = "I'm not fully sure what you want me to look at. Could you be a bit more specific?"
                print(f"\nassistant> {answer}\n")

            elif route["route"] == "WEB_SEARCH":
                print_status("[auto] web search only")

                results = search_web(route["search_query"])

                page_reads = []
                for item in results[:READ_TOP_N]:
                    url = item.get("url", "")
                    title = item.get("title", "")

                    if not url:
                        continue

                    print_status(f"[auto] reading: {url}")
                    page = read_url(url)

                    if page.get("success") and page.get("text", "").strip():
                        top_chunks = rank_chunks_for_query(user_input, page["text"], top_k=3)
                        page["top_chunks"] = top_chunks
                        page_reads.append(page)

                        saved = save_page(url, title, page["text"])
                        if saved:
                            print_status(f"[memory] saved: {url}")
                        else:
                            print_status(f"[memory] skipped duplicate: {url}")

                web_context = build_web_context(
                    user_input,
                    results,
                    page_reads,
                    memory_hits=[]
                )

                messages = history + [
                    {"role": "user", "content": web_context}
                ]
                answer = chat_with_ollama_stream(messages)

            elif route["route"] == "WEB_SEARCH_AND_MEMORY":
                print_status("[auto] web search + memory")

                results = search_web(route["search_query"])

                page_reads = []
                for item in results[:READ_TOP_N]:
                    url = item.get("url", "")
                    title = item.get("title", "")

                    if not url:
                        continue

                    print_status(f"[auto] reading: {url}")
                    page = read_url(url)

                    if page.get("success") and page.get("text", "").strip():
                        top_chunks = rank_chunks_for_query(user_input, page["text"], top_k=3)
                        page["top_chunks"] = top_chunks
                        page_reads.append(page)

                        saved = save_page(url, title, page["text"])
                        if saved:
                            print_status(f"[memory] saved: {url}")
                        else:
                            print_status(f"[memory] skipped duplicate: {url}")

                web_context = build_web_context(
                    user_input,
                    results,
                    page_reads,
                    memory_hits=memory_hits
                )

                messages = history + [
                    {"role": "user", "content": web_context}
                ]
                answer = chat_with_ollama_stream(messages)

            elif route["route"] == "MEMORY_ONLY":
                print_status("[auto] memory only")

                memory_context = build_web_context(
                    user_input,
                    search_results=[],
                    page_reads=[],
                    memory_hits=memory_hits
                )

                messages = history + [
                    {"role": "user", "content": memory_context}
                ]
                answer = chat_with_ollama_stream(messages)

            else:
                print_status("[auto] local only")

                messages = history + [
                    {"role": "user", "content": user_input}
                ]
                answer = chat_with_ollama_stream(messages)

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": answer})

        except Exception:
            print("\nassistant> Error occurred:\n")
            traceback.print_exc()
            print()

