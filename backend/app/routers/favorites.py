import logging
import re
import json
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field, field_validator

from app.enmus.note_enums import DownloadQuality
from app.services.cookie_manager import CookieConfigManager
from app.utils.response import ResponseWrapper as R

router = APIRouter()

FAVORITE_API = "https://api.bilibili.com/x/v3/fav/resource/list"
VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"
PAGE_SIZE = 20
logger = logging.getLogger(__name__)


class FavoritePageRequest(BaseModel):
    favorite_url: str = Field(min_length=1, max_length=2048)
    page: int = Field(default=1, ge=1, le=10000)


class FavoriteBatchVideo(BaseModel):
    video_key: str = Field(min_length=1, max_length=128)
    bvid: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=500)
    video_url: str = Field(min_length=1, max_length=2048)
    page_number: int | None = Field(default=None, ge=1)
    page_count: int | None = Field(default=None, ge=1)
    resume_task_id: str | None = Field(default=None, max_length=128)

    @field_validator("video_url")
    @classmethod
    def validate_bilibili_video_url(cls, value: str) -> str:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme not in {"http", "https"}
            or not (hostname == "bilibili.com" or hostname.endswith(".bilibili.com"))
            or not parsed.path.startswith("/video/")
        ):
            raise ValueError("收藏夹批次只支持 Bilibili 视频链接")
        return value

    @field_validator("resume_task_id")
    @classmethod
    def validate_resume_task_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError("无效的已有任务编号") from exc


class FavoriteBatchFolder(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2048)


class FavoriteBatchConfig(BaseModel):
    quality: DownloadQuality = DownloadQuality.medium
    model_name: str = Field(min_length=1, max_length=200)
    provider_id: str = Field(min_length=1, max_length=200)
    screenshot: bool = False
    link: bool = False
    format: list[str] = Field(default_factory=list, max_length=20)
    style: str | None = Field(default=None, max_length=100)
    extras: str | None = Field(default=None, max_length=10000)
    video_understanding: bool = False
    video_interval: int = Field(default=0, ge=0, le=3600)
    grid_size: list[int] = Field(default_factory=list, max_length=2)


class FavoriteBatchStartRequest(BaseModel):
    favorite_folder: FavoriteBatchFolder
    videos: list[FavoriteBatchVideo] = Field(min_length=1, max_length=5000)
    config: FavoriteBatchConfig


_favorite_batches: dict[str, dict] = {}
_favorite_batches_lock = threading.RLock()


def _batch_snapshot(batch: dict) -> dict:
    snapshot = deepcopy(batch)
    snapshot.pop("worker_active", None)
    return snapshot


