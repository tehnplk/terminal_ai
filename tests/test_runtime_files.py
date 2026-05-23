import os
import tempfile
import unittest
from unittest import mock

import main


class RuntimeFilesTests(unittest.TestCase):
    def test_find_external_runtime_file_prefers_app_dir(self):
        with tempfile.TemporaryDirectory() as app_dir, tempfile.TemporaryDirectory() as cwd:
            app_prompt = os.path.join(app_dir, "system_prompt.md")
            cwd_prompt = os.path.join(cwd, "system_prompt.md")
            with open(app_prompt, "w", encoding="utf-8") as f:
                f.write("app prompt")
            with open(cwd_prompt, "w", encoding="utf-8") as f:
                f.write("cwd prompt")

            with mock.patch.object(main, "get_app_dir", return_value=app_dir), mock.patch("os.getcwd", return_value=cwd):
                self.assertEqual(main.find_external_runtime_file("system_prompt.md"), app_prompt)

    def test_terminalai_spec_does_not_bundle_system_prompt(self):
        with open("TerminalAI.spec", "r", encoding="utf-8") as f:
            spec = f.read()

        self.assertIn("datas = []", spec)
        self.assertNotIn("('system_prompt.md', '.')", spec)
        self.assertIn("dist_root = os.path.abspath(DISTPATH", spec)
        self.assertIn("copyfile('system_prompt.md', os.path.join(dist_root, 'system_prompt.md'))", spec)
        self.assertIn("copyfile(os.path.join('config', 'playwright_config.json')", spec)
        self.assertNotIn("copyfile('.env',", spec)

    def test_playwright_config_lives_in_config_directory(self):
        from tools import web_cli

        config_path = web_cli.get_playwright_config_path()

        self.assertEqual(
            os.path.normpath(os.path.join(os.getcwd(), "config", "playwright_config.json")),
            os.path.normpath(config_path),
        )

    def test_tool_output_is_limited_before_reentering_model_context(self):
        output = main.limit_tool_output_for_context("example_tool", "x" * (main.MAX_TOOL_MESSAGE_CHARS + 50))

        self.assertLess(len(output), main.MAX_TOOL_MESSAGE_CHARS + 500)
        self.assertIn("TRUNCATED TOOL OUTPUT from example_tool", output)

    def test_current_date_time_context_is_added_from_tool(self):
        messages = [{"role": "system", "content": "base"}]

        with mock.patch.dict(main.available_functions, {
            "get_current_date_time": lambda: "Current date and time in Asia/Bangkok: 2026-05-23 12:34:56 UTC+07:00"
        }):
            main.append_current_date_time_context(messages)

        self.assertEqual("system", messages[-1]["role"])
        self.assertIn("get_current_date_time", messages[-1]["content"])
        self.assertIn("2026-05-23 12:34:56", messages[-1]["content"])

    def test_model_choices_include_openai_gpt_oss_120b_paid_variant(self):
        import model_choice

        self.assertIn("openai/gpt-oss-120b", model_choice.MODEL_CHOICES)
        self.assertIn("openai/gpt-oss-120b:free", model_choice.MODEL_CHOICES)

    def test_model_choices_include_openai_gpt_oss_20b(self):
        import model_choice

        self.assertIn("openai/gpt-oss-20b", model_choice.MODEL_CHOICES)

    def test_model_choices_include_deepseek_v4_flash_paid_variant(self):
        import model_choice

        self.assertIn("deepseek/deepseek-v4-flash", model_choice.MODEL_CHOICES)
        self.assertIn("deepseek/deepseek-v4-flash:free", model_choice.MODEL_CHOICES)


if __name__ == "__main__":
    unittest.main()
