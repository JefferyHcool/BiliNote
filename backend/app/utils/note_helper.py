import re


_TIME_RE = r"(\d+:\d{2}(?::\d{2})?)"
_STRIP_CONTENT_RE = re.compile(
    r"\*?Content-(?:\[\d+:\d{2}(?::\d{2})?\]|\d+:\d{2}(?::\d{2})?)\*?"
)
_STRIP_SCREENSHOT_RE = re.compile(
    r"\*?Screenshot-(?:\[\d+:\d{2}(?::\d{2})?\]|\d+:\d{2}(?::\d{2})?)\*?"
)
_HEADING_TIME_RE = re.compile(
    rf"^(##|###)\s+(.+?)\s*(\*?Content-\[{_TIME_RE}\]\*?|\({_TIME_RE}\)\*?)\s*$",
    re.MULTILINE,
)
_TOC_HEADING_RE = re.compile(r"^##\s*目录\s*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^##\s+(?!目录\s*$).+", re.MULTILINE)
_TOC_TIME_RE = re.compile(r"Content-\[\d+:\d{2}|\(\d+:\d{2}")


def normalize_toc_timestamps(markdown: str | None) -> str | None:
    """
    补齐目录里的视频时间点。

    有些模型会给正文标题加时间点，但目录保持纯文本。这里从后续 ##/###
    标题反推目录，保证展示端和导出的 markdown 都能看到章节时间。
    """
    if not markdown:
        return markdown

    toc_match = _TOC_HEADING_RE.search(markdown)
    if not toc_match:
        return markdown

    next_heading = _NEXT_H2_RE.search(markdown, toc_match.end())
    if not next_heading:
        return markdown

    toc_body = markdown[toc_match.end():next_heading.start()]
    if _TOC_TIME_RE.search(toc_body):
        return markdown

    entries = []
    for match in _HEADING_TIME_RE.finditer(markdown, next_heading.start()):
        level = match.group(1)
        title = match.group(2).strip().rstrip("*").strip()
        marker = match.group(3)
        content_time = match.group(4)
        paren_time = match.group(5)
        time_text = content_time or paren_time

        if not title or "AI 总结" in title or title == "目录":
            continue

        if "Content-" in marker:
            time_marker = f"*Content-[{time_text}]"
        else:
            time_marker = f"({time_text})"

        indent = "  " if level == "###" else ""
        entries.append(f"{indent}- {title} {time_marker}")

    if not entries:
        return markdown

    new_toc_body = "\n" + "\n".join(entries) + "\n\n"
    return markdown[:toc_match.end()] + new_toc_body + markdown[next_heading.start():]


def prepend_source_link(markdown: str | None, source_url: str) -> str | None:
    """
    在笔记开头添加来源链接；若首个非空行已包含来源链接，则更新该行并避免重复。
    """
    if markdown is None:
        return None

    source = (source_url or "").strip()
    if not source:
        return markdown

    header = f"> 来源链接：{source}"
    lines = markdown.splitlines()
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break

    if first_non_empty_idx is not None:
        first_line = lines[first_non_empty_idx].strip()
        if first_line.startswith("> 来源链接：") or first_line.startswith("来源链接："):
            lines[first_non_empty_idx] = header
            return "\n".join(lines)

    if markdown.strip():
        return f"{header}\n\n{markdown}"
    return header


def strip_content_markers(markdown: str) -> str:
    """Remove *Content-[mm:ss]* markers when link=False (兜底清理，防止裸标记污染成品)。"""
    return _STRIP_CONTENT_RE.sub("", markdown)


def strip_screenshot_markers(markdown: str) -> str:
    """Remove *Screenshot-[mm:ss]* markers when screenshot=False。"""
    return _STRIP_SCREENSHOT_RE.sub("", markdown)


def replace_content_markers(markdown: str, video_id: str, platform: str = 'bilibili') -> str:
    """
    替换 *Content-04:16*、Content-04:16 或 Content-[04:16] 为超链接，跳转到对应平台视频的时间位置。
    支持 mm:ss、mmm:ss、h:mm:ss、hh:mm:ss 格式。
    """
    pattern = r"(?:\*?)Content-(?:\[(\d+:\d{2}(?::\d{2})?)\]|(\d+:\d{2}(?::\d{2})?))"
    parsed_video_id = video_id.replace("_p", "?p=")

    def replacer(match):
        time_str = match.group(1) or match.group(2)
        parts = [int(p) for p in time_str.split(":")]
        if len(parts) == 2:
            total_seconds = parts[0] * 60 + parts[1]
        else:
            total_seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]

        if platform == 'bilibili':
            url = f"https://www.bilibili.com/video/{parsed_video_id}&t={total_seconds}"
        elif platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={parsed_video_id}&t={total_seconds}s"
        elif platform == 'douyin':
            url = f"https://www.douyin.com/video/{parsed_video_id}"
            return f"[原片 @ {time_str}]({url})"
        else:
            return f"({time_str})"

        return f"[原片 @ {time_str}]({url})"

    return re.sub(pattern, replacer, markdown)
