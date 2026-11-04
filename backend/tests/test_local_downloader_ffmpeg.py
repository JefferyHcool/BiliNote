"""
Coverage for the local-upload "[WinError 2]" failure (issue #424).

Background: in the Tauri desktop build, a local video upload always failed
with "[WinError 2] The system cannot find the file specified". The upload
itself succeeded; note generation then died inside
``LocalDownloader.convert_to_mp3`` / ``extract_cover``, which invoked a bare
``'ffmpeg'`` and only caught ``CalledProcessError`` — so when the ffmpeg
executable could not be found (not on the backend process PATH and never
resolved through the repo's own ``FFMPEG_BIN_PATH`` setting), the raw
``FileNotFoundError`` from ``subprocess.run`` reached the user verbatim.

These tests pin the two guarantees of the fix:
  1. The ffmpeg executable is resolved through
     ``ffmpeg_helper.resolve_ffmpeg_executable`` (FFMPEG_BIN_PATH first,
     then PATH) and the resolved absolute path is what gets executed.
  2. A missing ffmpeg surfaces as a ``RuntimeError`` that names ffmpeg and
     explains how to install/configure it — never as a raw WinError 2.
"""
import importlib.util
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL_DOWNLOADER_PATH = ROOT / "app" / "downloaders" / "local_downloader.py"
FFMPEG_HELPER_PATH = ROOT / "ffmpeg_helper.py"

_STUBBED_KEYS = [
    "app",
    "app.downloaders",
    "app.enmus",
    "app.models",
    "app.utils",
    "app.utils.logger",
    "app.downloaders.base",
    "app.enmus.note_enums",
    "app.models.audio_model",
    "app.utils.video_helper",
    "dotenv",
    "ffmpeg_helper",
]


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _Downloader:
    def __init__(self):
        self.cache_data = "/tmp"


class _AudioDownloadResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# The stub ffmpeg_helper delegates to this holder so each test controls what
# the resolver returns without reloading the module under test.
_RESOLVE_HOLDER = {"value": None}


