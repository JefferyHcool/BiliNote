"""
YouTube 播放列表 API：拉取列表 + 批量生成笔记（支持取消）
"""
import uuid
import logging
from typing import Optional, List

import yt_dlp
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.cookie_manager import CookieConfigManager
from app.services.proxy_config_manager import ProxyConfigManager
import json, os

logger = logging.getLogger(__name__)
router = APIRouter()

# ---- 内存中的取消标记 ----
_batch_cancel: dict = {}  # batch_id -> True


class PlaylistInfoRequest(BaseModel):
    playlist_url: str


class BatchGenerateRequest(BaseModel):
    video_urls: List[str]
    platform: str = "youtube"
    quality: str = "fast"
    screenshot: bool = False
    link: bool = False
    model_name: str
    provider_id: str
    style: Optional[str] = None
    extras: Optional[str] = None
    video_understanding: bool = False
    video_interval: int = 0
    grid_size: Optional[List[int]] = None
    format: Optional[List[str]] = None


class CancelRequest(BaseModel):
    batch_id: str


def _get_ydl_opts_for_extraction():
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
    cookie = CookieConfigManager().get("youtube")
    if cookie:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(cookie.strip())
        tmp.close()
        opts["cookiefile"] = tmp.name
    proxy = ProxyConfigManager().get_proxy_url()
    if proxy:
        opts["proxy"] = proxy
    return opts


@router.post("/playlist/info")
def get_playlist_info(data: PlaylistInfoRequest):
    try:
        ydl_opts = _get_ydl_opts_for_extraction()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.playlist_url, download=False)

        if info is None:
            raise HTTPException(status_code=400, detail="无法获取播放列表信息")

        if info.get("_type") == "playlist" or "entries" in info:
            entries = info.get("entries") or []
        else:
            raise HTTPException(status_code=400, detail="该链接不是播放列表")

        videos = []
        for i, entry in enumerate(entries):
            if entry is None:
                continue
            vid = entry.get("id") or entry.get("video_id", "")
            url = entry.get("url") or entry.get("webpage_url", "")
            if not url and vid:
                url = "https://www.youtube.com/watch?v=" + vid
            thumb = entry.get("thumbnail")
            if not thumb and entry.get("thumbnails"):
                thumb = entry["thumbnails"][0].get("url")
            videos.append({
                "id": vid,
                "title": entry.get("title", "Video " + str(i+1)),
                "url": url,
                "duration": entry.get("duration"),
                "thumbnail": thumb,
                "index": i + 1,
            })

        return {
            "code": 0,
            "data": {
                "playlist_title": info.get("title", "未命名播放列表"),
                "playlist_id": info.get("id", ""),
                "video_count": len(videos),
                "videos": videos,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("播放列表解析失败")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/playlist/generate")
def batch_generate(data: BatchGenerateRequest, background_tasks: BackgroundTasks):
    if not data.video_urls:
        raise HTTPException(status_code=400, detail="请至少提供一个视频链接")

    batch_id = str(uuid.uuid4())
    _batch_cancel[batch_id] = False

    task_infos = []
    for i, url in enumerate(data.video_urls):
        task_id = str(uuid.uuid4())
        task_infos.append({
            "task_id": task_id,
            "video_url": url,
            "index": i + 1,
        })

    def _batch_execute():
        from app.routers.note import run_note_task
        from app.enmus.note_enums import DownloadQuality
        for t in task_infos:
            if _batch_cancel.get(batch_id):
                logger.info("批量任务已取消: batch=%s", batch_id)
                break
            try:
                logger.info("批量 [%s/%s]: %s", t["index"], len(task_infos), t["video_url"])
                run_note_task(
                    task_id=t["task_id"],
                    video_url=t["video_url"],
                    platform=data.platform,
                    quality=DownloadQuality(data.quality),
                    link=data.link,
                    screenshot=data.screenshot,
                    _format=data.format or [],
                    model_name=data.model_name,
                    provider_id=data.provider_id,
                    style=data.style,
                    extras=data.extras,
                    video_understanding=data.video_understanding,
                    video_interval=data.video_interval,
                    grid_size=data.grid_size or [],
                )
            except Exception as e:
                logger.error("批量任务 %s 失败: %s", t["task_id"], str(e))
        # 清理
        _batch_cancel.pop(batch_id, None)

    background_tasks.add_task(_batch_execute)

    return {
        "code": 0,
        "data": {
            "batch_id": batch_id,
            "tasks": task_infos,
            "total": len(task_infos),
        }
    }


@router.post("/playlist/cancel")
def cancel_batch(data: CancelRequest):
    if data.batch_id in _batch_cancel:
        _batch_cancel[data.batch_id] = True
        return {"code": 0, "msg": "已发送取消信号"}
    return {"code": 1, "msg": "未找到该批次或已结束"}

import io, zipfile, re, os

class ExportRequest(BaseModel):
    batch_id: str = ''
    task_ids: list = []
    playlist_name: str = 'playlist'


@router.post('/playlist/export')
def export_notes(data: ExportRequest):
    """导出笔记为 ZIP：{playlist_name}/{video_title}.md"""
    from fastapi.responses import StreamingResponse

    buf = io.BytesIO()
    NOTE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'note_results')
    NOTE_OUTPUT_DIR = os.path.normpath(NOTE_OUTPUT_DIR)

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        exported = 0
        for task_id in data.task_ids:
            note_path = os.path.join(NOTE_OUTPUT_DIR, task_id + '.json')
            if not os.path.exists(note_path):
                # 尝试旧路径
                alt_path = os.path.join(os.environ.get('NOTE_OUTPUT_DIR', 'data/note_results'), task_id + '.json')
                if os.path.exists(alt_path):
                    note_path = alt_path
                else:
                    continue
            try:
                with open(note_path, 'r', encoding='utf-8') as f:
                    note = json.load(f)
            except Exception:
                continue

            markdown = note.get('markdown', '')
            if not markdown:
                continue

            # 用视频标题做文件名
            title = note.get('audio_meta', {}).get('title', task_id[:8])
            safe_title = re.sub(r'[\/*?:"<>|]', '', title)[:80].strip()
            if not safe_title:
                safe_title = task_id[:8]

            folder = re.sub(r'[\/*?:"<>|]', '', data.playlist_name)[:60].strip() or 'playlist'
            path = folder + '/' + safe_title + '.md'
            zf.writestr(path, markdown)
            exported += 1

        if exported == 0:
            zf.writestr('empty.txt', 'No completed notes found. Please wait for tasks to finish.')

    buf.seek(0)
    safe_pl = re.sub(r'[\/*?:"<>|]', '', data.playlist_name)[:40] or 'notes'
    filename = safe_pl + '.zip'
    return StreamingResponse(
        buf,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
