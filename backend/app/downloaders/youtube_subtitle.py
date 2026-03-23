"""
通过 youtube-transcript-api 获取 YouTube 字幕。
优先人工字幕，其次自动生成字幕。不依赖 yt_dlp，无需下载任何文件。
"""

from typing import Optional, List

from youtube_transcript_api import YouTubeTranscriptApi

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.logger import get_logger

logger = get_logger(__name__)


class YouTubeSubtitleFetcher:
    """通过 youtube-transcript-api 获取 YouTube 字幕。"""

    def __init__(self):
        self._api = YouTubeTranscriptApi()

    def fetch_subtitles(
        self,
        video_id: str,
        langs: Optional[List[str]] = None,
    ) -> Optional[TranscriptResult]:
        if langs is None:
            langs = ["zh-Hans", "zh", "zh-CN", "zh-TW", "en", "en-US", "ja"]

        try:
            # 1. 列出所有可用字幕
            transcript_list = self._api.list(video_id)

            available = []
            for t in transcript_list:
                available.append(
                    f"{t.language_code}({'auto' if t.is_generated else 'manual'})"
                )
            logger.info(f"可用字幕轨道: {', '.join(available)}")

            # 2. 按优先级查找：先人工字幕，再自动字幕
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(langs)
                logger.info(f"选中人工字幕: {transcript.language_code} ({transcript.language})")
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(langs)
                    logger.info(f"选中自动字幕: {transcript.language_code} ({transcript.language})")
                except Exception:
                    # 都没匹配，取第一个可用的
                    for t in transcript_list:
                        transcript = t
                        source = "auto" if t.is_generated else "manual"
                        logger.info(f"使用首个可用字幕: {t.language_code} ({source})")
                        break

            if not transcript:
                logger.info(f"YouTube 视频 {video_id} 没有任何可用字幕")
                return None

            # 3. 获取字幕内容
            fetched = transcript.fetch()
            segments = []
            for snippet in fetched:
                text = snippet.get("text", "").strip() if isinstance(snippet, dict) else str(snippet).strip()
                if not text:
                    continue
                start = snippet.get("start", 0) if isinstance(snippet, dict) else 0
                duration = snippet.get("duration", 0) if isinstance(snippet, dict) else 0
                segments.append(TranscriptSegment(
                    start=float(start),
                    end=float(start) + float(duration),
                    text=text,
                ))

            if not segments:
                logger.warning(f"YouTube 字幕内容为空: {video_id}")
                return None

            full_text = " ".join(seg.text for seg in segments)
            logger.info(f"成功获取 YouTube 字幕，共 {len(segments)} 段")

            return TranscriptResult(
                language=transcript.language_code,
                full_text=full_text,
                segments=segments,
                raw={
                    "source": "youtube_transcript_api",
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                },
            )

        except Exception as e:
            logger.warning(f"YouTube 字幕获取失败: {e}")
            return None
