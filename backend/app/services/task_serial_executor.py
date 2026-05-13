import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable

from app.utils.path_helper import get_app_dir

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "default"


class ConcurrentTaskExecutor:
    """按队列 key 分组执行任务。

    同一个 key 使用单线程队列串行执行，不同 key 使用不同线程池并发执行。
    同时用文件锁兜住多个 backend 进程并存时的同 key 并发问题。
    """

    def __init__(self, max_workers: int | None = None):
        self._executors: dict[str, ThreadPoolExecutor] = {}
        self._lock = threading.Lock()
        self._lock_dir = get_app_dir("runtime_locks")

    def _get_executor(self, queue_key: str) -> ThreadPoolExecutor:
        safe_queue_key = _safe_key(queue_key)
        with self._lock:
            executor = self._executors.get(safe_queue_key)
            if executor is None:
                executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"task-{safe_queue_key[:24]}")
                self._executors[safe_queue_key] = executor
            return executor

    def _run_with_process_lock(self, queue_key: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if fcntl is None:
            return fn(*args, **kwargs)

        lock_path = os.path.join(self._lock_dir, f"{_safe_key(queue_key)}.lock")
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                return fn(*args, **kwargs)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def run(self, queue_key: str | Callable[..., Any], fn: Callable[..., Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        if fn is None and callable(queue_key):
            fn = queue_key
            queue_key = "default"
        if fn is None:
            raise ValueError("task function is required")

        executor = self._get_executor(str(queue_key))
        future: Future = executor.submit(self._run_with_process_lock, str(queue_key), fn, *args, **kwargs)
        return future.result()

    def shutdown(self, wait: bool = True):
        with self._lock:
            executors = list(self._executors.values())
            self._executors.clear()
        for executor in executors:
            executor.shutdown(wait=wait)


# 保持向后兼容的导出名
SerialTaskExecutor = ConcurrentTaskExecutor
task_serial_executor = ConcurrentTaskExecutor()
