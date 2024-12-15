from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ImageFaceRecognitionStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"
    RETRY = "retry"
    DONE = "done"


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
    face_recognition_status: Optional[
        ImageFaceRecognitionStatus
    ] = ImageFaceRecognitionStatus.PENDING
    group_name: Optional[str] = "Unknown"


class GroupMetadata(BaseModel):
    group_name: str
    group_thumbnail_url: str
    list_of_images: List[str]
    selection: str = (
        "unprocessed"  # Can be "unprocessed", "interesting", or "not interesting"
    )
    ron_in_group: Optional[bool] = False
    has_new_image: Optional[bool] = False

    @property
    def image_count(self):
        return len(self.list_of_images)


class GroupMetadata_V1(BaseModel):
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
    hide_face: Optional[bool] = Field(default=False)


# Define Pydantic model for paginated response
class PaginatedGroupsResponseV1(BaseModel):
    total_groups: int
    current_page: int
    page_size: int
    groups: List[GroupMetadata_V1]


# Define Pydantic model for paginated response
class PaginatedGroupsResponseV2(BaseModel):
    total_groups: int
    current_page: int
    page_size: int
    groups: List[GroupMetadata]


class ToggleGroupSelection(BaseModel):
    group_name: str
    selection: str


class UpdateClassificationRequest(BaseModel):
    group_name: str
    image_name: str
    classification: str


class UpdateRonInImageRequest(BaseModel):
    group_name: str
    image_name: str
    ron_in_image: bool
