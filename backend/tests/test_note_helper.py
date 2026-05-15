import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "note_helper.py"
spec = importlib.util.spec_from_file_location("note_helper", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("note_helper module spec not found")
note_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(note_helper)


class TestNoteHelper(unittest.TestCase):
    def test_replace_content_markers_standard(self):
        md = "## 简介 *Content-[04:16]*"
        result = note_helper.replace_content_markers(md, "BV1xx411c7mD", "bilibili")
        self.assertIn("t=256", result)
        self.assertIn("04:16", result)

    def test_replace_content_markers_three_digit_minutes(self):
        """长视频：100:03 → 6003s"""
        md = "## 长节 *Content-[100:03]*"
        result = note_helper.replace_content_markers(md, "BV1xx", "bilibili")
        self.assertIn("t=6003", result)

    def test_replace_content_markers_hour_format(self):
        """长视频：1:40:03 → 6003s（1h40m3s = 3600+2400+3）"""
        md = "## 超长节 *Content-[1:40:03]*"
        result = note_helper.replace_content_markers(md, "BV1xx", "bilibili")
        self.assertIn("t=6003", result)

    def test_prepend_source_link_adds_header_at_top(self):
        source_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        markdown = "## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertTrue(result.startswith(f"> 来源链接：{source_url}\n\n"))
        self.assertIn("## 标题", result)

    def test_prepend_source_link_does_not_duplicate_when_header_exists(self):
        source_url = "https://www.youtube.com/watch?v=abc123"
        markdown = f"> 来源链接：{source_url}\n\n## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertEqual(result, markdown)


class TestStripContentMarkers(unittest.TestCase):
    def test_strip_bracketed_mmss(self):
        md = "## 简介 *Content-[04:16]*\n正文"
        result = note_helper.strip_content_markers(md)
        self.assertNotIn("Content-", result)
        self.assertIn("## 简介", result)
        self.assertIn("正文", result)

    def test_strip_bracketed_hhmmss(self):
        md = "## 节 *Content-[1:40:03]*"
        result = note_helper.strip_content_markers(md)
        self.assertNotIn("Content-", result)

    def test_strip_unbracketed(self):
        md = "文字 Content-04:16 更多文字"
        result = note_helper.strip_content_markers(md)
        self.assertNotIn("Content-", result)
        self.assertIn("更多文字", result)

    def test_does_not_strip_plain_time_expressions(self):
        md = "第3分钟时讲到了这个概念，大约在1:30左右。"
        result = note_helper.strip_content_markers(md)
        self.assertEqual(result, md)

    def test_strips_multiple_markers(self):
        md = "- 节一 *Content-[00:00]*\n- 节二 *Content-[02:30]*\n- 节三 *Content-[1:00:00]*"
        result = note_helper.strip_content_markers(md)
        self.assertNotIn("Content-", result)
        self.assertIn("节一", result)
        self.assertIn("节二", result)
        self.assertIn("节三", result)

    def test_empty_string(self):
        self.assertEqual(note_helper.strip_content_markers(""), "")


class TestStripScreenshotMarkers(unittest.TestCase):
    def test_strip_bracketed(self):
        md = "段落 *Screenshot-[03:45]* 继续"
        result = note_helper.strip_screenshot_markers(md)
        self.assertNotIn("Screenshot-", result)
        self.assertIn("段落", result)
        self.assertIn("继续", result)

    def test_strip_bracketed_hhmmss(self):
        md = "*Screenshot-[1:20:00]*"
        result = note_helper.strip_screenshot_markers(md)
        self.assertNotIn("Screenshot-", result)

    def test_strip_unbracketed(self):
        md = "文字 Screenshot-03:45 结尾"
        result = note_helper.strip_screenshot_markers(md)
        self.assertNotIn("Screenshot-", result)

    def test_does_not_touch_content_markers(self):
        md = "## 节 *Content-[01:00]* *Screenshot-[01:00]*"
        result = note_helper.strip_screenshot_markers(md)
        self.assertIn("Content-[01:00]", result)
        self.assertNotIn("Screenshot-", result)

    def test_content_markers_unaffected_by_screenshot_strip(self):
        md = "*Content-[00:30]* 正文 *Screenshot-[00:30]*"
        result = note_helper.strip_screenshot_markers(md)
        self.assertIn("Content-[00:30]", result)
        self.assertNotIn("Screenshot-", result)

    def test_empty_string(self):
        self.assertEqual(note_helper.strip_screenshot_markers(""), "")


if __name__ == "__main__":
    unittest.main()
