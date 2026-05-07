"""
直接调用 B 站 player API 拿字幕，绕过 yt-dlp。

流程：
1. 从 URL 提 BV id（已有 utils.url_parser.extract_video_id）
2. GET /x/web-interface/view?bvid=BVxxx → 拿 cid
3. GET /x/player/wbi/v2?bvid=...&cid=... → 返回 data.subtitle.subtitles[]
   每条带 subtitle_url（B 站后端已经签好 auth_key 的完整地址）
4. 按优先级（人工 zh-CN > AI zh-CN > 任意 zh > 任意非空）选一条
5. fetch subtitle_url → JSON {body:[{from,to,content,...}]}
6. 解析为 TranscriptResult

AI 字幕需要登录态 cookie（SESSDATA）；通过 CookieConfigManager 注入。
"""

from typing import List, Optional

import requests

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.cookie_manager import CookieConfigManager
from app.utils.logger import get_logger
from app.utils.url_parser import extract_video_id

logger = get_logger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class BilibiliSubtitleFetcher:
    """通过 B 站官方 API 直拉字幕。"""

    def __init__(self):
        self._cookie = CookieConfigManager().get("bilibili") or ""

    def _headers(self) -> dict:
        h = {
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com",
        }
        if self._cookie:
            h["Cookie"] = self._cookie
        return h

    def _get_cid(self, bvid: str) -> Optional[int]:
        url = "https://api.bilibili.com/x/web-interface/view"
        try:
            resp = requests.get(url, params={"bvid": bvid}, headers=self._headers(), timeout=10)
            data = resp.json()
        except Exception as e:
            logger.warning(f"获取 cid 失败: {e}")
            return None
        if data.get("code") != 0:
            logger.warning(f"view API 返回错误: code={data.get('code')}, msg={data.get('message')}")
            return None
        cid = data.get("data", {}).get("cid")
        return int(cid) if cid else None

    def _list_subtitles(self, bvid: str, cid: int) -> List[dict]:
        url = "https://api.bilibili.com/x/player/wbi/v2"
        try:
            resp = requests.get(url, params={"bvid": bvid, "cid": cid}, headers=self._headers(), timeout=10)
            data = resp.json()
        except Exception as e:
            logger.warning(f"获取字幕列表失败: {e}")
            return []
        if data.get("code") != 0:
            logger.warning(f"player API 返回错误: code={data.get('code')}, msg={data.get('message')}")
            return []
        subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
        return subtitles or []

    def _pick(self, subtitles: List[dict]) -> Optional[dict]:
        """优先级：人工中文 > AI 中文 > 任意中文 > 任意非空。"""
        if not subtitles:
            return None

        def is_zh(s: dict) -> bool:
            lan = (s.get("lan") or "").lower()
            return lan.startswith("zh") or lan == "ai-zh"

        # 人工中文（type 0=AI, 1=人工 ；ai_type=0 视为人工）
        for s in subtitles:
            if is_zh(s) and not s.get("ai_type"):
                return s
        # AI 中文
        for s in subtitles:
            if is_zh(s):
                return s
        # 任意非空
        return subtitles[0]

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("//"):
            return "https:" + url
        return url

    def _fetch_body(self, subtitle_url: str) -> Optional[List[dict]]:
        try:
            resp = requests.get(self._normalize_url(subtitle_url), headers=self._headers(), timeout=15)
            data = resp.json()
            return data.get("body") or []
        except Exception as e:
            logger.warning(f"下载字幕 JSON 失败: {e}")
            return None

    def fetch_subtitles(self, video_url: str) -> Optional[TranscriptResult]:
        bvid = extract_video_id(video_url, "bilibili")
        if not bvid:
            logger.info("无法从 URL 提取 BV id")
            return None

        cid = self._get_cid(bvid)
        if not cid:
            logger.info(f"{bvid} 没有取到 cid")
            return None

        subtitles = self._list_subtitles(bvid, cid)
        if not subtitles:
            logger.info(f"{bvid} (cid={cid}) 没有可用字幕轨")
            return None

        track = self._pick(subtitles)
        if not track or not track.get("subtitle_url"):
            logger.info(f"{bvid} 字幕轨存在但没有 subtitle_url（可能未登录、需要 SESSDATA cookie）")
            return None

        lan = track.get("lan") or "zh"
        body = self._fetch_body(track["subtitle_url"])
        if not body:
            return None

        segments: List[TranscriptSegment] = []
        for item in body:
            text = (item.get("content") or "").strip()
            if not text:
                continue
            segments.append(TranscriptSegment(
                start=float(item.get("from", 0)),
                end=float(item.get("to", 0)),
                text=text,
            ))

        if not segments:
            return None

        full_text = " ".join(s.text for s in segments)
        logger.info(f"B站直拉字幕成功: {bvid} lan={lan} 共 {len(segments)} 段")
        return TranscriptResult(
            language=lan,
            full_text=full_text,
            segments=segments,
            raw={
                "source": "bilibili_player_api",
                "bvid": bvid,
                "cid": cid,
                "lan": lan,
                "ai_type": track.get("ai_type"),
            },
        )
