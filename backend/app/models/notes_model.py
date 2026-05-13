from dataclasses import dataclass, field
from typing import Optional

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult


@dataclass
class NoteResult:
    markdown: str                    # GPT 总结的 Markdown 内容
    transcript: TranscriptResult     # Whisper 转写结果
    audio_meta: AudioDownloadResult  # 音频下载的元信息（title、duration、封面等）
    generation_params: dict = field(default_factory=dict)  # 生成参数（模型、风格等）
    markdown_versions: list = field(default_factory=list)  # 历史 Markdown 版本
