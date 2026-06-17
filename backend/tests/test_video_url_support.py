import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(name, relative_path):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{name} module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


url_parser = _load_module("url_parser", pathlib.Path("app") / "utils" / "url_parser.py")
video_url_validator = _load_module(
    "video_url_validator",
    pathlib.Path("app") / "validators" / "video_url_validator.py",
)


class TestVideoUrlSupport(unittest.TestCase):
    def test_extract_youtube_video_id_from_supported_url_shapes(self):
        expected_id = "dQw4w9WgXcQ"

        cases = [
            f"https://www.youtube.com/watch?v={expected_id}",
            f"https://youtu.be/{expected_id}",
            f"https://www.youtube.com/shorts/{expected_id}",
        ]

        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(
                    url_parser.extract_video_id(url, "youtube"),
                    expected_id,
                )

    def test_accepts_youtube_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"

        self.assertTrue(video_url_validator.is_supported_video_url(url))


if __name__ == "__main__":
    unittest.main()
