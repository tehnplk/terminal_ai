import unittest

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


if __name__ == "__main__":
    unittest.main()
