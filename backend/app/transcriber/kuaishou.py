import requests
import logging
import os
from typing import Union, List, Dict, Optional

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptSegment, TranscriptResult
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger
from events import transcription_finished

logger = get_logger(__name__)

class KuaishouTranscriber(Transcriber):
    """快手语音识别实现"""
    
    API_URL = "https://ai.kuaishou.com/api/effects/subtitle_generate"
    
    def __init__(self):
        pass

    def _load_file(self, file_path: str) -> bytes:
        """读取文件内容"""
        with open(file_path, 'rb') as f:
            return f.read()

    def _submit(self, file_path: str) -> dict:
        """提交识别请求"""
        # 快手 ASR API 已于 2025 年永久关停 (code=501, msg="效果subtitle_generate禁用")，
        # 请使用 bcut（B站必剪）或 fast-whisper（本地）替代。
        raise RuntimeError(
            "快手 ASR 转写接口已永久关停（快手官方已禁用 subtitle_generate API）。"
            "请在「设置 → 音频转写配置」中将转写引擎切换为「必剪(bcut)」或「Faster Whisper(本地)」。"
        )

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        """执行转录过程，符合 Transcriber 接口"""
        try:
            logger.info(f"开始处理文件: {file_path}")
            
            # 提交请求并获取结果
            logger.info("向快手API提交识别请求...")
            result_data = self._submit(file_path)
            
            logger.info("请求成功，处理结果...")
            
            # 提取分段数据
            segments = []
            full_text = ""
            
            # 解析快手API返回的文本段
            texts = result_data.get('data', {}).get('text', [])
            for u in texts:
                text = u.get('text', '').strip()
                start_time = float(u.get('start_time', 0))
                end_time = float(u.get('end_time', 0))
                
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=start_time,
                    end=end_time,
                    text=text
                ))
            
            # 创建结果对象
            result = TranscriptResult(
                language="zh",  # 快手API可能不返回语言信息，默认为中文
                full_text=full_text.strip(),
                segments=segments,
                raw=result_data
            )
            
            # 触发完成事件
            # self.on_finish(file_path, result)
            
            return result
            
        except Exception as e:
            logger.error(f"快手ASR处理失败: {str(e)}")
            raise

    def on_finish(self, video_path: str, result: TranscriptResult) -> None:
        """转录完成的回调"""
        logger.info(f"快手ASR转写完成: {video_path}")
        transcription_finished.send({
            "file_path": video_path,
        })