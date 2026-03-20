from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.utils.response import ResponseWrapper as R

from app.services.cookie_manager import CookieConfigManager
from ffmpeg_helper import ensure_ffmpeg_or_raise

router = APIRouter()
cookie_manager = CookieConfigManager()


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
    
    # Whisper 模型状态
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    transcriber_type = os.getenv("TRANSCRIBER_TYPE", "fast-whisper")
    
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