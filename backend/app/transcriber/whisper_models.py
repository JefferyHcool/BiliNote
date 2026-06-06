"""fast-whisper 模型名 → 可加载标识（HF repo_id 或本地路径）的映射注册表。

背景：faster-whisper 加载时 `WhisperModel(model_size_or_path=...)` 接受三种入参——
内置 size 名、HF repo_id（含 "/"）、或本地模型目录（`os.path.isdir` 命中则直接用）。
此前后端把「size → Systran/faster-whisper-{size}」这层约定**隐式**散落在加载/下载/
检测三处，用户想用命名不符合该约定的模型（比如社区微调版、或自己下到本地的模型）就接不上。

本模块把映射**显式化 + 可配置**（对齐 mlx_whisper_transcriber.MLX_MODEL_MAP 的模式）：
  - 内置：size → Systran/faster-whisper-{size}
  - 自定义：用户在 config/whisper_models.json 登记 {名称: "<repo_id 或本地路径>"}
    （JSON 持久化；Docker 下随 config 卷持久化）

解析优先级（resolve）：自定义 > 内置 > 直通（含 "/" 当 repo_id；已存在目录当本地路径）。
加载 / 下载 / 完整性检测三处统一调用 resolve，路径不再各写各的。
"""
import json
import os
from pathlib import Path
from typing import Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)

# 内置模型：size → faster-whisper 兼容的 HF repo_id（CTranslate2 转换版，Systran 官方维护）。
BUILTIN_WHISPER_MODELS: Dict[str, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
}

# 前端下拉默认展示的内置档位（保持与历史 WHISPER_MODEL_SIZES 一致，不把 8 个全列出来）
DEFAULT_VISIBLE_BUILTINS: List[str] = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]


def is_local_target(target: str) -> bool:
    """判断解析出的 target 是本地路径而非 HF repo_id。

    HF repo_id 形如 'Org/Name'（恰一个斜杠、无前导斜杠、非已存在目录）。
    本地路径：绝对路径 / 以 . 或 ~ 开头 / 已存在的目录。
    """
    if not target:
        return False
    if os.path.isabs(target) or target.startswith(".") or target.startswith("~"):
        return True
    return os.path.isdir(target)


def hf_cache_dirname(repo_id: str) -> str:
    """huggingface_hub snapshot 的本地缓存目录名：Org/Name → models--Org--Name。"""
    return "models--" + repo_id.replace("/", "--")


class WhisperModelRegistry:
    """内置 + 用户自定义的 whisper 模型映射，自定义部分持久化到 JSON。"""

    def __init__(self, filepath: str = "config/whisper_models.json"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---- 持久化 ----
    def _read_custom(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception as e:
            logger.warning(f"读取自定义 whisper 模型配置失败，按空处理: {e}")
            return {}
        out: Dict[str, str] = {}
        for name, val in data.items():
            if isinstance(val, str) and val.strip():
                out[name] = val.strip()
            elif isinstance(val, dict) and isinstance(val.get("target"), str):
                out[name] = val["target"].strip()
        return out

    def _write_custom(self, data: Dict[str, str]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- 查询 ----
    def get_custom_models(self) -> Dict[str, str]:
        return self._read_custom()

    def visible_model_names(self) -> List[str]:
        """给前端下拉 / 下载状态用：默认可见内置档位 + 全部自定义名称。"""
        names = list(DEFAULT_VISIBLE_BUILTINS)
        for name in self._read_custom():
            if name not in names:
                names.append(name)
        return names

    def is_known(self, name: str) -> bool:
        try:
            self.resolve(name)
            return True
        except ValueError:
            return False

    def resolve(self, name: str) -> str:
        """模型名 → 可加载标识（HF repo_id 或本地路径）。

        优先级：自定义映射 > 内置映射 > 直通（含 "/" 的 repo_id / 已存在的本地目录）。
        无法识别时抛 ValueError。
        """
        name = (name or "").strip()
        custom = self._read_custom()
        if name in custom:
            return custom[name]
        if name in BUILTIN_WHISPER_MODELS:
            return BUILTIN_WHISPER_MODELS[name]
        # 直通：用户直接把 repo_id（含 "/"）或本地已存在目录当 model_size 传进来
        if "/" in name or os.path.isdir(name):
            return name
        raise ValueError(
            f"未知 whisper 模型 '{name}'。内置可选: {', '.join(BUILTIN_WHISPER_MODELS)}；"
            "或在「音频转写配置」添加自定义模型（HF repo_id 或本地路径）。"
        )

    # ---- 增删 ----
    def add_custom_model(self, name: str, target: str) -> Dict[str, str]:
        name = (name or "").strip()
        target = (target or "").strip()
        if not name or not target:
            raise ValueError("模型名称与目标（HF repo_id 或本地路径）都不能为空")
        if name in BUILTIN_WHISPER_MODELS:
            raise ValueError(f"'{name}' 与内置模型重名，请换一个名称")
        data = self._read_custom()
        data[name] = target
        self._write_custom(data)
        return data

    def remove_custom_model(self, name: str) -> Dict[str, str]:
        data = self._read_custom()
        data.pop((name or "").strip(), None)
        self._write_custom(data)
        return data


# 模块级单例
_registry = WhisperModelRegistry()


def get_registry() -> WhisperModelRegistry:
    return _registry


def resolve_whisper_model(name: str) -> str:
    return _registry.resolve(name)
