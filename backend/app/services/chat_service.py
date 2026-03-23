from typing import Optional

from app.gpt.gpt_factory import GPTFactory
from app.models.model_config import ModelConfig
from app.services.provider import ProviderService
from app.services.vector_store import VectorStoreManager
from app.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是一个视频笔记问答助手。你可以参考两种来源回答用户的问题：
1. [笔记] — AI 生成的视频摘要笔记
2. [转录] — 视频原始语音转录文本（含时间戳）

以下是检索到的相关内容：

--- 相关内容 ---
{context}
---

回答要求：
- 优先使用转录原文回答关于视频具体内容、原话、细节的问题
- 优先使用笔记回答关于总结、要点、结构的问题
- 如果确实没有相关信息，请诚实告知
- 请用中文回答，保持简洁准确"""


def _build_context(chunks: list[dict]) -> str:
    """将检索到的片段拼接为上下文文本。"""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source_type = meta.get("source_type", "unknown")
        if source_type == "markdown":
            label = f"[笔记 - {meta.get('section_title', '')}]"
        else:
            start = meta.get("start_time", 0)
            end = meta.get("end_time", 0)
            label = f"[转录 - {start:.0f}s~{end:.0f}s]"
        parts.append(f"{label}\n{chunk['text']}")
    return "\n\n".join(parts)


def _build_sources(chunks: list[dict]) -> list[dict]:
    """从检索片段中提取来源信息。"""
    sources = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        source = {
            "text": chunk["text"][:200],
            "source_type": meta.get("source_type", "unknown"),
        }
        if meta.get("section_title"):
            source["section_title"] = meta["section_title"]
        if meta.get("start_time") is not None:
            source["start_time"] = meta["start_time"]
        if meta.get("end_time") is not None:
            source["end_time"] = meta["end_time"]
        sources.append(source)
    return sources


def chat(
    task_id: str,
    question: str,
    history: list[dict],
    provider_id: str,
    model_name: str,
) -> dict:
    """
    RAG 问答：检索相关片段 → 构建 prompt → 调用 LLM → 返回答案 + 来源。

    Returns:
        {"answer": str, "sources": list[dict]}
    """
    vector_store = VectorStoreManager()

    # 1. 检索相关片段
    chunks = vector_store.query(task_id, question, n_results=5)
    if not chunks:
        return {
            "answer": "暂未找到相关笔记内容，请确认笔记已生成并完成索引。",
            "sources": [],
        }

    # 2. 构建上下文和来源
    context = _build_context(chunks)
    sources = _build_sources(chunks)

    # 3. 构建消息
    system_msg = SYSTEM_PROMPT.format(context=context)
    messages = [{"role": "system", "content": system_msg}]

    # 加入历史对话（最近 10 轮）
    for msg in history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    # 4. 调用 LLM
    provider = ProviderService.get_provider_by_id(provider_id)
    if not provider:
        raise ValueError(f"未找到模型供应商: {provider_id}")

    config = ModelConfig(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        model_name=model_name,
        provider=provider["type"],
        name=provider["name"],
    )
    gpt = GPTFactory.from_config(config)

    logger.info(f"Chat RAG: task_id={task_id}, provider={provider['name']}, model={model_name}")

    response = gpt.client.chat.completions.create(
        model=gpt.model,
        messages=messages,
        temperature=0.7,
    )

    answer = response.choices[0].message.content

    return {"answer": answer, "sources": sources}
