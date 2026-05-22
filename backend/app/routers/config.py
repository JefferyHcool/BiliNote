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


# ---- 全局代理配置（作用于 LLM API + 转写 API + yt-dlp 下载）----

class ProxyConfigRequest(BaseModel):
    enabled: bool
    url: Optional[str] = None


@router.get("/proxy_config")
def get_proxy_config():
    from app.services.proxy_config_manager import ProxyConfigManager
    mgr = ProxyConfigManager()
    cfg = mgr.get_config()
    # effective 给前端展示「当前实际生效的代理」——可能来自配置，也可能来自 env 兜底
    return R.success(data={
        **cfg,
        "effective": mgr.get_proxy_url() or "",
    })


@router.post("/proxy_config")
def update_proxy_config(data: ProxyConfigRequest):
    from app.services.proxy_config_manager import ProxyConfigManager
    mgr = ProxyConfigManager()
    cfg = mgr.update_config(enabled=data.enabled, url=data.url)
    return R.success(data={
        **cfg,
        "effective": mgr.get_proxy_url() or "",
    })


# ---- Whisper 模型下载状态 & 下载触发 ----

# 用于跟踪正在进行的下载任务
_downloading: dict[str, str] = {}  # model_size -> status ("downloading" | "done" | "failed")


def _check_whisper_model_exists(model_size: str, subdir: str = "whisper") -> bool:
    """检查指定 whisper 模型是否已下载完整到本地。

    faster-whisper 把模型缓存在 HF cache 布局下：
      <model_dir>/models--Systran--faster-whisper-{size}/snapshots/<hash>/model.bin
    必须能在某个 snapshot 目录里找到 model.bin 才算完成。
    （历史 modelscope 布局 <model_dir>/whisper-{size}/model.bin 也兼容识别。）
    """
    model_dir = Path(get_model_dir(subdir))
    # HF cache 布局
    hf_repo_dir = model_dir / f"models--Systran--faster-whisper-{model_size}" / "snapshots"
    if hf_repo_dir.exists():
        for snapshot in hf_repo_dir.iterdir():
            if (snapshot / "model.bin").exists():
                return True
    # 历史 modelscope 布局（向后兼容老用户）
    legacy = model_dir / f"whisper-{model_size}" / "model.bin"
    return legacy.exists()


