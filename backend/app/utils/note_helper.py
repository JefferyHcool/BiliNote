import re

def replace_content_markers(markdown: str, video_id: str, platform: str = 'bilibili') -> str:
    """
    替换 *Content-04:16*、Content-04:16 或 Content-[04:16] 为超链接
    目标格式：- [04:16](https://www.bilibili.com/video/BVxxx?t=256#t=04:16)
    """
    # 匹配三种形式：*Content-04:16*、Content-04:16、Content-[04:16]
    pattern = r"(?:\*?)Content-(?:\[(\d{2}):(\d{2})\]|(\d{2}):(\d{2}))"

    safe_video_id = video_id

    def replacer(match):
        mm = match.group(1) or match.group(3)
        ss = match.group(2) or match.group(4)
        total_seconds = int(mm) * 60 + int(ss)
        time_str = f"{mm}:{ss}"

        if platform == 'bilibili':
            # 处理多 P 情况，如果是 BV123_p3 转换为 BV123?p=3
            actual_video_id = video_id.replace("_p", "?p=")
            
            # 判断连接符是 ? 还是 & (如果 video_id 里已经有了 ?p=，则时间参数用 &t=)
            connector = "&t=" if "?" in actual_video_id else "?t="
            
            # 拼接最终 URL，并在末尾加上 #t=MM:SS 锚点
            url = f"https://www.bilibili.com/video/{actual_video_id}{connector}{total_seconds}#t={time_str}"
            return f"- [{time_str}]({url})"

        elif platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}&t={total_seconds}s"
            return f"- [{time_str}]({url})"

        elif platform == 'douyin':
            url = f"https://www.douyin.com/video/{video_id}"
            return f"[原片 @ {time_str}]({url})"
            
        else:
            return f"({time_str})"

    return re.sub(pattern, replacer, markdown)