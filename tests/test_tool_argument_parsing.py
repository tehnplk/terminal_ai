import unittest

import main


class ToolArgumentParsingTests(unittest.TestCase):
    def test_invalid_tool_arguments_return_error_message(self):
        args, error = main.parse_tool_arguments("create_html_file", '{"filename": "stroke_plk.html", "html_content": "<html>')

        self.assertEqual(args, {})
        self.assertIn("Invalid JSON arguments for tool 'create_html_file'", error)
        self.assertIn("Unterminated string", error)

    def test_valid_tool_arguments_parse_normally(self):
        args, error = main.parse_tool_arguments("web_fetch", '{"url": "https://example.com"}')

        self.assertIsNone(error)
        self.assertEqual(args, {"url": "https://example.com"})


if __name__ == "__main__":
    unittest.main()
