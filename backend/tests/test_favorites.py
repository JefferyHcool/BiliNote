import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks

from app.routers.favorites import (
    FavoriteBatchStartRequest,
    FavoritePageRequest,
    _favorite_batches,
    _favorite_batches_lock,
    get_bilibili_favorite_page,
    parse_favorite_id,
    run_favorite_batch,
    start_bilibili_favorite_batch,
)


class TestFavoriteIdParsing(unittest.TestCase):
    def test_parses_ml_favorite_url(self):
        self.assertEqual(
            parse_favorite_id("https://www.bilibili.com/list/ml123456789?spm_id_from=333"),
            "123456789",
        )

    def test_parses_space_favlist_url(self):
        self.assertEqual(
            parse_favorite_id("https://space.bilibili.com/123/favlist?fid=456"),
            "456",
        )

    def test_rejects_non_bilibili_hosts(self):
        with self.assertRaises(ValueError):
            parse_favorite_id("https://example.com/list/ml123")


class TestFavoritePageEndpoint(unittest.TestCase):
    def test_returns_video_page_without_returning_cookie(self):
        api_payload = {
            "code": 0,
            "data": {
                "info": {"title": "My List", "media_count": 1},
                "medias": [{
                    "bvid": "BV123",
                    "title": "Video title",
                    "cover": "https://example.com/cover.jpg",
                    "duration": 60,
                    "upper": {"name": "Uploader"},
                }],
                "has_more": False,
            },
        }
        response = type("Response", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: api_payload,
        })()
        with (
            patch("app.routers.favorites.CookieConfigManager.get", return_value="SESSDATA=secret"),
            patch("app.routers.favorites.httpx.get", return_value=response) as request,
        ):
            result = get_bilibili_favorite_page(
                FavoritePageRequest(favorite_url="https://www.bilibili.com/list/ml456", page=1)
            )

        body = json.loads(result.body)
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["title"], "My List")
        self.assertEqual(body["data"]["videos"][0]["video_url"], "https://www.bilibili.com/video/BV123")
        self.assertNotIn("secret", result.body.decode("utf-8"))
        self.assertEqual(request.call_args.kwargs["headers"]["Cookie"], "SESSDATA=secret")

    def test_expands_multi_page_video_into_distinct_items(self):
        favorite_payload = {
            "code": 0,
            "data": {
                "info": {"title": "My List", "media_count": 1},
                "medias": [{
                    "bvid": "BV123",
                    "title": "A multi-page video",
                    "page": 3,
                    "upper": {"name": "Uploader"},
                }],
                "has_more": False,
            },
        }
        favorite_response = type("Response", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: favorite_payload,
        })()
        page_response = type("Response", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "code": 0,
                "data": {
                    "pages": [
                        {"page": 1, "part": "先导课：必看"},
                        {"page": 2, "part": "第一课：新闻类公文"},
                        {"page": 3, "part": "第二课：作文怎么写"},
                    ],
                },
            },
        })()
        with (
            patch("app.routers.favorites.CookieConfigManager.get", return_value="SESSDATA=secret"),
            patch(
                "app.routers.favorites.httpx.get",
                side_effect=[favorite_response, page_response],
            ),
        ):
            result = get_bilibili_favorite_page(
                FavoritePageRequest(favorite_url="https://www.bilibili.com/list/ml456", page=1)
            )

        body = json.loads(result.body)
        videos = body["data"]["videos"]
        self.assertEqual([video["video_key"] for video in videos], ["BV123_p1", "BV123_p2", "BV123_p3"])
        self.assertEqual(
            [video["video_url"] for video in videos],
            [
                "https://www.bilibili.com/video/BV123?p=1",
                "https://www.bilibili.com/video/BV123?p=2",
                "https://www.bilibili.com/video/BV123?p=3",
            ],
        )
        self.assertEqual(
            [video["title"] for video in videos],
            ["先导课：必看", "第一课：新闻类公文", "第二课：作文怎么写"],
        )
        self.assertEqual([video["page_number"] for video in videos], [1, 2, 3])
        self.assertEqual(body["data"]["media_count"], 1)

    def test_requires_saved_cookie(self):
        with patch("app.routers.favorites.CookieConfigManager.get", return_value=None):
            result = get_bilibili_favorite_page(
                FavoritePageRequest(favorite_url="https://www.bilibili.com/list/ml456", page=1)
            )

        body = json.loads(result.body)
        self.assertEqual(body["code"], 401)


