"""Regression coverage for Bilibili yt-dlp proxy configuration."""
import ast
import pathlib
import unittest
from unittest.mock import patch

from app.downloaders import bilibili_downloader


MODULE_PATH = pathlib.Path(bilibili_downloader.__file__)


class TestBilibiliProxy(unittest.TestCase):
    def test_apply_proxy_sets_configured_proxy(self):
        options = {}
        with patch.object(
            bilibili_downloader.ProxyConfigManager,
            "get_proxy_url",
            return_value="http://127.0.0.1:17890",
        ):
            result = bilibili_downloader._apply_proxy(options)

        self.assertIs(result, options)
        self.assertEqual(options["proxy"], "http://127.0.0.1:17890")

    def test_all_ytdlp_paths_apply_proxy(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        helper_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_apply_proxy"
        ]
        self.assertEqual(len(helper_calls), 3)


if __name__ == "__main__":
    unittest.main()