def _check_mlx_whisper_model_exists(model_size: str) -> bool:
    """检查 mlx-whisper 模型是否已下载完整到本地。

    与 fast-whisper 的目录布局不同：mlx 模型按 HuggingFace repo_id
    （如 mlx-community/whisper-tiny-mlx）落盘，且没有 model.bin，
    用 config.json 作为「下载完成」的判据，和 mlx_whisper_transcriber.py 保持一致。
    """
    try:
        from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP
    except Exception:
        return False
    repo_id = MLX_MODEL_MAP.get(model_size)
    if not repo_id:
        return False
    model_dir = get_model_dir("mlx-whisper")
    model_path = os.path.join(model_dir, repo_id)
    return (Path(model_path) / "config.json").exists()


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
        from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP
        for size in WHISPER_MODEL_SIZES:
            mlx_key = f"mlx-{size}"
            repo_id = MLX_MODEL_MAP.get(size)
            # 用 config.json 判定，和 _check_mlx_whisper_model_exists / 加载逻辑保持一致
            downloaded = _check_mlx_whisper_model_exists(size)
            mlx_statuses.append({
                "model_size": size,
                "downloaded": downloaded,
                "downloading": _downloading.get(mlx_key) == "downloading",
                "available": repo_id is not None,
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
    """后台下载 faster-whisper 模型。

    直接走 huggingface_hub.snapshot_download，把模型放到 HF cache 布局里——
    这样 faster-whisper 加载时（WhisperModel(model_size_or_path=size_name,
    download_root=model_dir)）能直接命中缓存，跟加载路径完全对齐。
    """
    from huggingface_hub import snapshot_download

    try:
        _downloading[model_size] = "downloading"
        model_dir = get_model_dir("whisper")

        # 已经下好就不重复下
        if _check_whisper_model_exists(model_size, "whisper"):
            _downloading[model_size] = "done"
            return
        repo_id = f"Systran/faster-whisper-{model_size}"
        logger.info(f"开始下载 whisper 模型: {repo_id}")
        # 跟 faster-whisper utils.py 用同样的 allow_patterns，避免多下无关文件；
        # 不传 local_dir 让它走 HF 默认 cache 布局（与加载逻辑对齐）
        snapshot_download(
            repo_id,
            cache_dir=model_dir,
            allow_patterns=[
                "config.json",
                "preprocessor_config.json",
                "model.bin",
                "tokenizer.json",
                "vocabulary.*",
            ],
        )
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
        from app.transcriber.mlx_whisper_transcriber import resolve_mlx_repo_id

        try:
            repo_id = resolve_mlx_repo_id(model_size)
        except ValueError as e:
            logger.error(str(e))
            _downloading[key] = "failed"
            return

        model_dir = get_model_dir("mlx-whisper")
        model_path = os.path.join(model_dir, repo_id)
        # 用 config.json 判定而非目录存在：半成品目录不能算「已下载」
        if (Path(model_path) / "config.json").exists():
            _downloading[key] = "done"
            return
        logger.info(f"开始下载 mlx-whisper 模型: {model_size} ← {repo_id}")
        hf_download(repo_id, local_dir=model_path, local_dir_use_symlinks=False)
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
    """结构化健康状态——任何子项异常都不应让整个 endpoint 5xx。

    每个字段：'ok' | 'missing' | 'error'。
    前端 useCheckBackend 用 /sys_check 做存活判定（不依赖外部依赖），
    /sys_health 用来在设置页区分「后端没起」vs「后端起了但 ffmpeg 缺」vs「DB 写不进去」等更细的状态。
    """
    ffmpeg_status = "ok"
    try:
        ensure_ffmpeg_or_raise()
    except Exception:
        ffmpeg_status = "missing"

    db_status = "ok"
    try:
        from app.db.engine import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # 当前转写器配置 + 模型是否已下载（用 model.bin 落盘判定，与 transcriber 加载逻辑一致）
    whisper_info: dict = {"size": None, "type": None, "downloaded": False, "checked": False}
    try:
        cfg = transcriber_config_manager.get_config()
        size = cfg["whisper_model_size"]
        ttype = cfg["transcriber_type"]
        whisper_info["size"] = size
        whisper_info["type"] = ttype
        # 只有本地引擎才有「下载」概念；groq / bcut / kuaishou 在线引擎跳过
        if ttype == "fast-whisper":
            whisper_info["downloaded"] = _check_whisper_model_exists(size, "whisper")
            whisper_info["checked"] = True
        elif ttype == "mlx-whisper":
            whisper_info["downloaded"] = _check_mlx_whisper_model_exists(size)
            whisper_info["checked"] = True
    except Exception:
        pass

    return R.success(data={
        "backend": "ok",
        "ffmpeg": ffmpeg_status,
        "db": db_status,
        "whisper_model": whisper_info,
    })


@router.get("/sys_check")
async def sys_check():
    """轻量存活判定：后端进程能响应这个 endpoint 就算「起来了」，不查外部依赖。

    给桌面端 useCheckBackend / Tauri ready-probe 用。
    """
    return R.success()


@router.get("/deploy_status")
async def deploy_status():
    """返回部署监控所需的所有状态信息。

    所有子项都用 try 包起来——监控页本身不应该被任何一个子项打死。
    特别是 torch：它只在 fast-whisper 路径用得到，用 Groq / 必剪 / 快手在线
    引擎的轻量部署完全可以不装，那种情况这个 endpoint 不应该 500。
    """
    import os

    # CUDA 状态
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        cuda_info = {
            "available": cuda_available,
            "torch_installed": True,
            "version": torch.version.cuda if cuda_available else None,
            "gpu_name": torch.cuda.get_device_name(0) if cuda_available else None,
        }
    except Exception:
        cuda_info = {
            "available": False,
            "torch_installed": False,
            "version": None,
            "gpu_name": None,
        }

    # Whisper 模型 / 转写器配置 + 本地下载状态
    try:
        transcriber_cfg = transcriber_config_manager.get_config()
        size = transcriber_cfg["whisper_model_size"]
        ttype = transcriber_cfg["transcriber_type"]
        if ttype == "fast-whisper":
            downloaded = _check_whisper_model_exists(size, "whisper")
        elif ttype == "mlx-whisper":
            downloaded = _check_mlx_whisper_model_exists(size)
        else:
            downloaded = False  # 在线引擎无下载概念
        whisper_info = {
            "model_size": size,
            "transcriber_type": ttype,
            "downloaded": downloaded,
        }
    except Exception:
        whisper_info = {"model_size": None, "transcriber_type": None, "downloaded": False}

    # FFmpeg 状态
    try:
        ensure_ffmpeg_or_raise()
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False

    return R.success(data={
        "backend": {"status": "running", "port": int(os.getenv("BACKEND_PORT", 8483))},
        "cuda": cuda_info,
        "whisper": whisper_info,
        "ffmpeg": {"available": ffmpeg_ok},
    })