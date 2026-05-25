import json
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.vector_store import VectorStoreManager
from app.utils.logger import get_logger

logger = get_logger(__name__)

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))

TASK_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
TASK_ARTIFACT_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"(?:_(?:audio|markdown|request|transcript))?$"
)
TASK_ARTIFACT_SUFFIXES = ("_audio", "_markdown", "_request", "_transcript")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"读取 JSON 失败: {path}, {e}")
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _base_task_id_from_artifact(stem: str) -> str | None:
    if TASK_ID_RE.match(stem):
        return stem

    for suffix in TASK_ARTIFACT_SUFFIXES:
        if stem.endswith(suffix):
            candidate = stem[:-len(suffix)]
            if TASK_ID_RE.match(candidate):
                return candidate

    return None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def persist_task_request(task_id: str, form_data: dict[str, Any], video_id: str | None = None) -> None:
    """Persist request metadata so pending tasks and generated notes can sync to other devices."""
    payload = {
        "task_id": task_id,
        "video_id": video_id,
        "platform": form_data.get("platform"),
        "form_data": form_data,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _write_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json", payload)


def save_note_result(task_id: str, note: Any, form_data: dict[str, Any] | None = None) -> dict[str, Any]:
    request_meta = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json") or {}
    note_payload = _jsonable(note)
    payload = {
        **note_payload,
        "task_id": task_id,
        "created_at": request_meta.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
    }
    if form_data or request_meta.get("form_data"):
        payload["form_data"] = form_data or request_meta.get("form_data")

    _write_json(NOTE_OUTPUT_DIR / f"{task_id}.json", payload)
    return payload


def _infer_form_data(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    request_meta = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json") or {}
    if isinstance(payload.get("form_data"), dict):
        return payload["form_data"]
    if isinstance(request_meta.get("form_data"), dict):
        return request_meta["form_data"]

    audio_meta = payload.get("audio_meta") or {}
    raw_info = audio_meta.get("raw_info") or {}
    return {
        "video_url": raw_info.get("webpage_url") or raw_info.get("original_url") or "",
        "platform": audio_meta.get("platform") or request_meta.get("platform") or "",
        "quality": "medium",
        "model_name": "",
        "provider_id": "",
        "style": "minimal",
        "format": [],
        "screenshot": False,
        "link": False,
        "extras": "",
        "video_understanding": False,
        "video_interval": 6,
        "grid_size": [2, 2],
    }


def _status_for_task(task_id: str, has_result: bool) -> tuple[str, str]:
    status = _read_json(NOTE_OUTPUT_DIR / f"{task_id}.status.json")
    if status:
        return status.get("status") or ("SUCCESS" if has_result else "PENDING"), status.get("message") or ""
    return ("SUCCESS" if has_result else "PENDING"), ""


def _audio_meta_for_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    audio_meta = payload.get("audio_meta")
    if isinstance(audio_meta, dict):
        return audio_meta
    audio = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_audio.json") or {}
    return audio if isinstance(audio, dict) else {}


def list_notes() -> list[dict[str, Any]]:
    NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    task_ids: set[str] = set()
    for path in NOTE_OUTPUT_DIR.glob("*.json"):
        name = path.name
        if name.endswith(".status.json"):
            # 旧逻辑会把 <task_id>_markdown.status.json 误当成一个真实任务，
            # 导致网页端出现删不掉的“等待中”伪任务。这里只同步真实 task_id。
            task_id = _base_task_id_from_artifact(name[:-len(".status.json")])
            if task_id and TASK_ID_RE.match(task_id):
                task_ids.add(task_id)
            continue
        stem = path.stem
        task_id = _base_task_id_from_artifact(stem)
        if task_id:
            task_ids.add(task_id)

    notes = []
    for task_id in task_ids:
        result_path = NOTE_OUTPUT_DIR / f"{task_id}.json"
        payload = _read_json(result_path) or {}
        has_result = result_path.exists() and bool(payload)
        status, message = _status_for_task(task_id, has_result)
        request_meta = _read_json(NOTE_OUTPUT_DIR / f"{task_id}_request.json") or {}

        mtime = result_path.stat().st_mtime if result_path.exists() else (
            (NOTE_OUTPUT_DIR / f"{task_id}.status.json").stat().st_mtime
            if (NOTE_OUTPUT_DIR / f"{task_id}.status.json").exists()
            else 0
        )
        updated_at = payload.get("updated_at") or request_meta.get("updated_at") or (
            datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else _now_iso()
        )
        created_at = payload.get("created_at") or request_meta.get("created_at") or updated_at

        notes.append({
            "task_id": task_id,
            "id": task_id,
            "status": status,
            "message": message,
            "created_at": created_at,
            "updated_at": updated_at,
            "markdown": payload.get("markdown") or "",
            "transcript": payload.get("transcript") or {"full_text": "", "language": "", "raw": None, "segments": []},
            "audio_meta": _audio_meta_for_task(task_id, payload),
            "form_data": _infer_form_data(task_id, payload),
        })

    return sorted(notes, key=lambda item: item.get("updated_at") or "", reverse=True)


def delete_note_artifacts(task_id: str) -> int:
    """Delete persisted note artifacts for one task. Returns deleted file count."""
    deleted = 0
    if not TASK_ARTIFACT_ID_RE.match(task_id or ""):
        return 0

    for path in NOTE_OUTPUT_DIR.glob(f"{task_id}*"):
        if path.is_file():
            try:
                path.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"删除笔记文件失败: {path}, {e}")

    try:
        VectorStoreManager().delete_index(task_id)
    except Exception as e:
        logger.warning(f"删除向量索引失败: {task_id}, {e}")

    return deleted

