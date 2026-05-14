import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.db.init_db import init_db
from app.db.provider_dao import seed_default_providers
from app.exceptions.exception_handlers import register_exception_handlers
# from app.db.model_dao import init_model_table
# from app.db.provider_dao import init_provider_table
from app.utils.logger import get_logger
from app import create_app
from app.services.transcriber_config_manager import TranscriberConfigManager
from events import register_handler
from ffmpeg_helper import ensure_ffmpeg_or_raise

logger = get_logger(__name__)
load_dotenv()

# 读取 .env 中的路径
static_path = os.getenv('STATIC', '/static')
out_dir = os.getenv('OUT_DIR', './static/screenshots')

# 自动创建本地目录（static 和 static/screenshots）
static_dir = "static"
uploads_dir = "uploads"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动序列拆成 5 步、每步独立日志 + 异常时打明确的 [startup N/5 FAILED] 标记。
    # 目的：用户 docker logs 一眼能看出后端死在哪一步，避免「容器一直重启但看不出原因」。
    try:
        logger.info("[startup 1/5] register_handler() — 注册事件处理器")
        register_handler()

        logger.info("[startup 2/5] init_db() — 初始化 SQLite 数据库")
        init_db()

        logger.info("[startup 3/5] TranscriberConfigManager — 读取转写器配置")
        # 转写器不再在启动时强制初始化，而是在首次生成笔记时按需创建。
        # 如果配置了不可用的类型（如 mlx-whisper 未安装），会在使用时报错而非静默回退。
        _cfg = TranscriberConfigManager().get_config()
        logger.info(
            f"           当前转写器: type={_cfg['transcriber_type']}, "
            f"model_size={_cfg['whisper_model_size']}"
        )

        logger.info("[startup 4/5] seed_default_providers() — 初始化默认 LLM 供应商")
        seed_default_providers()

        logger.info("[startup 5/5] 启动完成，等待请求")
    except Exception:
        logger.exception("[startup FAILED] 后端启动期异常，详见堆栈；容器会退出并由 restart 策略决定是否重试")
        raise

    yield

app = create_app(lifespan=lifespan)

# 允许的源：本地 web 端 + Tauri 桌面端 + 浏览器扩展（chrome/edge/firefox）
# 用 regex 是因为 chrome-extension://<id> 的 id 在每次开发版加载时不固定
# Tauri 2 不同平台 webview origin 不一样，必须全列：
#   - macOS:   tauri://localhost  （自定义协议）
#   - Windows: https://tauri.localhost  （Edge WebView2）
#   - Linux:   http://tauri.localhost   （WebKitGTK）
# 漏掉哪个都会导致桌面端 fetch 返回 200 但 browser 因为 CORS 拒绝读响应，
# 表现为前端「连不上后端」但后端日志一片 200 OK。
CORS_ORIGIN_REGEX = (
    r"^chrome-extension://[a-z]+$"
    r"|^moz-extension://.+$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    r"|^tauri://localhost$"
    r"|^https?://tauri\.localhost$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
register_exception_handlers(app)
app.mount(static_path, StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")









if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)