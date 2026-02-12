import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "screenshot_marker.py"
spec = importlib.util.spec_from_file_location("screenshot_marker", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("screenshot_marker module spec not found")
screenshot_marker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screenshot_marker)
extract_screenshot_timestamps = screenshot_marker.extract_screenshot_timestamps


class TestScreenshotMarker(unittest.TestCase):
    def test_extract_accepts_star_bracket_format(self):
        markdown = "A\n*Screenshot-[01:02]\nB"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [("*Screenshot-[01:02]", 62)])

    def test_extract_accepts_legacy_formats(self):
        markdown = "*Screenshot-03:04 and Screenshot-[05:06]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(
            matches,
            [
                ("*Screenshot-03:04", 184),
                ("Screenshot-[05:06]", 306),
            ],
        )


if __name__ == "__main__":
    unittest.main()
