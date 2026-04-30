import os
import platform
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger
from app.utils.path_helper import get_model_dir

from app.services.cookie_manager import CookieConfigManager
from app.services.transcriber_config_manager import TranscriberConfigManager
from ffmpeg_helper import ensure_ffmpeg_or_raise

logger = get_logger(__name__)

router = APIRouter()
cookie_manager = CookieConfigManager()
transcriber_config_manager = TranscriberConfigManager()


class CookieUpdateRequest(BaseModel):
    platform: str
    cookie: str


@router.get("/get_downloader_cookie/{platform}")
def get_cookie(platform: str):
    cookie = cookie_manager.get(platform)
    if not cookie:
        return R.success(msg='未找到Cookies')
    return R.success(
        data={"platform": platform, "cookie": cookie}
    )


@router.post("/update_downloader_cookie")
def update_cookie(data: CookieUpdateRequest):
    cookie_manager.set(data.platform, data.cookie)
    return R.success(

    )

class TranscriberConfigRequest(BaseModel):
    transcriber_type: str
    whisper_model_size: Optional[str] = None


AVAILABLE_TRANSCRIBER_TYPES = [
    {"value": "fast-whisper", "label": "Faster Whisper（本地）"},
    {"value": "bcut", "label": "必剪（在线）"},
    {"value": "kuaishou", "label": "快手（在线）"},
    {"value": "groq", "label": "Groq（在线）"},
    {"value": "mlx-whisper", "label": "MLX Whisper（仅macOS）"},
]

WHISPER_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]


@router.get("/transcriber_config")
def get_transcriber_config():
    from app.transcriber.transcriber_provider import MLX_WHISPER_AVAILABLE

    config = transcriber_config_manager.get_config()
    return R.success(data={
        **config,
        "available_types": AVAILABLE_TRANSCRIBER_TYPES,
        "whisper_model_sizes": WHISPER_MODEL_SIZES,
        "mlx_whisper_available": MLX_WHISPER_AVAILABLE,
    })


@router.post("/transcriber_config")
def update_transcriber_config(data: TranscriberConfigRequest):
    config = transcriber_config_manager.update_config(
        transcriber_type=data.transcriber_type,
        whisper_model_size=data.whisper_model_size,
    )
    return R.success(data=config)


# ---- Whisper 模型下载状态 & 下载触发 ----

# 用于跟踪正在进行的下载任务
_downloading: dict[str, str] = {}  # model_size -> 下载状态（"downloading" | "done" | "failed"）


def _check_whisper_model_exists(model_size: str, subdir: str = "whisper") -> bool:
    """检查指定 whisper 模型是否已下载到本地。"""
    model_dir = get_model_dir(subdir)
    model_path = os.path.join(model_dir, f"whisper-{model_size}")
    return Path(model_path).exists()


@router.get("/transcriber_models_status")
def get_transcriber_models_status():
    """返回所有 whisper 模型的下载状态。"""
    statuses = []
    for size in WHISPER_MODEL_SIZES:
        downloaded = _check_whisper_model_exists(size, "whisper")
        download_status = _downloading.get(size)
        statuses.append({
            "model_size": size,
            "downloaded": downloaded,
            "downloading": download_status == "downloading",
        })

    # 也检查 mlx-whisper（仅 macOS）
    mlx_available = platform.system() == "Darwin"
    mlx_statuses = []
    if mlx_available:
        for size in WHISPER_MODEL_SIZES:
            mlx_key = f"mlx-{size}"
            model_dir = get_model_dir("mlx-whisper")
            model_path = os.path.join(model_dir, f"mlx-community/whisper-{size}")
            downloaded = Path(model_path).exists()
            mlx_statuses.append({
                "model_size": size,
                "downloaded": downloaded,
                "downloading": _downloading.get(mlx_key) == "downloading",
            })

    return R.success(data={
        "whisper": statuses,
        "mlx_whisper": mlx_statuses,
        "mlx_available": mlx_available,
    })


class ModelDownloadRequest(BaseModel):
    model_size: str
    transcriber_type: str = "fast-whisper"  # "fast-whisper" 或 "mlx-whisper"


