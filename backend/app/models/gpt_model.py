from dataclasses import dataclass
from typing import List, Union, Optional

from app.models.transcriber_model import TranscriptSegment


@dataclass
class GPTSource:
    segment: Union[List[TranscriptSegment], List]
    title: str
    tags:str
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    style: Optional[str] = None
    extras: Optional[str] = None
    _format: Optional[list] = None
    video_img_urls:  Optional[list] = None
    checkpoint_key: Optional[str] = None
    # 视频原始 URL；仅 TwelveLabs Pegasus 视频理解后端需要（直接「看」视频）。
    video_url: Optional[str] = None

