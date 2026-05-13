from app.gpt.base import GPT
from app.gpt.prompt_builder import generate_base_prompt
from app.models.gpt_model import GPTSource
import logging
import os
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from app.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT, LINK, MERGE_PROMPT
from app.gpt.utils import fix_markdown
from app.gpt.request_chunker import RequestChunker
from app.models.transcriber_model import TranscriptSegment
from datetime import timedelta
from typing import List


DEFAULT_CONTEXT_WINDOW = 32768
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_CONTEXT_SAFETY_RATIO = 0.9
DEFAULT_IMAGE_TOKEN_ESTIMATE = 1500
DEFAULT_RUNTIME_DIR = ".runtime"
MODEL_CONTEXT_CACHE_FILENAME = "model_context_cache.json"
CONTEXT_WINDOW_PATTERNS = (
    r"Input length\s*\(\s*\d+\s*\)\s*exceeds.*?maximum context length\s*\(\s*(\d+)\s*\)",
    r"model'?s maximum context length\s*(?:is)?\s*\(?\s*(\d+)\s*\)?",
    r"maximum context length\s*(?:is|:)?\s*\(?\s*(\d+)\s*\)?",
    r"max(?:imum)? context length\s*(?:is|:)?\s*(\d+)",
    r"max_model_len[^0-9]*(\d+)",
    r"context[_ ]window[^0-9]*(\d+)",
    r"context[_ ]length[^0-9]*(\d+)",
)


