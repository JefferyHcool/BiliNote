"""Retire transcripts derived from the old Douyin music download path."""
import json
from pathlib import Path
from uuid import uuid4


def retire_legacy_douyin_cache(audio_cache: Path, transcript_cache: Path) -> bool:
    if not audio_cache.exists() and not transcript_cache.exists():
        return False
    try:
        data = json.loads(audio_cache.read_text(encoding="utf-8"))
        if data.get("raw_info", {}).get("audio_source") == "video_track_v1":
            return False
    except (OSError, ValueError, AttributeError):
        pass
    # Keep old results recoverable, but prevent retries from reusing music transcripts.
    suffix = f".legacy-music-{uuid4().hex}.bak"
    for path in (transcript_cache, audio_cache):
        if path.exists():
            path.rename(path.with_name(path.name + suffix))
    return True
