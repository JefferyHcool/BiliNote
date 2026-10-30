import importlib.util
import os
import pathlib
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "task_serial_executor.py"
spec = importlib.util.spec_from_file_location("task_serial_executor", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("task_serial_executor module spec not found")
task_serial_executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_serial_executor)
executor_module = task_serial_executor
SerialTaskExecutor = executor_module.SerialTaskExecutor
ConcurrentTaskExecutor = executor_module.ConcurrentTaskExecutor


class TestTaskExecutor(unittest.TestCase):
    """task_serial_executor.py 的名字是历史包袱：c105342 已经把串行锁换成
    ThreadPoolExecutor（并发上限 = TASK_MAX_WORKERS，默认 3），只保留
    SerialTaskExecutor 作为兼容别名。原先这里断言 "peak_active == 1"，
    即要求严格串行，与实现有意提供的并发相矛盾，所以无论测试顺序如何都恒失败。
    下面按真实契约来断言。
    """

    def _make(self, **kwargs):
        executor = SerialTaskExecutor(**kwargs)
        self.addCleanup(executor.shutdown)
        return executor

    def test_run_returns_result_to_the_caller(self):
        executor = self._make(max_workers=2)
        self.assertEqual(executor.run(lambda a, b: a + b, 2, 3), 5)
        self.assertEqual(executor.run(lambda *, scale: scale * 2, scale=4), 8)

    def test_run_propagates_worker_exceptions(self):
        def boom():
            raise ValueError("transcribe failed")

        executor = self._make(max_workers=1)
        with self.assertRaises(ValueError):
            executor.run(boom)

    def test_concurrency_is_capped_at_max_workers(self):
        """并发是允许的，但绝不能越过 max_workers——这是它唯一的资源约束。"""
        workers = 3
        executor = self._make(max_workers=workers)
        state_lock = threading.Lock()
        state = {"active": 0, "peak_active": 0, "done": 0}

        def critical_work():
            with state_lock:
                state["active"] += 1
                state["peak_active"] = max(state["peak_active"], state["active"])
            time.sleep(0.05)
            with state_lock:
                state["active"] -= 1
                state["done"] += 1

        threads = [
            threading.Thread(target=lambda: executor.run(critical_work))
            for _ in range(workers + 5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(state["done"], workers + 5)
        self.assertLessEqual(state["peak_active"], workers)

    def test_tasks_actually_run_in_parallel(self):
        """反向锁死另一个方向：不许有人再把它悄悄改回串行。

        两个任务在同一道 barrier 上会合；若执行器串行，第一个任务会永远等不到
        同伴，barrier 超时 -> 本用例失败。
        """
        executor = self._make(max_workers=2)
        barrier = threading.Barrier(2, timeout=10)
        outcomes = []

        def rendezvous():
            try:
                barrier.wait()
                return "met"
            except threading.BrokenBarrierError:
                return "serialized"

        threads = [
            threading.Thread(target=lambda: outcomes.append(executor.run(rendezvous)))
            for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(outcomes), ["met", "met"])

    def test_default_worker_count_comes_from_env(self):
        os.environ["TASK_MAX_WORKERS"] = "2"
        self.addCleanup(os.environ.pop, "TASK_MAX_WORKERS")
        executor = SerialTaskExecutor()
        self.addCleanup(executor.shutdown)
        self.assertEqual(executor._max_workers, 2)

    def test_serial_alias_is_still_exported(self):
        """路由和调用方按旧名字 import，别名不能悄悄消失。"""
        self.assertIs(SerialTaskExecutor, ConcurrentTaskExecutor)
        self.assertIsInstance(executor_module.task_serial_executor, ConcurrentTaskExecutor)


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
