import mlx_whisper
from pathlib import Path
import os
import platform
from huggingface_hub import snapshot_download

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptSegment, TranscriptResult
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger
from app.utils.path_helper import get_model_dir
from events import transcription_finished

logger = get_logger(__name__)


# mlx-community 上的 Whisper 仓库命名不统一：常规版本是 'whisper-{size}-mlx'，
# turbo 例外没有 -mlx 后缀。直接拼 'mlx-community/whisper-{size}' 会 404。
# 已用 https://huggingface.co/api/models?author=mlx-community&search=whisper 核对过。
MLX_MODEL_MAP = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v1": "mlx-community/whisper-large-v1-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


def resolve_mlx_repo_id(model_size: str) -> str:
    if model_size not in MLX_MODEL_MAP:
        raise ValueError(
            f"不支持的 MLX Whisper 模型大小: {model_size}。"
            f"可选: {', '.join(MLX_MODEL_MAP.keys())}"
        )
    return MLX_MODEL_MAP[model_size]


class MLXWhisperTranscriber(Transcriber):
    def __init__(
            self,
            model_size: str = "base"
    ):
        # 检查平台
        if platform.system() != "Darwin":
            raise RuntimeError("MLX Whisper 仅支持 Apple 平台")

        # 检查环境变量
        if os.environ.get("TRANSCRIBER_TYPE") != "mlx-whisper":
            raise RuntimeError("必须设置环境变量 TRANSCRIBER_TYPE=mlx-whisper 才能使用 MLX Whisper")

        self.model_size = model_size
        self.model_name = resolve_mlx_repo_id(model_size)
        self.model_path = None
        
        # 设置模型路径
        model_dir = get_model_dir("mlx-whisper")
        self.model_path = os.path.join(model_dir, self.model_name)
        # 用 config.json 而非目录存在作为「下载完成」的判据，
        # 同 fast-whisper 的 model.bin：避免半成品目录把后续下载吞掉
        config_file = Path(self.model_path) / "config.json"
        if not config_file.exists():
            if Path(self.model_path).exists():
                logger.warning(
                    f"MLX 模型目录 {self.model_path} 存在但 config.json 缺失（上次下载未完成），重新下载"
                )
            else:
                logger.info(f"模型 {self.model_name} 不存在，开始下载...")
            snapshot_download(
                self.model_name,
                local_dir=self.model_path,
                local_dir_use_symlinks=False,
            )
            logger.info("模型下载完成")
        
        logger.info(f"初始化 MLX Whisper 转录器，模型：{self.model_name}")

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        try:
            # 使用 MLX Whisper 进行转录
            result = mlx_whisper.transcribe(
                file_path,
                path_or_hf_repo=f"{self.model_name}"
            )
            
            # 转换为标准格式
            segments = []
            full_text = ""
            
            for segment in result["segments"]:
                text = segment["text"].strip()
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=segment["start"],
                    end=segment["end"],
                    text=text
                ))
            
            transcript_result = TranscriptResult(
                language=result.get("language", "unknown"),
                full_text=full_text.strip(),
                segments=segments,
                raw=result
            )
            
            # self.on_finish(file_path, transcript_result)
            return transcript_result
            
        except Exception as e:
            logger.error(f"MLX Whisper 转写失败：{e}")
            raise e

    def on_finish(self, video_path: str, result: TranscriptResult) -> None:
        logger.info("MLX Whisper 转写完成")
        transcription_finished.send({
            "file_path": video_path,
        }) 