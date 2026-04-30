import base64
import hashlib
import os
import re
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import ffmpeg
from PIL import Image, ImageDraw, ImageFont

from app.utils.logger import get_logger
from app.utils.path_helper import get_app_dir

logger = get_logger(__name__)


def _find_ffmpeg_tool(binary_name: str) -> str:
    configured_dir = os.getenv("FFMPEG_BIN_PATH")
    exe_name = f"{binary_name}.exe" if os.name == "nt" else binary_name
    if configured_dir:
        candidate = os.path.join(configured_dir, exe_name)
        if os.path.exists(candidate):
            return candidate
    return shutil.which(binary_name) or shutil.which(exe_name) or binary_name


class VideoReader:
    def __init__(self,
                 video_path: str,
                 grid_size=(3, 3),
                 frame_interval=2,
                 dedupe_enabled=True,
                 unit_width=960,
                 unit_height=540,
                 save_quality=90,
                 font_path="fonts/arial.ttf",
                 frame_dir=None,
                 grid_dir=None,
                 max_frames=None):
        self.video_path = video_path
        self.grid_size = grid_size
        self.frame_interval = max(1, int(frame_interval or 1))
        self.dedupe_enabled = dedupe_enabled
        self.unit_width = unit_width
        self.unit_height = unit_height
        self.save_quality = save_quality
        suffix = f"{Path(video_path).stem}_{uuid.uuid4().hex[:8]}"
        self.frame_dir = frame_dir or os.path.join(get_app_dir("output_frames"), suffix)
        self.grid_dir = grid_dir or os.path.join(get_app_dir("grid_output"), suffix)
        self.max_frames = self._resolve_max_frames(max_frames)
        logger.info("视频路径：%s frame_dir=%s grid_dir=%s max_frames=%s", video_path, self.frame_dir, self.grid_dir, self.max_frames)
        self.font_path = font_path

    @staticmethod
    def _calculate_file_md5(file_path: str) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _resolve_max_frames(value) -> int:
        if value is None:
            value = os.getenv("VIDEO_UNDERSTANDING_MAX_FRAMES", "80")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 80
        return max(1, parsed)

    def _grid_group_size(self) -> int:
        if not self.grid_size or len(self.grid_size) < 2:
            return 1
        return max(1, int(self.grid_size[0]) * int(self.grid_size[1]))

    def _target_frame_count(self) -> int:
        group_size = self._grid_group_size()
        groups = max(1, self.max_frames // group_size)
        return groups * group_size

    @staticmethod
    def _format_timestamp_token(seconds: float) -> str:
        whole_seconds = max(0, int(round(seconds)))
        hours = whole_seconds // 3600
        minutes = (whole_seconds % 3600) // 60
        secs = whole_seconds % 60
        return f"{hours:02d}_{minutes:02d}_{secs:02d}"

    def format_time(self, seconds: float) -> str:
        return self._format_timestamp_token(seconds)

    def extract_time_from_filename(self, filename: str) -> float:
        match = re.search(r"frame_(\d{2})_(\d{2})_(\d{2})\.jpg", filename)
        if match:
            hh, mm, ss = map(int, match.groups())
            return hh * 3600 + mm * 60 + ss
        legacy_match = re.search(r"frame_(\d{2})_(\d{2})\.jpg", filename)
        if legacy_match:
            mm, ss = map(int, legacy_match.groups())
            return mm * 60 + ss
        return float('inf')

    def _build_timestamps(self, duration: float, max_frames: int) -> list[int]:
        duration_int = max(0, int(duration))
        if duration_int <= 0:
            return [0]

        interval_timestamps = list(range(0, duration_int, self.frame_interval))
        if not interval_timestamps:
            interval_timestamps = [0]

        if len(interval_timestamps) <= max_frames:
            return interval_timestamps

        # 均匀抽样整个视频，而不是只截前 max_frames 帧；这样长视频也能覆盖末尾。
        if max_frames == 1:
            return [0]
        last_idx = len(interval_timestamps) - 1
        sampled = []
        seen = set()
        for i in range(max_frames):
            idx = round(i * last_idx / (max_frames - 1))
            ts = interval_timestamps[idx]
            if ts not in seen:
                sampled.append(ts)
                seen.add(ts)
        return sampled

    def _extract_single_frame(self, ts: int) -> str | None:
        """提取单帧，返回输出路径或 None（失败时）。"""
        time_label = self.format_time(ts)
        output_path = os.path.join(self.frame_dir, f"frame_{time_label}.jpg")
        cmd = [_find_ffmpeg_tool("ffmpeg"), "-ss", str(ts), "-i", self.video_path, "-frames:v", "1", "-q:v", "2", "-y", output_path,
               "-hide_banner", "-loglevel", "error"]
        try:
            subprocess.run(cmd, check=True)
            return output_path
        except subprocess.CalledProcessError:
            return None

    def extract_frames(self, max_frames=None) -> list[str]:

        try:
            os.makedirs(self.frame_dir, exist_ok=True)
            duration = float(ffmpeg.probe(self.video_path, cmd=_find_ffmpeg_tool("ffprobe"))["format"]["duration"])
            effective_max_frames = self._resolve_max_frames(max_frames) if max_frames is not None else self._target_frame_count()
            timestamps = self._build_timestamps(duration, effective_max_frames)
            logger.info(
                "视频理解抽帧：duration=%.2fs interval=%ss frames=%s cap=%s",
                duration,
                self.frame_interval,
                len(timestamps),
                effective_max_frames,
            )

            if not timestamps:
                return []

            # 并行提取帧
            max_workers = min(os.cpu_count() or 4, 8, len(timestamps))
            frame_results: dict[int, str | None] = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(self._extract_single_frame, ts): ts for ts in timestamps}
                for future in as_completed(futures):
                    ts = futures[future]
                    frame_results[ts] = future.result()

            # 按时间戳顺序整理结果，并进行去重
            image_paths = []
            last_hash = None
            for ts in timestamps:
                output_path = frame_results.get(ts)
                if not output_path or not os.path.exists(output_path):
                    continue

                if self.dedupe_enabled:
                    frame_hash = self._calculate_file_md5(output_path)
                    if frame_hash == last_hash:
                        os.remove(output_path)
                        continue
                    last_hash = frame_hash

                image_paths.append(output_path)
            return image_paths
        except Exception as e:
            logger.error(f"分割帧发生错误：{str(e)}")
            raise ValueError("视频处理失败")

    def group_images(self, image_files: list[str] | None = None) -> list[list[str]]:
        if image_files is None:
            image_files = [os.path.join(self.frame_dir, f) for f in os.listdir(self.frame_dir) if
                           f.startswith("frame_") and f.endswith(".jpg")]
        image_files.sort(key=lambda f: self.extract_time_from_filename(os.path.basename(f)))
        group_size = self._grid_group_size()
        complete_count = (len(image_files) // group_size) * group_size
        return [image_files[i:i + group_size] for i in range(0, complete_count, group_size)]

    def concat_images(self, image_paths: list[str], name: str) -> str:
        os.makedirs(self.grid_dir, exist_ok=True)
        font = ImageFont.truetype(self.font_path, 48) if os.path.exists(self.font_path) else ImageFont.load_default()
        images = []

        for path in image_paths:
            img = Image.open(path).convert("RGB").resize((self.unit_width, self.unit_height), Image.Resampling.LANCZOS)
            seconds = self.extract_time_from_filename(os.path.basename(path))
            if seconds == float("inf"):
                time_text = ""
            else:
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                time_text = f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), time_text, fill="yellow", font=font, stroke_width=1, stroke_fill="black")
            images.append(img)

        cols, rows = self.grid_size
        grid_img = Image.new("RGB", (self.unit_width * cols, self.unit_height * rows), (255, 255, 255))

        for i, img in enumerate(images):
            x = (i % cols) * self.unit_width
            y = (i // cols) * self.unit_height
            grid_img.paste(img, (x, y))

        save_path = os.path.join(self.grid_dir, f"{name}.jpg")
        grid_img.save(save_path, quality=self.save_quality)
        return save_path

    def encode_images_to_base64(self, image_paths: list[str]) -> list[str]:
        base64_images = []
        for path in image_paths:
            with open(path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
                base64_images.append(f"data:image/jpeg;base64,{encoded_string}")
        return base64_images

    def run(self)->list[str]:
        logger.info("开始提取视频帧...")
        try:
            # 确保目录存在
            os.makedirs(self.frame_dir, exist_ok=True)
            os.makedirs(self.grid_dir, exist_ok=True)
            # 清空帧文件夹
            for file in os.listdir(self.frame_dir):
                if file.startswith("frame_"):
                    os.remove(os.path.join(self.frame_dir, file))
            # 清空网格文件夹
            for file in os.listdir(self.grid_dir):
                if file.startswith("grid_"):
                    os.remove(os.path.join(self.grid_dir, file))
            extracted_frames = self.extract_frames()
            logger.info("开始拼接网格图...")
            image_paths = []
            groups = self.group_images(extracted_frames)
            for idx, group in enumerate(groups, start=1):
                if len(group) < self._grid_group_size():
                    logger.warning(f"⚠️ 跳过第 {idx} 组，图片不足 {self._grid_group_size()} 张")
                    continue
                out_path = self.concat_images(group, f"grid_{idx}")
                image_paths.append(out_path)

            logger.info("开始编码图像...")
            urls = self.encode_images_to_base64(image_paths)
            return urls
        except Exception as e:
            logger.error(f"发生错误：{str(e)}")
            raise ValueError("视频处理失败")


