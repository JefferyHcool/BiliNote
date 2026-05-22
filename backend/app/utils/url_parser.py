import re
from typing import Optional
import requests


def extract_video_id(url: str, platform: str) -> Optional[str]:
    """
    从视频链接中提取视频 ID

    :param url: 视频链接
    :param platform: 平台名（bilibili / youtube / douyin）
    :return: 提取到的视频 ID 或 None
    """
    if platform == "bilibili":
        # 如果是短链接，则解析真实链接
        if "b23.tv" in url:
            resolved_url = resolve_bilibili_short_url(url)
            if resolved_url:
                url = resolved_url

        # 匹配 BV号（如 BV1vc411b7Wa）
        match = re.search(r"BV([0-9A-Za-z]+)", url)
        if not match:
            return None
        return f"BV{match.group(1)}"

    elif platform == "youtube":
        # 匹配 v=xxxxx 或 youtu.be/xxxxx，ID 长度通常为 11
        match = re.search(r"(?:v=|youtu\.be/)([0-9A-Za-z_-]{11})", url)
        return match.group(1) if match else None

    elif platform == "douyin":
        # 匹配 douyin.com/video/1234567890123456789
        match = re.search(r"/video/(\d+)", url)
        return match.group(1) if match else None

    return None


def extract_bilibili_task_id(url: str) -> str:
    """
    从 B 站链接中提取带分 P 信息的任务签名，用于缓存文件名区分不同 P。

    :param url: Bilibili 视频链接
    :return: 纯 BV 号，若存在 p 参数则追加为 BVxxxx_p2
    """
    bvid = extract_video_id(url, "bilibili")
    if not bvid:
        return ""
    p_match = re.search(r'[?&]p=(\d+)', url)
    if p_match:
        return f"{bvid}_p{p_match.group(1)}"
    return bvid


def resolve_bilibili_short_url(short_url: str) -> Optional[str]:
    """
    解析哔哩哔哩短链接以获取真实视频链接

    :param short_url: Bilibili短链接（如"https://b23.tv/xxxxxx"）
    :return: 真实的视频链接或None
    """
    try:
        response = requests.head(short_url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        print(f"Error resolving short URL: {e}")
        return None
