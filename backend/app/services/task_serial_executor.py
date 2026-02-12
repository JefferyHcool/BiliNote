import threading
from typing import Any, Callable


class SerialTaskExecutor:
    def __init__(self):
        self._lock = threading.Lock()

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return fn(*args, **kwargs)


task_serial_executor = SerialTaskExecutor()
