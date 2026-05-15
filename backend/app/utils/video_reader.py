import base64
import hashlib
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import ffmpeg
from PIL import Image, ImageDraw, ImageFont

from app.utils.logger import get_logger
from app.utils.path_helper import get_app_dir
from app.utils.time_utils import format_timestamp

logger = get_logger(__name__)


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
                 grid_dir=None):
        self.video_path = video_path
        self.grid_size = grid_size
        self.frame_interval = frame_interval
        self.dedupe_enabled = dedupe_enabled
        self.unit_width = unit_width
        self.unit_height = unit_height
        self.save_quality = save_quality
        self.frame_dir = frame_dir or get_app_dir("output_frames")
        self.grid_dir = grid_dir or get_app_dir("grid_output")
        print(f"视频路径：{video_path}", self.frame_dir, self.grid_dir)
        self.font_path = font_path

    @staticmethod
    def _calculate_file_md5(file_path: str) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def format_time(self, seconds: float) -> str:
        """Internal filename format: MM_SS (total minutes, no hour wrap)."""
        mm = int(seconds // 60)
        ss = int(seconds % 60)
        return f"{mm:02d}_{ss:02d}"

    def extract_time_from_filename(self, filename: str) -> float:
        match = re.search(r"frame_(\d+)_(\d{2})\.jpg", filename)
        if match:
            mm, ss = map(int, match.groups())
            return mm * 60 + ss
        return float('inf')

    def _extract_single_frame(self, ts: int) -> str | None:
        """提取单帧，返回输出路径或 None（失败时）。"""
        time_label = self.format_time(ts)
        output_path = os.path.join(self.frame_dir, f"frame_{time_label}.jpg")
        cmd = ["ffmpeg", "-ss", str(ts), "-i", self.video_path, "-frames:v", "1", "-q:v", "2", "-y", output_path,
               "-hide_banner", "-loglevel", "error"]
        try:
            subprocess.run(cmd, check=True)
            return output_path
        except subprocess.CalledProcessError:
            return None

    def extract_frames(self, max_frames: int | None = None) -> list[str]:
        try:
            os.makedirs(self.frame_dir, exist_ok=True)
            duration = float(ffmpeg.probe(self.video_path)["format"]["duration"])
            timestamps = list(range(0, int(duration), self.frame_interval))
            if max_frames is not None:
                timestamps = timestamps[:max_frames]

            max_workers = min(os.cpu_count() or 4, 8, len(timestamps))
            frame_results: dict[int, str | None] = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(self._extract_single_frame, ts): ts for ts in timestamps}
                for future in as_completed(futures):
                    ts = futures[future]
                    frame_results[ts] = future.result()

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

    def group_images(self) -> list[list[str]]:
        image_files = [os.path.join(self.frame_dir, f) for f in os.listdir(self.frame_dir) if
                       f.startswith("frame_") and f.endswith(".jpg")]
        image_files.sort(key=lambda f: self.extract_time_from_filename(os.path.basename(f)))
        group_size = self.grid_size[0] * self.grid_size[1]
        return [image_files[i:i + group_size] for i in range(0, len(image_files), group_size)]

    def concat_images(self, image_paths: list[str], name: str) -> str:
        os.makedirs(self.grid_dir, exist_ok=True)
        font = ImageFont.truetype(self.font_path, 48) if os.path.exists(self.font_path) else ImageFont.load_default()
        images = []

        for path in image_paths:
            img = Image.open(path).convert("RGB").resize((self.unit_width, self.unit_height), Image.Resampling.LANCZOS)
            ts = self.extract_time_from_filename(os.path.basename(path))
            time_text = format_timestamp(ts) if ts != float('inf') else ""
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

    def _build_cells(self, image_paths: list[str]) -> list[dict]:
        """Build cell metadata from the actual frame paths that entered a grid."""
        cells = []
        for path in image_paths:
            ts = self.extract_time_from_filename(os.path.basename(path))
            if ts != float('inf'):
                ts_int = int(ts)
                cells.append({"ts": ts_int, "label": format_timestamp(ts_int)})
        return cells

    def _prepare_directories(self) -> None:
        os.makedirs(self.frame_dir, exist_ok=True)
        os.makedirs(self.grid_dir, exist_ok=True)
        for file in os.listdir(self.frame_dir):
            if file.startswith("frame_"):
                os.remove(os.path.join(self.frame_dir, file))
        for file in os.listdir(self.grid_dir):
            if file.startswith("grid_"):
                os.remove(os.path.join(self.grid_dir, file))

    def _should_include_group(self, group: list[str], idx: int, total: int) -> bool:
        min_size = self.grid_size[0] * self.grid_size[1]
        if len(group) >= min_size:
            return True
        if idx == total and len(group) > 0:
            logger.info(f"最后一组仅 {len(group)} 帧，以留白填充生成网格")
            return True
        logger.warning(f"⚠️ 跳过第 {idx} 组，图片不足 {min_size} 张")
        return False

    def _build_grids(self) -> tuple[list[str], list[dict]]:
        """
        Core: extract frames → group → concat.
        Returns (grid_paths, grid_metadata_list).
        grid_metadata_list items:
            {grid_index, path, grid_size, interval, start_ts, end_ts, cells}
        """
        self._prepare_directories()
        self.extract_frames()
        logger.info("开始拼接网格图...")

        grid_paths: list[str] = []
        grid_metas: list[dict] = []
        groups = self.group_images()
        total = len(groups)

        for idx, group in enumerate(groups, start=1):
            if not self._should_include_group(group, idx, total):
                continue

            out_path = self.concat_images(group, f"grid_{idx}")
            grid_paths.append(out_path)

            cells = self._build_cells(group)
            if cells:
                start_ts = cells[0]["ts"]
                end_ts = cells[-1]["ts"] + self.frame_interval
            else:
                start_ts = end_ts = 0

            grid_metas.append({
                "grid_index": idx,
                "path": out_path,
                "grid_size": list(self.grid_size),
                "interval": self.frame_interval,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "cells": cells,
            })

        return grid_paths, grid_metas

    def run(self) -> list[str]:
        logger.info("开始提取视频帧...")
        try:
            grid_paths, _ = self._build_grids()
            logger.info("📤 开始编码图像...")
            return self.encode_images_to_base64(grid_paths)
        except Exception as e:
            logger.error(f"发生错误：{str(e)}")
            raise ValueError("视频处理失败")

    def run_with_metadata(self) -> dict:
        """
        Like run() but also returns structured grid metadata for time-aware visual analysis.

        Returns:
            {
                "image_urls": [...],          # same as run()
                "grids": [
                    {
                        "grid_index": 1,
                        "image_url": "data:image/jpeg;base64,...",
                        "grid_size": [3, 3],
                        "interval": 6,
                        "start_ts": 0,
                        "end_ts": 54,
                        "cells": [{"ts": 0, "label": "00:00"}, ...]
                    }
                ]
            }
        """
        logger.info("开始提取视频帧（含 metadata）...")
        try:
            grid_paths, grid_metas = self._build_grids()
            logger.info("📤 开始编码图像...")
            urls = self.encode_images_to_base64(grid_paths)

            grids = []
            for i, meta in enumerate(grid_metas):
                grids.append({
                    "grid_index": meta["grid_index"],
                    "image_url": urls[i],
                    "grid_size": meta["grid_size"],
                    "interval": meta["interval"],
                    "start_ts": meta["start_ts"],
                    "end_ts": meta["end_ts"],
                    "cells": meta["cells"],
                })

            return {"image_urls": urls, "grids": grids}
        except Exception as e:
            logger.error(f"发生错误：{str(e)}")
            raise ValueError("视频处理失败")
