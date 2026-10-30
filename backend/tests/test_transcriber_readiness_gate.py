"""Regression tests for the transcriber readiness gate (is_model_ready).

Background: the gate pulls model-existence checks from app.routers.config and the
download status from app.transcriber.model_download_state. That status used to be a
module-level `_downloading` dict inside routers.config; when it moved to its own
module the gate's import was not updated, so every call raised ImportError and hit
the "conservative pass" branch — `ready` became permanently True and the gate
silently stopped blocking tasks that would hang on a first-time model download.

These tests fail against that broken import, and lock the contract so the same
class of rename/move breaks loudly here instead of silently in production.
"""
import importlib.util
import json
import logging
import os
import pathlib
import shutil
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANAGER_PATH = ROOT / "app" / "services" / "transcriber_config_manager.py"


def _load_manager():
    """Load the manager by path with its app-level imports stubbed out.

    Stubbing (instead of importing the real packages) keeps this off app/__init__.py,
    which pulls in faster_whisper and the cookie managers.
    """
    # 桩包只为绕开 app/__init__.py，__path__ 仍指向真实目录，否则后面的测试（以及本文件
    # 的接口面检查）就 import 不到真实的 app.* 子模块了。
    for name, path in (("app", ROOT / "app"),
                       ("app.utils", ROOT / "app" / "utils"),
                       ("app.services", ROOT / "app" / "services")):
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(path)]
            sys.modules[name] = pkg
    if "app.utils.logger" not in sys.modules:
        logger_mod = types.ModuleType("app.utils.logger")
        logger_mod.get_logger = lambda name=None: logging.getLogger(name or "test")
        sys.modules["app.utils.logger"] = logger_mod

    spec = importlib.util.spec_from_file_location("tcm_under_test", MANAGER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadinessGateTestCase(unittest.TestCase):
    """Installs stub modules for the gate's two collaborators, then restores them."""

    def setUp(self):
        self.manager_module = _load_manager()
        self.tmp = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmp, "transcriber.json")
        self.saved = {}
        self.downloaded = set()
        self.downloading = set()
        for name in ("app.routers", "app.routers.config",
                     "app.transcriber", "app.transcriber.model_download_state"):
            self.saved[name] = sys.modules.get(name)

        config_stub = types.ModuleType("app.routers.config")
        config_stub._check_whisper_model_exists = (
            lambda size, subdir="whisper": size in self.downloaded)
        config_stub._check_mlx_whisper_model_exists = (
            lambda size: size in self.downloaded)

        mds_stub = types.ModuleType("app.transcriber.model_download_state")
        mds_stub.is_downloading = lambda key: key in self.downloading

        routers_pkg = types.ModuleType("app.routers")
        routers_pkg.__path__ = []
        transcriber_pkg = types.ModuleType("app.transcriber")
        transcriber_pkg.__path__ = []
        sys.modules.update({
            "app.routers": routers_pkg,
            "app.routers.config": config_stub,
            "app.transcriber": transcriber_pkg,
            "app.transcriber.model_download_state": mds_stub,
        })

    def tearDown(self):
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gate(self, transcriber_type="fast-whisper", model_size="medium"):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"transcriber_type": transcriber_type,
                       "whisper_model_size": model_size}, f)
        return self.manager_module.TranscriberConfigManager(
            filepath=self.config_path).is_model_ready()


class TestReadinessGate(ReadinessGateTestCase):

    def test_missing_local_model_blocks(self):
        """未下载的 fast-whisper 模型必须让门禁判定为不可用（修复前这里是 ready=True）。"""
        result = self.gate("fast-whisper", "medium")
        self.assertFalse(result["ready"])
        self.assertFalse(result["downloading"])
        self.assertIn("尚未下载就绪", result["reason"])
        self.assertIn("请先在", result["reason"])

    def test_download_in_progress_is_surfaced(self):
        """正在下载时 reason 要提示稍等，而不是让人重复发起任务。"""
        self.downloading.add("medium")
        result = self.gate("fast-whisper", "medium")
        self.assertFalse(result["ready"])
        self.assertTrue(result["downloading"])
        self.assertIn("正在下载中", result["reason"])

    def test_downloaded_model_is_ready(self):
        self.downloaded.add("large-v3-turbo")
        result = self.gate("fast-whisper", "large-v3-turbo")
        self.assertTrue(result["ready"])
        self.assertEqual(result["reason"], "")
        self.assertFalse(result["downloading"])

    def test_mlx_uses_size_prefixed_status_key(self):
        """mlx 分支的下载状态 key 是 mlx-{size}，不能和 whisper 的 key 撞车。"""
        self.downloading.add("mlx-medium")
        result = self.gate("mlx-whisper", "medium")
        self.assertFalse(result["ready"])
        self.assertTrue(result["downloading"])

    def test_online_transcribers_need_no_local_model(self):
        for ttype in ("bcut", "kuaishou", "groq"):
            with self.subTest(ttype=ttype):
                self.assertTrue(self.gate(ttype)["ready"])


class TestGateDependencySurface(unittest.TestCase):
    """门禁 import 的名字必须真的住在它 import 的模块里。

    这正是当初失效的方式：状态字典被搬走，调用方还在按旧名字 import。
    """

    def test_import_targets_exist(self):
        from app.routers.config import (  # noqa: F401
            _check_mlx_whisper_model_exists,
            _check_whisper_model_exists,
        )
        from app.transcriber.model_download_state import is_downloading  # noqa: F401

        self.assertTrue(callable(_check_whisper_model_exists))
        self.assertTrue(callable(_check_mlx_whisper_model_exists))
        self.assertTrue(callable(is_downloading))


if __name__ == "__main__":
    unittest.main()
