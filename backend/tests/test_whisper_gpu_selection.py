import unittest
from unittest.mock import patch

from app.transcriber import whisper


class TestWhisperGpuSelection(unittest.TestCase):
    def test_selected_device_index_is_passed_to_faster_whisper(self):
        selected_device = {
            "index": 5,
            "name": "NVIDIA RTX A6000",
            "free_memory_bytes": 90,
            "total_memory_bytes": 100,
            "free_memory_ratio": 0.9,
        }
        with (
            patch.object(whisper, "get_cuda_device_with_memory_headroom", return_value=selected_device),
            patch.object(whisper, "get_model_dir", return_value="/tmp/models"),
            patch.object(whisper, "resolve_whisper_model", return_value="tiny"),
            patch.object(whisper, "WhisperModel") as model_factory,
        ):
            transcriber = whisper.WhisperTranscriber(model_size="tiny", device="cuda")

        self.assertEqual(transcriber.device, "cuda")
        self.assertEqual(transcriber.device_index, 5)
        self.assertEqual(model_factory.call_args.kwargs["device_index"], 5)

    def test_falls_back_to_cpu_when_no_device_meets_the_threshold(self):
        with (
            patch.object(whisper, "get_cuda_device_with_memory_headroom", return_value=None),
            patch.object(whisper, "is_torch_installed", return_value=True),
            patch.object(whisper, "get_model_dir", return_value="/tmp/models"),
            patch.object(whisper, "resolve_whisper_model", return_value="tiny"),
            patch.object(whisper, "WhisperModel") as model_factory,
        ):
            transcriber = whisper.WhisperTranscriber(model_size="tiny", device="cuda")

        self.assertEqual(transcriber.device, "cpu")
        self.assertIsNone(transcriber.device_index)
        self.assertNotIn("device_index", model_factory.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
