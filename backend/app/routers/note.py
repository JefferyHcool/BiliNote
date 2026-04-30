# app/routers/note.py
import json
import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, field_validator
from dataclasses import asdict

from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.task_serial_executor import task_serial_executor
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id
from app.validators.video_url_validator import is_supported_video_url
from fastapi import Request
from fastapi.responses import StreamingResponse
import httpx
from app.enmus.task_status_enums import TaskStatus

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()


class RecordRequest(BaseModel):
    video_id: str
    platform: str


class VideoRequest(BaseModel):
    video_url: str
    platform: str
    quality: DownloadQuality
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    model_name: str
    provider_id: str
    task_id: Optional[str] = None
    format: Optional[list] = []
    style: str = None
    extras: Optional[str]=None
    video_understanding: Optional[bool] = False
    video_interval: Optional[int] = 0
    grid_size: Optional[list] = []

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        url = str(v)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            # 是网络链接，继续用原有平台校验
            if not is_supported_video_url(url):
                raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                                message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)

        return v


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
UPLOAD_DIR = "uploads"


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
    temp_path = result_path.with_suffix(".json.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)
    os.replace(temp_path, result_path)


def _read_result_file(task_id: str) -> Optional[dict]:
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")
    if not os.path.exists(result_path):
        return None
    try:
        with open(result_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning("结果文件尚未写完整: task_id=%s, error=%s", task_id, exc)
        return None


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: list = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size=[]
                  ):

    if not model_name or not provider_id:
        NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message="请选择模型和提供者")
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    def _execute_note_task():
        return NoteGenerator().generate(
            video_url=video_url,
            platform=platform,
            quality=quality,
            task_id=task_id,
            model_name=model_name,
            provider_id=provider_id,
            link=link,
            _format=_format,
            style=style,
            extras=extras,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
        )

    try:
        logger.info(f"任务进入执行队列 (task_id={task_id})")
        note = task_serial_executor.run(_execute_note_task)
        logger.info(f"Note generated: {task_id}")
        if not note or not note.markdown:
            logger.warning(f"任务 {task_id} 执行失败，跳过保存")
            NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message="任务执行失败，未生成有效笔记")
            return
        save_note_to_file(task_id, note)
        NoteGenerator()._update_status(task_id, TaskStatus.SUCCESS)

        # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
        try:
            from app.services.vector_store import VectorStoreManager
            VectorStoreManager().index_task(task_id)
        except Exception as e:
            logger.warning(f"向量索引失败（不影响笔记）: {e}")
    except Exception as exc:
        logger.error(f"任务执行异常 (task_id={task_id}): {exc}", exc_info=True)
        NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message=str(exc))


@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        # TODO: 待持久化完成
        # NoteGenerator().delete_note(video_id=data.video_id, platform=data.platform)
        return R.success(msg='删除成功')
    except Exception as e:
        return R.error(msg=e)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb+") as f:
        f.write(await file.read())

    # 假设你静态目录挂载了 /uploads
    return R.success({"url": f"/uploads/{file.filename}"})


@router.post("/generate_note")
def generate_note(data: VideoRequest):
    try:

        video_id = extract_video_id(data.video_url, data.platform)
        # if not video_id:
        #     raise HTTPException(status_code=400, detail="无法提取视频 ID")
        # existing = get_task_by_video(video_id, data.platform)
        # if existing:
        #     return R.error(
        #         msg='笔记已生成，请勿重复发起',
        #
        #     )
        if data.task_id:
            # 如果传了task_id，说明是重试！
            task_id = data.task_id
            logger.info(f"重试模式，复用已有 task_id={task_id}")
        else:
            # 正常新建任务
            task_id = str(uuid.uuid4())

        # 统一先写入 PENDING，表示已进入队列等待串行执行
        NoteGenerator()._update_status(task_id, TaskStatus.PENDING)

        task_serial_executor.submit(
            run_note_task,
            task_id,
            data.video_url,
            data.platform,
            data.quality,
            data.link,
            data.screenshot,
            data.model_name,
            data.provider_id,
            data.format,
            data.style,
            data.extras,
            data.video_understanding,
            data.video_interval,
            data.grid_size,
        )
        return R.success({"task_id": task_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    status_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.status.json")

    # Result JSON is the source of truth. If it exists and parses, return
    # SUCCESS even if a stale status file says DOWNLOADING/SUMMARIZING.
    result_content = _read_result_file(task_id)
    if result_content is not None:
        return R.success({
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "message": "",
            "task_id": task_id
        })

    # 优先读状态文件
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8-sig") as f:
            status_content = json.load(f)

        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            return R.success({
                "status": TaskStatus.SAVING.value,
                "message": "结果文件写入中",
                "task_id": task_id
            })

        if status == TaskStatus.FAILED.value:
            return R.success({
                "status": TaskStatus.FAILED.value,
                "message": message or "任务失败",
                "task_id": task_id
            })

        if (
            status in {
                TaskStatus.PARSING.value,
                TaskStatus.DOWNLOADING.value,
                TaskStatus.TRANSCRIBING.value,
                TaskStatus.SUMMARIZING.value,
                TaskStatus.FORMATTING.value,
                TaskStatus.SAVING.value,
            }
            and not task_serial_executor.has_task(task_id)
        ):
            return R.success({
                "status": TaskStatus.FAILED.value,
                "message": f"任务已停止但状态停留在 {status}，请重新生成",
                "task_id": task_id
            })

        # 处理中状态
        return R.success({
            "status": status,
            "message": message,
            "task_id": task_id
        })

    # 什么都没有，默认PENDING
    return R.success({
        "status": TaskStatus.PENDING.value,
        "message": "任务排队中",
        "task_id": task_id
    })


@router.get("/task_queue_status")
def get_task_queue_status():
    return R.success(data=task_serial_executor.stats())


@router.get("/image_proxy")
async def image_proxy(request: Request, url: str):
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": request.headers.get("User-Agent", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  #  缓存一天
                    "Content-Type": content_type,
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
