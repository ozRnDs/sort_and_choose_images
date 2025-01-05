import os
import pickle
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import exifread
from fastapi import FastAPI, exceptions, status
from fastapi.responses import JSONResponse
from tqdm import tqdm

from src.services.groups_db import sort_and_save_groups
from src.services.groups_db_service import GroupDBService
from src.services.images_db_service import ImageDBService
from src.utils.model_pydantic import GroupMetadata, GroupMetadata_V1, ImageMetadata


class ImagesProcessingV1:
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
            raise exceptions.HTTPException(
                status_code=status.HTTP_410_GONE, detail="This function is disabled"
            )
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


class ImagesProcessingV2:
    def __init__(
        self,
        images_base_path: str,
        group_db_service: GroupDBService,
        image_db_service: ImageDBService,
    ):
        self._image_base_path = images_base_path
        self._group_db_service = group_db_service
        self._image_db_service = image_db_service

    def create_entry_points(self, app: FastAPI):
        @app.get("/v2/load_images", tags=["Admin"])
        async def load_images(rewrite: bool = False):
            # Get the total number of files to process for progress tracking
            total_files = sum(
                len(files)
                for _, _, files in os.walk(self._image_base_path)
                if any(
                    file.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")
                    )
                    for file in files
                )
            )

            # Use tqdm for progress tracking
            with tqdm(
                total=total_files, desc="Processing Images", unit="image"
            ) as pbar:
                # Walk through the base path to find images
                for root, _, files in os.walk(self._image_base_path):
                    for file in files:
                        if file.lower().endswith(
                            (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")
                        ):
                            image_metadata = self.extract_image_metadata(file, root)

                            # Check if the image is already in the database
                            existing_images = self._image_db_service.get_images(
                                query={
                                    "full_client_path": image_metadata.full_client_path
                                }
                            )

                            if existing_images:
                                pbar.update(1)  # Update progress even for skipped files
                                if rewrite:
                                    image_metadata.classification = existing_images[
                                        0
                                    ].classification
                                    image_metadata.face_recognition_status = (
                                        existing_images[0].face_recognition_status
                                    )
                                    image_metadata.ron_in_image = existing_images[
                                        0
                                    ].ron_in_image
                                else:
                                    continue  # Skip processing if image exists

                            # Determine the group for the image
                            group_name = self._determine_group(image_metadata)
                            image_metadata.group_name = group_name

                            # Add image to group
                            self._group_db_service.add_image_to_group(
                                group_name, image_metadata.full_client_path
                            )

                            # Add image to the database
                            self._image_db_service.add_image(image_metadata)

                            # Update progress bar
                            pbar.update(1)

            # Save databases after processing
            self._group_db_service.save_db()
            self._image_db_service.save_db()

            return JSONResponse(
                content={"message": "Images processed successfully"},
                status_code=200,
            )

    def extract_image_metadata(self, file: str, root: str) -> ImageMetadata:
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

        # Use last modified date if EXIF metadata is unavailable
        if creation_date == "Unknown":
            modified_timestamp = os.path.getmtime(full_path)
            creation_date = datetime.fromtimestamp(modified_timestamp).strftime(
                "%Y:%m:%d %H:%M:%S"
            )

        # Check for WhatsApp-style image naming
        if camera == "Unknown" or "whatsapp":
            whatsapp_date = self._get_whatsapp_image_date(file)
            if whatsapp_date:
                camera = "whatsapp"
                creation_date = whatsapp_date

        return ImageMetadata(
            name=file,
            full_client_path=full_path.replace(self._image_base_path, "/images"),
            size=size,
            type=type_,
            camera=camera,
            creationDate=creation_date,
        )

    def _get_whatsapp_image_date(self, image_name: str):
        whatsapp_pattern = r"IMG-(\d{8})-WA\d+"
        match = re.match(whatsapp_pattern, image_name)
        if match:
            # Extract the date from the file name
            file_date = match.group(1)  # The "20201212" part

            # Convert the file date into a datetime object
            creation_date = datetime.strptime(file_date, "%Y%m%d").strftime(
                "%Y:%m:%d %H:%M:%S"
            )
            return creation_date
        return None

    def _determine_group(self, image_metadata: ImageMetadata) -> str:
        """
        Determines the group for an image based on its creation date.

        Args:
            image_metadata (ImageMetadata): Metadata of the image.

        Returns:
            str: The name of the group the image belongs to.
        """
        try:
            date_str = image_metadata.creationDate.split(" ")[0]
            date_obj = datetime.strptime(date_str, "%Y:%m:%d")
            group_name = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            group_name = "Unknown"

        # Check if the group already exists in the database
        existing_group = self._group_db_service.get_group(group_name)
        if not existing_group:
            # Create a new group if it doesn't exist
            group_metadata = GroupMetadata(
                group_name=group_name,
                group_thumbnail_url=image_metadata.full_client_path,
                list_of_images=[],
            )
            self._group_db_service.add_group(group_metadata, flush=True)

        return group_name

    async def fix_whatsapp_images_group(self):
        all_images = self._image_db_service.get_images()

        for image in tqdm(all_images):
            whatsapp_date = self._get_whatsapp_image_date(image.name)
            if not whatsapp_date:
                continue
            image.creationDate = whatsapp_date
            new_group_name = self._determine_group(image)
            if new_group_name == image.group_name:
                continue
            self._group_db_service.add_image_to_group(
                new_group_name, image.full_client_path
            )
            self._group_db_service.remove_image_from_group(
                image.group_name, image.full_client_path
            )
            image.group_name = new_group_name
            self._image_db_service.add_image(image=image)
            if image.ron_in_image is True or image.classification != "None":
                new_group = self._group_db_service.get_group(group_name=new_group_name)
                new_group.selection = "interesting"
                self._group_db_service.add_group(new_group)

        self._group_db_service.save_db()
        self._image_db_service.save_db()
