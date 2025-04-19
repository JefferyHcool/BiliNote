import os
from typing import Union

from pydantic import HttpUrl

from app.db.video_task_dao import insert_video_task, delete_task_by_video
from app.downloaders.base import Downloader
from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.youtube_downloader import YoutubeDownloader
from app.gpt.base import GPT
from app.gpt.deepseek_gpt import DeepSeekGPT
from app.gpt.openai_gpt import OpenaiGPT
from app.gpt.qwen_gpt import QwenGPT
from app.models.gpt_model import GPTSource
from app.models.notes_model import NoteResult
from app.models.notes_model import AudioDownloadResult
from app.enmus.note_enums import DownloadQuality
from app.models.transcriber_model import TranscriptResult
from app.transcriber.base import Transcriber
from app.transcriber.transcriber_provider import get_transcriber
from app.transcriber.whisper import WhisperTranscriber
import re

from app.utils.note_helper import replace_content_markers
from app.utils.video_helper import generate_screenshot

# from app.services.whisperer import transcribe_audio
# from app.services.gpt import summarize_text
from dotenv import load_dotenv
from app.utils.logger import get_logger
logger = get_logger(__name__)
load_dotenv()
BACKEND_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

output_dir = os.getenv('OUT_DIR')
image_base_url = os.getenv('IMAGE_BASE_URL')
logger.info("starting up")



class NoteGenerator:
    def __init__(self):
        self.model_size: str = 'base'
        self.device: Union[str, None] = None
        self.transcriber_type = os.getenv('TRANSCRIBER_TYPE','fast-whisper')
        self.transcriber = self.get_transcriber()
        # TODO 需要更换为可调节

        self.provider = os.getenv('MODEl_PROVIDER','openai')
        self.video_path = None
        logger.info("初始化NoteGenerator")


    def get_gpt(self) -> GPT:
        self.provider = self.provider.lower()
        if self.provider == 'openai':
            logger.info("使用OpenAI")
            return OpenaiGPT()
        elif self.provider == 'deepseek':
            logger.info("使用DeepSeek")
            return DeepSeekGPT()
        elif self.provider == 'qwen':
            logger.info("使用Qwen")
            return QwenGPT()
        else:
            self.provider = 'openai'
            logger.warning("不支持的AI提供商，使用 OpenAI 做完GPT")
            return OpenaiGPT()


    def get_downloader(self, platform: str) -> Downloader:
        if platform == "bilibili":
            logger.info("下载 Bilibili 平台视频")
            return BilibiliDownloader()
        elif platform == "youtube":
            logger.info("下载 YouTube 平台视频")
            return YoutubeDownloader()
        elif platform == 'douyin':
            logger.info("下载 Douyin 平台视频")
            return DouyinDownloader()
        else:
            logger.warning("不支持的平台")
            raise ValueError(f"不支持的平台：{platform}")

    def get_transcriber(self) -> Transcriber:
        '''

        :param transcriber: 选择的转义器
        :return:
        '''
        if self.transcriber_type == 'fast-whisper':
            logger.info("使用Whisper")
            return get_transcriber(transcriber_type='fast-whisper')
        else:
            logger.warning("不支持的转义器")
            raise ValueError(f"不支持的转义器：{self.transcriber}")

    def save_meta(self, video_id, platform, task_id):
        logger.info(f"记录已经生成的数据信息")
        insert_video_task(video_id=video_id, platform=platform, task_id=task_id)

    def insert_screenshots_into_markdown(self, markdown: str, video_path: str, image_base_url: str,
                                         output_dir: str) -> str:
        """
        扫描 markdown 中的 *Screenshot-xx:xx，生成截图并插入 markdown 图片
        :param markdown:
        :param image_base_url: 最终返回给前端的路径前缀（如 /static/screenshots）
        """
        matches = self.extract_screenshot_timestamps(markdown)
        new_markdown = markdown
        logger.info(f"开始为笔记生成截图")
        try:
            for idx, (marker, ts) in enumerate(matches):
                image_path = generate_screenshot(video_path, output_dir, ts, idx)
                image_relative_path = os.path.join(image_base_url, os.path.basename(image_path)).replace("\\", "/")
                image_url = f"{BACKEND_BASE_URL.rstrip('/')}/{image_relative_path.lstrip('/')}"
                replacement = f"![]({image_url})"
                new_markdown = new_markdown.replace(marker, replacement, 1)

            return new_markdown
        except Exception as e:
            logger.error(f"截图生成失败：{e}")
            raise e

    @staticmethod
    def delete_note(video_id: str, platform: str):
        logger.info(f"删除生成的笔记记录")
        return delete_task_by_video(video_id, platform)

    import re

    def extract_screenshot_timestamps(self, markdown: str) -> list[tuple[str, int]]:
        """
        从 Markdown 中提取 Screenshot 时间标记（如 *Screenshot-03:39 或 Screenshot-[03:39]），
        并返回匹配文本和对应时间戳（秒）
        """
        logger.info(f"开始提取截图时间标记")
        pattern = r"(?:\*Screenshot-(\d{2}):(\d{2})|Screenshot-\[(\d{2}):(\d{2})\])"
        matches = list(re.finditer(pattern, markdown))
        results = []
        for match in matches:
            mm = match.group(1) or match.group(3)
            ss = match.group(2) or match.group(4)
            total_seconds = int(mm) * 60 + int(ss)
            results.append((match.group(0), total_seconds))
        return results

    def generate(
            self,

            video_url: Union[str, HttpUrl],
            platform: str,
            quality: DownloadQuality = DownloadQuality.medium,
            task_id: Union[str, None] = None,
            link: bool = False,
            screenshot: bool = False,
            path: Union[str, None] = None

    ) -> NoteResult:
        logger.info(f"开始解析并生成笔记")
        # 1. 选择下载器
        downloader = self.get_downloader(platform)
        gpt = self.get_gpt()
        logger.info(f'使用{downloader.__class__.__name__}下载器')
        logger.info(f'使用{gpt.__class__.__name__}GPT')
        logger.info(f'视频地址：{video_url}')
        if screenshot:

            video_path = downloader.download_video(video_url)
            self.video_path = video_path
            print(video_path)

        # 2. 下载音频
        audio: AudioDownloadResult = downloader.download(
            video_url=video_url,
            quality=quality,
            output_dir=path,
            need_video=screenshot

        )
        logger.info(f"下载音频成功，文件路径：{audio.file_path}")
        # 3. Whisper 转写
        transcript: TranscriptResult = self.transcriber.transcript(file_path=audio.file_path)
        logger.info(f"Whisper 转写成功，转写结果：{transcript.full_text}")
        # 4. GPT 总结
        source = GPTSource(
            title=audio.title,
            segment=transcript.segments,
            tags=audio.raw_info.get('tags'),
            screenshot=screenshot,
            link=link
        )
        logger.info(f"GPT 总结完成，总结结果：{source}")
        markdown: str = gpt.summarize(source)
        print("markdown结果", markdown)

        markdown = replace_content_markers(markdown=markdown, video_id=audio.video_id, platform=platform)
        if self.video_path:
            markdown = self.insert_screenshots_into_markdown(markdown, self.video_path, image_base_url, output_dir)
        self.save_meta(video_id=audio.video_id, platform=platform, task_id=task_id)
        # 5. 返回结构体
        return NoteResult(
            markdown=markdown,
            transcript=transcript,
            audio_meta=audio
        )


