from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    name: str
    full_client_path: str
    size: int
    type: str
    camera: Optional[str] = "Unknown"
    location: Optional[str] = "Unknown"
    creationDate: Optional[str] = "Unknown"
    classification: str = "None"
    ron_in_image: bool = False


class GroupMetadata(BaseModel):
    group_name: str
    group_thumbnail_url: str
    list_of_images: List[ImageMetadata]
    selection: str = (
        "unprocessed"  # Can be "unprocessed", "interesting", or "not interesting"
    )

    @property
    def image_count(self):
        return len(self.list_of_images)


class Face(BaseModel):
    face_id: str = Field(default_factory=lambda: str(uuid4()))
    image_full_path: str
    bbox: List[int]
    embedding: List[float] = []
    ron_in_image: bool = False
    ron_in_face: Optional[bool] = Field(default=False)
