import inspect
import json

from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.enmus.task_status_enums import TaskStatus
from app.routers import note as note_router


def _response_payload(response):
    return json.loads(response.body.decode("utf-8"))


def test_empty_status_file_returns_pending_and_rewrites_json(tmp_path, monkeypatch):
    task_id = "empty-status"
    monkeypatch.setattr(note_router, "NOTE_OUTPUT_DIR", str(tmp_path))
    status_path = tmp_path / f"{task_id}.status.json"
    status_path.write_text("", encoding="utf-8")

    payload = _response_payload(note_router.get_task_status(task_id))

    assert payload["data"]["status"] == TaskStatus.PENDING.value
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == TaskStatus.PENDING.value


def test_invalid_status_file_returns_existing_result(tmp_path, monkeypatch):
    task_id = "invalid-status"
    monkeypatch.setattr(note_router, "NOTE_OUTPUT_DIR", str(tmp_path))
    (tmp_path / f"{task_id}.status.json").write_text("{", encoding="utf-8")
    (tmp_path / f"{task_id}.json").write_text('{"markdown": "done"}', encoding="utf-8")

    payload = _response_payload(note_router.get_task_status(task_id))

    assert payload["data"]["status"] == TaskStatus.SUCCESS.value
    assert payload["data"]["result"] == {"markdown": "done"}


def test_bilibili_downloader_accepts_skip_download_argument():
    signature = inspect.signature(BilibiliDownloader.download)

    assert "skip_download" in signature.parameters
