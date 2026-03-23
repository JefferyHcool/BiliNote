"""
Chat function calling 工具定义与执行。
提供给 LLM 调用，用于主动查询视频原文、笔记、元信息。
"""

import json
import os
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")


def _load_note_data(task_id: str) -> Optional[dict]:
    path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 工具定义（OpenAI function calling 格式）──────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_transcript",
            "description": "查询视频原始转录文本。可按时间范围筛选、按关键词搜索、或获取指定位置的内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "number",
                        "description": "起始时间（秒），例如 0 表示视频开头，60 表示第1分钟",
                    },
                    "end_time": {
                        "type": "number",
                        "description": "结束时间（秒），不传则到末尾",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，返回包含该关键词的转录片段",
                    },
                    "position": {
                        "type": "string",
                        "enum": ["start", "end"],
                        "description": "快捷位置：start=视频开头前30句，end=视频结尾后30句",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_video_info",
            "description": "获取视频的完整元信息，包括标题、作者、简介、标签、时长、播放量等。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_note_content",
            "description": "获取 AI 生成的完整笔记内容（Markdown 格式）。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── 工具执行 ──────────────────────────────────────────────────

def execute_tool(task_id: str, tool_name: str, arguments: dict) -> str:
    """执行工具调用，返回结果字符串。"""
    data = _load_note_data(task_id)
    if not data:
        return json.dumps({"error": "笔记数据不存在"}, ensure_ascii=False)

    if tool_name == "lookup_transcript":
        return _lookup_transcript(data, arguments)
    elif tool_name == "get_video_info":
        return _get_video_info(data)
    elif tool_name == "get_note_content":
        return _get_note_content(data)
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)


def _lookup_transcript(data: dict, args: dict) -> str:
    segments = data.get("transcript", {}).get("segments", [])
    if not segments:
        return json.dumps({"error": "没有转录数据"}, ensure_ascii=False)

    position = args.get("position")
    start_time = args.get("start_time")
    end_time = args.get("end_time")
    keyword = args.get("keyword", "").strip()

    # 快捷位置
    if position == "start":
        filtered = segments[:30]
    elif position == "end":
        filtered = segments[-30:]
    else:
        filtered = segments

    # 时间筛选
    if start_time is not None:
        filtered = [s for s in filtered if s.get("end", 0) >= start_time]
    if end_time is not None:
        filtered = [s for s in filtered if s.get("start", 0) <= end_time]

    # 关键词筛选
    if keyword:
        filtered = [s for s in filtered if keyword.lower() in s.get("text", "").lower()]

    # 限制返回量，避免 token 爆炸
    if len(filtered) > 50:
        filtered = filtered[:50]
        truncated = True
    else:
        truncated = False

    result = {
        "total_segments": len(data.get("transcript", {}).get("segments", [])),
        "returned": len(filtered),
        "truncated": truncated,
        "segments": [
            {
                "start": round(s.get("start", 0), 1),
                "end": round(s.get("end", 0), 1),
                "text": s.get("text", ""),
            }
            for s in filtered
        ],
    }
    return json.dumps(result, ensure_ascii=False)


def _get_video_info(data: dict) -> str:
    am = data.get("audio_meta", {})
    raw = am.get("raw_info", {}) or {}

    info = {
        "title": am.get("title") or raw.get("title", ""),
        "uploader": raw.get("uploader", ""),
        "description": raw.get("description", "")[:1000],
        "tags": raw.get("tags", [])[:20] if isinstance(raw.get("tags"), list) else [],
        "duration_seconds": am.get("duration", 0),
        "platform": am.get("platform", ""),
        "video_id": am.get("video_id", ""),
        "url": raw.get("webpage_url", ""),
        "view_count": raw.get("view_count"),
        "like_count": raw.get("like_count"),
        "comment_count": raw.get("comment_count"),
    }
    # 去除 None 值
    info = {k: v for k, v in info.items() if v is not None and v != ""}
    return json.dumps(info, ensure_ascii=False)


def _get_note_content(data: dict) -> str:
    md = data.get("markdown", "")
    if isinstance(md, list):
        # 多版本，取最新
        md = md[-1].get("content", "") if md else ""
    # 限制长度
    if len(md) > 5000:
        md = md[:5000] + "\n\n... (内容过长已截断)"
    return json.dumps({"markdown": md}, ensure_ascii=False)
