import functools
import http.server
import os
import socketserver
import tempfile
import threading
import unittest

import tools


class DownloadFileTests(unittest.TestCase):
    def start_server(self, root_dir):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root_dir)
        server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def test_download_file_saves_url_to_download_folder(self):
        original_cwd = tools.get_cwd()
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as web_root:
            source_path = os.path.join(web_root, "hello.txt")
            with open(source_path, "wb") as f:
                f.write(b"hello from local server")

            server = self.start_server(web_root)
            try:
                tools.set_cwd(temp_dir)
                url = f"http://127.0.0.1:{server.server_address[1]}/hello.txt"

                result = tools.download_file(url)

                expected_path = os.path.join(temp_dir, "download", "hello.txt")
                self.assertTrue(os.path.exists(expected_path))
                with open(expected_path, "rb") as f:
                    self.assertEqual(b"hello from local server", f.read())
                self.assertIn(expected_path, result)
            finally:
                server.shutdown()
                server.server_close()
                tools.set_cwd(original_cwd)

    def test_download_file_sanitizes_filename_inside_download_folder(self):
        original_cwd = tools.get_cwd()
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as web_root:
            source_path = os.path.join(web_root, "safe.txt")
            with open(source_path, "wb") as f:
                f.write(b"safe content")

            server = self.start_server(web_root)
            try:
                tools.set_cwd(temp_dir)
                url = f"http://127.0.0.1:{server.server_address[1]}/safe.txt"

                result = tools.download_file(url, filename="../evil.txt")

                expected_path = os.path.join(temp_dir, "download", "evil.txt")
                escaped_path = os.path.join(temp_dir, "evil.txt")
                self.assertTrue(os.path.exists(expected_path))
                self.assertFalse(os.path.exists(escaped_path))
                self.assertIn(expected_path, result)
            finally:
                server.shutdown()
                server.server_close()
                tools.set_cwd(original_cwd)


if __name__ == "__main__":
    unittest.main()
