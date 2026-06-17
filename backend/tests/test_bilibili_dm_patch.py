"""
TDD coverage for the Bilibili wbi/playurl dm_img risk-control patch.

Background: around 2026-06, Bilibili's `x/player/wbi/playurl` gateway began
rejecting requests that omit the browser fingerprint params
(dm_img_list / dm_img_str / dm_cover_img_str / dm_img_inter + web_location)
with HTTP 412. yt-dlp (incl. latest) does not yet send these for playurl, so
videos whose web page does not inline playinfo (forcing the API call) fail.

These tests verify our yt-dlp monkey-patch injects those params *before* wbi
signing, and that caller-supplied query params still win.
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "downloaders" / "bilibili_dm_patch.py"
spec = importlib.util.spec_from_file_location("bilibili_dm_patch", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("bilibili_dm_patch module spec not found")
bilibili_dm_patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bilibili_dm_patch)

REQUIRED_KEYS = {
    "web_location",
    "dm_img_list",
    "dm_img_str",
    "dm_cover_img_str",
    "dm_img_inter",
}


class BuildDmImgParamsTest(unittest.TestCase):
    def test_contains_all_required_risk_control_keys(self):
        params = bilibili_dm_patch.build_dm_img_params()
        self.assertTrue(REQUIRED_KEYS.issubset(params.keys()))

    def test_web_location_is_expected_sentinel(self):
        self.assertEqual(bilibili_dm_patch.build_dm_img_params()["web_location"], 1550101)


class ApplyPatchTest(unittest.TestCase):
    def setUp(self):
        try:
            import yt_dlp.extractor.bilibili  # noqa: F401
        except Exception as exc:  # pragma: no cover - env without yt-dlp
            self.skipTest(f"yt-dlp not importable: {exc}")

    def test_patch_is_idempotent(self):
        from yt_dlp.extractor.bilibili import BilibiliBaseIE

        self.assertTrue(bilibili_dm_patch.apply_bilibili_dm_img_patch())
        first = BilibiliBaseIE._download_playinfo
        self.assertTrue(bilibili_dm_patch.apply_bilibili_dm_img_patch())
        self.assertIs(BilibiliBaseIE._download_playinfo, first)

    def test_dm_params_reach_wbi_signing_with_caller_query_preserved(self):
        from yt_dlp import YoutubeDL
        from yt_dlp.extractor.bilibili import BilibiliBaseIE

        bilibili_dm_patch.apply_bilibili_dm_img_patch()

        captured = {}

        def fake_sign_wbi(params, video_id):
            # Capture the exact params handed to wbi signing (just before the
            # HTTP request). dm_* must already be present here, pre-signature.
            captured.update(params)
            return params

        def fake_download_json(url, video_id, **kwargs):
            # Avoid any network; the real playurl call would 412 without dm_*.
            return {"data": {"ok": True}}

        ie = BilibiliBaseIE(YoutubeDL({"quiet": True}))
        ie._sign_wbi = fake_sign_wbi
        ie._download_json = fake_download_json

        ie._download_playinfo("BV1X9L16oEgB", 4242, headers={}, query={"qn": 64})

        self.assertTrue(
            REQUIRED_KEYS.issubset(captured.keys()),
            f"missing dm_* keys, got: {sorted(captured)}",
        )
        self.assertEqual(captured["web_location"], 1550101)
        # caller-supplied query must survive the merge
        self.assertEqual(captured["qn"], 64)
        # the original method still builds its base params
        self.assertEqual(captured["bvid"], "BV1X9L16oEgB")


if __name__ == "__main__":
    unittest.main()
