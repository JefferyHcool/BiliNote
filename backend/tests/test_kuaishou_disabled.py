"""
Coverage for the Kuaishou ASR disabled-state guard.

Background: 快手 (Kuaishou) 关闭了对外开放的 subtitle_generate 语音识别接口,
任何调用都会立刻返回 ``{"code": 501, "msg": "效果subtitle_generate禁用"}``。
旧实现默默地把这条错误抛出去,前端没有针对性的提示,用户只能从
"未知错误" 里猜原因。

本次改动在 KuaishouTranscriber._submit 开头直接抛带操作指引的
``RuntimeError``,而不是花时间把文件 POST 上去再被 501 拒掉。
"""
import pytest

from app.transcriber import kuaishou as kuaishou_module
from app.transcriber.kuaishou import KuaishouTranscriber


def test_kuaishou_submit_raises_clear_error(tmp_path):
    """_submit should raise immediately with a message that names the replacement engines."""
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"fake")

    t = KuaishouTranscriber()
    with pytest.raises(RuntimeError) as exc:
        t._submit(str(f))
    msg = str(exc.value)
    # 用户需要能根据这条提示自助切换到 bcut / faster-whisper
    assert "快手" in msg or "Kuaishou" in msg
    assert "已" in msg or "关闭" in msg or "禁用" in msg
    assert "bcut" in msg or "必剪" in msg
    assert "whisper" in msg.lower() or "Faster Whisper" in msg


def test_kuaishou_submit_does_not_make_network_call(monkeypatch, tmp_path):
    """短路上线后,不应再发起网络请求 (避免无谓的上传带宽消耗)."""
    called = {"n": 0}

    def fake_post(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("submit() should not reach requests.post after the shutdown guard")

    monkeypatch.setattr(kuaishou_module.requests, "post", fake_post)
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"fake")

    t = KuaishouTranscriber()
    with pytest.raises(RuntimeError):
        t._submit(str(f))
    assert called["n"] == 0
