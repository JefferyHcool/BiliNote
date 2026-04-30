import json
import logging
import os
import time
from typing import Optional, List, Dict, Union

import requests

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptSegment, TranscriptResult
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger
from events import transcription_finished

__version__ = "0.0.3"

API_BASE_URL = "https://member.bilibili.com/x/bcut/rubick-interface"

# 申请上传
API_REQ_UPLOAD = API_BASE_URL + "/resource/create"

# 提交上传
API_COMMIT_UPLOAD = API_BASE_URL + "/resource/create/complete"

# 创建任务
API_CREATE_TASK = API_BASE_URL + "/task"

# 查询结果
API_QUERY_RESULT = API_BASE_URL + "/task/result"

logger = get_logger(__name__)

class BcutTranscriber(Transcriber):
    """必剪 语音识别接口"""
    headers = {
        'User-Agent': 'Bilibili/1.0.0 (https://www.bilibili.com)',
        'Content-Type': 'application/json'
    }

    def __init__(self):
        self.session = requests.Session()
        self.task_id = None
        self.__etags = []

        self.__in_boss_key: Optional[str] = None
        self.__resource_id: Optional[str] = None
        self.__upload_id: Optional[str] = None
        self.__upload_urls: List[str] = []
        self.__per_size: Optional[int] = None
        self.__clips: Optional[int] = None

        self.__etags: List[str] = []
        self.__download_url: Optional[str] = None
        self.task_id: Optional[str] = None
        
    def _load_file(self, file_path: str) -> bytes:
        """读取文件内容"""
        with open(file_path, 'rb') as f:
            return f.read()

    def _upload(self, file_path: str) -> None:
        """申请上传"""
        file_binary = self._load_file(file_path)
        if not file_binary:
            raise ValueError("无法读取文件数据")
            
        payload = json.dumps({
            "type": 2,
            "name": "audio.mp3",
            "size": len(file_binary),
            "ResourceFileType": "mp3",
            "model_id": "8",
        })

        resp = self.session.post(
            API_REQ_UPLOAD,
            data=payload,
            headers=self.headers
        )
        resp.raise_for_status()
        resp = resp.json()
        resp_data = resp["data"]

        self.__in_boss_key = resp_data["in_boss_key"]
        self.__resource_id = resp_data["resource_id"]
        self.__upload_id = resp_data["upload_id"]
        self.__upload_urls = resp_data["upload_urls"]
        self.__per_size = resp_data["per_size"]
        self.__clips = len(resp_data["upload_urls"])

        logger.info(
            f"申请上传成功, 总计大小{resp_data['size'] // 1024}KB, {self.__clips}分片, 分片大小{resp_data['per_size'] // 1024}KB: {self.__in_boss_key}"
        )
        self.__upload_part(file_binary)
        self.__commit_upload()

    def __upload_part(self, file_binary: bytes) -> None:
        """上传音频数据"""
        for clip in range(self.__clips):
            start_range = clip * self.__per_size
            end_range = min((clip + 1) * self.__per_size, len(file_binary))
            logger.info(f"开始上传分片{clip}: {start_range}-{end_range}")
            resp = self.session.put(
                self.__upload_urls[clip],
                data=file_binary[start_range:end_range],
                headers={'Content-Type': 'application/octet-stream'}
            )
            resp.raise_for_status()
            etag = resp.headers.get("Etag", "").strip('"')
            self.__etags.append(etag)
            logger.info(f"分片{clip}上传成功: {etag}")

    def __commit_upload(self) -> None:
        """提交上传数据"""
        data = json.dumps({
            "InBossKey": self.__in_boss_key,
            "ResourceId": self.__resource_id,
            "Etags": ",".join(self.__etags),
            "UploadId": self.__upload_id,
            "model_id": "8",
        })
        max_attempts = max(1, int(os.getenv("BCUT_COMMIT_RETRY_ATTEMPTS", "4")))
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.post(
                    API_COMMIT_UPLOAD,
                    data=data,
                    headers=self.headers
                )
                resp.raise_for_status()
                resp = resp.json()
                if resp.get("code") == 0:
                    break
                last_error = f"上传提交失败: {resp.get('message', '未知错误')}"
                logger.warning("%s (attempt %s/%s)", last_error, attempt, max_attempts)
            except Exception as exc:
                last_error = exc
                logger.warning("上传提交异常 (attempt %s/%s): %s", attempt, max_attempts, exc)

            if attempt < max_attempts:
                time.sleep(min(3 * attempt, 10))
        else:
            logger.error(str(last_error))
            raise Exception(str(last_error))

        self.__download_url = resp["data"]["download_url"]
        logger.info(f"提交成功，下载链接: {self.__download_url}")

    def _create_task(self) -> str:
        """开始创建转换任务"""
        resp = self.session.post(
            API_CREATE_TASK, json={"resource": self.__download_url, "model_id": "8"}, headers=self.headers
        )
        resp.raise_for_status()
        resp = resp.json()
        if resp.get("code") != 0:
            error_msg = f"创建任务失败: {resp.get('message', '未知错误')}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        self.task_id = resp["data"]["task_id"]
        logger.info(f"任务已创建: {self.task_id}")
        return self.task_id

    def _query_result(self) -> dict:
        """查询转换结果"""
        resp = self.session.get(
            API_QUERY_RESULT, 
            params={"model_id": 7, "task_id": self.task_id}, 
            headers=self.headers
        )
        resp.raise_for_status()
        resp = resp.json()
        if resp.get("code") != 0:
            error_msg = f"查询结果失败: {resp.get('message', '未知错误')}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        return resp["data"]

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        """执行识别过程，符合 Transcriber 接口"""
        try:
            logger.info(f"开始处理文件: {file_path}")
            
            # 上传文件
            logger.info("正在上传文件...")
            self._upload(file_path)
            
            # 创建任务
            logger.info("提交转录任务...")
            self._create_task()
            
            # 轮询检查任务状态
            logger.info("等待转录结果...")
            task_resp = None
            max_retries = 500
            for i in range(max_retries):
                task_resp = self._query_result()
                
                if task_resp["state"] == 4:  # 完成状态
                    break
                elif task_resp["state"] == 3:  # 失败状态
                    error_msg = f"B站ASR任务失败，状态码: {task_resp['state']}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
                # 每隔一段时间打印进度
                if i % 10 == 0:
                    logger.info(f"转录进行中... {i}/{max_retries}")
                    
                time.sleep(1)
                
            if not task_resp or task_resp["state"] != 4:
                error_msg = f"B站ASR任务未能完成，状态: {task_resp.get('state') if task_resp else 'Unknown'}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            # 解析结果
            logger.info("转录成功，处理结果...")
            result_json = json.loads(task_resp["result"])
            
            # 提取分段数据
            segments = []
            full_text = ""
            
            for u in result_json.get("utterances", []):
                text = u.get("transcript", "").strip()
                # B站ASR返回的时间戳是毫秒，需要转换为秒
                start_time = float(u.get("start_time", 0)) / 1000.0
                end_time = float(u.get("end_time", 0)) / 1000.0
                
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=start_time,
                    end=end_time,
                    text=text
                ))
            
            # 创建结果对象
            result = TranscriptResult(
                language=result_json.get("language", "zh"),
                full_text=full_text.strip(),
                segments=segments,
                raw=result_json
            )
            
            # 触发完成事件
            # self.on_finish(file_path, result)
            
            return result
            
        except Exception as e:
            logger.error(f"B站ASR处理失败: {str(e)}")
            raise

    def on_finish(self, video_path: str, result: TranscriptResult) -> None:
        """转录完成的回调"""
        logger.info(f"B站ASR转写完成: {video_path}")
        transcription_finished.send({
            "file_path": video_path,
        })
