import unittest
import tempfile
import json


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

    def test_terminal_subprocess_env_removes_parent_python_runtime_vars(self):
        import os
        from unittest import mock

        from tools.terminal import build_subprocess_env

        with mock.patch.dict(os.environ, {
            "PYTHONHOME": "bad-home",
            "PYTHONPATH": "bad-path",
            "PYTHONEXECUTABLE": "bad-exe",
            "UV_INTERNAL__PYTHONHOME": "bad-uv-home",
            "NORMAL_VAR": "kept",
        }):
            env = build_subprocess_env()

        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONEXECUTABLE", env)
        self.assertNotIn("UV_INTERNAL__PYTHONHOME", env)
        self.assertEqual("kept", env["NORMAL_VAR"])

    def test_terminal_compacts_notebooklm_query_json_for_agent_context(self):
        from tools.terminal import compact_stdout_for_agent

        raw = json.dumps({
            "value": {
                "answer": "Short answer from NotebookLM.",
                "conversation_id": "conversation-1",
                "sources_used": ["source-1"],
                "citations": {"1": "source-1"},
                "references": [{"cited_text": "x" * 50000}],
            }
        })

        result = compact_stdout_for_agent("nlm notebook query abc question", raw)

        self.assertIn("Short answer from NotebookLM.", result)
        self.assertIn("Conversation ID: conversation-1", result)
        self.assertIn("Sources used: source-1", result)
        self.assertIn("Raw references were omitted", result)
        self.assertNotIn("x" * 100, result)

    def test_main_uses_tools_package_registry(self):
        import main
        import tools

        self.assertIs(main.available_functions, tools.available_functions)
        self.assertIs(main.tools_schema, tools.tools_schema)


if __name__ == "__main__":
    unittest.main()
