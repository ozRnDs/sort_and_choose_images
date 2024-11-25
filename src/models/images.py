from typing import Optional

from pydantic import BaseModel


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
