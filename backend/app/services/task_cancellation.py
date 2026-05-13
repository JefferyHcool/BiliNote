import threading

_lock = threading.Lock()
_cancelled: set[str] = set()


class TaskCancelledError(Exception):
    pass


def cancel(task_id: str) -> None:
    with _lock:
        _cancelled.add(task_id)


def is_cancelled(task_id: str) -> bool:
    with _lock:
        return task_id in _cancelled


def check_cancelled(task_id: str) -> None:
    if is_cancelled(task_id):
        raise TaskCancelledError(task_id)


def clear(task_id: str) -> None:
    with _lock:
        _cancelled.discard(task_id)