def _do_download_whisper(model_size: str):
    """后台下载 faster-whisper 模型。"""
    from app.transcriber.whisper import MODEL_MAP
    from modelscope import snapshot_download

    try:
        _downloading[model_size] = "downloading"
        model_dir = get_model_dir("whisper")
        model_path = os.path.join(model_dir, f"whisper-{model_size}")
        if Path(model_path).exists():
            _downloading[model_size] = "done"
            return
        repo_id = MODEL_MAP.get(model_size)
        if not repo_id:
            _downloading[model_size] = "failed"
            return
        logger.info(f"开始下载 whisper 模型: {model_size}")
        snapshot_download(repo_id, local_dir=model_path)
        logger.info(f"whisper 模型下载完成: {model_size}")
        _downloading[model_size] = "done"
    except Exception as e:
        logger.error(f"whisper 模型下载失败: {model_size}, {e}")
        _downloading[model_size] = "failed"


def _do_download_mlx_whisper(model_size: str):
    """后台下载 mlx-whisper 模型。"""
    key = f"mlx-{model_size}"
    try:
        _downloading[key] = "downloading"
        from huggingface_hub import snapshot_download as hf_download

        model_dir = get_model_dir("mlx-whisper")
        model_name = f"mlx-community/whisper-{model_size}"
        model_path = os.path.join(model_dir, model_name)
        if Path(model_path).exists():
            _downloading[key] = "done"
            return
        logger.info(f"开始下载 mlx-whisper 模型: {model_size}")
        hf_download(model_name, local_dir=model_path, local_dir_use_symlinks=False)
        logger.info(f"mlx-whisper 模型下载完成: {model_size}")
        _downloading[key] = "done"
    except Exception as e:
        logger.error(f"mlx-whisper 模型下载失败: {model_size}, {e}")
        _downloading[key] = "failed"


@router.post("/transcriber_download")
def download_transcriber_model(data: ModelDownloadRequest, background_tasks: BackgroundTasks):
    """触发后台下载指定的 whisper 模型。"""
    if data.model_size not in WHISPER_MODEL_SIZES:
        return R.error(msg=f"不支持的模型大小: {data.model_size}")

    if data.transcriber_type == "mlx-whisper":
        if platform.system() != "Darwin":
            return R.error(msg="MLX Whisper 仅支持 macOS")
        key = f"mlx-{data.model_size}"
        if _downloading.get(key) == "downloading":
            return R.success(msg="模型正在下载中")
        background_tasks.add_task(_do_download_mlx_whisper, data.model_size)
    else:
        if _downloading.get(data.model_size) == "downloading":
            return R.success(msg="模型正在下载中")
        background_tasks.add_task(_do_download_whisper, data.model_size)

    return R.success(msg="模型下载已开始")


@router.get("/sys_health")
async def sys_health():
    try:
        ensure_ffmpeg_or_raise()
        return R.success()
    except EnvironmentError:
        return R.error(msg="系统未安装 ffmpeg 请先进行安装")

@router.get("/sys_check")
async def sys_check():
    return R.success()


@router.get("/deploy_status")
async def deploy_status():
    """返回部署监控所需的所有状态信息"""
    import torch
    import os
    
    # CUDA 状态
    cuda_available = torch.cuda.is_available()
    cuda_info = {
        "available": cuda_available,
        "version": torch.version.cuda if cuda_available else None,
        "gpu_name": torch.cuda.get_device_name(0) if cuda_available else None,
    }
    
    # Whisper 模型状态（从配置文件读取，与前端设置同步）
    transcriber_cfg = transcriber_config_manager.get_config()
    model_size = transcriber_cfg["whisper_model_size"]
    transcriber_type = transcriber_cfg["transcriber_type"]
    
    # FFmpeg 状态
    try:
        ensure_ffmpeg_or_raise()
        ffmpeg_ok = True
    except:
        ffmpeg_ok = False
    
    return R.success(data={
        "backend": {"status": "running", "port": int(os.getenv("BACKEND_PORT", 8483))},
        "cuda": cuda_info,
        "whisper": {"model_size": model_size, "transcriber_type": transcriber_type},
        "ffmpeg": {"available": ffmpeg_ok},
    })