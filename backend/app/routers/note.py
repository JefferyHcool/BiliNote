# app/routers/note.py
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, validator, field_validator
from dataclasses import asdict

from app.db.video_task_dao import delete_task_by_task_id, get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.task_serial_executor import task_serial_executor
from app.services import task_cancellation
from app.services.task_cancellation import TaskCancelledError
from app.utils.note_helper import normalize_toc_timestamps
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id
from app.validators.video_url_validator import is_supported_video_url
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from app.enmus.task_status_enums import TaskStatus

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()


class RecordRequest(BaseModel):
    task_id: str
    video_id: Optional[str] = None
    platform: Optional[str] = None


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


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
UPLOAD_DIR = "uploads"
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _prepare_task_result(result_content: dict, include_transcript: bool) -> dict:
    prepared = dict(result_content)
    if isinstance(prepared.get("markdown"), str):
        prepared["markdown"] = normalize_toc_timestamps(prepared["markdown"])
    if isinstance(prepared.get("markdown_versions"), list):
        prepared["markdown_versions"] = [
            {
                **version,
                "content": normalize_toc_timestamps(version.get("content")),
            }
            for version in prepared["markdown_versions"]
            if isinstance(version, dict)
        ]
    if not include_transcript:
        prepared.pop("transcript", None)
    return prepared


def _make_markdown_version(task_id: str, content: str, generation_params: dict, created_at: str | None = None) -> dict:
    return {
        "ver_id": f"{task_id}-{uuid.uuid4()}",
        "content": content,
        "style": generation_params.get("style", "") if generation_params else "",
        "model_name": generation_params.get("model_name", "") if generation_params else "",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def _merge_markdown_versions(task_id: str, payload: dict, result_path: Path) -> None:
    current_markdown = payload.get("markdown")
    if not isinstance(current_markdown, str) or not current_markdown:
        return

    current_params = payload.get("generation_params", {}) or {}
    previous_versions = []
    previous_markdown = None
    previous_params = {}
    previous_created_at = None

    if result_path.exists():
        try:
            previous_data = json.loads(result_path.read_text(encoding="utf-8"))
            previous_markdown = previous_data.get("markdown")
            previous_params = previous_data.get("generation_params", {}) or {}
            previous_versions = previous_data.get("markdown_versions", []) or []
            previous_created_at = datetime.fromtimestamp(
                result_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat()
        except Exception as exc:
            logger.warning(f"读取旧笔记版本失败 ({task_id})：{exc}")

    versions = [_make_markdown_version(task_id, current_markdown, current_params)]
    seen = {current_markdown}

    if isinstance(previous_markdown, str) and previous_markdown and previous_markdown not in seen:
        matching_previous = next(
            (
                version for version in previous_versions
                if isinstance(version, dict) and version.get("content") == previous_markdown
            ),
            None,
        )
        versions.append(
            matching_previous
            or _make_markdown_version(task_id, previous_markdown, previous_params, previous_created_at)
        )
        seen.add(previous_markdown)

    for version in previous_versions:
        if not isinstance(version, dict):
            continue
        content = version.get("content")
        if not isinstance(content, str) or not content or content in seen:
            continue
        versions.append(version)
        seen.add(content)

    payload["markdown_versions"] = versions


def _delete_note_result_files(task_id: str) -> list[str]:
    if not task_id or Path(task_id).name != task_id:
        raise ValueError("无效的 task_id")

    base = Path(NOTE_OUTPUT_DIR)
    deleted = []

    # 删前读取音频缓存，拿到实际媒体文件路径
    audio_cache = base / f"{task_id}_audio.json"
    media_file_path: str | None = None
    video_file_path: str | None = None
    if audio_cache.exists():
        try:
            data = json.loads(audio_cache.read_text(encoding="utf-8"))
            media_file_path = data.get("file_path") or None
            video_file_path = data.get("video_path") or None
        except Exception:
            pass

    # 删除 note_results 里所有 {task_id}* 文件
    for path in base.glob(f"{task_id}*"):
        if not path.is_file():
            continue
        path.unlink()
        deleted.append(path.name)

    # 如果音频/视频不在 uploads 目录（即系统下载的缓存），且无其他任务引用，则一并删除
    upload_prefix = str(Path(UPLOAD_DIR).resolve())
    still_referenced = {
        json.loads(p.read_text(encoding="utf-8")).get("file_path")
        for p in base.glob("*_audio.json")
        if p.is_file()
    }

    for media_path in filter(None, [media_file_path, video_file_path]):
        p = Path(media_path)
        if not p.exists():
            continue
        # 跳过用户上传文件
        if str(p.resolve()).startswith(upload_prefix):
            continue
        # 跳过仍被其他任务引用的文件
        if media_path in still_referenced:
            continue
        try:
            p.unlink()
            deleted.append(p.name)
        except Exception as exc:
            logger.warning(f"删除媒体文件失败 ({media_path}): {exc}")

    return deleted


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
    payload = asdict(note)
    _merge_markdown_versions(task_id, payload, result_path)
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


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


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: list = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size=[]
                  ):

    if not model_name or not provider_id:
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

    model_queue_key = f"{provider_id}:{model_name}"
    logger.info(f"任务进入执行队列 (task_id={task_id}, queue_key={model_queue_key})")
    try:
        note = task_serial_executor.run(model_queue_key, _execute_note_task)
    except TaskCancelledError:
        task_cancellation.clear(task_id)
        logger.info(f"任务 {task_id} 已被取消，停止执行")
        return
    except Exception as e:
        logger.error(f"任务 {task_id} 执行异常: {e}")
        NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message=str(e))
        return
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        NoteGenerator()._update_status(task_id, TaskStatus.FAILED, message="笔记内容为空，生成失败")
        return
    note.generation_params = {
        "video_url": video_url,
        "platform": platform,
        "quality": str(quality),
        "model_name": model_name or "",
        "provider_id": provider_id or "",
        "style": style or "",
        "link": link,
        "screenshot": screenshot,
        "extras": extras or "",
        "video_understanding": video_understanding,
        "video_interval": video_interval,
        "grid_size": grid_size,
    }
    save_note_to_file(task_id, note)

    # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().index_task(task_id)
    except Exception as e:
        logger.warning(f"向量索引失败（不影响笔记）: {e}")


