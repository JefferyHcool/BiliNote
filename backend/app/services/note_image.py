import json
import mimetypes
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Optional


MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}


class NoteImageError(ValueError):
    pass


class NoteImageManager:
    """Manage editor-uploaded images without exposing arbitrary filesystem paths."""

    def __init__(self, default_directory: Optional[Path] = None):
        backend_root = Path(__file__).resolve().parents[2]
        self.default_directory = (
            Path(default_directory).expanduser().resolve()
            if default_directory
            else (backend_root / "data" / "note_images").resolve()
        )
        self.registry_path = self.default_directory / ".image-index.json"
        self._lock = threading.RLock()

    def get_default_directory(self) -> str:
        return str(self.default_directory)

    def save_image(
        self,
        content: bytes,
        original_name: str,
        content_type: Optional[str],
        save_directory: Optional[str] = None,
    ) -> dict:
        if not content:
            raise NoteImageError("图片内容为空")
        if len(content) > MAX_IMAGE_BYTES:
            raise NoteImageError("图片不能超过 15 MB")

        mime_type, extension = self._validate_type(original_name, content_type)
        target_directory = self._resolve_directory(save_directory)
        try:
            target_directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise NoteImageError(f"无法创建图片目录：{exc}") from exc
        if not os.access(target_directory, os.W_OK):
            raise NoteImageError(f"图片目录不可写：{target_directory}")

        image_id = uuid.uuid4().hex
        safe_stem = self._safe_stem(Path(original_name or "image").stem)
        filename = f"{safe_stem}-{image_id[:10]}{extension}"
        target_path = target_directory / filename

        try:
            target_path.write_bytes(content)
        except OSError as exc:
            raise NoteImageError(f"图片保存失败：{exc}") from exc

        record = {
            "id": image_id,
            "path": str(target_path.resolve()),
            "filename": filename,
            "original_name": original_name or filename,
            "content_type": mime_type,
            "size": len(content),
        }
        try:
            with self._lock:
                records = self._load_registry()
                records[image_id] = record
                self._write_registry(records)
        except Exception as exc:
            target_path.unlink(missing_ok=True)
            if isinstance(exc, NoteImageError):
                raise
            raise NoteImageError(f"图片索引保存失败：{exc}") from exc
        return record

    def get_image(self, image_id: str) -> dict:
        self._validate_id(image_id)
        with self._lock:
            record = self._load_registry().get(image_id)
        if not record:
            raise FileNotFoundError("图片不存在或已被删除")

        image_path = Path(record["path"])
        if not image_path.is_file():
            raise FileNotFoundError("图片文件不存在")
        return record

    def delete_image(self, image_id: str) -> bool:
        self._validate_id(image_id)
        with self._lock:
            records = self._load_registry()
            record = records.pop(image_id, None)
            if not record:
                return False
            self._write_registry(records)

        Path(record["path"]).unlink(missing_ok=True)
        return True

    def _resolve_directory(self, save_directory: Optional[str]) -> Path:
        if not save_directory or not save_directory.strip():
            return self.default_directory

        candidate = Path(save_directory.strip()).expanduser()
        if not candidate.is_absolute():
            # Relative custom paths are resolved from the BiliNote repository root.
            repository_root = Path(__file__).resolve().parents[3]
            candidate = repository_root / candidate
        return candidate.resolve()

    @staticmethod
    def _validate_type(original_name: str, content_type: Optional[str]) -> tuple[str, str]:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        guessed_type, _ = mimetypes.guess_type(original_name or "")
        mime_type = normalized_type if normalized_type in ALLOWED_IMAGE_TYPES else guessed_type
        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise NoteImageError("仅支持 PNG、JPG、GIF、WebP、BMP 和 SVG 图片")
        return mime_type, ALLOWED_IMAGE_TYPES[mime_type]

    @staticmethod
    def _safe_stem(value: str) -> str:
        cleaned = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
        return cleaned.strip("-_")[:60] or "image"

    @staticmethod
    def _validate_id(image_id: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", image_id or ""):
            raise FileNotFoundError("图片不存在")

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {}
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_registry(self, records: dict) -> None:
        self.default_directory.mkdir(parents=True, exist_ok=True)
        temporary_path = self.registry_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.registry_path)


note_image_manager = NoteImageManager()
