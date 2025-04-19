import os

import uvicorn
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.utils.logger import get_logger
from app import create_app
from app.db.video_task_dao import init_video_task_table
from app.transcriber.transcriber_provider import get_transcriber
from events import register_handler
from ffmpeg_helper import ensure_ffmpeg_or_raise

logger = get_logger(__name__)
load_dotenv()

# 读取 .env 中的路径
static_path = os.getenv('STATIC', '/static')
out_dir = os.getenv('OUT_DIR', './static/screenshots')

# 自动创建本地目录（static 和 static/screenshots）
static_dir = "static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

app = create_app()
app.mount(static_path, StaticFiles(directory=static_dir), name="static")

async def startup_event():
    register_handler()
@app.on_event("startup")
async def startup_event():
    register_handler()
    ensure_ffmpeg_or_raise()
    get_transcriber(transcriber_type=os.getenv("TRANSCRIBER_TYPE","fast-whisper"))
    init_video_task_table()

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8000))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)