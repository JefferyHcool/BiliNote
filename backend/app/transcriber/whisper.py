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
from tqdm import tqdm
from modelscope import snapshot_download


'''
 Size of the model to use (tiny, tiny.en, base, base.en, small, small.en, distil-small.en, medium, medium.en, distil-medium.en, large-v1, large-v2, large-v3, large, distil-large-v2, distil-large-v3, large-v3-turbo, or turbo
'''
logger=get_logger(__name__)

MODEL_MAP={
    "tiny": "pengzhendong/faster-whisper-tiny",
    'base':'pengzhendong/faster-whisper-base',
    'small':'pengzhendong/faster-whisper-small',
    'medium':'pengzhendong/faster-whisper-medium',
    'large-v1':'pengzhendong/faster-whisper-large-v1',
    'large-v2':'pengzhendong/faster-whisper-large-v2',
    'large-v3':'pengzhendong/faster-whisper-large-v3',
    'large-v3-turbo':'pengzhendong/faster-whisper-large-v3-turbo',
}

class WhisperTranscriber(Transcriber):
    # TODO:修改为可配置
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

        model_dir = get_model_dir("whisper")
        model_path = os.path.join(model_dir, f"whisper-{model_size}")
        repo_id = MODEL_MAP[model_size]

        # 第一步：目录 / model.bin 不在 → 下载。
        # 关键判据用 model.bin 而不是目录存在：首次下载若被打断（网络中断 / 磁盘满 /
        # 容器被 kill）会留下半成品目录，只看目录存在会跳过下载。
        model_bin = Path(model_path) / "model.bin"
        if not model_bin.exists():
            if Path(model_path).exists():
                logger.warning(f"模型目录 {model_path} 存在但 model.bin 缺失（上次下载未完成），重新下载")
            else:
                logger.info(f"模型 whisper-{model_size} 不存在，开始下载...")
            model_path = snapshot_download(repo_id, local_dir=model_path)
            logger.info("模型下载完成")

        # 第二步：加载。model.bin 可能存在但【内容截断】（下载到一半被 kill），
        # 此时 WhisperModel() 会抛 "File model.bin is incomplete: failed to read a buffer..."。
        # 捕获后删掉损坏目录、重新下载、再试一次——自愈，避免 500 死循环。
        try:
            self.model = WhisperModel(
                model_size_or_path=model_path,
                device=self.device,
                compute_type=self.compute_type,
                download_root=model_dir,
            )
        except Exception as e:
            logger.warning(f"加载 whisper-{model_size} 失败（疑似模型文件损坏 / 截断）：{e}；删除后重新下载")
            shutil.rmtree(model_path, ignore_errors=True)
            model_path = snapshot_download(repo_id, local_dir=model_path)
            logger.info("模型重新下载完成，重试加载")
            self.model = WhisperModel(
                model_size_or_path=model_path,
                device=self.device,
                compute_type=self.compute_type,
                download_root=model_dir,
            )
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

