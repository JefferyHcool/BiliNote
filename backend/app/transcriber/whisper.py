from faster_whisper import WhisperModel

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptSegment, TranscriptResult
from app.transcriber.base import Transcriber
from app.utils.env_checker import is_cuda_available, is_torch_installed
from app.utils.logger import get_logger
from app.utils.path_helper import get_model_dir

from events import transcription_finished
from pathlib import Path
import os
import shutil


'''
 Size of the model to use (tiny, tiny.en, base, base.en, small, small.en, distil-small.en, medium, medium.en, distil-medium.en, large-v1, large-v2, large-v3, large, distil-large-v2, distil-large-v3, large-v3-turbo, or turbo
'''
logger=get_logger(__name__)

# 历史遗留：之前用 modelscope 下载到自定义目录然后把路径传给 WhisperModel。
# 但 faster-whisper 1.1.1 的 download_model（utils.py:76）逻辑是：
# 只要 size_or_id 里含 "/" 就当 HF repo_id 处理，没有「本地目录直接返回」分支。
# 我们传 /app/models/whisper/whisper-tiny 进去 → 被当成不存在的 HF repo →
# 在线请求失败 → fallback local_files_only=True → HF cache 找不到（因为是
# modelscope 目录布局不是 HF）→ LocalEntryNotFoundError，误导说"离线模式"。
# 解法：彻底让 faster-whisper 自己处理下载——传 size name，配 download_root
# 作为 HF cache 根目录，HF_ENDPOINT 已经在 Dockerfile 里指到 hf-mirror.com，
# 国内能用。删掉 modelscope 那一套，避免布局不匹配。
class WhisperTranscriber(Transcriber):
    def __init__(
            self,
            model_size: str = "base",
            device: str = 'cpu',
            compute_type: str = None,
            cpu_threads: int = 1,
    ):
        if device == 'cpu' or device is None:
            self.device = 'cpu'
        else:
            self.device = "cuda" if self.is_cuda() else "cpu"
            if device == 'cuda' and self.device == 'cpu':
                print('没有 cuda 使用 cpu进行计算')

        self.compute_type = compute_type or ("float16" if self.device == "cuda" else "int8")
        self.model_size = model_size

        model_dir = get_model_dir("whisper")
        try:
            self.model = self._build_model(model_size, model_dir)
        except Exception as e:
            # 自愈：损坏 / 截断 / 半成品 cache → 删掉对应 HF cache 重下一次
            logger.warning(f"加载 whisper-{model_size} 失败：{e}；清理 cache 后重新下载")
            self._purge_cache(model_dir, model_size)
            self.model = self._build_model(model_size, model_dir)

    def _build_model(self, model_size: str, model_dir: str) -> WhisperModel:
        return WhisperModel(
            model_size_or_path=model_size,  # 传 size name，让 faster-whisper 自己映射到 Systran/faster-whisper-*
            device=self.device,
            compute_type=self.compute_type,
            download_root=model_dir,
        )

    @staticmethod
    def _purge_cache(model_dir: str, model_size: str) -> None:
        """删掉 HF cache 里这个 size 对应的 snapshot 目录，强制下次重新下载。

        HF cache 布局：<model_dir>/models--Systran--faster-whisper-{size}/
        没找到也不报错——可能用户改了 endpoint 或者 cache 布局变了。
        """
        candidates = [
            Path(model_dir) / f"models--Systran--faster-whisper-{model_size}",
            Path(model_dir) / f"whisper-{model_size}",  # 历史 modelscope 目录，顺手清掉
        ]
        for path in candidates:
            if path.exists():
                logger.info(f"清理损坏 cache: {path}")
                shutil.rmtree(path, ignore_errors=True)
    @staticmethod
    def is_torch_installed() -> bool:
        try:
            import torch
            return True
        except ImportError:
            return False

    @staticmethod
    def is_cuda() -> bool:
        try:
            if is_cuda_available():
                print(" CUDA 可用，使用 GPU")
                return True
            elif is_torch_installed():
                print(" 只装了 torch，但没有 CUDA，用 CPU")
                return False
            else:
                print(" 还没有安装 torch，请先安装")
                return False

        except ImportError:
            return False

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        try:

            segments_raw, info = self.model.transcribe(file_path)

            segments = []
            full_text = ""

            for seg in segments_raw:
                text = seg.text.strip()
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=text
                ))

            result= TranscriptResult(
                language=info.language,
                full_text=full_text.strip(),
                segments=segments,
                raw=info
            )
            # self.on_finish(file_path, result)
            return result
        except Exception as e:
            print(f"转写失败：{e}")


    def on_finish(self,video_path:str,result: TranscriptResult)->None:
        print("转写完成")
        transcription_finished.send({
            "file_path": video_path,
        })