@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        task_id = data.task_id
        task_cancellation.cancel(task_id)
        deleted = _delete_note_result_files(task_id)
        delete_task_by_task_id(task_id)
        try:
            from app.services.vector_store import VectorStoreManager
            VectorStoreManager().delete_index(task_id)
        except Exception as exc:
            logger.warning(f"删除向量索引失败（已忽略）: {exc}")
        logger.info(f"删除任务 {task_id}，已移除文件: {deleted}")
        return R.success({"deleted_files": deleted}, msg='删除成功')
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return R.error(msg=str(e))


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_filename = Path(file.filename or "upload").name.replace("\\", "_")
    if not safe_filename or safe_filename in {".", ".."}:
        safe_filename = f"{uuid.uuid4().hex}.upload"

    upload_dir = Path(UPLOAD_DIR)
    file_location = upload_dir / safe_filename
    if file_location.exists():
        file_location = upload_dir / f"{file_location.stem}_{uuid.uuid4().hex[:8]}{file_location.suffix}"

    with file_location.open("wb") as f:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            f.write(chunk)

    # 假设你静态目录挂载了 /uploads
    return R.success({"url": f"/uploads/{file_location.name}"})


@router.post("/generate_note")
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
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


@router.get("/notes")
def get_notes():
    """
    返回所有已生成的笔记列表（跨浏览器共享用）
    """
    notes = []
    # 扫描所有 task 状态文件
    status_files = list(Path(NOTE_OUTPUT_DIR).glob("*.status.json"))
    # 排除 _markdown.status.json
    status_files = [f for f in status_files if not f.name.endswith("_markdown.status.json")]

    for sf in status_files:
        raw_name = sf.stem  # e.g. "xxx.status"
        task_id = raw_name.replace(".status", "")
        try:
            status_data = json.loads(sf.read_text(encoding="utf-8"))
            status = status_data.get("status", "UNKNOWN")

            # 读取笔记元数据
            result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
            generation_params = {}
            if result_path.exists():
                result_data = json.loads(result_path.read_text(encoding="utf-8"))
                audio_meta = result_data.get("audio_meta", {})
                title = audio_meta.get("title", task_id)
                platform = audio_meta.get("platform", "unknown")
                video_id = audio_meta.get("video_id", "")
                cover_url = audio_meta.get("cover_url", "")
                duration = audio_meta.get("duration", 0)
                generation_params = result_data.get("generation_params", {})
            else:
                title = task_id
                platform = "unknown"
                video_id = ""
                cover_url = ""
                duration = 0

            notes.append({
                "task_id": task_id,
                "status": status,
                "title": title,
                "platform": platform,
                "video_id": video_id,
                "cover_url": cover_url,
                "duration": duration,
                "created_at": sf.stat().st_ctime,
                "generation_params": generation_params,
            })
        except Exception as e:
            logger.warning(f"读取笔记 {task_id} 失败: {e}")
            continue

    # 按时间倒序
    notes.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return R.success(notes)


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str, include_transcript: bool = True):
    status_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.status.json")
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")

    # 优先读状态文件
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status_content = json.load(f)

        status = status_content.get("status")
        message = status_content.get("message", "")

        # 提取计时信息（无论什么状态都透传）
        timing = {
            "progress": status_content.get("progress", 0),
            "elapsed_time": status_content.get("elapsed_time", 0),
            "phase_durations": status_content.get("phase_durations", {}),
            "phase_started_at": status_content.get("phase_started_at"),
            "started_at": status_content.get("started_at"),
        }

        if status == TaskStatus.SUCCESS.value:
            # 成功状态的话，继续读取最终笔记内容
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    result_content = json.load(rf)
                result_content = _prepare_task_result(result_content, include_transcript)
                return R.success({
                    "status": status,
                    "result": result_content,
                    "message": message,
                    "task_id": task_id,
                    **timing,
                })
            else:
                # 理论上不会出现，保险处理
                return R.success({
                    "status": TaskStatus.PENDING.value,
                    "message": "任务完成，但结果文件未找到",
                    "task_id": task_id,
                })

        if status == TaskStatus.FAILED.value:
            return R.error(message or "任务失败", code=500)

        # 处理中状态
        return R.success({
            "status": status,
            "message": message,
            "task_id": task_id,
            **timing,
        })

    # 没有状态文件，但有结果
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        result_content = _prepare_task_result(result_content, include_transcript)
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
