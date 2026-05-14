from abc import ABC
import os

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.provider import ProviderService
from app.transcriber.base import Transcriber
from app.utils.openai_client import build_openai_client
import ffmpeg
import tempfile
from dotenv import load_dotenv
load_dotenv()
MAX_SIZE_MB = 18
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
def compress_audio(input_path: str, target_bitrate='64k') -> str:
    output_fd, output_path = tempfile.mkstemp(suffix=".mp3")  # 临时输出文件
    os.close(output_fd)  # 关闭文件描述符，ffmpeg 会用路径操作
    ffmpeg.input(input_path).output(output_path, audio_bitrate=target_bitrate).run(quiet=True, overwrite_output=True)
    return output_path

class GroqTranscriber(Transcriber, ABC):


    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        file_size = os.path.getsize(file_path)
        if file_size > MAX_SIZE_BYTES:
            print(f"文件超过 {MAX_SIZE_MB}MB，开始压缩（当前 {round(file_size / (1024 * 1024), 2)}MB）...")
            file_path = compress_audio(file_path)
            print(f"压缩完成，临时路径：{file_path}")
        provider = ProviderService.get_provider_by_id('groq')

        if not provider:
            raise Exception("Groq 供应商未配置,请配置以后使用。")
        # build_openai_client 会校验 api_key 非空（空 key 会抛天书般的
        # `Illegal header value b'Bearer '`），并自动注入全局代理
        client = build_openai_client(
            api_key=provider.get('api_key'),
            base_url=provider.get('base_url'),
            key_label="Groq 转写引擎的 API Key",
        )
        filename = file_path

        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model=os.getenv('GROQ_TRANSCRIBER_MODEL'),
                response_format="verbose_json",
            )
            print(transcription.text)
        print(transcription)
        segments = []
        full_text = ""

        for seg in transcription.segments:
            text = seg.text.strip()
            full_text += text + " "
            segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=text
            ))

        result = TranscriptResult(
            language=transcription.language,
            full_text=full_text.strip(),
            segments=segments,
            raw=transcription.to_dict()
        )
        return result
