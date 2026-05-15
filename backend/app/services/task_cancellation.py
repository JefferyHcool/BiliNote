import os

from app.utils.path_helper import get_app_dir

_cancel_dir = get_app_dir("runtime_locks")


class TaskCancelledError(Exception):
    pass


def _cancel_path(task_id: str) -> str:
    return os.path.join(_cancel_dir, f"{task_id}.cancel")


def cancel(task_id: str) -> None:
    os.makedirs(_cancel_dir, exist_ok=True)
    open(_cancel_path(task_id), "w").close()


def is_cancelled(task_id: str) -> bool:
    return os.path.exists(_cancel_path(task_id))


def check_cancelled(task_id: str) -> None:
    if is_cancelled(task_id):
        raise TaskCancelledError(task_id)


def clear(task_id: str) -> None:
    try:
        os.unlink(_cancel_path(task_id))
    except FileNotFoundError:
        pass
