import asyncio
import json
import logging
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from abc import ABC
from pathlib import Path
from typing import List, Optional, Union

import requests
import websockets
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from app.downloaders.base import Downloader, DownloadQuality, QUALITY_MAP
from app.models.notes_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.path_helper import get_data_dir
from app.utils.url_parser import extract_video_id

logger = logging.getLogger(__name__)

# B? cookies ???????????????????
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE") or os.getenv("BILIBILI_COOKIE_FILE", "cookies.txt")


class BilibiliDownloader(Downloader, ABC):
    def __init__(self):
        super().__init__()

    @staticmethod
    def _bilibili_headers() -> dict:
        return {
            "Referer": "https://www.bilibili.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    def _ydl_base_opts(self, output_path: str) -> dict:
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "64"}
            ],
            "noplaylist": True,
            "quiet": False,
            "http_headers": self._bilibili_headers(),
        }
        cookie_file = os.getenv("BILIBILI_COOKIE_FILE") or os.getenv("BILIBILI_COOKIES_FILE")
        if cookie_file:
            opts["cookiefile"] = cookie_file
        proxy = os.getenv("BILIBILI_PROXY")
        if proxy:
            opts["proxy"] = proxy
        return opts

    @staticmethod
    def _extract_bvid(video_url: str) -> str:
        match = re.search(r"BV[0-9A-Za-z]+", video_url)
        if not match:
            raise ValueError(f"??? Bilibili ???? BV ?: {video_url}")
        return match.group(0)

    @staticmethod
    def _http_json(url: str, method: str = "GET") -> dict:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _is_cdp_available(cdp_base: str) -> bool:
        try:
            BilibiliDownloader._http_json(f"{cdp_base}/json/version")
            return True
        except Exception:
            return False

    @staticmethod
    def _chrome_candidates() -> list[str]:
        return [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]

    def _ensure_cdp(self) -> str:
        cdp_base = os.getenv("BILIBILI_CDP_BASE", "http://127.0.0.1:9223").rstrip("/")
        if self._is_cdp_available(cdp_base):
            return cdp_base

        port_match = re.search(r":(\d+)$", urllib.parse.urlparse(cdp_base).netloc)
        port = port_match.group(1) if port_match else "9223"
        profile_dir = os.path.abspath(os.getenv("BILIBILI_CDP_PROFILE", ".bilinote-cdp-profile"))
        chrome_path = os.getenv("BILIBILI_CHROME_PATH")
        if not chrome_path:
            chrome_path = next((path for path in self._chrome_candidates() if os.path.exists(path)), None)
        if not chrome_path:
            raise RuntimeError("??? Chrome/Edge????? Bilibili CDP ????")

        os.makedirs(profile_dir, exist_ok=True)
        subprocess.Popen(
            [
                chrome_path,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            if self._is_cdp_available(cdp_base):
                return cdp_base
            time.sleep(0.5)
        raise RuntimeError(f"Chrome CDP ?????: {cdp_base}")

    async def _cdp_send(self, ws, message_id: int, method: str, params: Optional[dict] = None) -> tuple[int, dict]:
        await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(await ws.recv())
            if response.get("id") == message_id:
                return message_id + 1, response

    async def _get_playinfo_from_cdp(self, video_url: str) -> dict:
        cdp_base = self._ensure_cdp()
        clean_url = self._canonical_bilibili_url(video_url)
        target = self._http_json(
            f"{cdp_base}/json/new?{urllib.parse.quote(clean_url, safe=':/?=&')}",
            method="PUT",
        )
        ws_url = target["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=20_000_000) as ws:
            message_id = 1
            message_id, _ = await self._cdp_send(ws, message_id, "Page.enable")
            message_id, _ = await self._cdp_send(ws, message_id, "Runtime.enable")
            message_id, _ = await self._cdp_send(ws, message_id, "Network.enable")

            deadline = time.time() + int(os.getenv("BILIBILI_CDP_WAIT_SECONDS", "25"))
            last_state = {}
            while time.time() < deadline:
                expr = """
                (() => {
                  const play = window.__playinfo__;
                  const state = window.__INITIAL_STATE__;
                  const video = state?.videoData || {};
                  return {
                    title: document.title || video.title || '',
                    bvid: video.bvid || video.bv_id || '',
                    duration: video.duration || 0,
                    pic: video.pic || '',
                    desc: video.desc || '',
                    owner: video.owner?.name || '',
                    tags: (state?.tags || []).map((tag) => tag?.tag_name || tag?.tagName || tag?.name).filter(Boolean),
                    playinfo: play || null,
                  };
                })()
                """
                message_id, result = await self._cdp_send(
                    ws, message_id, "Runtime.evaluate", {"expression": expr, "returnByValue": True}
                )
                value = result.get("result", {}).get("result", {}).get("value") or {}
                last_state = value
                audios = (((value.get("playinfo") or {}).get("data") or {}).get("dash") or {}).get("audio") or []
                if audios:
                    return value
                await asyncio.sleep(0.8)
        raise RuntimeError(f"CDP ??? Bilibili ?????????????: {last_state}")

    @staticmethod
    def _canonical_bilibili_url(video_url: str) -> str:
        bvid = BilibiliDownloader._extract_bvid(video_url)
        return f"https://www.bilibili.com/video/{bvid}/"

    @staticmethod
    def _download_url(url: str, output_path: str, referer: str) -> None:
        """Download a Bilibili media URL with retries and resume support.

        Bilibili CDN connections often close early. requests then raises
        ChunkedEncodingError / IncompleteRead. Retrying with Range keeps the
        already downloaded bytes and avoids failing the whole note task.
        """
        headers = BilibiliDownloader._bilibili_headers()
        headers["Referer"] = referer
        max_attempts = max(1, int(os.getenv("BILIBILI_MEDIA_RETRY_ATTEMPTS", "8")))
        chunk_size = int(os.getenv("BILIBILI_MEDIA_CHUNK_SIZE", str(256 * 1024)))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        last_error = None
        expected_total = None
        for attempt in range(1, max_attempts + 1):
            resume_from = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            req_headers = dict(headers)
            if resume_from > 0:
                req_headers["Range"] = f"bytes={resume_from}-"

            try:
                with requests.get(url, headers=req_headers, stream=True, timeout=(10, 90)) as response:
                    if resume_from > 0 and response.status_code == 416:
                        # Range Not Satisfiable commonly means our local partial is already complete
                        # or the CDN rejected a stale range. Try to validate completion, otherwise restart.
                        content_range = response.headers.get("Content-Range") or ""
                        total_match = re.search(r"/(\d+)$", content_range)
                        if total_match and resume_from >= int(total_match.group(1)):
                            return
                        Path(output_path).unlink(missing_ok=True)
                        resume_from = 0
                        req_headers.pop("Range", None)
                        response.close()
                        with requests.get(url, headers=req_headers, stream=True, timeout=(10, 90)) as fresh_response:
                            fresh_response.raise_for_status()
                            with open(output_path, "wb") as file:
                                for chunk in fresh_response.iter_content(chunk_size=chunk_size):
                                    if chunk:
                                        file.write(chunk)
                            return

                    if resume_from > 0 and response.status_code == 200:
                        # Server ignored Range, restart cleanly.
                        resume_from = 0
                        Path(output_path).unlink(missing_ok=True)
                    response.raise_for_status()

                    content_range = response.headers.get("Content-Range") or ""
                    content_length = response.headers.get("Content-Length")
                    if content_range and "/" in content_range:
                        try:
                            expected_total = int(content_range.rsplit("/", 1)[1])
                        except ValueError:
                            expected_total = None
                    elif content_length and resume_from == 0:
                        expected_total = int(content_length)

                    mode = "ab" if resume_from > 0 and response.status_code == 206 else "wb"
                    with open(output_path, mode) as file:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)

                final_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                if expected_total is None or final_size >= expected_total:
                    return
                last_error = RuntimeError(f"incomplete media download: {final_size}/{expected_total} bytes")
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Bilibili media download interrupted (attempt %s/%s, downloaded=%s): %s",
                    attempt,
                    max_attempts,
                    os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                    exc,
                )

            time.sleep(min(2 * attempt, 10))

        raise RuntimeError(f"Bilibili media download failed after {max_attempts} attempts: {last_error}")

    @staticmethod
    def _find_ffmpeg() -> str:
        binary = os.getenv("FFMPEG_BINARY")
        if binary and os.path.exists(binary):
            return binary
        bin_dir = os.getenv("FFMPEG_BIN_PATH")
        if bin_dir:
            candidate = os.path.join(bin_dir, "ffmpeg.exe")
            if os.path.exists(candidate):
                return candidate
        return "ffmpeg"

    @staticmethod
    def _find_ffprobe() -> str:
        binary = os.getenv("FFPROBE_BINARY")
        if binary and os.path.exists(binary):
            return binary
        bin_dir = os.getenv("FFMPEG_BIN_PATH")
        if bin_dir:
            candidate = os.path.join(bin_dir, "ffprobe.exe")
            if os.path.exists(candidate):
                return candidate
        return "ffprobe"

    @staticmethod
    def _existing_file(path: Optional[str]) -> bool:
        return bool(path) and os.path.exists(path) and os.path.getsize(path) > 0

    @classmethod
    def _probe_duration(cls, media_path: Optional[str]) -> float:
        if not cls._existing_file(media_path):
            return 0
        try:
            command = [
                cls._find_ffprobe(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ]
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True).strip()
            return float(output) if output else 0
        except Exception:
            return 0

    @staticmethod
    def _note_result_dirs() -> list[Path]:
        configured = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
        backend_root = Path(__file__).resolve().parents[2]
        candidates = []
        if configured.is_absolute():
            candidates.append(configured)
        else:
            candidates.extend([
                Path.cwd() / configured,
                backend_root / configured,
                backend_root.parent / configured,
            ])

        result = []
        seen = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate.absolute()
            if resolved not in seen and resolved.exists():
                result.append(resolved)
                seen.add(resolved)
        return result

    def _prior_audio_cache_records(self, video_id: str) -> list[tuple[float, Path, dict]]:
        records: list[tuple[float, Path, dict]] = []
        for note_dir in self._note_result_dirs():
            for audio_json in note_dir.glob("*_audio.json"):
                try:
                    data = json.loads(audio_json.read_text(encoding="utf-8-sig"))
                except Exception:
                    continue
                if data.get("video_id") != video_id:
                    continue
                records.append((audio_json.stat().st_mtime, audio_json, data))
        records.sort(key=lambda item: item[0], reverse=True)
        return records

    def _cached_audio_result(
        self,
        video_url: str,
        output_dir: str,
        source: str,
        allow_metadata_only: bool = False,
    ) -> Optional[AudioDownloadResult]:
        """Return a usable local audio result when Bilibili blocks fresh CDP/yt-dlp.

        Bilibili sometimes serves an "error" page to the controlled browser even
        though the same video's audio/video was already cached locally by a
        previous successful run. In that case there is no reason to hit the site
        or bcut again just to recreate metadata.
        """
        video_id = self._extract_bvid(video_url)
        preferred_audio_path = os.path.join(output_dir, f"{video_id}.mp3")
        records = self._prior_audio_cache_records(video_id)

        audio_path = preferred_audio_path if self._existing_file(preferred_audio_path) else None
        if audio_path is None:
            for _, _, data in records:
                candidate = data.get("file_path")
                if self._existing_file(candidate):
                    audio_path = candidate
                    break

        if audio_path is None and not allow_metadata_only:
            return None

        prior = records[0][2] if records else {}
        raw_info = prior.get("raw_info") if isinstance(prior.get("raw_info"), dict) else {}
        raw_info = dict(raw_info)
        original_source = raw_info.get("source")
        raw_info["source"] = source
        if original_source:
            raw_info["original_source"] = original_source
        if records:
            raw_info["prior_audio_cache"] = str(records[0][1])
        raw_info["cached_audio_path"] = audio_path or preferred_audio_path

        duration = prior.get("duration") or self._probe_duration(audio_path)
        try:
            duration = float(duration or 0)
        except (TypeError, ValueError):
            duration = 0

        return AudioDownloadResult(
            file_path=audio_path or preferred_audio_path,
            title=prior.get("title") or video_id,
            duration=duration,
            cover_url=prior.get("cover_url") or "",
            platform="bilibili",
            video_id=video_id,
            raw_info=raw_info,
            video_path=prior.get("video_path"),
        )

    @classmethod
    def _run_ffmpeg_to_mp3(cls, input_path: str, output_path: str) -> None:
        command = [cls._find_ffmpeg(), "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-b:a", "64k", output_path]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def _run_ffmpeg_to_mp4(cls, input_path: str, output_path: str) -> None:
        # First try a fast remux; if the stream/container is not directly mp4-compatible,
        # fall back to a conservative H.264 encode for VideoReader frame extraction.
        remux = [cls._find_ffmpeg(), "-y", "-i", input_path, "-an", "-c:v", "copy", "-movflags", "+faststart", output_path]
        result = subprocess.run(remux, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return
        encode = [
            cls._find_ffmpeg(), "-y", "-i", input_path, "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path,
        ]
        subprocess.run(encode, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _select_dash_stream(streams: list[dict], prefer_lowest: bool = True) -> dict:
        if not streams:
            raise RuntimeError("Bilibili DASH stream list is empty")
        def score(item: dict) -> int:
            return int(item.get("bandwidth") or item.get("size") or 0)
        return min(streams, key=score) if prefer_lowest else max(streams, key=score)

    def _download_audio_via_cdp(self, video_url: str, output_dir: str) -> AudioDownloadResult:
        logger.info("yt-dlp ? B ?????? Chrome CDP ????")
        state = asyncio.run(self._get_playinfo_from_cdp(video_url))
        playinfo = state["playinfo"]
        data = playinfo["data"]
        audio_streams = data["dash"]["audio"]
        audio = self._select_dash_stream(
            audio_streams,
            prefer_lowest=self._env_enabled("BILIBILI_LOWEST_AUDIO_FIRST", True),
        )

        video_id = state.get("bvid") or self._extract_bvid(video_url)
        title = (state.get("title") or video_id).replace("_????_bilibili", "")
        duration = int(state.get("duration") or data.get("duration") or 0)
        cover_url = state.get("pic") or ""
        raw_audio_path = os.path.join(output_dir, f"{video_id}.m4s")
        audio_path = os.path.join(output_dir, f"{video_id}.mp3")

        self._download_url(audio.get("baseUrl") or audio.get("base_url"), raw_audio_path, video_url)
        self._run_ffmpeg_to_mp3(raw_audio_path, audio_path)

        return AudioDownloadResult(
            file_path=audio_path,
            title=title,
            duration=duration,
            cover_url=cover_url,
            platform="bilibili",
            video_id=video_id,
            raw_info={
                "path": raw_audio_path,
                "playinfo": playinfo,
                "description": state.get("desc") or "",
                "owner": state.get("owner") or "",
                "tags": state.get("tags") or [],
                "source": "chrome-cdp-playinfo",
                "audio_id": audio.get("id"),
            },
            video_path=None,
        )

    def _download_video_via_cdp(self, video_url: str, output_dir: str) -> str:
        logger.info("Downloading Bilibili video through Chrome CDP playinfo")
        state = asyncio.run(self._get_playinfo_from_cdp(video_url))
        playinfo = state["playinfo"]
        data = playinfo["data"]
        video_streams = ((data.get("dash") or {}).get("video") or [])
        video = self._select_dash_stream(
            video_streams,
            prefer_lowest=self._env_enabled("BILIBILI_LOWEST_VIDEO_FIRST", True),
        )

        video_id = state.get("bvid") or self._extract_bvid(video_url)
        raw_video_path = os.path.join(output_dir, f"{video_id}.video.m4s")
        video_path = os.path.join(output_dir, f"{video_id}.mp4")
        url = video.get("baseUrl") or video.get("base_url")
        if not url:
            raise RuntimeError("Bilibili CDP playinfo did not contain a video baseUrl")

        self._download_url(url, raw_video_path, video_url)
        self._run_ffmpeg_to_mp4(raw_video_path, video_path)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Bilibili CDP video file not found: {video_path}")
        return video_path

    @staticmethod
    def _should_fallback_to_cdp(error: Exception) -> bool:
        message = str(error)
        return "HTTP Error 412" in message or "Precondition Failed" in message

    @staticmethod
    def _env_enabled(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", "off"}

    def _prefer_cdp_first(self) -> bool:
        # Bilibili frequently returns HTTP 412 to yt-dlp metadata probes.
        # Prefer the real-browser CDP path first, matching the old-version fix.
        return self._env_enabled("BILIBILI_CDP_FIRST", True)

    def _reuse_existing_media(self) -> bool:
        return self._env_enabled("BILIBILI_REUSE_EXISTING_MEDIA", True)

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
        ydl_opts = self._ydl_base_opts(output_path)

        if self._reuse_existing_media():
            cached = self._cached_audio_result(
                str(video_url),
                output_dir,
                source="local-media-cache-before-network",
                allow_metadata_only=skip_download,
            )
            if cached is not None:
                logger.info("Reusing cached Bilibili audio for %s: %s", cached.video_id, cached.file_path)
                return cached

        cdp_first_error = None
        if self._prefer_cdp_first():
            try:
                return self._download_audio_via_cdp(video_url, output_dir)
            except Exception as cdp_error:
                cdp_first_error = cdp_error
                if self._reuse_existing_media():
                    cached = self._cached_audio_result(
                        str(video_url),
                        output_dir,
                        source="local-media-cache-after-cdp-failure",
                        allow_metadata_only=skip_download,
                    )
                    if cached is not None:
                        logger.warning(
                            "Bilibili CDP failed, using cached audio for %s instead: %s",
                            cached.video_id,
                            cdp_error,
                        )
                        return cached
                logger.warning("Bilibili CDP-first download failed, falling back to yt-dlp: %s", cdp_error)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=not skip_download)
                video_id = info.get("id")
                title = info.get("title")
                duration = info.get("duration", 0)
                cover_url = info.get("thumbnail")
                audio_path = os.path.join(output_dir, f"{video_id}.mp3")
        except Exception as error:
            if self._should_fallback_to_cdp(error):
                if cdp_first_error is not None:
                    if self._reuse_existing_media():
                        cached = self._cached_audio_result(
                            str(video_url),
                            output_dir,
                            source="local-media-cache-after-cdp-and-ytdlp-failure",
                            allow_metadata_only=skip_download,
                        )
                        if cached is not None:
                            logger.warning(
                                "Bilibili CDP and yt-dlp failed, using cached audio for %s",
                                cached.video_id,
                            )
                            return cached
                    logger.error("yt-dlp also returned 412 after CDP-first failure; raising original CDP error")
                    raise cdp_first_error
                return self._download_audio_via_cdp(video_url, output_dir)
            raise

        return AudioDownloadResult(
            file_path=audio_path,
            title=title,
            duration=duration,
            cover_url=cover_url,
            platform="bilibili",
            video_id=video_id,
            raw_info=info,
            video_path=None,
        )

    def download_video(self, video_url: str, output_dir: Union[str, None] = None) -> str:
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)
        video_id = extract_video_id(video_url, "bilibili")
        video_path = os.path.join(output_dir, f"{video_id}.mp4")
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            return video_path

        cdp_first_error = None
        if self._prefer_cdp_first():
            try:
                return self._download_video_via_cdp(video_url, output_dir)
            except Exception as cdp_error:
                cdp_first_error = cdp_error
                logger.warning("Bilibili CDP-first video download failed, falling back to yt-dlp: %s", cdp_error)

        output_path = os.path.join(output_dir, "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bv*[ext=mp4]/bestvideo+bestaudio/best",
            "outtmpl": output_path,
            "noplaylist": True,
            "quiet": False,
            "merge_output_format": "mp4",
            "http_headers": self._bilibili_headers(),
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_id = info.get("id")
                video_path = os.path.join(output_dir, f"{video_id}.mp4")
        except Exception as error:
            if self._should_fallback_to_cdp(error):
                if cdp_first_error is not None:
                    logger.error("yt-dlp video path also returned 412 after CDP-first failure; raising original CDP error")
                    raise cdp_first_error
                return self._download_video_via_cdp(video_url, output_dir)
            raise
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Bilibili video file not found: {video_path}")
        return video_path

    def delete_video(self, video_path: str) -> str:
        if os.path.exists(video_path):
            os.remove(video_path)
            return f"???????: {video_path}"
        return f"???????: {video_path}"

    def download_subtitles(self, video_url: str, output_dir: str = None,
                           langs: List[str] = None) -> Optional[TranscriptResult]:
        """
        尝试获取B站视频字幕

        :param video_url: 视频链接
        :param output_dir: 输出路径
        :param langs: 优先语言列表
        :return: TranscriptResult 或 None
        """
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        if self._env_enabled("BILIBILI_SKIP_YTDLP_SUBTITLES", True):
            logger.info("Skipping yt-dlp Bilibili subtitle probe; CDP/audio fallback will be used to avoid HTTP 412")
            return None

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

        # 添加 cookies 支持
        cookies_path = Path(BILIBILI_COOKIES_FILE)
        if not cookies_path.is_absolute():
            # 相对于 backend 目录
            cookies_path = Path(__file__).parent.parent.parent / BILIBILI_COOKIES_FILE

        if cookies_path.exists():
            ydl_opts['cookiefile'] = str(cookies_path)
            logger.info(f"使用 cookies 文件: {cookies_path}")
        else:
            logger.warning(f"B站 cookies 文件不存在: {cookies_path}，字幕获取可能失败")

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
