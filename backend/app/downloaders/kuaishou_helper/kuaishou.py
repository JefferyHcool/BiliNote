import logging
import os
import re

import requests
from dotenv import load_dotenv

from app.services.cookie_manager import CookieConfigManager
from app.utils.logger import get_logger
KUAISHOU_API_BASE = 'https://www.kuaishou.com/graphql'
KUAISHOU_URL = "https://www.kuaishou.com/"
load_dotenv()
headers = {
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    # 'Cookie': 'did=web_9e8cfa4403000587b9e7d67233e6b04c; didv=1719811812378; kpf=PC_WEB; clientid=3; kpn=KUAISHOU_VISION',
    'Origin': 'https://www.kuaishou.com',
    'Pragma': 'no-cache',
    'Referer': 'https://www.kuaishou.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'accept': '*/*',
    'content-type': 'application/json',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    # 'Cookie':cookies.strip()
}

logger = get_logger(__name__)

cfm=CookieConfigManager()
class KuaiShou:
    def __init__(self):
        self.header = headers.copy()
        self.cookie = None

    @staticmethod
    def _extract_kuaishou_link(text):

        url = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        return url[0]

    def get_photo_id(self, url):
        response = requests.get(url, allow_redirects=True, headers=self.header)
        real_url = response.url
        # 提取short—video/后面的id
        pattern = re.compile(r'short-video/(\w+)')
        match = pattern.search(real_url)
        return match.group().split('/')[1]

    def get_temp_cookies(self):
        is_exist = cfm.get('kuaishou')
        print(is_exist)
        if is_exist:
            return is_exist
        res = requests.get(url=KUAISHOU_URL, headers=self.header, allow_redirects=True)
        cookie_string = '; '.join([f"{k}={v}" for k, v in res.cookies.get_dict().items()])
        return cookie_string

    def get_video_details(self, url, photo_id):
        json_data = {
            'operationName': 'visionVideoDetail',
            "variables": {"photoId": photo_id, "page": "detail"},
            "query": "query visionVideoDetail($photoId: String, $type: String, $page: String, $webPageArea: String) {\n  visionVideoDetail(photoId: $photoId, type: $type, page: $page, webPageArea: $webPageArea) {\n    status\n    type\n    author {\n      id\n      name\n      following\n      headerUrl\n      __typename\n    }\n    photo {\n      id\n      duration\n      caption\n      likeCount\n      realLikeCount\n      coverUrl\n      photoUrl\n      liked\n      timestamp\n      expTag\n      llsid\n      viewCount\n      videoRatio\n      stereoType\n      croppedPhotoUrl\n      manifest {\n        mediaType\n        businessType\n        version\n        adaptationSet {\n          id\n          duration\n          representation {\n            id\n            defaultSelect\n            backupUrl\n            codecs\n            url\n            height\n            width\n            avgBitrate\n            maxBitrate\n            m3u8Slice\n            qualityType\n            qualityLabel\n            frameRate\n            featureP2sp\n            hidden\n            disableAdaptive\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    tags {\n      type\n      name\n      __typename\n    }\n    commentLimit {\n      canAddComment\n      __typename\n    }\n    llsid\n    danmakuSwitch\n    __typename\n  }\n}\n"
        }
        response = requests.post(url=KUAISHOU_API_BASE, headers=self.header, json=json_data)
        if response.status_code == 200:
            response.raise_for_status()

            return response.json()
        else:
            return None

    def run(self, url):
        real_url = self._extract_kuaishou_link(url)
        if not real_url:
            logger.error(f"快手视频 URL 解析失败 {url}")

        cookies = self.get_temp_cookies()
        if not cookies:
            logger.error(f"快手视频 cookies 解析失败 {url},请考虑设置环境变量 KUAISHOU_COOKIES")

        self.header['Cookie'] = cookies.strip()
        photo_id = self.get_photo_id(real_url)
        if photo_id is None:
            logger.error(f"快手视频 ID 解析失败 {url}")
        video_details = self.get_video_details(real_url, photo_id)
        print(video_details)
        if video_details is None:
            logger.error(f"快手视频详情解析失败 {url}")
        return video_details['data']


if __name__ == '__main__':
    ks = KuaiShou()
    ks.run(
        'https://v.kuaishou.com/2vBqX74 王宝强携手刘昊然、岳云鹏上演精彩名场面 全程高能 看一遍笑一遍 "唐探1900 "快成长计划 ...更多')
