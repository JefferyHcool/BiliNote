# app/routers/note.py
import json
import os
import uuid
from concurrent.futures import as_completed
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from dataclasses import asdict

from app.db.video_task_dao import get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.constant import SUPPORT_PLATFORM_MAP
from app.services.task_serial_executor import task_serial_executor
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id, build_bilibili_page_url
from app.validators.video_url_validator import is_supported_video_url
from fastapi import APIRouter, Request, HTTPException
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
    # 客户端（如浏览器插件）已经在用户浏览器里抓到字幕，直接传给后端复用，
    # 跳过 download_subtitles 和音频转写。形如：
    #   {"language": "zh", "full_text": "...", "segments": [{"start","end","text"}, ...]}
    prefetched_transcript: Optional[dict] = None

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


class BatchVideoRequest(VideoRequest):
    """B 站多 P 批量生成请求。每一集仍会创建独立任务和独立笔记。"""
    p_start: int = Field(ge=1)
    p_end: int = Field(ge=1)


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
UPLOAD_DIR = "uploads"
BATCH_MAX_EPISODES = int(os.getenv("BATCH_MAX_EPISODES", "100"))


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)


def _persist_prefetched_transcript(task_id: str, transcript: dict) -> None:
    """把客户端预取的字幕写到 NoteGenerator 期望的转写缓存文件里。

    NoteGenerator.generate 会优先读 <task_id>_transcript.json，命中即跳过 download_subtitles
    与音频转写流程。要求字段：language(可空)/full_text/segments[{start,end,text}]
    """
    segments = transcript.get("segments") or []
    cleaned_segments = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        cleaned_segments.append({
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": text,
        })
    if not cleaned_segments:
        raise ValueError("prefetched_transcript 没有可用的 segments")

    full_text = transcript.get("full_text") or " ".join(s["text"] for s in cleaned_segments)
    payload = {
        "language": transcript.get("language") or "zh",
        "full_text": full_text,
        "segments": cleaned_segments,
    }

    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    target = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}_transcript.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"已写入客户端预取字幕缓存: {target} ({len(cleaned_segments)} 段)")


def execute_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                      link: bool = False, screenshot: bool = False, model_name: str = None,
                      provider_id: str = None, _format: list = None, style: str = None,
                      extras: str = None, video_understanding: bool = False,
                      video_interval: int = 0, grid_size: Optional[list] = None):
    """实际执行一条笔记任务；单任务和批量任务共用这一实现。"""
    if not model_name or not provider_id:
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    note = NoteGenerator().generate(
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
        grid_size=grid_size or [],
    )
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_to_file(task_id, note)

    # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().index_task(task_id)
    except Exception as e:
        logger.warning(f"向量索引失败（不影响笔记）: {e}")


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None,
                  provider_id: str = None, _format: list = None, style: str = None,
                  extras: str = None, video_understanding: bool = False,
                  video_interval: int = 0, grid_size: Optional[list] = None):
    logger.info(f"任务进入执行队列 (task_id={task_id})")
    return task_serial_executor.run(
        execute_note_task, task_id, video_url, platform, quality, link, screenshot,
        model_name, provider_id, _format, style, extras, video_understanding,
        video_interval, grid_size,
    )


def run_note_batch(task_specs: list[dict]) -> None:
    """把整批任务提交到全局线程池，和普通单任务共享并发上限。"""
    futures = {
        task_serial_executor.submit(execute_note_task, **spec): spec["task_id"]
        for spec in task_specs
    }
    logger.info(
        "批量任务已进入执行队列: total=%s, max_workers=%s",
        len(futures), task_serial_executor.max_workers,
    )
    for future in as_completed(futures):
        task_id = futures[future]
        try:
            future.result()
        except Exception as exc:
            logger.error("批量子任务异常 (task_id=%s): %s", task_id, exc, exc_info=True)
            NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message=str(exc))


