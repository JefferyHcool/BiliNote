"""
Patch yt-dlp's Bilibili extractor to inject the dm_img_* / web_location
risk-control parameters required by Bilibili's wbi/playurl gateway.

Background
----------
Around 2026-06 Bilibili's ``x/player/wbi/playurl`` gateway began rejecting
requests that omit the browser fingerprint params
``dm_img_list`` / ``dm_img_str`` / ``dm_cover_img_str`` / ``dm_img_inter`` +
``web_location`` with **HTTP 412**. Current yt-dlp (incl. the latest release)
does not send these for the playurl endpoint, so any video whose web page does
*not* inline ``playinfo`` — forcing yt-dlp onto the API path — fails with 412.
Refreshing cookies does not help; the params themselves are missing.

We inject dummy-but-well-formed values *before* wbi signing. The value shapes
deliberately mirror yt-dlp's own usage of the same fields for the
``x/space/wbi/arc/search`` endpoint (``BiliBiliSpaceIE``), which is the only
place upstream currently sends them.
"""
import base64
import logging
import random
import string

logger = logging.getLogger(__name__)


def build_dm_img_params() -> dict:
    """Return dummy ``dm_img_*`` / ``web_location`` params the gateway expects."""
    return {
        'web_location': 1550101,
        'dm_img_list': '[]',
        'dm_img_str': base64.b64encode(
            ''.join(random.choices(string.printable, k=random.randint(16, 64))).encode()
        )[:-2].decode(),
        'dm_cover_img_str': base64.b64encode(
            ''.join(random.choices(string.printable, k=random.randint(32, 128))).encode()
        )[:-2].decode(),
        'dm_img_inter': '{"ds":[],"wh":[6093,6631,31],"of":[430,760,380]}',
    }


def apply_bilibili_dm_img_patch() -> bool:
    """
    Monkey-patch ``BilibiliBaseIE._download_playinfo`` to inject dm_img params.

    Idempotent and defensive: returns ``True`` if the patch is in place (whether
    applied now or previously), ``False`` if yt-dlp's internals could not be
    patched (logged, never raised — the caller stays functional).
    """
    try:
        from yt_dlp.extractor.bilibili import BilibiliBaseIE
    except Exception as e:  # yt-dlp missing or module layout changed upstream
        logger.warning("Bilibili dm_img patch skipped, cannot import extractor: %s", e)
        return False

    original = BilibiliBaseIE._download_playinfo
    if getattr(original, '_bili_dm_patched', False):
        return True

    def _patched_download_playinfo(self, bvid, cid, headers=None, query=None):
        # dm_* are merged into the query that the original method signs via
        # _sign_wbi; caller-supplied query params (e.g. try_look/qn) take
        # precedence over the injected dummies.
        merged_query = {**build_dm_img_params(), **(query or {})}
        return original(self, bvid, cid, headers=headers, query=merged_query)

    _patched_download_playinfo._bili_dm_patched = True
    BilibiliBaseIE._download_playinfo = _patched_download_playinfo
    logger.info("Applied Bilibili wbi/playurl dm_img patch to yt-dlp BilibiliBaseIE")
    return True
