import tempfile
import unittest
from pathlib import Path

from app.services.note_image import NoteImageError, NoteImageManager


class TestNoteImageManager(unittest.TestCase):
    def test_save_read_and_delete_default_image(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = NoteImageManager(Path(directory) / "default")
            record = manager.save_image(b"png-data", "课程 截图.png", "image/png")

            self.assertTrue(Path(record["path"]).is_file())
            self.assertEqual(manager.get_image(record["id"])["original_name"], "课程 截图.png")
            self.assertTrue(manager.delete_image(record["id"]))
            self.assertFalse(Path(record["path"]).exists())
            with self.assertRaises(FileNotFoundError):
                manager.get_image(record["id"])

    def test_custom_directory_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = NoteImageManager(root / "default")
            record = manager.save_image(
                b"jpeg-data",
                "diagram.jpeg",
                "image/jpeg",
                str(root / "course-images"),
            )
            self.assertEqual(Path(record["path"]).parent, root / "course-images")

    def test_rejects_non_image_and_oversized_content(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = NoteImageManager(Path(directory) / "default")
            with self.assertRaises(NoteImageError):
                manager.save_image(b"text", "notes.txt", "text/plain")
            with self.assertRaises(NoteImageError):
                manager.save_image(b"x" * (15 * 1024 * 1024 + 1), "huge.png", "image/png")


if __name__ == "__main__":
    unittest.main()
