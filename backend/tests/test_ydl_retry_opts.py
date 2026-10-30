"""
Coverage for the yt-dlp retry settings shared by the downloaders.

Background: yt-dlp's documented `retries` default of 10 comes from its *command
line* option parser. Nothing applies that default to the Python API, so a
`YoutubeDL({...})` built without `retries` ends up in:

    # yt_dlp/downloader/http.py
    for retry in RetryManager(self.params.get('retries'), ...)   # -> None
    # yt_dlp/utils/_utils.py
    self.retries = _retries or 0                                 # -> 0

i.e. exactly one attempt and no retries. A single transient network hiccup
(observed: read timeout from upos-sz-mirrorcosov.bilivideo.com) then fails the
whole note task, even though an immediate re-run succeeds.

These tests pin both halves of the fix: the constant produces a real retry
budget, and every yt-dlp options dict in the downloaders actually carries it.
"""
import ast
import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOWNLOADERS = ROOT / "app" / "downloaders"
DOWNLOADER_SOURCES = ["youtube_downloader.py", "bilibili_downloader.py"]


def _load_base():
    """Load app/downloaders/base.py with its app-level imports stubbed out.

    The stubs are force-installed and rolled back on exit. base.py's `app.*`
    imports are all top-level, so they only need to exist while exec_module runs.

    `setdefault` was the bug: it silently kept whatever another collected test
    module had already put in sys.modules -- e.g. a partial transcriber_model stub
    that defines TranscriptSegment but not TranscriptResult -- and the import then
    died with "cannot import name 'TranscriptResult' ... (unknown location)". The
    file passed on its own and failed in a single-process suite run, purely
    because of collection order.
    """
    saved = dict(sys.modules)
    try:
        for name, attrs in {
            "app": {},
            "app.enmus": {},
            "app.models": {},
            "app.enmus.note_enums": {"DownloadQuality": str},
            "app.models.notes_model": {"AudioDownloadResult": object},
            "app.models.transcriber_model": {"TranscriptResult": object},
        }.items():
            module = types.ModuleType(name)
            module.__path__ = []  # behave like a package, not a leaf module
            for key, value in attrs.items():
                setattr(module, key, value)
            sys.modules[name] = module

        spec = importlib.util.spec_from_file_location("dl_base", DOWNLOADERS / "base.py")
        if spec is None or spec.loader is None:
            raise ImportError("base module spec not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        # Keys added inside the window get dropped; keys that did not exist before
        # (saved value is None) must be removed too -- writing None back into
        # sys.modules breaks every later `import app.*` in the same process.
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]


class RetryOptsValueTest(unittest.TestCase):
    def setUp(self):
        self.base = _load_base()

    def test_retry_budget_is_not_zero(self):
        try:
            from yt_dlp.utils import RetryManager
        except Exception as exc:  # pragma: no cover - env without yt-dlp
            self.skipTest(f"yt-dlp not importable: {exc}")

        retries = self.base.YDL_RETRY_OPTS["retries"]
        budget = RetryManager(retries, lambda *a, **k: None).retries
        self.assertGreater(budget, 0)

    def test_documents_the_zero_default_being_guarded_against(self):
        """The bug this guards: an unset `retries` collapses to a 0 budget."""
        try:
            from yt_dlp.utils import RetryManager
        except Exception as exc:  # pragma: no cover - env without yt-dlp
            self.skipTest(f"yt-dlp not importable: {exc}")

        self.assertEqual(RetryManager(None, lambda *a, **k: None).retries, 0)

    def test_socket_timeout_is_bounded(self):
        # Without a bound, a stalled read can hang a task instead of failing
        # fast enough for the retries above to be useful.
        timeout = self.base.YDL_RETRY_OPTS["socket_timeout"]
        self.assertGreater(timeout, 0)


class RetryOptsAreAppliedTest(unittest.TestCase):
    """
    Structural check: every `ydl_opts = {...}` literal in the downloaders must
    unpack YDL_RETRY_OPTS. Catches a newly added download path that silently
    goes back to the zero-retry default.
    """

    def _ydl_opts_dicts(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "ydl_opts" in names:
                found.append(node.value)
        return found

    def test_every_ydl_opts_dict_unpacks_retry_opts(self):
        for filename in DOWNLOADER_SOURCES:
            path = DOWNLOADERS / filename
            dicts = self._ydl_opts_dicts(path)
            self.assertTrue(dicts, f"no ydl_opts dict found in {filename}")

            for index, node in enumerate(dicts):
                with self.subTest(file=filename, dict_index=index, line=node.lineno):
                    unpacked = {
                        value.id
                        for key, value in zip(node.keys, node.values)
                        if key is None and isinstance(value, ast.Name)
                    }
                    self.assertIn(
                        "YDL_RETRY_OPTS",
                        unpacked,
                        f"{filename}:{node.lineno} builds yt-dlp options without "
                        f"YDL_RETRY_OPTS, so it gets zero retries",
                    )


if __name__ == "__main__":
    unittest.main()
