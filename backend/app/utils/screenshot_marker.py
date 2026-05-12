import re
from typing import List, Tuple


def extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
    pattern = r"(\*?Screenshot-(?:\[((?:\d{2}:)?\d{2}:\d{2})\]|((?:\d{2}:)?\d{2}:\d{2}))\*?)"
    results: List[Tuple[str, int]] = []
    for match in re.finditer(pattern, markdown):
        timestamp = match.group(2) or match.group(3)
        parts = [int(part) for part in timestamp.split(":")]
        if len(parts) == 2:
            mm, ss = parts
            total_seconds = mm * 60 + ss
        else:
            hh, mm, ss = parts
            total_seconds = hh * 3600 + mm * 60 + ss
        results.append((match.group(1), total_seconds))
    return results
