import json
import pathlib
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks

# 部分轻量单元测试会向 sys.modules 注入没有 __path__ 的 app 桩模块。
# 清掉这些桩，确保本测试无论在单独运行还是 discover 全量运行时都能导入真实路由。
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.routers import note as note_router


class TestGenerateNoteBatch(unittest.TestCase):
    def _request(self, p_start=2, p_end=34):
        return note_router.BatchVideoRequest(
            video_url=(
                "https://www.bilibili.com/video/BV1YY4y1i7SN"
                "?spm_id_from=333.788&vd_source=test&p=2"
            ),
            platform="bilibili",
            quality="medium",
            model_name="test-model",
            provider_id="test-provider",
            format=[],
            style="minimal",
            grid_size=[2, 2],
            p_start=p_start,
            p_end=p_end,
        )

    @staticmethod
    def _series(total=40):
        return {
            "bvid": "BV1YY4y1i7SN",
            "title": "计算机组成与设计：RISC-V",
            "total": total,
            "pages": [
                {"p": p, "title": f"第 {p} 讲", "duration": 600}
                for p in range(1, total + 1)
            ],
        }

    def test_p2_to_p34_creates_33_independent_tasks_without_running_them(self):
        downloader = Mock()
        downloader.get_series_info.return_value = self._series()
        background = BackgroundTasks()

        with (
            patch.object(note_router, "_submission_gate", return_value=None),
            patch.dict(note_router.SUPPORT_PLATFORM_MAP, {"bilibili": downloader}),
            patch.object(note_router, "NoteGenerator") as generator,
        ):
            response = note_router.generate_note_batch(self._request(), background)

        payload = json.loads(response.body)
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["total"], 33)
        self.assertEqual(data["tasks"][0]["p"], 2)
        self.assertEqual(data["tasks"][-1]["p"], 34)
        self.assertEqual(
            data["tasks"][0]["video_url"],
            "https://www.bilibili.com/video/BV1YY4y1i7SN?p=2",
        )
        self.assertEqual(
            data["tasks"][-1]["video_url"],
            "https://www.bilibili.com/video/BV1YY4y1i7SN?p=34",
        )
        self.assertEqual(len({item["task_id"] for item in data["tasks"]}), 33)
        self.assertEqual(generator.return_value._update_status.call_count, 33)
        self.assertEqual(len(background.tasks), 1)

    def test_rejects_range_beyond_series_without_creating_tasks(self):
        downloader = Mock()
        downloader.get_series_info.return_value = self._series(total=30)
        background = BackgroundTasks()

        with (
            patch.object(note_router, "_submission_gate", return_value=None),
            patch.dict(note_router.SUPPORT_PLATFORM_MAP, {"bilibili": downloader}),
            patch.object(note_router, "NoteGenerator") as generator,
        ):
            response = note_router.generate_note_batch(self._request(), background)

        payload = json.loads(response.body)
        self.assertEqual(payload["code"], 300104)
        self.assertEqual(payload["data"]["reason"], "page_range_exceeded")
        generator.assert_not_called()
        self.assertEqual(len(background.tasks), 0)


if __name__ == "__main__":
    unittest.main()
