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
    logger.info(f"FFMPEG_BIN_PATH: {ffmpeg_bin_path}")
    if ffmpeg_bin_path and os.path.isdir(ffmpeg_bin_path):
        os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"使用FFMPEG_BIN_PATH: {ffmpeg_bin_path}")
    else:
        # 遍历系统PATH寻找ffmpeg.exe
        system_path = os.environ.get("PATH", "")
        path_dirs = system_path.split(os.pathsep)
        for path_dir in path_dirs:
            ffmpeg_exe_path = os.path.join(path_dir, "ffmpeg.exe")
            if os.path.isfile(ffmpeg_exe_path):
                os.environ["PATH"] = path_dir + os.pathsep + system_path
                logger.info(f"在系统PATH中找到ffmpeg: {path_dir}")
                break
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        logger.info("ffmpeg 已安装")
        return True
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        logger.info("ffmpeg 未安装")
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
