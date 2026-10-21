import importlib.util
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def _install_stubs():
    app_mod = types.ModuleType("app")
    utils_pkg = types.ModuleType("app.utils")

    logger_mod = types.ModuleType("app.utils.logger")

    class _Logger:
        @staticmethod
        def info(*_args, **_kwargs):
            return None

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def error(*_args, **_kwargs):
            return None

    def _get_logger(_name):
        return _Logger()

    logger_mod.get_logger = _get_logger

    path_helper_mod = types.ModuleType("app.utils.path_helper")
    ffmpeg_mod = types.ModuleType("ffmpeg")

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_draw_mod = types.ModuleType("PIL.ImageDraw")
    pil_font_mod = types.ModuleType("PIL.ImageFont")

    class _FakeImage:
        pass

    class _FakeImageDraw:
        @staticmethod
        def Draw(*_args, **_kwargs):
            return None

    class _FakeImageFont:
        @staticmethod
        def truetype(*_args, **_kwargs):
            return None

        @staticmethod
        def load_default():
            return None

    pil_image_mod.Image = _FakeImage
    pil_draw_mod.ImageDraw = _FakeImageDraw
    pil_font_mod.ImageFont = _FakeImageFont

    def _get_app_dir(name):
        return name

    path_helper_mod.get_app_dir = _get_app_dir
    ffmpeg_mod.probe = lambda *_args, **_kwargs: {"format": {"duration": "0"}}

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.utils", utils_pkg)
    sys.modules["PIL"] = pil_mod
    sys.modules["PIL.Image"] = pil_image_mod
    sys.modules["PIL.ImageDraw"] = pil_draw_mod
    sys.modules["PIL.ImageFont"] = pil_font_mod
    sys.modules["ffmpeg"] = ffmpeg_mod
    sys.modules["app.utils.logger"] = logger_mod
    sys.modules["app.utils.path_helper"] = path_helper_mod


def _load_video_reader_module():
    _install_stubs()
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "utils" / "video_reader.py"
    spec = importlib.util.spec_from_file_location("video_reader", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("video_reader module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


video_reader_module = _load_video_reader_module()
VideoReader = video_reader_module.VideoReader


def _make_fake_ffmpeg_runner(scene_stdout, colors_by_second):
    """同时模拟场景检测与抽帧两类 ffmpeg 调用。"""

    def _run(cmd, check=True, capture_output=False, text=False, timeout=None):
        args = [arg for arg in cmd if isinstance(arg, str)]
        if any("select=" in arg for arg in args):
            return types.SimpleNamespace(stdout=scene_stdout, stderr="")
        output_path = next((arg for arg in args if arg.endswith(".jpg")), None)
        if output_path is None:
            raise AssertionError("Output path not found in ffmpeg cmd")
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg$", output_path)
        if match is None:
            raise AssertionError("Unexpected output path")
        sec = int(match.group(1)) * 60 + int(match.group(2))
        payload = colors_by_second[sec]
        with open(output_path, "wb") as f:
            f.write(payload)
        return types.SimpleNamespace(stdout="", stderr="")

    return _run


class TestDetectSceneCuts(unittest.TestCase):
    def test_parses_pts_time_lines_into_sorted_unique_seconds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reader = VideoReader(video_path="dummy.mp4", frame_dir=str(tmp_dir), grid_dir=str(tmp_dir))
            stdout = (
                "frame:12 pts:1234 pts_time:16.08\n"
                "lavfi.scene_score=0.420000\n"
                "frame:48 pts:4321 pts_time:8.40\n"
                "lavfi.scene_score=0.510000\n"
                "frame:96 pts:8640 pts_time:16.9\n"
            )
            with patch.object(video_reader_module.subprocess, "run",
                              return_value=types.SimpleNamespace(stdout=stdout, stderr="")):
                cuts = reader._detect_scene_cuts()
        self.assertEqual(cuts, [8, 16])

    def test_returns_empty_list_when_ffmpeg_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reader = VideoReader(video_path="dummy.mp4", frame_dir=str(tmp_dir), grid_dir=str(tmp_dir))

            def _boom(*_args, **_kwargs):
                raise RuntimeError("ffmpeg missing")

            with patch.object(video_reader_module.subprocess, "run", side_effect=_boom):
                cuts = reader._detect_scene_cuts()
        self.assertEqual(cuts, [])


class TestPlanSceneTimestamps(unittest.TestCase):
    def test_always_includes_first_frame_and_respects_min_gap(self):
        planned = VideoReader._plan_scene_timestamps([1, 2, 60], duration=120, max_frames=100, min_gap=10)
        self.assertEqual(planned, [0, 60])

    def test_caps_at_max_frames(self):
        planned = VideoReader._plan_scene_timestamps([5, 10, 20, 30], duration=100, max_frames=2, min_gap=1)
        self.assertEqual(planned, [0, 5])

    def test_drops_cuts_beyond_duration(self):
        planned = VideoReader._plan_scene_timestamps([5, 90], duration=60, max_frames=100, min_gap=1)
        self.assertEqual(planned, [0, 5])


class TestExtractFramesWithSmartSampling(unittest.TestCase):
    def test_uses_scene_timestamps_when_available(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=10,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
                smart_sampling=True,
            )

            scene_stdout = "frame:0 pts_time:8.4\nlavfi.scene_score=0.51\nframe:1 pts_time:16.2\n"
            fake_colors = {0: b"frame-a", 8: b"frame-b", 10: b"frame-c", 16: b"frame-d", 20: b"frame-e"}

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "24"}}), \
                    patch.object(video_reader_module.subprocess, "run",
                                 side_effect=_make_fake_ffmpeg_runner(scene_stdout, fake_colors)):
                paths = reader.extract_frames(max_frames=100)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_08.jpg", "frame_00_16.jpg"])

    def test_falls_back_to_fixed_interval_when_no_scene_detected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=10,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
                smart_sampling=True,
            )

            fake_colors = {0: b"frame-a", 10: b"frame-b", 20: b"frame-c"}

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "24"}}), \
                    patch.object(video_reader_module.subprocess, "run",
                                 side_effect=_make_fake_ffmpeg_runner("", fake_colors)):
                paths = reader.extract_frames(max_frames=100)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_10.jpg", "frame_00_20.jpg"])

    def test_fixed_interval_used_when_smart_sampling_disabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=10,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
                smart_sampling=False,
            )

            fake_colors = {0: b"frame-a", 10: b"frame-b", 20: b"frame-c"}
            base_runner = _make_fake_ffmpeg_runner("", fake_colors)

            def _run(cmd, check=True, capture_output=False, text=False, timeout=None):
                args = [arg for arg in cmd if isinstance(arg, str)]
                if any("select=" in arg for arg in args):
                    raise AssertionError("scene detection should not run when smart_sampling is disabled")
                return base_runner(cmd, check=check, capture_output=capture_output, text=text, timeout=timeout)

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "24"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_run):
                paths = reader.extract_frames(max_frames=100)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_10.jpg", "frame_00_20.jpg"])


if __name__ == "__main__":
    unittest.main()
