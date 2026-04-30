from typing import List
from app.gpt.base import GPT
from openai import OpenAI
from app.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT
from app.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.gpt.utils import fix_markdown
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment
from datetime import timedelta


class QwenGPT(GPT):
    def __init__(self):
        from os import getenv
        self.api_key = getenv("QWEN_API_KEY")
        self.base_url = getenv("QWEN_API_BASE_URL")
        self.model=getenv('QWEN_MODEL')
        print(self.model)
        self.client = OpenAICompatibleProvider(api_key=self.api_key, base_url=self.base_url)
        self.screenshot = False

    def _format_time(self, seconds: float) -> str:
        return str(timedelta(seconds=int(seconds)))[2:]  # 格式如 03:15

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [
            TranscriptSegment(**seg) if isinstance(seg, dict) else seg
            for seg in segments
        ]

    def create_messages(self, segments: List[TranscriptSegment], title: str,tags:str):
        content = BASE_PROMPT.format(
            video_title=title,
            segment_text=self._build_segment_text(segments),
            tags=tags
        )
        if self.screenshot:
            print(":需要截图")
            content += SCREENSHOT
        print(content)
        return [{"role": "user", "content": content + AI_SUM}]
    def list_models(self):
        return self.client.list_models()
    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        source.segment = self.ensure_segments_type(source.segment)
        messages = self.create_messages(source.segment, source.title,source.tags)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

if __name__ == '__main__':
    gpt = QwenGPT()
    print(gpt.list_models())
