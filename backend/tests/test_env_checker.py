import types
import unittest
from unittest.mock import patch

from app.utils.env_checker import get_cuda_device_with_memory_headroom


class TestCudaDeviceSelection(unittest.TestCase):
    def test_selects_candidate_with_highest_free_memory_ratio(self):
        output = """\
0, 6000, 10000, Busy GPU
1, 9000, 10000, Available GPU
2, 3000, 10000, Low-memory GPU
"""
        completed = types.SimpleNamespace(stdout=output)
        with patch("app.utils.env_checker.shutil.which", return_value="/usr/bin/nvidia-smi"):
            with patch("app.utils.env_checker.subprocess.run", return_value=completed):
                selected = get_cuda_device_with_memory_headroom()

        self.assertEqual(selected["index"], 1)
        self.assertEqual(selected["name"], "Available GPU")
        self.assertEqual(selected["free_memory_ratio"], 0.9)

    def test_requires_strictly_more_than_half_free_memory(self):
        completed = types.SimpleNamespace(stdout="0, 5000, 10000, Half GPU\n1, 4900, 10000, Busy GPU\n")
        with patch("app.utils.env_checker.shutil.which", return_value="/usr/bin/nvidia-smi"):
            with patch("app.utils.env_checker.subprocess.run", return_value=completed):
                selected = get_cuda_device_with_memory_headroom()

        self.assertIsNone(selected)

    def test_returns_none_when_nvidia_smi_is_unavailable(self):
        with patch("app.utils.env_checker.shutil.which", return_value=None):
            selected = get_cuda_device_with_memory_headroom()

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
