from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.chat_service import chat as chat_service
from app.services.vector_store import VectorStoreManager
from app.utils.logger import get_logger
from app.utils.response import ResponseWrapper as R

logger = get_logger(__name__)

router = APIRouter()


class IndexRequest(BaseModel):
    task_id: str


class ChatMessage(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    task_id: str
    question: str
    history: list[ChatMessage] = []
    provider_id: str
    model_name: str


@router.post("/chat/index")
def index_task(data: IndexRequest):
    """为笔记建立向量索引。"""
    try:
        store = VectorStoreManager()
        store.index_task(data.task_id)
        return R.success(msg="索引完成")
    except Exception as e:
        logger.error(f"索引失败: {e}")
        return R.error(msg=f"索引失败: {str(e)}")


@router.get("/chat/status")
def chat_status(task_id: str):
    """检查笔记是否已建立向量索引。"""
    try:
        store = VectorStoreManager()
        indexed = store.is_indexed(task_id)
        return R.success(data={"indexed": indexed})
    except Exception as e:
        logger.error(f"查询索引状态失败: {e}")
        return R.success(data={"indexed": False})


@router.post("/chat/ask")
def ask_question(data: AskRequest):
    """基于笔记内容的 RAG 问答。"""
    try:
        history = [{"role": m.role, "content": m.content} for m in data.history]
        result = chat_service(
            task_id=data.task_id,
            question=data.question,
            history=history,
            provider_id=data.provider_id,
            model_name=data.model_name,
        )
        return R.success(data=result)
    except ValueError as e:
        return R.error(msg=str(e))
    except Exception as e:
        logger.error(f"Chat 问答失败: {e}", exc_info=True)
        return R.error(msg=f"问答失败: {str(e)}")
