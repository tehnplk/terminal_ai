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
        self.assertIn("copyfile('system_prompt.md', 'dist/system_prompt.md')", spec)


if __name__ == "__main__":
    unittest.main()
