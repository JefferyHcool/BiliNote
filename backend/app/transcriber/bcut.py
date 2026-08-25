import json
import logging
import threading
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

# —— 临时性错误处理（被三个上传/任务/查询接口共用）——
# B 站 ASR 偶发返回 code=139201 / 业务 -400 / 业务 -500，等几秒重试通常恢复；
# 此外网关层常返 412（wbi 链路风控抖动）和 5xx。详见 issue #433。
RETRYABLE_BUSINESS_CODES = {139201, -400, -500}
RETRYABLE_HTTP_STATUSES = {412, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 3  # 含首次共 3 次请求，指数退避 1s / 2s / 4s


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
        # 实例被 transcriber_provider 缓存复用，并发任务会交错读写上传会话状态
        # （etags/upload_id/task_id），必须整段串行化
        # ponytail: 全局实例锁，并发转写会排队；如需吞吐量应改为每任务独立实例
        self._lock = threading.Lock()

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
        # 实例被 transcriber_provider 缓存复用，必须清掉上一次上传的会话状态，
        # 否则 __etags 跨上传残留，提交的 etag 数与本次分片数不符，B 站会拒绝合并
        self.__etags = []
        self.__in_boss_key = None
        self.__resource_id = None
        self.__upload_id = None
        self.__upload_urls = []
        self.__download_url = None

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
        """提交上传数据（含重试：应对 B 站 139201 等临时服务异常）"""
        data = json.dumps({
            "InBossKey": self.__in_boss_key,
            "ResourceId": self.__resource_id,
            "Etags": ",".join(self.__etags),
            "UploadId": self.__upload_id,
            "model_id": "8",
        })

        last_error = None
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                resp = self.session.post(
                    API_COMMIT_UPLOAD,
                    data=data,
                    headers=self.headers,
                    timeout=30,
                )
                resp.raise_for_status()
                resp_data = resp.json()

                if resp_data.get("code") == 0:
                    self.__download_url = resp_data["data"]["download_url"]
                    logger.info(f"提交成功，下载链接: {self.__download_url}")
                    return

                code = resp_data.get("code")
                msg = resp_data.get("message", "未知错误")

                if code in RETRYABLE_BUSINESS_CODES:
                    if attempt < DEFAULT_MAX_RETRIES - 1:
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(
                            f"提交上传返回 code={code} msg={msg}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                        )
                        time.sleep(wait)
                        last_error = Exception(f"上传提交失败: {msg}")
                        continue
                    error_msg = (
                        f"上传提交失败（重试 {DEFAULT_MAX_RETRIES} 次后仍返回 code={code}）: {msg}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

                error_msg = f"上传提交失败: {msg}"
                logger.error(error_msg)
                raise Exception(error_msg)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"提交上传网络错误: {e}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})")
                    time.sleep(wait)
                    last_error = e
                    continue
                raise
            except requests.exceptions.HTTPError as e:
                # 网关层风控抖动（412）或临时 5xx：重试可绕过。
                status = e.response.status_code if e.response is not None else None
                if status in RETRYABLE_HTTP_STATUSES and attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"提交上传 HTTP {status}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise

        raise last_error or Exception("上传提交失败: 重试次数已用完")

    def _create_task(self) -> str:
        """开始创建转换任务（含重试）"""
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                resp = self.session.post(
                    API_CREATE_TASK,
                    json={"resource": self.__download_url, "model_id": "8"},
                    headers=self.headers,
                    timeout=15,
                )
                resp.raise_for_status()
                resp_data = resp.json()

                if resp_data.get("code") == 0:
                    self.task_id = resp_data["data"]["task_id"]
                    logger.info(f"任务已创建: {self.task_id}")
                    return self.task_id

                code = resp_data.get("code")
                msg = resp_data.get("message", "未知错误")
                if code in RETRYABLE_BUSINESS_CODES:
                    if attempt < DEFAULT_MAX_RETRIES - 1:
                        wait = 2 ** attempt
                        logger.warning(
                            f"创建任务返回 code={code} msg={msg}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                        )
                        time.sleep(wait)
                        continue
                    error_msg = (
                        f"创建任务失败（重试 {DEFAULT_MAX_RETRIES} 次后仍返回 code={code}）: {msg}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

                error_msg = f"创建任务失败: {msg}"
                logger.error(error_msg)
                raise Exception(error_msg)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"创建任务网络错误: {e}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                raise
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in RETRYABLE_HTTP_STATUSES and attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"创建任务 HTTP {status}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                    continue
                raise

        raise Exception("创建任务失败: 重试次数已用完")

    def _query_result(self) -> dict:
        """查询转换结果（含重试）"""
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                resp = self.session.get(
                    API_QUERY_RESULT,
                    params={"model_id": 7, "task_id": self.task_id},
                    headers=self.headers,
                    timeout=15,
                )
                resp.raise_for_status()
                resp_data = resp.json()

                if resp_data.get("code") == 0:
                    return resp_data["data"]

                code = resp_data.get("code")
                msg = resp_data.get("message", "未知错误")
                if code in RETRYABLE_BUSINESS_CODES:
                    if attempt < DEFAULT_MAX_RETRIES - 1:
                        wait = 2 ** attempt
                        logger.warning(
                            f"查询结果返回 code={code} msg={msg}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                        )
                        time.sleep(wait)
                        continue
                    error_msg = (
                        f"查询结果失败（重试 {DEFAULT_MAX_RETRIES} 次后仍返回 code={code}）: {msg}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)

                error_msg = f"查询结果失败: {msg}"
                logger.error(error_msg)
                raise Exception(error_msg)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"查询结果网络错误: {e}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                raise
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in RETRYABLE_HTTP_STATUSES and attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"查询结果 HTTP {status}，{wait}s 后重试 ({attempt + 1}/{DEFAULT_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                    continue
                raise

        raise Exception("查询结果失败: 重试次数已用完")

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        """执行识别过程，符合 Transcriber 接口"""
        with self._lock:
            return self._transcript_locked(file_path)

    def _transcript_locked(self, file_path: str) -> TranscriptResult:
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