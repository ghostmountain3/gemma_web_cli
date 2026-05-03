import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma_web_cli import reader, research, search


class FakeDDGS:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def text(self, query, max_results=5):
        return [
            {"title": "Official Docs", "href": "https://docs.example.com/page", "body": f"{query} docs"},
            {"title": "Official Docs", "href": "https://docs.example.com/page?utm=1", "body": "duplicate"},
            {"title": "Forum Thread", "href": "https://reddit.com/r/local/thread", "body": "community discussion"},
        ][:max_results]

    def news(self, query, max_results=5):
        return []


class FakeResponse:
    def __init__(self, text="<html><title>T</title><body>Hello</body></html>", status_code=200, content_type="text/html"):
        self._text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.url = "https://example.com/final"
        self.encoding = "utf-8"

    def iter_content(self, chunk_size=65536, decode_unicode=False):
        yield self._text.encode("utf-8")


class ResearchTests(unittest.TestCase):
    def test_search_returns_structured_results(self):
        with mock.patch.object(search, "DDGS", FakeDDGS):
            result = search.search("local agents", max_results=2)
        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["title"], "Official Docs")
        self.assertEqual(result["results"][0]["provider"], "ddgs")
        self.assertEqual(result["results"][0]["rank"], 1)

    def test_fetch_handles_success(self):
        with mock.patch.object(reader.requests, "get", lambda *args, **kwargs: FakeResponse()):
            result = reader.fetch("https://example.com")
        self.assertTrue(result["success"])
        self.assertEqual(result["status_code"], 200)
        self.assertIn("Hello", result["html"])

    def test_fetch_handles_403_gracefully(self):
        with mock.patch.object(reader.requests, "get", lambda *args, **kwargs: FakeResponse("blocked", 403)):
            result = reader.fetch("https://example.com")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_message"], "HTTP 403")

    def test_fetch_handles_timeout(self):
        def timeout(*args, **kwargs):
            raise reader.requests.exceptions.Timeout()

        with mock.patch.object(reader.requests, "get", timeout):
            result = reader.fetch("https://example.com")
        self.assertFalse(result["success"])
        self.assertIn("timed out", result["error_message"])

    def test_extract_succeeds_from_mocked_html(self):
        html = "<html><title>Title</title><body><h1>Head</h1><p>Local agents are useful for coding.</p><pre>code()</pre></body></html>"
        result = reader.extract("https://example.com", html)
        self.assertTrue(result["extraction_success"])
        self.assertEqual(result["title"], "Title")
        self.assertIn("Head", result["headings"])
        self.assertTrue(result["code_blocks"])

    def test_large_page_truncation(self):
        html = "<html><body>" + ("word " * 3000) + "</body></html>"
        with mock.patch.object(reader, "MAX_PAGE_CHARS", 200):
            result = reader.extract("https://example.com", html)
        self.assertLessEqual(result["text_char_count"], 215)
        self.assertIn("[truncated]", result["main_text"])

    def test_research_fetches_and_extracts_top_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(research, "RESEARCH_CACHE_DIR", str(Path(tmp) / "cache")):
                with mock.patch.object(research, "search_query", lambda query, max_results=5: {"success": True, "query": query, "provider": "ddgs", "results": [{"title": "Docs", "url": "https://docs.example.com/a", "snippet": "local agents docs", "rank": 1, "provider": "ddgs"}]}):
                    with mock.patch.object(research, "fetch_page", lambda url: {"success": True, "url": url, "final_url": url, "html": "<html><title>Docs</title><body><h1>Docs</h1><p>Local agents inspect edit and verify code safely.</p></body></html>", "fetched_at": "now"}):
                        with mock.patch.object(research, "extract_page", reader.extract):
                            result = research.research("local agents", max_results=2, fetch_top=1, no_cache=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "research")
        self.assertTrue(result["sources"][0]["extraction_success"])
        self.assertTrue(result["answer_outline"]["main_findings"])
        self.assertEqual(result["response_mode"], "research_answer")
        self.assertIn("Short answer:", result["synthesized_answer"])
        self.assertIn("Sources:", result["synthesized_answer"])

    def test_research_output_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(research, "RESEARCH_CACHE_DIR", str(Path(tmp) / "cache-json")):
                with mock.patch.object(research, "search_query", lambda query, max_results=5: {"success": True, "query": query, "provider": "ddgs", "results": []}):
                    result = research.research("empty", no_cache=True)
        self.assertEqual(json.loads(json.dumps(result))["query"], "empty")

    def test_trending_query_expands_searches(self):
        variants = research.trend_query_variants("what is trending in local agents")
        self.assertGreaterEqual(len(variants), 4)
        self.assertTrue(any("news" in variant for variant in variants))

    def test_response_mode_detection(self):
        self.assertEqual(research.choose_response_mode("what is happening with local LLM agents?"), "research_answer")
        self.assertEqual(research.choose_response_mode("show me top 5 results for local LLM agents"), "search_results")

    def test_query_expansion_respects_max_searches(self):
        variants = research.query_variants("what is trending in local agents", max_searches=2)
        self.assertLessEqual(len(variants), 2)
        self.assertEqual(variants[0], "what is trending in local agents")

    def test_irrelevant_meanings_filtered_generally(self):
        results = [
            {"title": "Python package documentation", "url": "https://docs.python.org/pkg", "snippet": "software library package docs", "rank": 1},
            {"title": "Python snake health guide", "url": "https://animals.example/python", "snippet": "snake diet and habitat", "rank": 2},
        ]
        kept, filtered = research.filter_irrelevant_results("python package docs", research.rank_candidates("python package docs", results), minimum_score=0.35)
        self.assertEqual(kept[0]["title"], "Python package documentation")
        self.assertTrue(any("snake" in item["title"].lower() for item in filtered))

    def test_research_search_results_mode_does_not_synthesize_or_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(research, "RESEARCH_CACHE_DIR", str(Path(tmp) / "cache-search-mode")):
                with mock.patch.object(research, "search_query", lambda query, max_results=5: {"success": True, "query": query, "provider": "ddgs", "results": [{"title": "A", "url": "https://example.com/a", "snippet": "local agents", "rank": 1}]}):
                    with mock.patch.object(research, "fetch_page", mock.Mock(side_effect=AssertionError("fetch should not run"))):
                        result = research.research("top results for local agents", response_mode="search_results", no_cache=True)
        self.assertEqual(result["response_mode"], "search_results")
        self.assertEqual(result["synthesized_answer"], "")
        self.assertTrue(result["sources"][0]["snippet_only"])

    def test_snippet_only_sources_are_labeled_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(research, "RESEARCH_CACHE_DIR", str(Path(tmp) / "cache-snippet")):
                with mock.patch.object(research, "search_query", lambda query, max_results=5: {"success": True, "query": query, "provider": "ddgs", "results": [{"title": "A", "url": "https://example.com/a", "snippet": "local agents evidence", "rank": 1}]}):
                    with mock.patch.object(research, "fetch_page", lambda url: {"success": False, "error_message": "blocked"}):
                        result = research.research("local agents evidence", no_cache=True)
        self.assertTrue(result["sources"][0]["snippet_only"])
        self.assertTrue(any("snippet-only" in item for item in result["limitations"]))

    def test_duplicate_urls_dedupe(self):
        results = research.dedupe_results(
            [
                {"title": "A", "url": "https://example.com/a"},
                {"title": "A", "url": "https://example.com/a?x=1"},
                {"title": "B", "url": "https://example.com/b"},
            ]
        )
        self.assertEqual(len(results), 2)

    def test_no_cache_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}

            def fake_search(query, max_results=5):
                calls["count"] += 1
                return {"success": True, "query": query, "provider": "ddgs", "results": []}

            with mock.patch.object(research, "RESEARCH_CACHE_DIR", str(Path(tmp) / "cache-bypass")):
                with mock.patch.object(research, "search_query", fake_search):
                    research.research("cache me", response_mode="search_results", no_cache=False)
                    research.research("cache me", response_mode="search_results", no_cache=False)
                    research.research("cache me", response_mode="search_results", no_cache=True)
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
