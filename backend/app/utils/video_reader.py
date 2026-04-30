import base64
import hashlib
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.utils.logger import get_logger
from app.utils.path_helper import get_app_dir

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
        print(f"视频路径：{video_path}",self.frame_dir,self.grid_dir)
        self.font_path = font_path

    @staticmethod
    def _calculate_file_md5(file_path: str) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def format_time(self, seconds: float) -> str:
        mm = int(seconds // 60)
        ss = int(seconds % 60)
        return f"{mm:02d}_{ss:02d}"

    def extract_time_from_filename(self, filename: str) -> float:
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg", filename)
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

    @staticmethod
    def _scene_change_score(img_path_a: str, img_path_b: str) -> float:
        """计算两帧之间的场景变化分数（0-1）。
        使用缩略图差异，对画面内容变化敏感，忽略细微噪声。"""
        try:
            a = Image.open(img_path_a).convert("L").resize((64, 36), Image.Resampling.NEAREST)
            b = Image.open(img_path_b).convert("L").resize((64, 36), Image.Resampling.NEAREST)
            arr_a = np.array(a, dtype=np.float32)
            arr_b = np.array(b, dtype=np.float32)
            diff = np.abs(arr_a - arr_b).mean() / 255.0
            return float(diff)
        except Exception:
            return 0.0

    def extract_frames(self, max_frames=1000) -> list[str]:

        try:
            os.makedirs(self.frame_dir, exist_ok=True)
            duration = float(ffmpeg.probe(self.video_path)["format"]["duration"])

            # 按 1 秒间隔密集采样，后续用场景检测筛选关键帧
            dense_interval = 1
            timestamps = [i for i in range(0, int(duration), dense_interval)][:max_frames * 2]

            # 并行提取帧
            max_workers = min(os.cpu_count() or 4, 8, len(timestamps))
            frame_results: dict[int, str | None] = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(self._extract_single_frame, ts): ts for ts in timestamps}
                for future in as_completed(futures):
                    ts = futures[future]
                    frame_results[ts] = future.result()

            # 收集有效帧（按时间戳排序）
            valid_frames: list[tuple[int, str]] = []
            for ts in timestamps:
                output_path = frame_results.get(ts)
                if output_path and os.path.exists(output_path):
                    valid_frames.append((ts, output_path))

            if not valid_frames:
                logger.warning("未提取到任何有效帧")
                return []

            # 场景检测：计算相邻帧差异，为每帧打分
            scores: dict[int, float] = {}
            for i in range(1, len(valid_frames)):
                prev_ts, prev_path = valid_frames[i - 1]
                curr_ts, curr_path = valid_frames[i]
                diff = self._scene_change_score(prev_path, curr_path)
                # 当前帧得分 = 与前帧的差异（它引入了多少新画面）
                scores[curr_ts] = max(scores.get(curr_ts, 0), diff)
                # 前一帧也得分（它是变化前的最后一帧，可能也很关键）
                scores[prev_ts] = max(scores.get(prev_ts, 0), diff)

            # 根据 grid_size 计算需要的帧数，取分数最高的帧
            grid_capacity = self.grid_size[0] * self.grid_size[1]
            MAX_GRIDS = 25  # 最多发送 25 张网格图，避免超出多模态模型的 token 上限
            max_selected = grid_capacity * MAX_GRIDS
            # 估算网格组数：按 frame_interval 估算有多少组
            total_groups = max(1, int(duration) // self.frame_interval)
            needed_frames = min(max_frames, grid_capacity * total_groups, max_selected)
            needed_frames = max(grid_capacity, needed_frames)

            # 按场景变化分数排序，取 top-N 关键帧
            scored_timestamps = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)
            selected_timestamps = set(scored_timestamps[:needed_frames])

            # 同时确保覆盖视频全程：每隔 frame_interval 至少保留一帧
            for ts in range(0, int(duration), self.frame_interval):
                # 找到该区间内得分最高的帧
                candidates = [(t, p) for t, p in valid_frames if ts <= t < ts + self.frame_interval]
                if candidates:
                    best = max(candidates, key=lambda x: scores.get(x[0], 0))
                    selected_timestamps.add(best[0])

            # 最终上限：场景分最高的 N 帧，确保不超出模型 token 限制
            if len(selected_timestamps) > max_selected:
                selected_timestamps = set(sorted(
                    selected_timestamps, key=lambda t: scores.get(t, 0), reverse=True
                )[:max_selected])

            # 按时间戳顺序输出，并去重
            image_paths = []
            last_hash = None
            for ts in timestamps:
                if ts not in selected_timestamps:
                    continue
                output_path = frame_results.get(ts)
                if not output_path or not os.path.exists(output_path):
                    continue

                if self.dedupe_enabled:
                    frame_hash = self._calculate_file_md5(output_path)
                    if frame_hash == last_hash:
                        # 删掉未被选中的冗余帧
                        if ts not in selected_timestamps:
                            os.remove(output_path)
                        continue
                    last_hash = frame_hash

                image_paths.append(output_path)

            # 清理未选中的帧文件
            for ts, output_path in valid_frames:
                if ts not in selected_timestamps and os.path.exists(output_path):
                    os.remove(output_path)

            logger.info(f"场景检测完成：从 {len(valid_frames)} 帧中筛选了 {len(image_paths)} 个关键帧")
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
            timestamp = re.search(r"frame_(\d{2})_(\d{2})\.jpg", os.path.basename(path))
            time_text = f"{timestamp.group(1)}:{timestamp.group(2)}" if timestamp else ""
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
            print(self.frame_dir,self.grid_dir)
            os.makedirs(self.frame_dir, exist_ok=True)
            os.makedirs(self.grid_dir, exist_ok=True)
            #清空帧文件夹
            for file in os.listdir(self.frame_dir):
                if file.startswith("frame_"):
                    os.remove(os.path.join(self.frame_dir, file))
            print(self.frame_dir,self.grid_dir)
            #清空网格文件夹
            for file in os.listdir(self.grid_dir):
                if file.startswith("grid_"):
                    os.remove(os.path.join(self.grid_dir, file))
            print(self.frame_dir,self.grid_dir)
            self.extract_frames()
            print("2#3",self.frame_dir,self.grid_dir)
            logger.info("开始拼接网格图...")
            image_paths = []
            groups = self.group_images()
            for idx, group in enumerate(groups, start=1):
                if len(group) < self.grid_size[0] * self.grid_size[1]:
                    logger.warning(f"⚠️ 跳过第 {idx} 组，图片不足 {self.grid_size[0] * self.grid_size[1]} 张")
                    continue
                out_path = self.concat_images(group, f"grid_{idx}")
                image_paths.append(out_path)

            logger.info("📤 开始编码图像...")
            urls = self.encode_images_to_base64(image_paths)
            return urls
        except Exception as e:
            logger.error(f"发生错误：{str(e)}")
            raise ValueError("视频处理失败")