class UniversalGPT(GPT):
    def __init__(self, client, model: str, temperature: float = 0.7):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.screenshot = False
        self.link = False
        self.checkpoint_dir = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = Path(os.getenv("BILINOTE_RUNTIME_DIR", DEFAULT_RUNTIME_DIR))
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.context_window = self._resolve_context_window()
        self.max_output_tokens = self._read_positive_int_env(
            "OPENAI_MAX_OUTPUT_TOKENS",
            DEFAULT_MAX_OUTPUT_TOKENS
        )
        self.context_safety_ratio = self._read_float_env(
            "OPENAI_CONTEXT_SAFETY_RATIO",
            DEFAULT_CONTEXT_SAFETY_RATIO
        )
        self.image_token_estimate = self._read_positive_int_env(
            "OPENAI_IMAGE_TOKEN_ESTIMATE",
            DEFAULT_IMAGE_TOKEN_ESTIMATE
        )
        self.max_request_tokens = self._calculate_max_request_tokens()
        # Backward-compatible alias for code that may still inspect this attribute.
        self.max_request_bytes = self.max_request_tokens
        # 初始化时缓存重试配置，避免每次请求重复读取环境变量
        self._max_retry_attempts = max(1, int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3")))
        self._retry_base_backoff = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))

    def _format_time(self, seconds: float) -> str:
        return str(timedelta(seconds=int(seconds)))[2:]

    @staticmethod
    def _read_positive_int_env(name: str, default: int | None = None) -> int | None:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            value = int(str(raw).strip())
            return value if value > 0 else default
        except ValueError:
            return default

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            value = float(str(raw).strip())
            return value if value > 0 else default
        except ValueError:
            return default

    def _get_client_base_url(self) -> str:
        for attr in ("base_url", "_base_url"):
            value = getattr(self.client, attr, None)
            if value:
                return str(value).rstrip("/")
        return ""

    def _model_context_cache_key(self) -> str:
        base_url = self._get_client_base_url()
        return f"{base_url}:{self.model}" if base_url else self.model

    def _context_cache_path(self) -> Path:
        return self.runtime_dir / MODEL_CONTEXT_CACHE_FILENAME

    def _load_context_cache(self) -> dict:
        path = self._context_cache_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _get_cached_context_window(self) -> int | None:
        cache = self._load_context_cache()
        entry = cache.get(self._model_context_cache_key()) or cache.get(self.model)
        if not isinstance(entry, dict):
            return None
        value = entry.get("context_window")
        return value if isinstance(value, int) and value > 0 else None

    def _resolve_context_window(self) -> int:
        explicit = (
            self._read_positive_int_env("OPENAI_CONTEXT_WINDOW")
            or self._read_positive_int_env("OPENAI_MAX_CONTEXT_TOKENS")
        )
        if explicit:
            return explicit
        # Minimal fix boundary: we intentionally do not query provider model
        # metadata here yet. Unknown large-context models should be configured
        # with OPENAI_CONTEXT_WINDOW until a provider-specific discovery layer is
        # added.
        return self._get_cached_context_window() or DEFAULT_CONTEXT_WINDOW

    def _calculate_max_request_tokens(self) -> int:
        available = max(1024, self.context_window - self.max_output_tokens)
        ratio = min(max(self.context_safety_ratio, 0.1), 1.0)
        return max(1024, int(available * ratio))

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [TranscriptSegment(**seg) if isinstance(seg, dict) else seg for seg in segments]

    def create_messages(self, segments: List[TranscriptSegment], **kwargs):

        content_text = generate_base_prompt(
            title=kwargs.get('title'),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get('tags'),
            _format=kwargs.get('_format'),
            style=kwargs.get('style'),
            extras=kwargs.get('extras'),
        )

        video_img_urls = kwargs.get('video_img_urls', [])

        content: list[dict] | str
        if video_img_urls:
            # 有截图时走 OpenAI 多模态 content 数组（text + image_url）
            content = [{"type": "text", "text": content_text}]
            for url in video_img_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "auto"
                    }
                })
        else:
            # 纯文本场景退回 string content：DeepSeek deepseek-chat 等非多模态模型
            # 不识别 [{"type":"text",...}] 数组形态，会返回 invalid_request_error
            # （issue #282）。OpenAI 规范本身也允许 content 为 string。
            content = content_text

        messages = [{
            "role": "user",
            "content": content
        }]

        return messages

    def list_models(self):
        return self.client.models.list()

    def _estimate_text_tokens(self, text: str) -> int:
        if not text:
            return 0
        non_ascii = sum(1 for ch in text if ord(ch) > 127)
        ascii_chars = len(text) - non_ascii
        return non_ascii + ((ascii_chars + 3) // 4)

    def _estimate_single_image_tokens(self, image_part: dict) -> int:
        return self.image_token_estimate

    def _estimate_image_tokens(self, value) -> int:
        if isinstance(value, dict):
            if value.get("type") == "image_url":
                return self._estimate_single_image_tokens(value)
            return sum(self._estimate_image_tokens(item) for item in value.values())
        if isinstance(value, list):
            return sum(self._estimate_image_tokens(item) for item in value)
        return 0

    def _scrub_image_payloads_for_token_estimate(self, value):
        if isinstance(value, dict):
            if value.get("type") == "image_url":
                scrubbed = dict(value)
                image_url = scrubbed.get("image_url")
                if isinstance(image_url, dict):
                    scrubbed["image_url"] = {**image_url, "url": "<image>"}
                else:
                    scrubbed["image_url"] = "<image>"
                return scrubbed
            return {
                key: self._scrub_image_payloads_for_token_estimate(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._scrub_image_payloads_for_token_estimate(item) for item in value]
        return value

    def _estimate_messages_tokens(self, messages: list) -> int:
        text_messages = self._scrub_image_payloads_for_token_estimate(messages)
        raw = json.dumps(text_messages, ensure_ascii=False)
        image_tokens = self._estimate_image_tokens(messages)
        return self._estimate_text_tokens(raw) + image_tokens + 256

    def _estimate_messages_bytes(self, messages: list) -> int:
        return self._estimate_messages_tokens(messages)

    @staticmethod
    def _extract_context_window_from_error(raw: str) -> int | None:
        for pattern in CONTEXT_WINDOW_PATTERNS:
            match = re.search(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            value = int(match.group(1))
            if value > 0:
                return value
        return None

    def _save_learned_context_window(self, context_window: int, raw_error: str) -> None:
        try:
            cache = self._load_context_cache()
            cache[self._model_context_cache_key()] = {
                "context_window": context_window,
                "model": self.model,
                "base_url": self._get_client_base_url(),
                "learned_from": "error",
                "last_error": raw_error[:1000],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            path = self._context_cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(path)
        except Exception:
            return

    def _learn_context_window_from_error(self, exc: Exception) -> int | None:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        raw = str(exc)
        raw_lower = raw.lower()
        looks_like_context_error = (
            status in {400, 413}
            or "context length" in raw_lower
            or "max_model_len" in raw_lower
            or "input length" in raw_lower
            or "token limit" in raw_lower
        )
        if not looks_like_context_error:
            return None

        context_window = self._extract_context_window_from_error(raw)
        if not context_window:
            return None

        self._save_learned_context_window(context_window, raw)
        self.context_window = context_window
        self.max_request_tokens = self._calculate_max_request_tokens()
        self.max_request_bytes = self.max_request_tokens
        return context_window

    def _build_merge_messages(self, partials: list) -> list:
        merge_text = MERGE_PROMPT + "\n\n" + "\n\n---\n\n".join(partials)
        # 合并阶段没有图片，直接用 string content 兼容非多模态模型（issue #282）
        return [{
            "role": "user",
            "content": merge_text
        }]

    def _checkpoint_path(self, checkpoint_key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in checkpoint_key)
        return self.checkpoint_dir / f"{safe_key}.gpt.checkpoint.json"

    def _build_source_signature(self, source: GPTSource) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_request_tokens": self.max_request_tokens,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "title": source.title,
            "tags": source.tags,
            "format": source._format,
            "style": source.style,
            "extras": source.extras,
            "video_img_urls": source.video_img_urls or [],
            "segments": [
                {
                    "start": getattr(seg, "start", None),
                    "end": getattr(seg, "end", None),
                    "text": getattr(seg, "text", "")
                }
                for seg in source.segment
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_checkpoint(self, checkpoint_key: str, source_signature: str) -> dict | None:
        path = self._checkpoint_path(checkpoint_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("source_signature") != source_signature:
                path.unlink(missing_ok=True)
                return None
            return data
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def _save_checkpoint(self, checkpoint_key: str, source_signature: str, partials: list, phase: str) -> None:
        path = self._checkpoint_path(checkpoint_key)
        data = {
            "version": 1,
            "source_signature": source_signature,
            "phase": phase,
            "partials": partials,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _clear_checkpoint(self, checkpoint_key: str) -> None:
        self._checkpoint_path(checkpoint_key).unlink(missing_ok=True)

    @staticmethod
    def _is_insufficient_quota_error(exc: Exception) -> bool:
        raw = str(exc)
        return (
            "insufficient_user_quota" in raw
            or "预扣费额度失败" in raw
            or "insufficient quota" in raw.lower()
        )

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        raw = str(exc).lower()
        retryable_tokens = (
            "error code: 524",
            "bad_response_status_code",
            "timed out",
            "timeout",
            "rate limit",
            "error code: 429",
            "error code: 500",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "apiconnectionerror",
            "connection error",
            "service unavailable",
        )
        if any(token in raw for token in retryable_tokens):
            return True

        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        return status in {408, 409, 429, 500, 502, 503, 504, 524}

    def _chat_completion_create(self, messages: list):
        last_exc = None
        for attempt in range(self._max_retry_attempts):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
            except Exception as exc:
                # Learning updates future chunk budgets only. The current
                # summarize() call has already built its chunks, so this retry
                # loop intentionally does not attempt to re-split in place.
                self._learn_context_window_from_error(exc)
                last_exc = exc
                if attempt == self._max_retry_attempts - 1 or not self._is_retryable_error(exc):
                    raise
                sleep_seconds = self._retry_base_backoff * (2 ** attempt)
                time.sleep(sleep_seconds)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("chat completion failed without exception")

    def _merge_partials(self, partials: list, checkpoint_key: str | None, source_signature: str | None) -> str:
        def build_messages(texts, *_args, **_kwargs):
            return self._build_merge_messages(texts)

        merge_chunker = RequestChunker(
            lambda *_args, **_kwargs: [],
            self.max_request_tokens,
            self._estimate_messages_tokens
        )

        current_partials = list(partials)
        while len(current_partials) > 1:
            groups = merge_chunker.group_texts_by_budget(current_partials, build_messages)
            new_partials = []
            for group_idx, group in enumerate(groups):
                messages = build_messages(group)
                try:
                    response = self._chat_completion_create(messages)
                except Exception as exc:
                    if checkpoint_key and source_signature:
                        self._save_checkpoint(checkpoint_key, source_signature, current_partials, "merge")
                    raise

                new_partials.append(response.choices[0].message.content.strip())

                if checkpoint_key and source_signature:
                    remaining_partials = []
                    for remaining_group in groups[group_idx + 1:]:
                        remaining_partials.extend(remaining_group)
                    resumable_partials = new_partials + remaining_partials
                    self._save_checkpoint(checkpoint_key, source_signature, resumable_partials, "merge")

            current_partials = new_partials

        return current_partials[0]

    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        self.link = source.link
        source.segment = self.ensure_segments_type(source.segment)
        checkpoint_key = source.checkpoint_key
        source_signature = self._build_source_signature(source) if checkpoint_key else None

        def message_builder(segments, image_urls, **kwargs):
            return self.create_messages(segments, video_img_urls=image_urls, **kwargs)

        chunker = RequestChunker(message_builder, self.max_request_tokens, self._estimate_messages_tokens)

        try:
            chunks = chunker.chunk(
                source.segment,
                source.video_img_urls or [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
        except ValueError:
            chunks = chunker.chunk(
                source.segment,
                [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )

        partials = []
        if checkpoint_key and source_signature:
            checkpoint = self._load_checkpoint(checkpoint_key, source_signature)
            if checkpoint and isinstance(checkpoint.get("partials"), list):
                partials = checkpoint["partials"]

        if len(partials) > len(chunks):
            partials = []

        for chunk in chunks[len(partials):]:
            messages = self.create_messages(
                chunk.segments,
                title=source.title,
                tags=source.tags,
                video_img_urls=chunk.image_urls,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
            try:
                response = self._chat_completion_create(messages)
            except Exception as exc:
                if checkpoint_key and source_signature:
                    self._save_checkpoint(checkpoint_key, source_signature, partials, "summarize")
                raise

            partials.append(response.choices[0].message.content.strip())
            if checkpoint_key and source_signature:
                self._save_checkpoint(checkpoint_key, source_signature, partials, "summarize")

        if len(partials) == 1:
            if checkpoint_key:
                self._clear_checkpoint(checkpoint_key)
            return partials[0]
        merged = self._merge_partials(partials, checkpoint_key, source_signature)
        if checkpoint_key:
            self._clear_checkpoint(checkpoint_key)
        return merged

    def analyze_video_frames(self, image_urls: List[str], batch_size: int = 8) -> str:
        """分批分析视频帧截图，返回合并后的视觉描述文本。

        每批发送 batch_size 张图片，收集各批次描述后拼接为连贯的画面摘要。
        这样即使有几百张截图也不会超出上下文限制。
        """
        if not image_urls:
            return ""

        total = len(image_urls)
        total_batches = (total + batch_size - 1) // batch_size
        descriptions = []

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            batch = image_urls[start:start + batch_size]
            prompt = (
                f"请用中文简洁描述这组视频截图（第 {batch_idx + 1}/{total_batches} 组）中"
                f"的主要内容：场景、人物动作、重要文字或信息。不需要逐帧描述，概括即可。"
            )
            content: list = [{"type": "text", "text": prompt}]
            for url in batch:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url, "detail": "auto"},
                })
            messages = [{"role": "user", "content": content}]
            try:
                response = self._chat_completion_create(messages)
                desc = response.choices[0].message.content.strip()
                descriptions.append(desc)
                logger.info(f"视频帧分析进度：{batch_idx + 1}/{total_batches}")
            except Exception as exc:
                logger.warning(f"视频帧分析批次 {batch_idx + 1}/{total_batches} 失败，已跳过：{exc}")

        if not descriptions:
            return ""

        lines = [f"第{i + 1}段：{desc}" for i, desc in enumerate(descriptions)]
        return "\n".join(lines)