def _load_local_downloader():
    _stub("app")
    _stub("app.downloaders")
    _stub("app.enmus")
    _stub("app.models")
    _stub("app.utils")
    _stub("app.downloaders.base", Downloader=_Downloader)
    _stub("app.enmus.note_enums", DownloadQuality=str)
    _stub("app.models.audio_model", AudioDownloadResult=_AudioDownloadResult)
    _stub(
        "app.utils.video_helper",
        save_cover_to_static=lambda path, subfolder="cover": "/static/cover/x.jpg",
    )
    _stub(
        "ffmpeg_helper",
        resolve_ffmpeg_executable=lambda: _RESOLVE_HOLDER["value"],
    )
    spec = importlib.util.spec_from_file_location(
        "local_downloader_under_test", LOCAL_DOWNLOADER_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError("local_downloader module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_ffmpeg_helper():
    _stub("app")
    _stub("app.utils")
    _stub("app.utils.logger", get_logger=lambda name: logging.getLogger(name))
    _stub("dotenv", load_dotenv=lambda *args, **kwargs: None)
    spec = importlib.util.spec_from_file_location(
        "ffmpeg_helper_under_test", FFMPEG_HELPER_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError("ffmpeg_helper module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubbedModulesTestCase(unittest.TestCase):
    """Snapshot/restore sys.modules so this file's stubs never leak into
    other test modules sharing the pytest process."""

    def setUp(self):
        self._saved_modules = {key: sys.modules.get(key) for key in _STUBBED_KEYS}
        self.addCleanup(self._restore_modules)

    def _restore_modules(self):
        for key, module in self._saved_modules.items():
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module


class LocalDownloaderMissingFfmpegTest(_StubbedModulesTestCase):
    def setUp(self):
        super().setUp()
        self.module = _load_local_downloader()
        self.downloader = self.module.LocalDownloader()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.input_path = os.path.join(self._tmp.name, "sample.mp4")
        with open(self.input_path, "wb") as f:
            f.write(b"\x00" * 16)
        _RESOLVE_HOLDER["value"] = None

    def _assert_clear_ffmpeg_error(self, fn):
        with self.assertRaises(RuntimeError) as ctx:
            fn()
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)
        self.assertIn("ffmpeg", str(ctx.exception))
        self.assertNotIn("WinError", str(ctx.exception))

    def test_convert_to_mp3_missing_ffmpeg_raises_clear_error(self):
        self._assert_clear_ffmpeg_error(
            lambda: self.downloader.convert_to_mp3(self.input_path)
        )

    def test_extract_cover_missing_ffmpeg_raises_clear_error(self):
        self._assert_clear_ffmpeg_error(
            lambda: self.downloader.extract_cover(self.input_path)
        )

    def test_download_missing_ffmpeg_raises_clear_error(self):
        self._assert_clear_ffmpeg_error(
            lambda: self.downloader.download(self.input_path)
        )

    def test_vanished_executable_is_translated_to_clear_error(self):
        # Resolver found a path, but exec still raises FileNotFoundError
        # (e.g. the binary was removed between resolution and launch).
        _RESOLVE_HOLDER["value"] = os.path.join(self._tmp.name, "ffmpeg.exe")

        def _raising_run(*args, **kwargs):
            raise FileNotFoundError(2, "The system cannot find the file specified")

        with mock.patch.object(self.module.subprocess, "run", _raising_run):
            self._assert_clear_ffmpeg_error(
                lambda: self.downloader.convert_to_mp3(self.input_path)
            )
            self._assert_clear_ffmpeg_error(
                lambda: self.downloader.extract_cover(self.input_path)
            )


class LocalDownloaderResolvedFfmpegTest(_StubbedModulesTestCase):
    def setUp(self):
        super().setUp()
        self.module = _load_local_downloader()
        self.downloader = self.module.LocalDownloader()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.input_path = os.path.join(self._tmp.name, "sample.mp4")
        with open(self.input_path, "wb") as f:
            f.write(b"\x00" * 16)
        self.fake_ffmpeg = os.path.join(self._tmp.name, "ffmpeg.exe")
        _RESOLVE_HOLDER["value"] = self.fake_ffmpeg
        self.captured_commands = []

    def _fake_run(self, command, *args, **kwargs):
        self.captured_commands.append(command)
        # The downloader expects the output file (last argv) to exist.
        with open(command[-1], "wb") as f:
            f.write(b"out")
        return subprocess.CompletedProcess(command, 0)

    def test_convert_to_mp3_runs_resolved_executable(self):
        with mock.patch.object(self.module.subprocess, "run", self._fake_run):
            output_path = self.downloader.convert_to_mp3(self.input_path)
        self.assertEqual(self.captured_commands[0][0], self.fake_ffmpeg)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(output_path.endswith(".mp3"))

    def test_extract_cover_runs_resolved_executable(self):
        with mock.patch.object(self.module.subprocess, "run", self._fake_run):
            output_path = self.downloader.extract_cover(self.input_path)
        self.assertEqual(self.captured_commands[0][0], self.fake_ffmpeg)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(output_path.endswith("_cover.jpg"))


class ResolveFfmpegExecutableTest(_StubbedModulesTestCase):
    def setUp(self):
        super().setUp()
        self.helper = _load_ffmpeg_helper()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_bin_path_directory_containing_ffmpeg(self):
        exe = os.path.join(self._tmp.name, "ffmpeg.exe")
        with open(exe, "wb") as f:
            f.write(b"fake")
        with mock.patch.dict(os.environ, {"FFMPEG_BIN_PATH": self._tmp.name}):
            self.assertEqual(self.helper.resolve_ffmpeg_executable(), exe)

    def test_bin_path_direct_file(self):
        exe = os.path.join(self._tmp.name, "ffmpeg-custom")
        with open(exe, "wb") as f:
            f.write(b"fake")
        with mock.patch.dict(os.environ, {"FFMPEG_BIN_PATH": exe}):
            self.assertEqual(self.helper.resolve_ffmpeg_executable(), exe)

    def test_falls_back_to_path_lookup(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FFMPEG_BIN_PATH", None)
            with mock.patch.object(
                self.helper.shutil, "which", lambda name: "/some/bin/ffmpeg"
            ):
                self.assertEqual(
                    self.helper.resolve_ffmpeg_executable(), "/some/bin/ffmpeg"
                )

    def test_returns_none_when_not_found(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FFMPEG_BIN_PATH", None)
            with mock.patch.object(self.helper.shutil, "which", lambda name: None):
                self.assertIsNone(self.helper.resolve_ffmpeg_executable())


if __name__ == "__main__":
    unittest.main()
