import unittest


class ToolsPackageTests(unittest.TestCase):
    def test_tools_package_exports_tool_registry_and_schema(self):
        import tools

        self.assertIn("execute_terminal_command", tools.available_functions)
        self.assertIn("read_text_file", tools.available_functions)
        self.assertTrue(any(
            item["function"]["name"] == "execute_terminal_command"
            for item in tools.tools_schema
        ))

    def test_main_uses_tools_package_registry(self):
        import main
        import tools

        self.assertIs(main.available_functions, tools.available_functions)
        self.assertIs(main.tools_schema, tools.tools_schema)


if __name__ == "__main__":
    unittest.main()
