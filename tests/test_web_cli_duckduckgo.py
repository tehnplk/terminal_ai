import unittest
import os
import tempfile
from unittest import mock

from tools import web_cli


class DuckDuckGoSearchTests(unittest.TestCase):
    def test_search_web_uses_duckduckgo_first(self):
        calls = []
        original_duckduckgo = getattr(web_cli, "search_with_duckduckgo", None)
        original_playwright = web_cli.search_with_playwright
        original_urllib = web_cli.search_with_urllib

        def fake_duckduckgo(query):
            calls.append(("duckduckgo", query))
            return "duckduckgo result"

        def fail_fallback(query):
            self.fail("search_web should not call fallback engines when DuckDuckGo returns results")

        web_cli.search_with_duckduckgo = fake_duckduckgo
        web_cli.search_with_playwright = fail_fallback
        web_cli.search_with_urllib = fail_fallback
        try:
            result = web_cli.search_web("terminal ai")
        finally:
            if original_duckduckgo is None:
                delattr(web_cli, "search_with_duckduckgo")
            else:
                web_cli.search_with_duckduckgo = original_duckduckgo
            web_cli.search_with_playwright = original_playwright
            web_cli.search_with_urllib = original_urllib

        self.assertEqual(result, "duckduckgo result")
        self.assertEqual(calls, [("duckduckgo", "terminal ai")])

    def test_format_duckduckgo_results_parses_html_results(self):
        self.assertTrue(hasattr(web_cli, "format_duckduckgo_results"))

        html = """
        <div class="result">
          <a class="result__a" href="https://example.com/page">Example Title</a>
          <a class="result__snippet">A useful search snippet.</a>
        </div>
        """

        output = web_cli.format_duckduckgo_results(html)

        self.assertIn("1. Title: Example Title", output)
        self.assertIn("URL: https://example.com/page", output)
        self.assertIn("Snippet: A useful search snippet.", output)

    def test_search_web_does_not_fallback_to_legacy_urllib_search(self):
        calls = []
        original_duckduckgo = web_cli.search_with_duckduckgo
        original_playwright = web_cli.search_with_playwright
        original_urllib = web_cli.search_with_urllib

        def fail_duckduckgo(query):
            calls.append("duckduckgo")
            raise RuntimeError("duckduckgo unavailable")

        def fail_playwright(query):
            calls.append("playwright")
            raise RuntimeError("browser search unavailable")

        def fake_urllib(query):
            calls.append("urllib")
            return "legacy result"

        web_cli.search_with_duckduckgo = fail_duckduckgo
        web_cli.search_with_playwright = fail_playwright
        web_cli.search_with_urllib = fake_urllib
        try:
            result = web_cli.search_web("terminal ai")
        finally:
            web_cli.search_with_duckduckgo = original_duckduckgo
            web_cli.search_with_playwright = original_playwright
            web_cli.search_with_urllib = original_urllib

        self.assertNotIn("urllib", calls)
        self.assertIn("Error performing web search", result)

    def test_fetch_web_uses_crawl4ai_first(self):
        calls = []
        original_crawl4ai = getattr(web_cli, "fetch_with_crawl4ai", None)
        original_playwright = web_cli.fetch_with_playwright
        original_urllib = web_cli.fetch_with_urllib

        def fake_crawl4ai(url):
            calls.append(("crawl4ai", url))
            return "# Clean markdown\n\nUseful page content."

        def fail_fallback(url):
            self.fail("fetch_web should not call fallback fetchers when Crawl4AI returns content")

        web_cli.fetch_with_crawl4ai = fake_crawl4ai
        web_cli.fetch_with_playwright = fail_fallback
        web_cli.fetch_with_urllib = fail_fallback
        try:
            result = web_cli.fetch_web("https://example.com")
        finally:
            if original_crawl4ai is None:
                delattr(web_cli, "fetch_with_crawl4ai")
            else:
                web_cli.fetch_with_crawl4ai = original_crawl4ai
            web_cli.fetch_with_playwright = original_playwright
            web_cli.fetch_with_urllib = original_urllib

        self.assertEqual(result, "# Clean markdown\n\nUseful page content.")
        self.assertEqual(calls, [("crawl4ai", "https://example.com")])

    def test_fetch_web_falls_back_from_crawl4ai_to_playwright_cli(self):
        calls = []
        original_crawl4ai = getattr(web_cli, "fetch_with_crawl4ai", None)
        original_playwright = web_cli.fetch_with_playwright
        original_urllib = web_cli.fetch_with_urllib

        def fail_crawl4ai(url):
            calls.append("crawl4ai")
            raise RuntimeError("crawl unavailable")

        def fake_playwright(url):
            calls.append("playwright")
            return "browser-rendered content"

        def fail_urllib(url):
            calls.append("urllib")
            raise AssertionError("fetch_web should not use urllib in the primary fallback chain")

        web_cli.fetch_with_crawl4ai = fail_crawl4ai
        web_cli.fetch_with_playwright = fake_playwright
        web_cli.fetch_with_urllib = fail_urllib
        try:
            result = web_cli.fetch_web("https://example.com")
        finally:
            if original_crawl4ai is None:
                delattr(web_cli, "fetch_with_crawl4ai")
            else:
                web_cli.fetch_with_crawl4ai = original_crawl4ai
            web_cli.fetch_with_playwright = original_playwright
            web_cli.fetch_with_urllib = original_urllib

        self.assertEqual(result, "browser-rendered content")
        self.assertEqual(calls, ["crawl4ai", "playwright"])

    def test_configure_sidecar_playwright_browsers_uses_runtime_browser_folder(self):
        original_value = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        with tempfile.TemporaryDirectory() as runtime_dir:
            browser_dir = os.path.join(runtime_dir, "ms-playwright")
            os.makedirs(browser_dir)

            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
            try:
                with mock.patch.object(web_cli, "get_runtime_base_dir", return_value=runtime_dir):
                    web_cli.configure_sidecar_playwright_browsers()

                self.assertEqual(os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), browser_dir)
            finally:
                if original_value is None:
                    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
                else:
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = original_value


if __name__ == "__main__":
    unittest.main()
