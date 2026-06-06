"""Unit tests for app.transcriber.whisper_models（whisper 模型名→标识 的映射注册表）。

直接按文件路径加载被测模块，并桩掉 app.utils.logger，避免触发 app/__init__.py
（会 import faster_whisper / ctranslate2 等重依赖），使本测试无需安装转写依赖即可运行。
"""
import importlib.util
import logging
import os
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "transcriber" / "whisper_models.py"


def _load_module():
    if "app" not in sys.modules:
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = []  # 标记为 package
        sys.modules["app"] = app_pkg
    if "app.utils" not in sys.modules:
        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = []
        sys.modules["app.utils"] = utils_pkg
    if "app.utils.logger" not in sys.modules:
        logger_mod = types.ModuleType("app.utils.logger")
        logger_mod.get_logger = lambda name=None: logging.getLogger(name or "test")
        sys.modules["app.utils.logger"] = logger_mod
    spec = importlib.util.spec_from_file_location("whisper_models_under_test", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wm = _load_module()


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "whisper_models.json")
        self.reg = wm.WhisperModelRegistry(filepath=self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_builtin_resolves_to_systran(self):
        self.assertEqual(self.reg.resolve("tiny"), "Systran/faster-whisper-tiny")
        self.assertEqual(self.reg.resolve("large-v3-turbo"), "Systran/faster-whisper-large-v3-turbo")

    def test_passthrough_repo_id(self):
        # 用户直接把 HF repo_id 当 model_size 传进来（含 "/"）
        self.assertEqual(self.reg.resolve("SomeOrg/my-whisper-ct2"), "SomeOrg/my-whisper-ct2")

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.reg.resolve("definitely-not-a-model")

    def test_custom_overrides_and_persists(self):
        self.reg.add_custom_model("myhf", "someorg/whisper-ct2")
        self.assertEqual(self.reg.resolve("myhf"), "someorg/whisper-ct2")
        # 新实例读同一文件 → 确认持久化（Docker 下随 config 卷保留）
        reg2 = wm.WhisperModelRegistry(filepath=self.cfg)
        self.assertEqual(reg2.resolve("myhf"), "someorg/whisper-ct2")

    def test_custom_can_override_builtin_key_resolution(self):
        # 自定义优先级高于内置：把 "tiny" 强行指到别的 repo（resolve 层允许；add 层禁止重名）
        self.reg._write_custom({"tiny": "Other/tiny-ct2"})
        self.assertEqual(self.reg.resolve("tiny"), "Other/tiny-ct2")

    def test_local_path_resolution_and_detection(self):
        model_dir = os.path.join(self.tmp.name, "mymodel")
        os.makedirs(model_dir)
        self.reg.add_custom_model("local1", model_dir)
        self.assertEqual(self.reg.resolve("local1"), model_dir)
        self.assertTrue(wm.is_local_target(self.reg.resolve("local1")))

    def test_bare_existing_dir_passthrough(self):
        # 没登记、但直接传一个已存在目录 → 直通为本地路径
        model_dir = os.path.join(self.tmp.name, "bare")
        os.makedirs(model_dir)
        self.assertEqual(self.reg.resolve(model_dir), model_dir)

    def test_add_rejects_builtin_collision_and_empty(self):
        with self.assertRaises(ValueError):
            self.reg.add_custom_model("tiny", "x/y")  # 与内置重名
        with self.assertRaises(ValueError):
            self.reg.add_custom_model("", "x/y")
        with self.assertRaises(ValueError):
            self.reg.add_custom_model("ok", "")

    def test_remove(self):
        self.reg.add_custom_model("tmpm", "a/b")
        self.assertIn("tmpm", self.reg.get_custom_models())
        self.reg.remove_custom_model("tmpm")
        self.assertNotIn("tmpm", self.reg.get_custom_models())

    def test_visible_includes_builtin_and_custom(self):
        self.reg.add_custom_model("zzz", "a/b")
        names = self.reg.visible_model_names()
        self.assertIn("tiny", names)
        self.assertIn("large-v3", names)
        self.assertIn("zzz", names)

    def test_is_known(self):
        self.assertTrue(self.reg.is_known("base"))
        self.assertTrue(self.reg.is_known("Org/Name"))
        self.assertFalse(self.reg.is_known("nope-not-real"))


class TestHelpers(unittest.TestCase):
    def test_hf_cache_dirname(self):
        self.assertEqual(
            wm.hf_cache_dirname("Systran/faster-whisper-tiny"),
            "models--Systran--faster-whisper-tiny",
        )
        self.assertEqual(wm.hf_cache_dirname("Org/Name"), "models--Org--Name")

    def test_is_local_target(self):
        self.assertTrue(wm.is_local_target("/abs/path"))
        self.assertTrue(wm.is_local_target("./rel"))
        self.assertTrue(wm.is_local_target("~/home/model"))
        self.assertFalse(wm.is_local_target("Org/Name"))  # repo_id 不是本地路径
        self.assertFalse(wm.is_local_target(""))


if __name__ == "__main__":
    unittest.main()
