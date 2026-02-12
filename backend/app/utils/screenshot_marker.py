import re
from typing import List, Tuple


def extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
    pattern = r"(\*?Screenshot-(?:\[(\d{2}):(\d{2})\]|(\d{2}):(\d{2})))"
    results: List[Tuple[str, int]] = []
    for match in re.finditer(pattern, markdown):
        mm = match.group(2) or match.group(4)
        ss = match.group(3) or match.group(5)
        total_seconds = int(mm) * 60 + int(ss)
        results.append((match.group(1), total_seconds))
    return results
