"""whisper / mlx 模型后台下载状态跟踪（含失败原因）。

routers.config 的「触发下载」与「查询状态」共享这份进程内内存态：
  - key：fast-whisper 直接用 model_size；mlx 用 "mlx-{size}" 前缀（与历史一致）
  - 状态：downloading / done / failed；failed 时另存最近一次错误原因

为什么抽成独立的轻量模块（仅依赖 logger）：
  1) 把原先散落在 config.py 多处的字符串状态赋值收敛到一处，避免拼写漂移；
  2) 失败原因能透传到 /transcriber_models_status → 前端，修复「下载失败前端无任何
     提示、状态一直显示未下载」（issue #402 的衍生问题：原先状态接口只回传
     downloading/downloaded 两个布尔，failed 态被直接丢弃）；
  3) 不引入 faster_whisper / ctranslate2 等重依赖，可被单测隔离加载。
"""
from typing import Dict, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

DOWNLOADING = "downloading"
DONE = "done"
FAILED = "failed"

# key -> 状态字符串；key -> 最近一次失败原因（仅 failed 时有意义）
_status: Dict[str, str] = {}
_errors: Dict[str, str] = {}


def mark_downloading(key: str) -> None:
    _status[key] = DOWNLOADING
    _errors.pop(key, None)  # 重新开始下载，清掉上一次的失败原因


def mark_done(key: str) -> None:
    _status[key] = DONE
    _errors.pop(key, None)


def mark_failed(key: str, error: str = "") -> None:
    _status[key] = FAILED
    if error:
        _errors[key] = error


def get_status(key: str) -> Optional[str]:
    return _status.get(key)


def is_downloading(key: str) -> bool:
    return _status.get(key) == DOWNLOADING


def get_error(key: str) -> Optional[str]:
    return _errors.get(key)


def status_row(name: str, downloaded: bool, key: Optional[str] = None) -> dict:
    """构造单个模型给前端的状态行：downloaded / downloading / failed (+error)。

    key 默认用 name；mlx 传 "mlx-{size}"。已下载成功（downloaded=True）的模型
    一律不回传 failed/error——避免「先失败后又下好」时残留旧的错误状态。
    """
    k = key if key is not None else name
    st = _status.get(k)
    row: dict = {
        "model_size": name,
        "downloaded": downloaded,
        "downloading": st == DOWNLOADING,
        "failed": (not downloaded) and st == FAILED,
    }
    if row["failed"]:
        err = _errors.get(k)
        if err:
            row["error"] = err
    return row
