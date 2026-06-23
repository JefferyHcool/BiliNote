"""Unit tests for app.transcriber.model_download_state（模型下载状态 + 失败原因跟踪）。

与 test_whisper_models 一样按文件路径隔离加载，并桩掉 app.utils.logger，
避免触发 app/__init__.py（会 import faster_whisper 等重依赖）。
"""
import importlib.util
import logging
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "transcriber" / "model_download_state.py"


def _load_module():
    if "app" not in sys.modules:
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = []
        sys.modules["app"] = app_pkg
    if "app.utils" not in sys.modules:
        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = []
        sys.modules["app.utils"] = utils_pkg
    if "app.utils.logger" not in sys.modules:
        logger_mod = types.ModuleType("app.utils.logger")
        logger_mod.get_logger = lambda name=None: logging.getLogger(name or "test")
        sys.modules["app.utils.logger"] = logger_mod
    spec = importlib.util.spec_from_file_location("model_download_state_under_test", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ds = _load_module()


class TestDownloadState(unittest.TestCase):
    def setUp(self):
        # 模块级单例，测试间互相隔离
        ds._status.clear()
        ds._errors.clear()

    def test_unknown_key_defaults(self):
        row = ds.status_row("tiny", downloaded=False)
        self.assertEqual(
            row,
            {"model_size": "tiny", "downloaded": False, "downloading": False, "failed": False},
        )
        self.assertNotIn("error", row)
        self.assertFalse(ds.is_downloading("tiny"))

    def test_downloading(self):
        ds.mark_downloading("tiny")
        self.assertTrue(ds.is_downloading("tiny"))
        row = ds.status_row("tiny", downloaded=False)
        self.assertTrue(row["downloading"])
        self.assertFalse(row["failed"])

    def test_failed_surfaces_error(self):
        ds.mark_failed("tiny", "401 Repository Not Found")
        row = ds.status_row("tiny", downloaded=False)
        self.assertTrue(row["failed"])
        self.assertFalse(row["downloading"])
        self.assertEqual(row["error"], "401 Repository Not Found")
        self.assertEqual(ds.get_error("tiny"), "401 Repository Not Found")

    def test_failed_without_message_has_no_error_field(self):
        ds.mark_failed("tiny")
        row = ds.status_row("tiny", downloaded=False)
        self.assertTrue(row["failed"])
        self.assertNotIn("error", row)

    def test_downloaded_overrides_failed(self):
        # 先失败后又下好：downloaded=True 时不应再回传 failed/error
        ds.mark_failed("tiny", "boom")
        row = ds.status_row("tiny", downloaded=True)
        self.assertFalse(row["failed"])
        self.assertTrue(row["downloaded"])
        self.assertNotIn("error", row)

    def test_mark_done_clears_error(self):
        ds.mark_failed("tiny", "boom")
        ds.mark_done("tiny")
        self.assertIsNone(ds.get_error("tiny"))
        row = ds.status_row("tiny", downloaded=True)
        self.assertFalse(row["failed"])

    def test_redownload_clears_previous_error(self):
        ds.mark_failed("tiny", "boom")
        ds.mark_downloading("tiny")  # 重新开始下载
        self.assertIsNone(ds.get_error("tiny"))
        row = ds.status_row("tiny", downloaded=False)
        self.assertTrue(row["downloading"])
        self.assertFalse(row["failed"])
        self.assertNotIn("error", row)

    def test_mlx_key_is_independent(self):
        # mlx 用 "mlx-{size}" 前缀，与 fast-whisper 的同名档位互不影响
        ds.mark_failed("mlx-tiny", "mlx boom")
        ds.mark_downloading("tiny")
        whisper_row = ds.status_row("tiny", downloaded=False)
        mlx_row = ds.status_row("tiny", downloaded=False, key="mlx-tiny")
        self.assertTrue(whisper_row["downloading"])
        self.assertFalse(whisper_row["failed"])
        self.assertTrue(mlx_row["failed"])
        self.assertEqual(mlx_row["error"], "mlx boom")


if __name__ == "__main__":
    unittest.main()
