import base64
import json
import os
import time
from typing import Any, Dict, List

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile

logger = get_logger(__name__)


class TencentAsrTranscriber(Transcriber):
    """腾讯云录音文件识别实现（CreateRecTask + DescribeTaskStatus）"""

    def __init__(self):
        self.secret_id = os.getenv("TENCENT_ASR_SECRET_ID", "").strip()
        self.secret_key = os.getenv("TENCENT_ASR_SECRET_KEY", "").strip()
        self.region = os.getenv("TENCENT_ASR_REGION", "ap-shanghai").strip()
        self.engine_model_type = os.getenv("TENCENT_ASR_ENGINE_MODEL_TYPE", "").strip()
        self.poll_interval_seconds = float(os.getenv("TENCENT_ASR_POLL_INTERVAL_SECONDS", "2"))
        self.timeout_seconds = int(os.getenv("TENCENT_ASR_TIMEOUT_SECONDS", "600"))

        if not self.secret_id or not self.secret_key:
            raise ValueError("缺少腾讯云配置：请设置 TENCENT_ASR_SECRET_ID 和 TENCENT_ASR_SECRET_KEY")

        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile(endpoint="asr.tencentcloudapi.com")
        client_profile = ClientProfile(httpProfile=http_profile)
        self.client = asr_client.AsrClient(cred, self.region, client_profile)

    def _build_create_request(self, file_path: str) -> models.CreateRecTaskRequest:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        if not audio_bytes:
            raise ValueError("音频文件为空，无法提交腾讯云识别任务")

        params: Dict[str, Any] = {
            "EngineModelType": self.engine_model_type or "16k_zh",
            "SourceType": 1,
            "Data": base64.b64encode(audio_bytes).decode("utf-8"),
            "DataLen": len(audio_bytes),
            "ChannelNum": 1,
            "ResTextFormat": 0,
        }

        request = models.CreateRecTaskRequest()
        request.from_json_string(json.dumps(params))
        return request

    @staticmethod
    def _extract_task_id(create_response: Any) -> int:
        payload = json.loads(create_response.to_json_string())
        task_id = payload.get("Data", {}).get("TaskId")
        if not task_id:
            raise RuntimeError("腾讯云 CreateRecTask 未返回 TaskId")
        return int(task_id)

    def _query_task_status(self, task_id: int) -> Dict[str, Any]:
        request = models.DescribeTaskStatusRequest()
        request.from_json_string(json.dumps({"TaskId": task_id}))
        response = self.client.DescribeTaskStatus(request)
        payload = json.loads(response.to_json_string())
        return payload.get("Data", {})

    @staticmethod
    def _build_segments(result_detail: List[Dict[str, Any]]) -> List[TranscriptSegment]:
        segments: List[TranscriptSegment] = []
        for item in result_detail:
            text = (item.get("FinalSentence") or item.get("SliceSentence") or "").strip()
            if not text:
                continue

            start_ms = float(item.get("StartMs", 0))
            end_ms = float(item.get("EndMs", 0))
            segments.append(
                TranscriptSegment(
                    start=start_ms / 1000.0,
                    end=end_ms / 1000.0,
                    text=text,
                )
            )
        return segments

    @staticmethod
    def _build_full_text(status_data: Dict[str, Any], segments: List[TranscriptSegment]) -> str:
        if segments:
            return " ".join(seg.text for seg in segments).strip()
        return (status_data.get("Result") or "").strip()

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        try:
            logger.info(f"腾讯云ASR提交任务: {file_path}")
            create_request = self._build_create_request(file_path)
            create_response = self.client.CreateRecTask(create_request)
            task_id = self._extract_task_id(create_response)
            logger.info(f"腾讯云ASR任务创建成功, task_id={task_id}")

            start_at = time.time()
            while True:
                status_data = self._query_task_status(task_id)
                status = int(status_data.get("Status", -1))
                status_str = status_data.get("StatusStr", "unknown")

                if status == 2:
                    result_detail = status_data.get("ResultDetail") or []
                    segments = self._build_segments(result_detail)
                    full_text = self._build_full_text(status_data, segments)
                    return TranscriptResult(
                        language="zh",
                        full_text=full_text,
                        segments=segments,
                        raw=status_data,
                    )

                if status == 3:
                    error_msg = status_data.get("ErrorMsg") or "腾讯云识别失败"
                    raise RuntimeError(f"腾讯云ASR任务失败(task_id={task_id}, status={status_str}): {error_msg}")

                elapsed = time.time() - start_at
                if elapsed >= self.timeout_seconds:
                    raise TimeoutError(
                        f"腾讯云ASR轮询超时(task_id={task_id}, status={status_str}, elapsed={int(elapsed)}s)"
                    )

                logger.info(f"腾讯云ASR任务处理中(task_id={task_id}, status={status_str})")
                time.sleep(self.poll_interval_seconds)

        except TencentCloudSDKException as e:
            logger.error(f"腾讯云ASR SDK调用异常: {e}")
            raise
        except Exception as e:
            logger.error(f"腾讯云ASR处理失败: {e}")
            raise