class TestFavoriteBatchExecution(unittest.TestCase):
    def test_start_schedules_backend_batch_and_assigns_task_ids(self):
        request = FavoriteBatchStartRequest.model_validate({
            "favorite_folder": {
                "id": "456",
                "title": "My List",
                "url": "https://www.bilibili.com/list/ml456",
            },
            "videos": [{
                "video_key": "BV123_p1",
                "bvid": "BV123",
                "title": "Part 1",
                "video_url": "https://www.bilibili.com/video/BV123?p=1",
                "page_number": 1,
                "page_count": 2,
            }],
            "config": {
                "quality": "medium",
                "model_name": "test-model",
                "provider_id": "test-provider",
                "format": [],
                "style": "minimal",
            },
        })

        class Tasks:
            def __init__(self):
                self.calls = []

            def add_task(self, fn, *args, **kwargs):
                self.calls.append((fn, args, kwargs))

        tasks = Tasks()
        with (
            patch(
                "app.services.transcriber_config_manager.TranscriberConfigManager.is_model_ready",
                return_value={"ready": True},
            ),
            patch("app.routers.favorites._write_batch_task_status"),
        ):
            response = start_bilibili_favorite_batch(request, tasks)

        body = json.loads(response.body)
        batch = body["data"]
        self.assertEqual(body["code"], 0)
        self.assertEqual(len(batch["videos"]), 1)
        self.assertTrue(batch["videos"][0]["task_id"])
        self.assertEqual(batch["videos"][0]["status"], "queued")
        self.assertEqual(tasks.calls[0][0], run_favorite_batch)
        self.assertEqual(tasks.calls[0][1], (batch["batch_id"],))
        with _favorite_batches_lock:
            _favorite_batches.pop(batch["batch_id"], None)

    def test_worker_runs_items_in_order_and_pauses_at_item_boundary(self):
        batch_id = "test-favorite-batch"
        task_ids = ["test-task-1", "test-task-2"]
        with _favorite_batches_lock:
            _favorite_batches[batch_id] = {
                "batch_id": batch_id,
                "state": "running",
                "favorite_folder": {"id": "456", "title": "My List", "url": "https://bilibili.com"},
                "config": {
                    "quality": "medium",
                    "model_name": "test-model",
                    "provider_id": "test-provider",
                    "link": False,
                    "screenshot": False,
                    "format": [],
                    "style": "minimal",
                    "extras": "",
                    "video_understanding": False,
                    "video_interval": 0,
                    "grid_size": [],
                },
                "videos": [{
                    "task_id": task_id,
                    "video_key": f"BV123_p{index}",
                    "bvid": "BV123",
                    "title": f"Part {index}",
                    "video_url": f"https://www.bilibili.com/video/BV123?p={index}",
                    "status": "queued",
                    "error": None,
                } for index, task_id in enumerate(task_ids, start=1)],
                "next_index": 0,
                "current_index": None,
                "pause_requested": False,
                "worker_active": True,
            }

        calls = []

        def complete_first_and_request_pause(task_id, *args):
            calls.append(task_id)
            with _favorite_batches_lock:
                _favorite_batches[batch_id]["pause_requested"] = True
            return SimpleNamespace(markdown="note")

        with patch("app.routers.note.run_note_task", side_effect=complete_first_and_request_pause):
            run_favorite_batch(batch_id)

        with _favorite_batches_lock:
            batch = _favorite_batches[batch_id]
            self.assertEqual(batch["state"], "paused")
            self.assertEqual(batch["next_index"], 1)
            self.assertEqual([video["status"] for video in batch["videos"]], ["success", "queued"])
            batch["state"] = "running"
            batch["worker_active"] = True
            batch["pause_requested"] = False

        with (
            patch("app.routers.note.run_note_task", return_value=None),
            patch("app.routers.favorites._task_status_message", return_value="generation failed"),
        ):
            run_favorite_batch(batch_id)

        with _favorite_batches_lock:
            batch = _favorite_batches.pop(batch_id)
        self.assertEqual(calls, [task_ids[0]])
        self.assertEqual(batch["state"], "done")
        self.assertEqual([video["status"] for video in batch["videos"]], ["success", "failed"])
        self.assertEqual(batch["videos"][1]["error"], "generation failed")

    def test_worker_restarts_stale_in_progress_task_using_same_task_id(self):
        batch_id = "test-recovered-favorite-batch"
        task_id = "72a79d7b-fbb0-4866-a2e1-acdf14af29d4"
        with _favorite_batches_lock:
            _favorite_batches[batch_id] = {
                "batch_id": batch_id,
                "state": "running",
                "favorite_folder": {"id": "456", "title": "My List", "url": "https://bilibili.com"},
                "config": {
                    "quality": "medium",
                    "model_name": "test-model",
                    "provider_id": "test-provider",
                    "link": False,
                    "screenshot": False,
                    "format": [],
                    "style": "minimal",
                    "extras": "",
                    "video_understanding": False,
                    "video_interval": 0,
                    "grid_size": [],
                },
                "videos": [{
                    "task_id": task_id,
                    "resume_task_id": task_id,
                    "video_key": "BV123_p1",
                    "bvid": "BV123",
                    "title": "Part 1",
                    "video_url": "https://www.bilibili.com/video/BV123?p=1",
                    "status": "running",
                    "error": None,
                }],
                "next_index": 0,
                "current_index": None,
                "pause_requested": False,
                "worker_active": True,
            }

        with (
            patch("app.routers.note.is_note_task_active", return_value=False),
            patch("app.routers.note.run_note_task", return_value=SimpleNamespace(markdown="recovered note")) as run_task,
            patch("app.routers.favorites._read_task_status", return_value={"status": "TRANSCRIBING"}),
            patch("app.services.note.NOTE_OUTPUT_DIR", "unused-note-results"),
        ):
            run_favorite_batch(batch_id)

        with _favorite_batches_lock:
            batch = _favorite_batches.pop(batch_id)
        self.assertEqual(run_task.call_args.args[0], task_id)
        self.assertEqual(batch["state"], "done")
        self.assertEqual(batch["videos"][0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
