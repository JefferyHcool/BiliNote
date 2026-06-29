import importlib.util
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "proxy_config_manager.py"
spec = importlib.util.spec_from_file_location("proxy_config_manager", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("proxy_config_manager module spec not found")
pcm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcm)
ProxyConfigManager = pcm.ProxyConfigManager

PROXY_ENV_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)


class TestApplyToEnv(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in PROXY_ENV_KEYS}
        for k in PROXY_ENV_KEYS:
            os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.cfg_path = os.path.join(self._tmp.name, "proxy.json")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def test_enabled_proxy_exported_to_env(self):
        mgr = ProxyConfigManager(filepath=self.cfg_path)
        mgr.update_config(enabled=True, url="http://127.0.0.1:7890")
        returned = mgr.apply_to_env()
        self.assertEqual(returned, "http://127.0.0.1:7890")
        # huggingface_hub / requests 只认环境变量，必须 export 进去
        for k in PROXY_ENV_KEYS:
            self.assertEqual(os.environ.get(k), "http://127.0.0.1:7890", k)

    def test_no_proxy_returns_none_and_no_env(self):
        mgr = ProxyConfigManager(filepath=self.cfg_path)
        returned = mgr.apply_to_env()
        self.assertIsNone(returned)
        for k in PROXY_ENV_KEYS:
            self.assertIsNone(os.environ.get(k), k)

    def test_env_fallback_is_idempotent(self):
        # 没配文件代理但环境已有代理：apply 应把它补全到所有别名（含小写）
        os.environ["HTTPS_PROXY"] = "http://10.0.0.1:1080"
        mgr = ProxyConfigManager(filepath=self.cfg_path)
        returned = mgr.apply_to_env()
        self.assertEqual(returned, "http://10.0.0.1:1080")
        self.assertEqual(os.environ.get("https_proxy"), "http://10.0.0.1:1080")


if __name__ == "__main__":
    unittest.main()
