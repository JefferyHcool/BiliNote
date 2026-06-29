"""内置供应商的回退模型清单 + 模型对象归一化（issue #417）。

背景：设置页的「模型下拉」依赖 provider 的 `/v1/models` 动态列表。但这个接口
并不可靠——

  - DeepSeek 的 `/models` 在部分账号/网络下取不到，下拉直接空白；
  - 不少自建 OpenAI 兼容网关压根不实现 `/models`；
  - key 没有 inference 权限时也可能返回异常。

（`OpenAI_compatible_provider.test_connection` 的注释里已经记录过这个不可靠性。）

所以对**内置供应商**额外维护一份已知可用清单兜底：动态拿不到时退回这份清单，
保证下拉永远有内容，用户不至于卡在空列表。清单数据写在
`app/db/builtin_providers.json` 的 `models` 字段里，单一数据源，方便维护。

本模块只依赖标准库，便于单测隔离加载（不触发 app 包的重依赖导入链）。
"""
import json
from pathlib import Path
from typing import Any, List, Optional

# builtin_providers.json 与本文件同属 backend/app 下：app/services/ -> app/db/
_BUILTIN_JSON = Path(__file__).resolve().parent.parent / "db" / "builtin_providers.json"


def _load_builtin() -> List[dict]:
    try:
        return json.loads(_BUILTIN_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


def builtin_fallback_models(provider: Optional[dict]) -> List[str]:
    """按 provider 的 id 或 name（忽略大小写）匹配内置清单里的 models 字段。

    自定义供应商（DB 里 id 是 uuid）通常 name 也对得上内置名，所以 id / name 都试。
    匹配不到或没配 models 返回空列表。
    """
    if not provider:
        return []
    keys = {str(provider.get("id", "")).strip().lower(), str(provider.get("name", "")).strip().lower()}
    keys.discard("")
    if not keys:
        return []
    for p in _load_builtin():
        candidate = {str(p.get("id", "")).strip().lower(), str(p.get("name", "")).strip().lower()}
        if keys & candidate:
            models = p.get("models") or []
            return [str(m) for m in models if m]
    return []


def normalize_models(raw: Any) -> List[dict]:
    """把 SDK 返回值统一成 [{'id', 'object', 'owned_by', ...}] 列表。

    兼容三种形态：
      - openai SDK 的 SyncPage（取 .data）
      - 普通 list（含旧代码失败时返回的 []，绝不能再 .data）
      - list 里既可能是 pydantic Model 也可能是 dict
    """
    if raw is None:
        return []
    data = getattr(raw, "data", raw)  # SyncPage -> .data；list/tuple 原样
    if not isinstance(data, (list, tuple)):
        return []
    out: List[dict] = []
    for m in data:
        if isinstance(m, dict):
            d = m
        elif hasattr(m, "model_dump"):
            d = m.model_dump()
        elif hasattr(m, "dict"):
            d = m.dict()
        else:
            d = {"id": getattr(m, "id", None)}
        if d.get("id"):
            out.append(d)
    return out


def as_model_dicts(model_ids: List[str], owned_by: str = "") -> List[dict]:
    """把模型名列表包成与 SDK Model 一致的 dict，前端下拉直接复用同一套渲染。"""
    return [
        {"id": mid, "object": "model", "created": None, "owned_by": owned_by}
        for mid in model_ids
    ]
