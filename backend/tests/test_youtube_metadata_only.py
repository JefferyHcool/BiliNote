"""
Coverage for the YouTube "metadata only" download path.

Background: when a YouTube video already has subtitles, NoteGenerator skips the
audio download and calls `YoutubeDownloader.download(skip_download=True)` purely
to read title/duration/cover. That call used to still request
`format='bestaudio[ext=m4a]/bestaudio/best'`.

Whenever the installed yt-dlp lags behind YouTube's player, nsig extraction
fails, every audio/video format is dropped (only storyboard images remain) and
format selection raises "Requested format is not available" — killing a task
whose transcript had already been fetched successfully.

These tests pin the two guarantees of that path:
  1. skip_download implies ignore_no_formats_error, so a formatless extraction
     degrades to "no audio" instead of failing the whole note.
  2. ext falls back to m4a, since yt-dlp reports ext=None when skipping the
     download (dict.get's default does not fire on an explicit None).
"""
import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "downloaders" / "youtube_downloader.py"


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    # Tests in this repository load downloader modules with lightweight app
    # stubs. Replace a previous test's stub instead of inheriting it; otherwise
    # a prior import can leave AudioDownloadResult as ``object`` and turn this
    # metadata-only test into a TypeError unrelated to the behavior under test.
    sys.modules[name] = module
    return module


class _Downloader:
    def __init__(self):
        self.cache_data = "/tmp"


class _AudioDownloadResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _load_youtube_downloader():
    """Load the module with its app-level dependencies stubbed out.

    `_stub` intentionally overwrites whatever a previous test left in sys.modules
    (see its comment). That equally means this function has to hand those names
    back when it is done: path-less stubs for `app` / `app.utils` / `app.models`
    leaking into the process break every later `import app.*` -- collecting this
    file first (e.g. running the suite in reverse order) turned unrelated test
    modules into ModuleNotFoundError at collection time.
    """
    saved = dict(sys.modules)
    try:
        _stub("app")
        _stub("app.downloaders")
        _stub("app.models")
        _stub("app.services")
        _stub("app.utils")
        _stub(
            "app.downloaders.base",
            Downloader=_Downloader,
            DownloadQuality=str,
            YDL_RETRY_OPTS={"retries": 3, "fragment_retries": 3, "socket_timeout": 30},
        )
        _stub("app.downloaders.youtube_subtitle", YouTubeSubtitleFetcher=object)
        _stub("app.models.notes_model", AudioDownloadResult=_AudioDownloadResult)
        _stub("app.models.transcriber_model", TranscriptResult=object)
        _stub(
            "app.services.proxy_config_manager",
            ProxyConfigManager=type(
                "ProxyConfigManager", (), {"get_proxy_url": lambda self: None}
            ),
        )
        _stub("app.utils.path_helper", get_data_dir=lambda: "/tmp")
        _stub("app.utils.url_parser", extract_video_id=lambda url, platform: "vid")

        spec = importlib.util.spec_from_file_location("youtube_downloader", MODULE_PATH)
        if spec is None or spec.loader is None:
            raise ImportError("youtube_downloader module spec not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        # Drop keys added here and put back the ones `_stub` replaced. Writing a
        # saved value of None back into sys.modules would itself break imports.
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]


class _FakeYoutubeDL:
    """Records the opts it was constructed with; mimics a formatless extraction."""

    captured_opts = None

    def __init__(self, opts):
        type(self).captured_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=True):
        # What yt-dlp yields for a metadata-only extraction: no media, so no ext.
        return {
            "id": "CJ4ndXv3CkY",
            "title": "example",
            "duration": 2231,
            "thumbnail": "https://example.invalid/t.jpg",
            "ext": None,
            "tags": [],
        }


class YoutubeMetadataOnlyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.module = _load_youtube_downloader()
        except Exception as exc:  # pragma: no cover - env without yt-dlp
            raise unittest.SkipTest(f"youtube_downloader not importable: {exc}")

    def setUp(self):
        self._real_ydl = self.module.yt_dlp.YoutubeDL
        self.module.yt_dlp.YoutubeDL = _FakeYoutubeDL
        _FakeYoutubeDL.captured_opts = None

    def tearDown(self):
        self.module.yt_dlp.YoutubeDL = self._real_ydl

    def test_skip_download_tolerates_missing_formats(self):
        self.module.YoutubeDownloader().download(
            "https://www.youtube.com/watch?v=CJ4ndXv3CkY",
            output_dir="/tmp",
            skip_download=True,
        )
        self.assertTrue(_FakeYoutubeDL.captured_opts.get("ignore_no_formats_error"))

    def test_missing_ext_falls_back_to_m4a(self):
        result = self.module.YoutubeDownloader().download(
            "https://www.youtube.com/watch?v=CJ4ndXv3CkY",
            output_dir="/tmp",
            skip_download=True,
        )
        self.assertTrue(result.file_path.endswith(".m4a"), result.file_path)
        self.assertNotIn("None", result.file_path)

    def test_full_download_still_selects_an_audio_format(self):
        self.module.YoutubeDownloader().download(
            "https://www.youtube.com/watch?v=CJ4ndXv3CkY",
            output_dir="/tmp",
        )
        opts = _FakeYoutubeDL.captured_opts
        self.assertIn("bestaudio", opts.get("format", ""))
        self.assertNotIn("ignore_no_formats_error", opts)


if __name__ == "__main__":
    unittest.main()
