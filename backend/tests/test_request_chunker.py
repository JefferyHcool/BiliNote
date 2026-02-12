import importlib.util
import pathlib
import unittest
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "gpt" / "request_chunker.py"
spec = importlib.util.spec_from_file_location("request_chunker", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("request_chunker module spec not found")
request_chunker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(request_chunker)
RequestChunker = request_chunker.RequestChunker


@dataclass
class DummySeg:
    start: float
    end: float
    text: str


def build_messages(segments, image_urls, **_):
    content = [{"type": "text", "text": "".join(s.text for s in segments)}]
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url, "detail": "auto"}})
    return [{"role": "user", "content": content}]


def size_estimator(messages):
    size = 0
    for part in messages[0]["content"]:
        if part["type"] == "text":
            size += len(part["text"])
        else:
            size += len(part["image_url"]["url"])
    return size


class TestRequestChunker(unittest.TestCase):
    def test_chunk_segments_preserves_order_and_content(self):
        segments = [
            DummySeg(0, 1, "aaaa"),
            DummySeg(1, 2, "bbbb"),
            DummySeg(2, 3, "cccc"),
        ]
        chunker = RequestChunker(build_messages, max_bytes=8, size_estimator=size_estimator)
        chunks = chunker.chunk(segments, [])
        texts = ["".join(seg.text for seg in c.segments) for c in chunks]
        self.assertEqual("".join(texts), "aaaabbbbcccc")
        self.assertTrue(all(texts))

    def test_chunk_images_distributed_across_batches(self):
        segments = [DummySeg(0, 1, "aa")]
        images = ["i" * 6, "j" * 6, "k" * 6]
        chunker = RequestChunker(build_messages, max_bytes=10, size_estimator=size_estimator)
        chunks = chunker.chunk(segments, images)
        all_images = [img for c in chunks for img in c.image_urls]
        self.assertEqual(all_images, images)

    def test_chunk_images_are_not_front_loaded_when_multiple_segment_chunks(self):
        segments = [
            DummySeg(0, 1, "aaaaaa"),
            DummySeg(1, 2, "bbbbbb"),
            DummySeg(2, 3, "cccccc"),
        ]
        images = ["11111", "22222", "33333"]
        chunker = RequestChunker(build_messages, max_bytes=12, size_estimator=size_estimator)
        chunks = chunker.chunk(segments, images)

        self.assertGreaterEqual(len(chunks), 3)
        image_counts = [len(c.image_urls) for c in chunks]
        self.assertGreater(image_counts[1], 0)
        self.assertGreater(image_counts[2], 0)
        all_images = [img for c in chunks for img in c.image_urls]
        self.assertEqual(all_images, images)

    def test_split_oversized_segment(self):
        segments = [DummySeg(0, 1, "x" * 25)]
        chunker = RequestChunker(build_messages, max_bytes=10, size_estimator=size_estimator)
        chunks = chunker.chunk(segments, [])
        combined = "".join(seg.text for c in chunks for seg in c.segments)
        self.assertEqual(combined, "x" * 25)

    def test_group_texts_by_budget(self):
        chunker = RequestChunker(build_messages, max_bytes=10, size_estimator=size_estimator)

        def build_text_messages(texts, *_args, **_kwargs):
            content = [{"type": "text", "text": "".join(texts)}]
            return [{"role": "user", "content": content}]

        groups = chunker.group_texts_by_budget(["aaaaa", "bbbbb", "ccccc"], build_text_messages)
        self.assertEqual(groups, [["aaaaa", "bbbbb"], ["ccccc"]])


if __name__ == "__main__":
    unittest.main()
