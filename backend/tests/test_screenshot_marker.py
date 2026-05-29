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

    def test_extract_accepts_single_digit_minutes(self):
        """LLM 有时输出 1-digit 分钟（如 *Screenshot-[1:05]），本应兼容"""
        markdown = "*Screenshot-[1:05]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [("*Screenshot-[1:05]", 65)])

    def test_extract_accepts_single_digit_both(self):
        """兼容分钟和秒都是 1-digit 的情况（如 *Screenshot-[1:5]）"""
        markdown = "*Screenshot-[1:5]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [("*Screenshot-[1:5]", 65)])

    def test_extract_accepts_mixed_digits(self):
        """混合 1-digit 和 2-digit 格式"""
        markdown = "A *Screenshot-[01:05] B *Screenshot-[1:05] C *Screenshot-[1:5]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(
            matches,
            [
                ("*Screenshot-[01:05]", 65),
                ("*Screenshot-[1:05]", 65),
                ("*Screenshot-[1:5]", 65),
            ],
        )

    def test_extract_without_asterisk_single_digit(self):
        """Screenshot- 不带星号 + 1-digit 分钟"""
        markdown = "Screenshot-[1:05]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [("Screenshot-[1:05]", 65)])

    def test_extract_long_timestamp(self):
        """10 分钟以上时间戳（如 10:30），确保多位数字正常匹配"""
        markdown = "*Screenshot-[10:30]"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [("*Screenshot-[10:30]", 630)])

    def test_extract_no_match(self):
        """不含截图标记的文本应返回空列表"""
        markdown = "这是一段普通文本，没有截图标记"
        matches = extract_screenshot_timestamps(markdown)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
