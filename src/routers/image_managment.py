import os
import pickle
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import exifread
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.services.groups_db import sort_and_save_groups
from src.utils.model_pydantic import GroupMetadata_V1, ImageMetadata


class ImagesProcessing_V1:
    def __init__(
        self, images_base_path: str, pickle_file_path: str, group_file_path: str
    ):
        self._image_base_path = images_base_path  # BasePath
        self._pickle_file_path = pickle_file_path  # PICKLE_FILE
        self._group_file_path = group_file_path

    def create_entry_points(self, app: FastAPI):
        # Update the load_images function to use the new extract_image_metadata function
        @app.get("/load_images", tags=["Admin"])
        async def load_images():
            images: List[ImageMetadata] = []
            for root, _, files in os.walk(self._image_base_path):
                for file in files:
                    if file.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")
                    ):
                        image_metadata = self.extract_image_metadata(file, root)
                        images.append(image_metadata)

            # Convert Pydantic objects to a list of dictionaries for pickling
            images_data = [image.model_dump() for image in images]
            # Save the metadata to a pickle file
            with open(self._pickle_file_path, "wb") as f:
                pickle.dump(images_data, f)

            print("Loaded images and saved metadata to pickle file.")

            # Group images by date (e.g., per day)
            groups = defaultdict(list)
            for image in images_data:
                # Assuming 'creationDate' is in format 'YYYY:MM:DD HH:MM:SS'
                try:
                    date_str = image.get("creationDate", "").split(" ")[
                        0
                    ]  # Extract the date part only
                    date_obj = datetime.strptime(date_str, "%Y:%m:%d")
                    group_key = date_obj.strftime("%Y-%m-%d")  # Group by date
                except ValueError:
                    group_key = "Unknown"
                groups[group_key].append(image)

            # Save groups using the new function
            self.save_groups(groups)

            return JSONResponse(
                content={"message": "Images loaded and grouped successfully"},
                status_code=200,
            )

    def extract_image_metadata(self, file: str, root: str) -> ImageMetadata:
        """
        Extracts metadata from a single image file.

        Args:
            file (str): The name of the image file.
            root (str): The directory path where the file is located.

        Returns:
            ImageMetadata: An object containing metadata of the image.
        """
        full_path = os.path.join(root, file)
        size = os.path.getsize(full_path)
        type_ = file.split(".")[-1].upper()
        creation_date = "Unknown"
        camera = "Unknown"

        # Extract EXIF metadata if available
        with open(full_path, "rb") as image_file:
            tags = exifread.process_file(
                image_file, stop_tag="DateTimeOriginal", details=False
            )
            if "EXIF DateTimeOriginal" in tags:
                creation_date = tags["EXIF DateTimeOriginal"].values
            if "Image Model" in tags:
                camera = tags["Image Model"].values

        # If creation_date is still unknown, use the file's last modified date
        if creation_date == "Unknown":
            modified_timestamp = os.path.getmtime(full_path)
            creation_date = datetime.fromtimestamp(modified_timestamp).strftime(
                "%Y:%m:%d %H:%M:%S"
            )

        # Check if the file name matches the WhatsApp image naming structure
        if camera == "Unknown":
            whatsapp_pattern = r"IMG-\d{8}-WA\d+"
            if re.match(whatsapp_pattern, file):
                camera = "whatsapp"

        return ImageMetadata(
            name=file,
            full_client_path=full_path.replace(self._image_base_path, "/images"),
            size=size,
            type=type_,
            camera=camera,
            creationDate=creation_date,
        )

    def save_groups(self, groups: Dict[str, List[Dict]]):
        """
        Save the groups to the grouped metadata file after sorting by creation date.

        Args:
            groups (Dict[str, List[Dict]]): The dictionary of groups to save.
        """
        # Load existing grouped metadata if it exists
        if os.path.exists(self._group_file_path):
            with open(self._group_file_path, "rb") as f:
                grouped_metadata = pickle.load(f)
        else:
            grouped_metadata = []

        # Update or add new groups to grouped metadata
        existing_group_names = {
            group["group_name"]: group for group in grouped_metadata
        }
        for group_key, images in groups.items():
            # Sort images by creation date
            images.sort(key=lambda x: x.get("creationDate", "Unknown"))
            representative_image = images[0]  # Select the first image as representative
            group_thumbnail_url = representative_image.get("full_client_path")

            if group_key in existing_group_names:
                # Update existing group
                existing_group = existing_group_names[group_key]

                # Preserve existing group's selection field
                selection = existing_group.get("selection")

                # Update list_of_images, preserving classification and ron_in_image fields if they exist
                existing_images = {
                    img.get("image_id"): img for img in existing_group["list_of_images"]
                }
                for image in images:
                    image_id = image.get("image_id")
                    if image_id in existing_images:
                        existing_image = existing_images[image_id]
                        image["classification"] = existing_image.get(
                            "classification", image.get("classification")
                        )
                        image["ron_in_image"] = existing_image.get(
                            "ron_in_image", image.get("ron_in_image")
                        )

                existing_group["list_of_images"] = images
                existing_group["selection"] = selection
            else:
                # Add new group
                group_metadata = GroupMetadata_V1(
                    group_name=group_key,
                    group_thumbnail_url=group_thumbnail_url,
                    list_of_images=images,
                )
                grouped_metadata.append(group_metadata.model_dump())

        # Save updated grouped metadata to a pickle file
        sort_and_save_groups(grouped_metadata)