def _submission_gate(data: VideoRequest):
    """单任务与批量任务共用的模型能力和转写模型就绪检查。"""
    if data.video_understanding and (
        str(data.provider_id).lower() == "deepseek"
        or str(data.model_name).lower().startswith("deepseek-")
    ):
        return R.error(
            msg="DeepSeek API 当前不支持图片输入，请关闭「视频理解」，或改用支持视觉的多模态模型",
            code=300103,
            data={"reason": "vision_model_required"},
        )

    if not data.prefetched_transcript:
        from app.services.transcriber_config_manager import TranscriberConfigManager
        readiness = TranscriberConfigManager().is_model_ready()
        if not readiness["ready"]:
            logger.warning(f"拒绝笔记任务：{readiness['reason']}")
            return R.error(
                msg=readiness["reason"],
                code=300102,
                data={
                    "reason": "transcriber_model_not_ready",
                    "transcriber_type": readiness["transcriber_type"],
                    "model_size": readiness["model_size"],
                    "downloading": readiness["downloading"],
                },
            )
    return None


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
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
    try:
        gate_error = _submission_gate(data)
        if gate_error:
            return gate_error

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

        # 客户端已经抓好字幕的话，写到转写缓存文件，NoteGenerator 的 cache-hit 逻辑会直接用上
        if data.prefetched_transcript:
            try:
                _persist_prefetched_transcript(task_id, data.prefetched_transcript)
            except Exception as e:
                logger.warning(f"写入预取字幕失败 (task_id={task_id}): {e}")

        background_tasks.add_task(run_note_task, task_id, data.video_url, data.platform, data.quality, data.link,
                                  data.screenshot, data.model_name, data.provider_id, data.format, data.style,
                                  data.extras, data.video_understanding, data.video_interval, data.grid_size)
        return R.success({"task_id": task_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate_note_batch")
def generate_note_batch(data: BatchVideoRequest, background_tasks: BackgroundTasks):
    """按 B 站分 P 范围创建独立笔记任务，并受控并发执行。"""
    try:
        if data.platform != "bilibili":
            return R.error(
                msg="批量分集生成目前仅支持哔哩哔哩多 P 视频",
                code=300104,
                data={"reason": "batch_platform_not_supported"},
            )
        if data.task_id:
            return R.error(
                msg="批量任务不支持复用单个 task_id，请新建批量任务",
                code=300104,
                data={"reason": "batch_retry_not_supported"},
            )
        if data.prefetched_transcript:
            return R.error(
                msg="批量任务不能为所有分集共用同一份预取字幕",
                code=300104,
                data={"reason": "batch_transcript_not_supported"},
            )
        if data.p_end < data.p_start:
            return R.error(
                msg="结束 P 必须大于或等于起始 P",
                code=300104,
                data={"reason": "invalid_page_range"},
            )

        count = data.p_end - data.p_start + 1
        if count > BATCH_MAX_EPISODES:
            return R.error(
                msg=f"单次最多生成 {BATCH_MAX_EPISODES} 集笔记",
                code=300104,
                data={"reason": "batch_too_large", "limit": BATCH_MAX_EPISODES},
            )

        gate_error = _submission_gate(data)
        if gate_error:
            return gate_error

        downloader = SUPPORT_PLATFORM_MAP["bilibili"]
        try:
            series = downloader.get_series_info(data.video_url)
        except Exception as exc:
            logger.warning("解析 B 站分集列表失败: %s", exc)
            return R.error(
                msg=f"无法读取 B 站分集列表：{exc}",
                code=300105,
                data={"reason": "series_parse_failed"},
            )

        if data.p_end > series["total"]:
            return R.error(
                msg=f"分集范围超出课程总集数（共 {series['total']} 集）",
                code=300104,
                data={
                    "reason": "page_range_exceeded",
                    "total": series["total"],
                },
            )

        batch_id = str(uuid.uuid4())
        task_specs = []
        response_tasks = []
        status_writer = NoteGenerator()
        for page_number in range(data.p_start, data.p_end + 1):
            task_id = str(uuid.uuid4())
            page = series["pages"][page_number - 1]
            page_url = build_bilibili_page_url(data.video_url, page_number)
            display_title = f"{series['title']} - P{page_number} {page['title']}"

            status_writer._update_status(task_id, TaskStatus.PENDING)
            task_specs.append({
                "task_id": task_id,
                "video_url": page_url,
                "platform": data.platform,
                "quality": data.quality,
                "link": bool(data.link),
                "screenshot": bool(data.screenshot),
                "model_name": data.model_name,
                "provider_id": data.provider_id,
                "_format": list(data.format or []),
                "style": data.style,
                "extras": data.extras,
                "video_understanding": bool(data.video_understanding),
                "video_interval": data.video_interval or 0,
                "grid_size": list(data.grid_size or []),
            })
            response_tasks.append({
                "task_id": task_id,
                "p": page_number,
                "video_url": page_url,
                "title": display_title,
            })

        background_tasks.add_task(run_note_batch, task_specs)
        logger.info(
            "创建批量笔记任务 batch_id=%s, range=P%s-P%s, total=%s",
            batch_id, data.p_start, data.p_end, len(task_specs),
        )
        return R.success({
            "batch_id": batch_id,
            "total": len(response_tasks),
            "max_parallel": task_serial_executor.max_workers,
            "series_title": series["title"],
            "tasks": response_tasks,
        })
    except Exception as exc:
        logger.error("创建批量笔记任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    status_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.status.json")
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")

    # 优先读状态文件
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status_content = json.load(f)

        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            # 成功状态的话，继续读取最终笔记内容
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    result_content = json.load(rf)
                return R.success({
                    "status": status,
                    "result": result_content,
                    "message": message,
                    "task_id": task_id
                })
            else:
                # 理论上不会出现，保险处理
                return R.success({
                    "status": TaskStatus.PENDING.value,
                    "message": "任务完成，但结果文件未找到",
                    "task_id": task_id
                })

        if status == TaskStatus.FAILED.value:
            return R.error(message or "任务失败", code=500)

        # 处理中状态
        return R.success({
            "status": status,
            "message": message,
            "task_id": task_id
        })

    # 没有状态文件，但有结果
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        return R.success({
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "task_id": task_id
        })

    # 什么都没有，默认PENDING
    return R.success({
        "status": TaskStatus.PENDING.value,
        "message": "任务排队中",
        "task_id": task_id
    })


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
