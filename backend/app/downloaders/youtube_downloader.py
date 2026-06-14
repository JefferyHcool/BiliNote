import os
import logging
from abc import ABC
from typing import Union, Optional, List

import yt_dlp

from app.downloaders.base import Downloader, DownloadQuality
from app.downloaders.youtube_subtitle import YouTubeSubtitleFetcher
from app.models.notes_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult
from app.services.proxy_config_manager import ProxyConfigManager
from app.utils.path_helper import get_data_dir
from app.utils.url_parser import extract_video_id
from app.services.cookie_manager import CookieConfigManager
import tempfile

logger = logging.getLogger(__name__)


def _apply_proxy(ydl_opts: dict) -> dict:
    proxy = ProxyConfigManager().get_proxy_url()
    if proxy:
        ydl_opts["proxy"] = proxy
        logger.info(f"yt-dlp proxy: {proxy}")
    return ydl_opts


class YoutubeDownloader(Downloader, ABC):
    def __init__(self):
        super().__init__()
        self._cookie_mgr = CookieConfigManager()
        self._cookie = self._cookie_mgr.get("youtube")
        self._cookiefile = self._write_netscape_cookie_file()

    def _write_netscape_cookie_file(self):
        if not self._cookie:
            return None
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        cookie = self._cookie.strip()
        # Netscape format from browser extension
        if cookie.startswith("# Netscape") or cookie.startswith("# HTTP Cookie"):
            tmp.write(cookie)
        elif "\t" in cookie:
            # Netscape format without header
            tmp.write("# Netscape HTTP Cookie File\n")
            tmp.write(cookie)
        else:
            # Simple key=value; key=value format
            tmp.write("# Netscape HTTP Cookie File\n")
            for pair in cookie.split("; "):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    tmp.write(".youtube.com\tTRUE\t/\tFALSE\t0\t" + key + "\t" + value + "\n")
        tmp.close()
        logger.info("YouTube Netscape cookie file: %s", tmp.name)
        return tmp.name

    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video: Optional[bool] = False,
        skip_download: bool = False,
    ) -> AudioDownloadResult:
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_path,
            "noplaylist": True,
            "quiet": False,
        }

        if skip_download:
            ydl_opts["skip_download"] = True

        if self._cookiefile:
            ydl_opts["cookiefile"] = self._cookiefile
        _apply_proxy(ydl_opts)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=not skip_download)
            video_id = info.get("id")
            title = info.get("title")
            duration = info.get("duration", 0)
            cover_url = info.get("thumbnail")
            ext = info.get("ext", "m4a")
            audio_path = os.path.join(output_dir, f"{video_id}.{ext}")

        return AudioDownloadResult(
            file_path=audio_path,
            title=title,
            duration=duration,
            cover_url=cover_url,
            platform="youtube",
            video_id=video_id,
            raw_info={"tags": info.get("tags")},
            video_path=None,
        )

    def download_video(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        max_height: int = 720,
    ) -> str:
        if output_dir is None:
            output_dir = get_data_dir()
        video_id = extract_video_id(video_url, "youtube")
        video_path = os.path.join(output_dir, f"{video_id}.mp4")
        if os.path.exists(video_path):
            return video_path
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "%(id)s.%(ext)s")

        fmt = f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]"
        ydl_opts = {
            "format": fmt,
            "outtmpl": output_path,
            "noplaylist": True,
            "quiet": False,
            "merge_output_format": "mp4",
        }

        if self._cookiefile:
            ydl_opts["cookiefile"] = self._cookiefile
        _apply_proxy(ydl_opts)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get("id")
            video_path = os.path.join(output_dir, f"{video_id}.mp4")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"video not found: {video_path}")

        return video_path

    def download_subtitles(self, video_url: str, output_dir: str = None,
                           langs: List[str] = None) -> Optional[TranscriptResult]:
        if langs is None:
            langs = ["zh-Hans", "zh", "zh-CN", "zh-TW", "en", "en-US", "ja"]

        video_id = extract_video_id(video_url, "youtube")
        fetcher = YouTubeSubtitleFetcher()
        print(
            f"fetch subtitles, video_id={video_id}, langs={langs}"
        )
        return fetcher.fetch_subtitles(video_id, langs)
