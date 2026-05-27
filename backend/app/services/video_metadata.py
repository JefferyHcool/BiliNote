from __future__ import annotations

import logging
from typing import Any

import yt_dlp

from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.kuaishou_helper.kuaishou import KuaiShou
from app.downloaders.youtube_downloader import _apply_proxy

logger = logging.getLogger(__name__)


def _merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in (updates or {}).items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _normalize_douyin_info(video_data: dict[str, Any], video_url: str) -> dict[str, Any]:
    aweme = video_data.get("aweme_detail") or {}
    author = aweme.get("author") or {}
    statistics = aweme.get("statistics") or {}
    tags = [
        tag.get("tag_name")
        for tag in aweme.get("video_tag", [])
        if isinstance(tag, dict) and tag.get("tag_name")
    ]

    return {
        "tags": tags,
        "description": aweme.get("desc") or aweme.get("caption") or aweme.get("item_title") or "",
        "caption": aweme.get("caption") or "",
        "uploader": author.get("nickname") or author.get("unique_id") or "",
        "author": {
            "id": author.get("uid") or author.get("sec_uid") or "",
            "name": author.get("nickname") or "",
            "follower_count": author.get("follower_count"),
        },
        "follower_count": author.get("follower_count"),
        "play_count": statistics.get("play_count"),
        "comment_count": statistics.get("comment_count"),
        "like_count": statistics.get("digg_count"),
        "share_count": statistics.get("share_count"),
        "create_time": aweme.get("create_time"),
        "duration": (aweme.get("video") or {}).get("duration"),
        "webpage_url": video_url,
    }


def _normalize_kuaishou_info(video_raw_info: dict[str, Any], video_url: str) -> dict[str, Any]:
    detail = video_raw_info.get("visionVideoDetail") or {}
    photo = detail.get("photo") or {}
    author = detail.get("author") or {}
    tags = [
        tag.get("name")
        for tag in detail.get("tags", [])
        if isinstance(tag, dict) and tag.get("name")
    ]

    return {
        "tags": tags,
        "description": photo.get("caption") or "",
        "caption": photo.get("caption") or "",
        "uploader": author.get("name") or "",
        "author": {
            "id": author.get("id") or "",
            "name": author.get("name") or "",
            "follower_count": author.get("followerCount") or author.get("fansCount"),
        },
        "follower_count": author.get("followerCount") or author.get("fansCount"),
        "play_count": photo.get("viewCount"),
        "view_count": photo.get("viewCount"),
        "comment_count": photo.get("commentCount"),
        "like_count": photo.get("realLikeCount") or photo.get("likeCount"),
        "timestamp": photo.get("timestamp"),
        "duration": photo.get("duration"),
        "photo": photo,
        "webpage_url": video_url,
    }


def _has_follower(raw_info: dict[str, Any]) -> bool:
    owner = raw_info.get("owner") if isinstance(raw_info.get("owner"), dict) else {}
    author = raw_info.get("author") if isinstance(raw_info.get("author"), dict) else {}
    return any(
        raw_info.get(key)
        for key in ("uploader_follower_count", "follower_count", "fans")
    ) or any(owner.get(key) for key in ("fans", "follower_count")) or bool(author.get("follower_count"))


def refresh_audio_meta(audio_meta: dict[str, Any], form_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Best-effort refresh for display metadata. Never downloads media."""
    audio_meta = dict(audio_meta or {})
    form_data = form_data or {}
    platform = audio_meta.get("platform") or form_data.get("platform") or ""
    raw_info = dict(audio_meta.get("raw_info") or {})
    video_url = (
        form_data.get("video_url")
        or raw_info.get("webpage_url")
        or raw_info.get("original_url")
        or ""
    )

    if not platform:
        return audio_meta

    try:
        if platform == "bilibili":
            downloader = BilibiliDownloader()
            refreshed = downloader._enrich_info(raw_info)
            if not _has_follower(refreshed) and video_url:
                ydl_opts = {
                    "quiet": True,
                    "skip_download": True,
                    "noplaylist": True,
                    "http_headers": {"Referer": "https://www.bilibili.com"},
                }
                if downloader._cookiefile:
                    ydl_opts["cookiefile"] = downloader._cookiefile
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                refreshed = downloader._enrich_info(_merge_dict(refreshed, info))
                audio_meta.update({
                    "title": refreshed.get("title") or audio_meta.get("title"),
                    "duration": refreshed.get("duration") or audio_meta.get("duration"),
                    "cover_url": refreshed.get("thumbnail") or audio_meta.get("cover_url"),
                    "video_id": refreshed.get("id") or audio_meta.get("video_id"),
                })
            audio_meta["raw_info"] = refreshed
            return audio_meta

        if platform == "youtube" and video_url:
            ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True}
            _apply_proxy(ydl_opts)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
            audio_meta.update({
                "title": info.get("title") or audio_meta.get("title"),
                "duration": info.get("duration") or audio_meta.get("duration"),
                "cover_url": info.get("thumbnail") or audio_meta.get("cover_url"),
                "video_id": info.get("id") or audio_meta.get("video_id"),
            })
            audio_meta["raw_info"] = _merge_dict(raw_info, info)
            return audio_meta

        if platform == "douyin" and video_url:
            video_data = DouyinDownloader().fetch_video_info(video_url)
            refreshed = _normalize_douyin_info(video_data, video_url)
            audio_meta["raw_info"] = _merge_dict(raw_info, refreshed)
            if refreshed.get("duration"):
                audio_meta["duration"] = refreshed["duration"]
            return audio_meta

        if platform == "kuaishou" and video_url:
            video_raw_info = KuaiShou().run(video_url)
            refreshed = _normalize_kuaishou_info(video_raw_info, video_url)
            audio_meta["raw_info"] = _merge_dict(raw_info, refreshed)
            if refreshed.get("duration"):
                audio_meta["duration"] = refreshed["duration"]
            return audio_meta

    except Exception as e:
        logger.warning("刷新视频元信息失败 platform=%s video_url=%s err=%s", platform, video_url, e)

    return audio_meta