def _write_batch_task_status(task_id: str, status: str, message: str | None = None) -> None:
    from app.services.note import NOTE_OUTPUT_DIR

    output_dir = Path(NOTE_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / f"{task_id}.status.json"
    payload = {"status": status}
    if message:
        payload["message"] = message
    temp_path = status_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(status_path)


def _task_status_message(task_id: str) -> str | None:
    return _read_task_status(task_id).get("message")


def _read_task_status(task_id: str) -> dict:
    from app.services.note import NOTE_OUTPUT_DIR

    status_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.status.json"
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _wait_for_existing_task(task_id: str) -> tuple[bool, str | None]:
    from app.services.note import NOTE_OUTPUT_DIR

    output_dir = Path(NOTE_OUTPUT_DIR)
    status_path = output_dir / f"{task_id}.status.json"
    result_path = output_dir / f"{task_id}.json"
    while True:
        status_data = _read_task_status(task_id)
        status = status_data.get("status")
        if status == "FAILED":
            return False, status_data.get("message") or "笔记生成失败"
        if status == "SUCCESS" and result_path.exists():
            return True, None
        time.sleep(2)


def _run_favorite_video(video: dict, config: dict):
    from app.enmus.note_enums import DownloadQuality
    from app.routers.note import run_note_task_tracked

    return run_note_task_tracked(
        video["task_id"],
        video["video_url"],
        "bilibili",
        DownloadQuality(config["quality"]),
        config["link"],
        config["screenshot"],
        config["model_name"],
        config["provider_id"],
        config["format"],
        config["style"],
        config["extras"],
        config["video_understanding"],
        config["video_interval"],
        config["grid_size"],
    )


def run_favorite_batch(batch_id: str) -> None:
    """Run accepted favorite videos sequentially without depending on a browser session."""
    try:
        while True:
            with _favorite_batches_lock:
                batch = _favorite_batches.get(batch_id)
                if not batch:
                    return

                if batch["next_index"] >= len(batch["videos"]):
                    batch["state"] = "done"
                    batch["current_index"] = None
                    batch["pause_requested"] = False
                    batch["worker_active"] = False
                    return

                if batch["pause_requested"]:
                    batch["state"] = "paused"
                    batch["current_index"] = None
                    batch["pause_requested"] = False
                    batch["worker_active"] = False
                    return

                index = batch["next_index"]
                video = deepcopy(batch["videos"][index])
                config = deepcopy(batch["config"])
                batch["state"] = "running"
                batch["current_index"] = index
                batch["videos"][index]["status"] = "running"

            try:
                if video.get("resume_task_id"):
                    from app.routers.note import is_note_task_active
                    from app.services.note import NOTE_OUTPUT_DIR

                    status_data = _read_task_status(video["task_id"])
                    result_path = Path(NOTE_OUTPUT_DIR) / f"{video['task_id']}.json"
                    if is_note_task_active(video["task_id"]):
                        succeeded, message = _wait_for_existing_task(video["task_id"])
                    elif status_data.get("status") == "SUCCESS" and result_path.exists():
                        succeeded, message = True, None
                    elif status_data.get("status") == "FAILED":
                        succeeded = False
                        message = status_data.get("message") or "笔记生成失败"
                    else:
                        result = _run_favorite_video(video, config)
                        succeeded = bool(result and result.markdown)
                        message = None if succeeded else _task_status_message(video["task_id"]) or "笔记生成失败"
                else:
                    result = _run_favorite_video(video, config)
                    succeeded = bool(result and result.markdown)
                    message = None if succeeded else _task_status_message(video["task_id"]) or "笔记生成失败"
            except Exception as exc:
                logger.exception("收藏夹批次任务异常 (batch_id=%s, task_id=%s)", batch_id, video["task_id"])
                succeeded = False
                message = str(exc)
                _write_batch_task_status(video["task_id"], "FAILED", message)

            with _favorite_batches_lock:
                batch = _favorite_batches.get(batch_id)
                if not batch:
                    return
                batch_video = batch["videos"][index]
                batch_video["status"] = "success" if succeeded else "failed"
                batch_video["error"] = message
                batch["next_index"] = index + 1
                batch["current_index"] = None
    except Exception as exc:
        logger.exception("收藏夹批次执行异常 (batch_id=%s)", batch_id)
        with _favorite_batches_lock:
            batch = _favorite_batches.get(batch_id)
            if batch:
                batch["state"] = "failed"
                batch["worker_active"] = False
                batch["pause_requested"] = False
                current_index = batch["current_index"]
                if current_index is not None:
                    current_video = batch["videos"][current_index]
                    current_video["status"] = "failed"
                    current_video["error"] = str(exc)
                    batch["next_index"] = current_index + 1
                    batch["current_index"] = None


def get_favorite_batch_snapshot(batch_id: str) -> dict | None:
    with _favorite_batches_lock:
        batch = _favorite_batches.get(batch_id)
        return _batch_snapshot(batch) if batch else None


def _page_count(media: dict) -> int:
    try:
        return max(int(media.get("page") or 1), 1)
    except (TypeError, ValueError):
        return 1


def _get_page_titles(bvid: str, headers: dict) -> dict[int, str]:
    try:
        response = httpx.get(VIDEO_INFO_API, params={"bvid": bvid}, headers=headers, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("读取 Bilibili 分 P 标题失败 (%s): %s", bvid, exc)
        return {}

    if payload.get("code") != 0:
        logger.warning("读取 Bilibili 分 P 标题失败 (%s): %s", bvid, payload.get("message") or payload.get("msg"))
        return {}

    titles = {}
    for page in (payload.get("data") or {}).get("pages") or []:
        try:
            page_number = int(page.get("page"))
        except (TypeError, ValueError):
            continue
        title = (page.get("part") or "").strip()
        if title:
            titles[page_number] = title
    return titles


def _expand_media(media: dict, page_titles: dict[int, str] | None = None) -> list[dict]:
    bvid = media.get("bvid")
    if not bvid:
        return []

    page_count = _page_count(media)
    base = {
        "bvid": bvid,
        "title": media.get("title") or "无标题视频",
        "cover": media.get("cover") or "",
        "duration": media.get("duration") or 0,
        "uploader": (media.get("upper") or {}).get("name") or "",
        "page_count": page_count,
    }
    if page_count == 1:
        return [{
            **base,
            "video_key": bvid,
            "video_url": f"https://www.bilibili.com/video/{bvid}",
        }]

    return [{
        **base,
        "video_key": f"{bvid}_p{page_number}",
        "title": (page_titles or {}).get(page_number) or base["title"],
        "page_number": page_number,
        "video_url": f"https://www.bilibili.com/video/{bvid}?p={page_number}",
    } for page_number in range(1, page_count + 1)]


def parse_favorite_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value

    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if not (hostname == "bilibili.com" or hostname.endswith(".bilibili.com")):
        raise ValueError("请输入 Bilibili 收藏夹链接或收藏夹 ID")

    match = re.search(r"/list/ml(\d+)(?:/|$)", parsed.path)
    if match:
        return match.group(1)

    folder_id = parse_qs(parsed.query).get("fid", [None])[0]
    if folder_id and folder_id.isdigit():
        return folder_id

    raise ValueError("链接中没有识别到收藏夹 ID，请使用 /list/ml... 或 favlist?fid=... 链接")


@router.post("/bilibili/favorites/page")
def get_bilibili_favorite_page(data: FavoritePageRequest):
    try:
        favorite_id = parse_favorite_id(data.favorite_url)
    except ValueError as exc:
        return R.error(msg=str(exc), code=400)

    cookie = CookieConfigManager().get("bilibili")
    if not cookie:
        return R.error(
            msg="请先在「设置 → 下载器配置 → Bilibili」保存登录 Cookie，再读取私人收藏夹",
            code=401,
        )

    params = {
        "media_id": favorite_id,
        "pn": data.page,
        "ps": PAGE_SIZE,
        "keyword": "",
        "order": "mtime",
        "type": 0,
        "tid": 0,
        "platform": "web",
    }
    headers = {
        "Cookie": cookie,
        "Referer": "https://www.bilibili.com/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    try:
        response = httpx.get(FAVORITE_API, params=params, headers=headers, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return R.error(msg=f"读取 Bilibili 收藏夹失败：{exc}", code=502)

    if payload.get("code") != 0:
        api_message = payload.get("message") or payload.get("msg") or "未知错误"
        if payload.get("code") in (-101, -111, -352):
            return R.error(msg="Bilibili 登录状态无效或需要重新验证，请更新设置中的 Cookie", code=401)
        return R.error(msg=f"Bilibili 收藏夹读取失败：{api_message}", code=502)

    data_payload = payload.get("data") or {}
    info = data_payload.get("info") or {}
    medias = data_payload.get("medias") or []
    videos = []
    for media in medias:
        page_count = _page_count(media)
        page_titles = _get_page_titles(media["bvid"], headers) if page_count > 1 and media.get("bvid") else {}
        videos.extend(_expand_media(media, page_titles))

    media_count = int(info.get("media_count") or 0)
    return R.success(data={
        "favorite_id": favorite_id,
        "title": info.get("title") or "Bilibili 收藏夹",
        "media_count": media_count,
        "page": data.page,
        "page_size": PAGE_SIZE,
        "videos": videos,
        "has_more": bool(data_payload.get("has_more", data.page * PAGE_SIZE < media_count)),
    })


@router.post("/bilibili/favorites/batches")
def start_bilibili_favorite_batch(data: FavoriteBatchStartRequest, background_tasks: BackgroundTasks):
    from app.services.transcriber_config_manager import TranscriberConfigManager

    readiness = TranscriberConfigManager().is_model_ready()
    if not readiness["ready"]:
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

    video_keys = [video.video_key for video in data.videos]
    if len(video_keys) != len(set(video_keys)):
        return R.error(msg="批次中包含重复的视频或分 P", code=400)

    batch_id = str(uuid.uuid4())
    videos = []
    for video in data.videos:
        task_id = video.resume_task_id or str(uuid.uuid4())
        videos.append({
            **video.model_dump(),
            "task_id": task_id,
            "status": "running" if video.resume_task_id else "queued",
            "error": None,
        })
        if not video.resume_task_id:
            _write_batch_task_status(task_id, "PENDING")

    batch = {
        "batch_id": batch_id,
        "state": "running",
        "favorite_folder": data.favorite_folder.model_dump(),
        "config": data.config.model_dump(mode="json"),
        "videos": videos,
        "next_index": 0,
        "current_index": None,
        "pause_requested": False,
        "worker_active": True,
    }
    with _favorite_batches_lock:
        _favorite_batches[batch_id] = batch

    background_tasks.add_task(run_favorite_batch, batch_id)
    return R.success(data=_batch_snapshot(batch))


@router.get("/bilibili/favorites/batches/{batch_id}")
def get_bilibili_favorite_batch(batch_id: str):
    snapshot = get_favorite_batch_snapshot(batch_id)
    if not snapshot:
        return R.error(msg="找不到该收藏夹批次，后端可能已重启", code=404)
    return R.success(data=snapshot)


@router.post("/bilibili/favorites/batches/{batch_id}/pause")
def pause_bilibili_favorite_batch(batch_id: str):
    with _favorite_batches_lock:
        batch = _favorite_batches.get(batch_id)
        if not batch:
            return R.error(msg="找不到该收藏夹批次，后端可能已重启", code=404)
        if batch["state"] == "running":
            batch["pause_requested"] = True
        snapshot = _batch_snapshot(batch)
    return R.success(data=snapshot)


@router.post("/bilibili/favorites/batches/{batch_id}/resume")
def resume_bilibili_favorite_batch(batch_id: str, background_tasks: BackgroundTasks):
    with _favorite_batches_lock:
        batch = _favorite_batches.get(batch_id)
        if not batch:
            return R.error(msg="找不到该收藏夹批次，后端可能已重启", code=404)
        if batch["state"] == "paused" and not batch["worker_active"]:
            batch["state"] = "running"
            batch["pause_requested"] = False
            batch["worker_active"] = True
            background_tasks.add_task(run_favorite_batch, batch_id)
        snapshot = _batch_snapshot(batch)
    return R.success(data=snapshot)


@router.delete("/bilibili/favorites/batches/{batch_id}")
def delete_bilibili_favorite_batch(batch_id: str):
    with _favorite_batches_lock:
        batch = _favorite_batches.get(batch_id)
        if not batch:
            return R.success()
        if batch["state"] == "running":
            return R.error(msg="运行中的批次不能清除", code=409)
        _favorite_batches.pop(batch_id, None)
    return R.success()
