import os
import subprocess
from dotenv import load_dotenv

from app.utils.logger import get_logger
logger = get_logger(__name__)

load_dotenv()
def check_ffmpeg_exists() -> bool:
    """
    检查 ffmpeg 是否可用。优先使用 FFMPEG_BIN_PATH 环境变量指定的路径。
    """
    ffmpeg_bin_path = os.getenv("FFMPEG_BIN_PATH")
    
    # 1. 如果配置了自定义路径，将其注入当前进程的 PATH 前缀
    if ffmpeg_bin_path:
        if os.path.isdir(ffmpeg_bin_path):
            os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"已将 FFMPEG_BIN_PATH 加入搜索路径: {ffmpeg_bin_path}")
        else:
            logger.warning(f"配置的 FFMPEG_BIN_PATH 不是有效目录: {ffmpeg_bin_path}")

    # 2. 直接尝试运行 ffmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            check=True
        )
        logger.info("ffmpeg 已安装")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("ffmpeg 未安装")
        return False


def ensure_ffmpeg_or_raise():
    """
    校验 ffmpeg 是否可用，否则抛出异常并提示安装方式。
    """
    if not check_ffmpeg_exists():
        logger.error("未检测到 ffmpeg，请先安装后再使用本功能。")
        raise EnvironmentError(
            " 未检测到 ffmpeg，请先安装后再使用本功能。\n"
            "👉 下载地址：https://ffmpeg.org/download.html\n"
            "🪟 Windows 推荐：https://www.gyan.dev/ffmpeg/builds/\n"
            "💡 如果你已安装，请将其路径写入 `.env` 文件，例如：\n"
            "FFMPEG_BIN_PATH=/your/custom/ffmpeg/bin"
        )
