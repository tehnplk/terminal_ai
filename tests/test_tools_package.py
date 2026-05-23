import unittest
import tempfile


class ToolsPackageTests(unittest.TestCase):
    def test_tools_package_exports_tool_registry_and_schema(self):
        import tools

        self.assertIn("execute_terminal_command", tools.available_functions)
        self.assertIn("read_text_file", tools.available_functions)
        self.assertTrue(any(
            item["function"]["name"] == "execute_terminal_command"
            for item in tools.tools_schema
        ))

    def test_tools_package_exports_generate_image_tool(self):
        import tools

        self.assertIn("generate_image", tools.available_functions)

        schema = next(
            item["function"]
            for item in tools.tools_schema
            if item["function"]["name"] == "generate_image"
        )

        self.assertIn("prompt", schema["parameters"]["required"])
        self.assertIn("filename", schema["parameters"]["properties"])
        self.assertIn("model", schema["parameters"]["properties"])
        self.assertIn("size", schema["parameters"]["properties"])

    def test_tools_package_exports_current_location_tool(self):
        import tools

        self.assertIn("current_location", tools.available_functions)

        schema = next(
            item["function"]
            for item in tools.tools_schema
            if item["function"]["name"] == "current_location"
        )

        self.assertEqual([], schema["parameters"].get("required", []))
        self.assertEqual({}, schema["parameters"]["properties"])

    def test_tools_package_exports_grep_tool(self):
        import tools

        self.assertIn("grep", tools.available_functions)

        schema = next(
            item["function"]
            for item in tools.tools_schema
            if item["function"]["name"] == "grep"
        )

        self.assertEqual(["query"], schema["parameters"]["required"])
        self.assertIn("path", schema["parameters"]["properties"])
        self.assertIn("mode", schema["parameters"]["properties"])
        self.assertIn("case_sensitive", schema["parameters"]["properties"])
        self.assertIn("max_results", schema["parameters"]["properties"])

    def test_grep_searches_absolute_paths_outside_current_directory(self):
        import os
        import tools

        with tempfile.TemporaryDirectory() as temp_dir:
            target_file = os.path.join(temp_dir, "outside.txt")
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("needle outside workspace\n")

            result = tools.grep("needle", path=temp_dir, mode="content", max_results=10)

        self.assertIn(target_file, result)
        self.assertIn(":1:", result)

    def test_configure_updates_shared_tool_runtime_state(self):
        import os
        import tools

        original_cwd = tools.get_cwd()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                target_file = os.path.join(temp_dir, "shared-state.txt")
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write("shared runtime state\n")

                tools.configure(initial_cwd=temp_dir)
                result = tools.grep("shared runtime", mode="content", max_results=10)

            self.assertIn(target_file, result)
        finally:
            tools.set_cwd(original_cwd)

    def test_main_uses_tools_package_registry(self):
        import main
        import tools

        self.assertIs(main.available_functions, tools.available_functions)
        self.assertIs(main.tools_schema, tools.tools_schema)


if __name__ == "__main__":
    unittest.main()
