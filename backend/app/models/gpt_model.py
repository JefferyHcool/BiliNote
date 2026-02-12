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

