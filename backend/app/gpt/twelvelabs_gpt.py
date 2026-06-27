"""TwelveLabs Pegasus 视频理解后端（可选）。

与其它 GPT 后端不同，本后端不依赖音频转写文本，而是把视频 URL 直接交给
TwelveLabs Pegasus 模型「看」视频本身，从画面 + 语音两路信息生成笔记。
对于演示、操作录屏、图表讲解类视频，画面里往往承载了转写文本拿不到的信息。

为什么是可选：
  - 仅当供应商 type == 'twelvelabs' 时，GPTFactory 才会路由到这里；
    未配置 TwelveLabs 供应商时整条链路行为不变。
  - 没有视频 URL（如本地文件、纯音频）时优雅退回，提示用户改用常规模型。

契约（针对官方 SDK twelvelabs>=1.2.8，已对线上 API 实测）：
  - TwelveLabs(api_key=...).analyze(model_name='pegasus1.5', video=VideoContext_Url(url=...),
    prompt=..., max_tokens=...).data 返回 Markdown 文本。
  - Pegasus 1.5 不接受裸 video_id，必须传公网 URL 或已上传 asset。
  - max_tokens 取值区间为 [512, 98304]，低于 512 会报 parameter_invalid。
  - 被分析视频时长需 >= 4s。
"""
from typing import List, Optional

from app.gpt.base import GPT
from app.gpt.prompt_builder import generate_base_prompt
from app.models.gpt_model import GPTSource
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Pegasus 输出 token 下限；低于该值 API 直接报 parameter_invalid。
_MIN_MAX_TOKENS = 512
_DEFAULT_MAX_TOKENS = 2048


class TwelveLabsGPT(GPT):
    """用 TwelveLabs Pegasus 直接理解视频内容生成笔记。"""

    def __init__(self, api_key: str, model: str = "pegasus1.5", temperature: float = 0.7):
        # 延迟 import：未安装 twelvelabs 的用户不应在加载 gpt 包时就报错。
        try:
            from twelvelabs import TwelveLabs
        except ImportError as exc:  # pragma: no cover - 取决于运行环境是否装了依赖
            raise ImportError(
                "使用 TwelveLabs 视频理解需要先安装 twelvelabs SDK："
                "pip install 'twelvelabs>=1.2.8'"
            ) from exc

        if not api_key or not str(api_key).strip():
            raise ValueError("TwelveLabs 的 API Key 未配置，请先在「设置」里填写后再使用")

        self.client = TwelveLabs(api_key=str(api_key).strip())
        self.model = model or "pegasus1.5"
        self.temperature = temperature

    def _build_prompt(self, source: GPTSource) -> str:
        """复用现有笔记 prompt 生成器；Pegasus 直接看视频，故不喂转写文本。"""
        prompt = generate_base_prompt(
            title=source.title,
            segment_text="（本次由视频理解模型直接观看视频，无需转写文本）",
            tags=source.tags,
            _format=source._format,
            style=source.style,
            extras=source.extras,
        )
        return (
            prompt
            + "\n\n你正在直接观看这段视频，请结合**画面与语音**两路信息生成笔记，"
            "充分利用画面中的演示、图表、UI、文字等转写文本无法体现的内容。"
        )

    def summarize(self, source: GPTSource) -> str:
        video_url = getattr(source, "video_url", None)
        if not video_url:
            raise ValueError(
                "TwelveLabs Pegasus 视频理解需要可公开访问的视频 URL，"
                "当前任务没有可用 URL（如本地文件 / 纯音频）。请改用常规文本模型。"
            )

        from twelvelabs.types.video_context import VideoContext_Url

        max_tokens = max(_MIN_MAX_TOKENS, _DEFAULT_MAX_TOKENS)
        logger.info(f"使用 TwelveLabs Pegasus 直接理解视频：{video_url}")
        response = self.client.analyze(
            model_name=self.model,
            video=VideoContext_Url(url=video_url),
            prompt=self._build_prompt(source),
            temperature=self.temperature,
            max_tokens=max_tokens,
        )
        text = (response.data or "").strip()
        if not text:
            raise RuntimeError("TwelveLabs Pegasus 返回空结果")
        return text

    # 与 base.GPT 接口保持一致；视频理解后端不走分段消息拼装。
    def create_messages(self, segments: List, **kwargs) -> list:
        return []

    def list_models(self) -> Optional[list]:
        return [self.model]
