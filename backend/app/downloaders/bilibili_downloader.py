import os
import json
import logging
import subprocess
import tempfile
from abc import ABC
from typing import Union, Optional, List

import requests
import yt_dlp

from app.downloaders.base import Downloader, DownloadQuality, QUALITY_MAP
from app.downloaders.bilibili_dm_patch import apply_bilibili_dm_img_patch
from app.downloaders.bilibili_subtitle import BilibiliSubtitleFetcher
from app.models.notes_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.path_helper import get_data_dir
from app.utils.url_parser import extract_video_id, extract_bilibili_p_number
from app.services.cookie_manager import CookieConfigManager

logger = logging.getLogger(__name__)

BILIBILI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Inject the dm_img_* / web_location risk-control params Bilibili's wbi/playurl
# gateway now requires; without them the API path returns HTTP 412. See
# app/downloaders/bilibili_dm_patch.py for details.
apply_bilibili_dm_img_patch()


class BilibiliDownloader(Downloader, ABC):
    def __init__(self):
        super().__init__()
        self._cookie_mgr = CookieConfigManager()
        self._cookie = self._cookie_mgr.get('bilibili')
        self._cookiefile = self._write_netscape_cookie_file()

    def _headers(self) -> dict:
        headers = {
            'User-Agent': BILIBILI_UA,
            'Referer': 'https://www.bilibili.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        if self._cookie:
            headers['Cookie'] = self._cookie
        return headers

    def _direct_info(self, video_url: str) -> dict:
        """通过 Bilibili 官方 API 获取分集元数据，避开易触发 412 的网页。"""
        bvid = extract_video_id(video_url, "bilibili")
        if not bvid:
            raise ValueError(f"无法从 Bilibili 链接提取 BV 号: {video_url}")
        p = extract_bilibili_p_number(video_url)
        response = requests.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                f"Bilibili view API 失败: {payload.get('message') or payload.get('code')}"
            )

        data = payload.get("data") or {}
        pages = data.get("pages") or []
        page_number = p or 1
        if pages:
            if page_number < 1 or page_number > len(pages):
                raise ValueError(f"分集 p={page_number} 超出范围（共 {len(pages)} 集）")
            page = pages[page_number - 1]
        else:
            page = data

        cid = page.get("cid") or data.get("cid")
        if not cid:
            raise RuntimeError("Bilibili view API 未返回 cid")

        title = data.get("title") or bvid
        part_title = page.get("part")
        if len(pages) > 1 and part_title:
            title = f"{title} - P{page_number} {part_title}"
        return {
            "id": f"{bvid}_p{page_number}" if p else bvid,
            "bvid": bvid,
            "cid": int(cid),
            "p": page_number,
            "title": title,
            "duration": float(page.get("duration") or data.get("duration") or 0),
            "thumbnail": data.get("pic"),
            "raw_view": data,
        }

    def get_series_info(self, video_url: str) -> dict:
        """返回多 P 视频的分集清单，供批量生成入口做一次性范围校验。"""
        info = self._direct_info(video_url)
        data = info["raw_view"]
        raw_pages = data.get("pages") or [data]
        pages = []
        for index, page in enumerate(raw_pages, start=1):
            pages.append({
                "p": index,
                "title": page.get("part") or f"P{index}",
                "duration": float(page.get("duration") or 0),
            })
        return {
            "bvid": info["bvid"],
            "title": data.get("title") or info["bvid"],
            "total": len(pages),
            "pages": pages,
        }

    def _direct_media_urls(self, info: dict) -> List[str]:
        """获取带音轨的渐进式 MP4 地址；匿名访问通常可获得 720p。"""
        response = requests.get(
            "https://api.bilibili.com/x/player/playurl",
            params={
                "bvid": info["bvid"],
                "cid": info["cid"],
                "qn": 64,
                "fnval": 1,
                "platform": "html5",
                "high_quality": 1,
            },
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                f"Bilibili playurl API 失败: {payload.get('message') or payload.get('code')}"
            )
        durl = (payload.get("data") or {}).get("durl") or []
        urls: List[str] = []
        for item in durl:
            if item.get("url"):
                urls.append(item["url"])
            urls.extend(item.get("backup_url") or [])
        if not urls:
            raise RuntimeError("Bilibili playurl API 未返回可下载的 MP4 地址")
        return urls

    def _direct_download_video(self, video_url: str, output_dir: str) -> tuple[str, dict]:
        info = self._direct_info(video_url)
        video_path = os.path.join(output_dir, f"{info['id']}.mp4")
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            return video_path, info

        part_path = video_path + ".part"
        last_error: Optional[Exception] = None
        for media_url in self._direct_media_urls(info):
            try:
                with requests.get(
                    media_url,
                    headers=self._headers(),
                    stream=True,
                    timeout=(15, 60),
                ) as response:
                    response.raise_for_status()
                    with open(part_path, "wb") as output:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                output.write(chunk)
                if os.path.getsize(part_path) == 0:
                    raise RuntimeError("Bilibili CDN 返回了空文件")
                os.replace(part_path, video_path)
                logger.info("Bilibili 官方 API 下载完成: %s", video_path)
                return video_path, info
            except Exception as exc:
                last_error = exc
                logger.warning("Bilibili CDN 地址下载失败，尝试备用地址: %s", exc)
                if os.path.exists(part_path):
                    os.unlink(part_path)
        raise RuntimeError(f"Bilibili 官方 API 下载失败: {last_error}")

    @staticmethod
    def _extract_audio(video_path: str, audio_path: str, bitrate: str) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path, "-vn",
                "-acodec", "libmp3lame", "-b:a", f"{bitrate}k", audio_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _write_netscape_cookie_file(self) -> Optional[str]:
        """将 Cookie 写入 Netscape 格式临时文件，返回文件路径（供 yt-dlp cookiefile 使用）"""
        if not self._cookie:
            logger.warning("B站 Cookie 未配置，下载可能失败")
            return None
        lines = ["# Netscape HTTP Cookie File\n"]
        for pair in self._cookie.split("; "):
            if "=" in pair:
                key, value = pair.split("=", 1)
                lines.append(f".bilibili.com\tTRUE\t/\tFALSE\t0\t{key}\t{value}\n")
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
        tmp.writelines(lines)
        tmp.close()
        logger.info("已生成 B站 Netscape Cookie 文件: %s (条目: %d)", tmp.name, len(lines) - 1)
        return tmp.name

    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video:Optional[bool]=False,
        skip_download: bool = False,
    ) -> AudioDownloadResult:
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir=self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        # Bilibili 网页端会按 IP/指纹返回 HTTP 412。官方 view/playurl API
        # 不依赖网页解析，也能准确保留多 P 视频的 p 参数，优先使用该路径。
        direct_info = self._direct_info(video_url)
        audio_path = os.path.join(output_dir, f"{direct_info['id']}.mp3")
        video_path = os.path.join(output_dir, f"{direct_info['id']}.mp4")
        if not skip_download and not os.path.exists(audio_path):
            video_path, direct_info = self._direct_download_video(video_url, output_dir)
            self._extract_audio(video_path, audio_path, QUALITY_MAP.get(quality, "64"))

        return AudioDownloadResult(
            file_path=audio_path if not skip_download else "",
            title=direct_info["title"],
            duration=direct_info["duration"],
            cover_url=direct_info["thumbnail"],
            platform="bilibili",
            video_id=direct_info["id"],
            raw_info=direct_info,
            video_path=video_path if need_video and os.path.exists(video_path) else None,
        )

    def download_video(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
    ) -> str:
        """
        下载视频，返回视频文件路径
        """

        if output_dir is None:
            output_dir = get_data_dir()
        os.makedirs(output_dir, exist_ok=True)
        video_path, _ = self._direct_download_video(video_url, output_dir)
        return video_path

    def delete_video(self, video_path: str) -> str:
        """
        删除视频文件
        """
        if os.path.exists(video_path):
            os.remove(video_path)
            return f"视频文件已删除: {video_path}"
        else:
            return f"视频文件未找到: {video_path}"

    def download_subtitles(self, video_url: str, output_dir: str = None,
                           langs: List[str] = None) -> Optional[TranscriptResult]:
        """
        尝试获取B站视频字幕

        :param video_url: 视频链接
        :param output_dir: 输出路径
        :param langs: 优先语言列表
        :return: TranscriptResult 或 None
        """
        # 1) 优先走 B 站官方 player API（直拉，无需下视频；AI 字幕需 SESSDATA cookie）
        try:
            result = BilibiliSubtitleFetcher().fetch_subtitles(video_url)
            if result and result.segments:
                return result
        except Exception as e:
            logger.warning(f"player API 直拉字幕异常，回退到 yt-dlp: {e}")

        # 2) Fallback：原 yt-dlp 路径（更脆弱，遇到签名/Cookie 问题失败概率较高）
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        if langs is None:
            langs = ['zh-Hans', 'zh', 'zh-CN', 'ai-zh', 'en', 'en-US']

        video_id = extract_video_id(video_url, "bilibili")

        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': langs,
            'subtitlesformat': 'srt/json3/best',  # 支持多种格式
            'skip_download': True,
            'outtmpl': os.path.join(output_dir, f'{video_id}.%(ext)s'),
            'quiet': True,
        }

        # 通过 CookieConfigManager 注入 B站 Cookie（Netscape cookiefile）
        if self._cookiefile:
            ydl_opts['cookiefile'] = self._cookiefile
            ydl_opts['http_headers'] = {'Referer': 'https://www.bilibili.com'}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)

                # 查找下载的字幕文件
                subtitles = info.get('requested_subtitles') or {}
                if not subtitles:
                    logger.info(f"B站视频 {video_id} 没有可用字幕")
                    return None

                # 按优先级查找字幕
                detected_lang = None
                sub_info = None
                for lang in langs:
                    if lang in subtitles:
                        detected_lang = lang
                        sub_info = subtitles[lang]
                        break

                # 如果按优先级没找到，取第一个可用的（排除弹幕）
                if not detected_lang:
                    for lang, info_item in subtitles.items():
                        if lang != 'danmaku':  # 排除弹幕
                            detected_lang = lang
                            sub_info = info_item
                            break

                if not sub_info:
                    logger.info(f"B站视频 {video_id} 没有可用字幕（排除弹幕）")
                    return None

                # 检查是否有内嵌数据（yt-dlp 有时直接返回字幕内容）
                if 'data' in sub_info and sub_info['data']:
                    logger.info(f"直接从返回数据解析字幕: {detected_lang}")
                    return self._parse_srt_content(sub_info['data'], detected_lang)

                # 查找字幕文件
                ext = sub_info.get('ext', 'srt')
                subtitle_file = os.path.join(output_dir, f"{video_id}.{detected_lang}.{ext}")

                if not os.path.exists(subtitle_file):
                    logger.info(f"字幕文件不存在: {subtitle_file}")
                    return None

                # 根据格式解析字幕文件
                if ext == 'json3':
                    return self._parse_json3_subtitle(subtitle_file, detected_lang)
                else:
                    with open(subtitle_file, 'r', encoding='utf-8') as f:
                        return self._parse_srt_content(f.read(), detected_lang)

        except Exception as e:
            logger.warning(f"获取B站字幕失败: {e}")
            return None

    def _parse_srt_content(self, srt_content: str, language: str) -> Optional[TranscriptResult]:
        """
        解析 SRT 格式字幕内容

        :param srt_content: SRT 字幕文本内容
        :param language: 语言代码
        :return: TranscriptResult
        """
        import re
        try:
            segments = []
            # SRT 格式: 序号\n时间戳\n文本\n\n
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n\d+\n|$)'
            matches = re.findall(pattern, srt_content, re.DOTALL)

            for match in matches:
                idx, start_time, end_time, text = match
                text = text.strip()
                if not text:
                    continue

                # 转换时间格式 00:00:00,000 -> 秒
                def time_to_seconds(t):
                    parts = t.replace(',', '.').split(':')
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

                segments.append(TranscriptSegment(
                    start=time_to_seconds(start_time),
                    end=time_to_seconds(end_time),
                    text=text
                ))

            if not segments:
                return None

            full_text = ' '.join(seg.text for seg in segments)
            logger.info(f"成功解析B站SRT字幕，共 {len(segments)} 段")
            return TranscriptResult(
                language=language,
                full_text=full_text,
                segments=segments,
                raw={'source': 'bilibili_subtitle', 'format': 'srt'}
            )

        except Exception as e:
            logger.warning(f"解析SRT字幕失败: {e}")
            return None

    def _parse_json3_subtitle(self, subtitle_file: str, language: str) -> Optional[TranscriptResult]:
        """
        解析 json3 格式字幕文件

        :param subtitle_file: 字幕文件路径
        :param language: 语言代码
        :return: TranscriptResult
        """
        try:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            segments = []
            events = data.get('events', [])

            for event in events:
                # json3 格式中时间单位是毫秒
                start_ms = event.get('tStartMs', 0)
                duration_ms = event.get('dDurationMs', 0)

                # 提取文本
                segs = event.get('segs', [])
                text = ''.join(seg.get('utf8', '') for seg in segs).strip()

                if text:  # 只添加非空文本
                    segments.append(TranscriptSegment(
                        start=start_ms / 1000.0,
                        end=(start_ms + duration_ms) / 1000.0,
                        text=text
                    ))

            if not segments:
                return None

            full_text = ' '.join(seg.text for seg in segments)

            logger.info(f"成功解析B站字幕，共 {len(segments)} 段")
            return TranscriptResult(
                language=language,
                full_text=full_text,
                segments=segments,
                raw={'source': 'bilibili_subtitle', 'file': subtitle_file}
            )

        except Exception as e:
            logger.warning(f"解析字幕文件失败: {e}")
            return None
