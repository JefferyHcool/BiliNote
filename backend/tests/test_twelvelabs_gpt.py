"""TwelveLabs Pegasus 视频理解后端测试。

无网络单测（默认运行）：用 stub 替掉 twelvelabs SDK，验证
  - GPTSource 携带 video_url 时调用 Pegasus URL analyze，返回其文本
  - 没有 video_url 时优雅抛错（本地文件 / 纯音频场景）

可选联网测试（仅设置 TWELVELABS_API_KEY 时运行）：对线上 Pegasus 实测一次。
"""
import importlib.util
import os
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_stubs(captured):
    """装一套最小 app.* + twelvelabs stub，让 twelvelabs_gpt 可在隔离环境里加载。"""
    app_mod = types.ModuleType("app")
    gpt_pkg = types.ModuleType("app.gpt")
    models_pkg = types.ModuleType("app.models")
    utils_pkg = types.ModuleType("app.utils")

    base_mod = types.ModuleType("app.gpt.base")

    class _GPT:
        pass

    base_mod.GPT = _GPT

    prompt_builder_mod = types.ModuleType("app.gpt.prompt_builder")

    def _generate_base_prompt(**kwargs):
        captured["prompt_kwargs"] = kwargs
        return "PROMPT_BODY"

    prompt_builder_mod.generate_base_prompt = _generate_base_prompt

    gpt_model_mod = types.ModuleType("app.models.gpt_model")

    class _GPTSource:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    gpt_model_mod.GPTSource = _GPTSource

    logger_mod = types.ModuleType("app.utils.logger")
    logger_mod.get_logger = lambda *_a, **_k: types.SimpleNamespace(
        info=lambda *a, **k: None, warning=lambda *a, **k: None
    )

    # twelvelabs SDK stub
    tl_mod = types.ModuleType("twelvelabs")
    tl_types_mod = types.ModuleType("twelvelabs.types")
    tl_vc_mod = types.ModuleType("twelvelabs.types.video_context")

    class _VideoContextUrl:
        def __init__(self, url):
            self.url = url

    tl_vc_mod.VideoContext_Url = _VideoContextUrl

    class _FakeTwelveLabs:
        def __init__(self, api_key):
            captured["api_key"] = api_key

        def analyze(self, *, model_name, video, prompt, temperature, max_tokens):
            captured["analyze"] = {
                "model_name": model_name,
                "url": video.url,
                "prompt": prompt,
                "max_tokens": max_tokens,
            }
            return types.SimpleNamespace(data="# 视频笔记\n来自画面与语音")

    tl_mod.TwelveLabs = _FakeTwelveLabs

    mods = {
        "app": app_mod,
        "app.gpt": gpt_pkg,
        "app.gpt.base": base_mod,
        "app.gpt.prompt_builder": prompt_builder_mod,
        "app.models": models_pkg,
        "app.models.gpt_model": gpt_model_mod,
        "app.utils": utils_pkg,
        "app.utils.logger": logger_mod,
        "twelvelabs": tl_mod,
        "twelvelabs.types": tl_types_mod,
        "twelvelabs.types.video_context": tl_vc_mod,
    }
    for name, mod in mods.items():
        sys.modules[name] = mod
    return _GPTSource


def _load_module():
    path = ROOT / "app" / "gpt" / "twelvelabs_gpt.py"
    spec = importlib.util.spec_from_file_location("twelvelabs_gpt", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTwelveLabsGPTUnit(unittest.TestCase):
    def setUp(self):
        self._saved = dict(sys.modules)
        self.captured = {}
        self.GPTSource = _install_stubs(self.captured)
        self.mod = _load_module()

    def tearDown(self):
        sys.modules.clear()
        sys.modules.update(self._saved)

    def test_summarize_calls_pegasus_with_url(self):
        gpt = self.mod.TwelveLabsGPT(api_key="sk-test")
        src = self.GPTSource(
            title="演示视频", tags="tag", _format=None, style=None, extras=None,
            video_url="https://example.com/v.mp4",
        )
        out = gpt.summarize(src)
        self.assertIn("视频笔记", out)
        self.assertEqual(self.captured["analyze"]["url"], "https://example.com/v.mp4")
        self.assertEqual(self.captured["analyze"]["model_name"], "pegasus1.5")
        # Pegasus 要求 max_tokens >= 512
        self.assertGreaterEqual(self.captured["analyze"]["max_tokens"], 512)

    def test_missing_url_raises(self):
        gpt = self.mod.TwelveLabsGPT(api_key="sk-test")
        src = self.GPTSource(title="本地", tags="", _format=None, style=None, extras=None, video_url=None)
        with self.assertRaises(ValueError):
            gpt.summarize(src)

    def test_empty_api_key_raises(self):
        with self.assertRaises(ValueError):
            self.mod.TwelveLabsGPT(api_key="")


@unittest.skipUnless(os.getenv("TWELVELABS_API_KEY"), "需要 TWELVELABS_API_KEY 才跑联网测试")
class TestTwelveLabsGPTLive(unittest.TestCase):
    def test_live_pegasus_url_analyze(self):
        # 真实 SDK，真实 API：Pegasus 直接看一段公开短视频返回文本笔记。
        from twelvelabs import TwelveLabs
        from twelvelabs.types.video_context import VideoContext_Url

        client = TwelveLabs(api_key=os.environ["TWELVELABS_API_KEY"])
        url = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4"
        resp = client.analyze(
            model_name="pegasus1.5",
            video=VideoContext_Url(url=url),
            prompt="In one sentence, what happens in this video?",
            max_tokens=512,
        )
        self.assertTrue((resp.data or "").strip())


if __name__ == "__main__":
    unittest.main()
