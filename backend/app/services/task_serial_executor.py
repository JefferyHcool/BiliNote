import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class SerialTaskExecutor:
    """Run note generation tasks with bounded concurrency.

    Heavy note tasks can be slow, so the worker count is configurable. Keep the
    default conservative because Bilibili/CDP and online ASR providers may rate
    limit or fail when too many jobs are started at once.
    """

    def __init__(self, max_workers: int = 1):
        self.max_workers = max(1, int(max_workers))
        self._state_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="note-worker")
        self._queued = 0
        self._active = 0
        self._queued_task_ids: list[str] = []
        self._active_task_ids: list[str] = []

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        task_id = args[0] if args and isinstance(args[0], str) else None
        with self._state_lock:
            self._queued += 1
            if task_id:
                self._queued_task_ids.append(task_id)

        def _wrapped():
            with self._state_lock:
                self._queued = max(0, self._queued - 1)
                self._active += 1
                if task_id and task_id in self._queued_task_ids:
                    self._queued_task_ids.remove(task_id)
                if task_id:
                    self._active_task_ids.append(task_id)
            try:
                return fn(*args, **kwargs)
            finally:
                with self._state_lock:
                    self._active = max(0, self._active - 1)
                    if task_id and task_id in self._active_task_ids:
                        self._active_task_ids.remove(task_id)

        return self._executor.submit(_wrapped)

    def queue_size(self) -> int:
        with self._state_lock:
            return self._queued

    def active_count(self) -> int:
        with self._state_lock:
            return self._active

    def stats(self) -> dict[str, int]:
        with self._state_lock:
            return {
                "max_workers": self.max_workers,
                "queued": self._queued,
                "active": self._active,
                "queued_task_ids": list(self._queued_task_ids),
                "active_task_ids": list(self._active_task_ids),
            }

    def has_task(self, task_id: str) -> bool:
        with self._state_lock:
            return task_id in self._queued_task_ids or task_id in self._active_task_ids

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)


def _env_int(name: str, default: int) -> int:
    try:
        return int(__import__("os").getenv(name, str(default)))
    except Exception:
        return default


task_serial_executor = SerialTaskExecutor(max_workers=_env_int("NOTE_TASK_MAX_WORKERS", 2))
