from enum import Enum
from typing import List

from fastapi import FastAPI, exceptions, status
from fastapi.responses import FileResponse
from loguru import logger
from tqdm import tqdm

from src.services.face_reid import FaceRecognitionService
from src.services.groups_db import load_groups_from_pickle_file
from src.services.groups_db_service import GroupDBService
from src.services.images_db_service import ImageDBService
from src.utils.model_pydantic import (
    GroupMetadata,
    GroupMetadata_V1,
    ImageFaceRecognitionStatus,
    ImageMetadata,
)


class DBType(str, Enum):
    PICKLE = "pickle"
    TINYDB = "tinydb"


class DbRouter:
    def __init__(
        self,
        image_db_path: str,
        group_db_path: str,
        image_db_path_pickle: str,
        groups_db_path_pickle: str,
        image_db_service: ImageDBService,
        group_db_service: GroupDBService,
        face_recognition_service: FaceRecognitionService,
    ):
        """
        Initialize the DbRouter with paths to the image and groups databases.
        """
        self._image_db_path = image_db_path
        self._groups_db_path = group_db_path
        self._image_db_path_pickle = image_db_path_pickle
        self._groups_db_path_pickle = groups_db_path_pickle
        self._image_db_service = image_db_service
        self._groups_db_service = group_db_service
        self._face_recognition_service = face_recognition_service

    def create_entry_points(self, app: FastAPI):
        """
        Create the endpoints for downloading the image and groups databases.
        """

        @app.get(
            "/download/images_db",
            description="Download Images DB",
            response_class=FileResponse,
            tags=["DB Managment"],
        )
        def get_images_db(db_type: DBType = DBType.TINYDB):
            """
            Endpoint to download the images database file.
            """
            if db_type == DBType.PICKLE:
                filename = self._image_db_path_pickle
            if db_type == DBType.TINYDB:
                filename = self._image_db_path
            return FileResponse(
                path=filename,
                filename="images.db",
                media_type="application/octet-stream",
            )

        @app.get(
            "/download/groups_db",
            description="Download Groups DB",
            response_class=FileResponse,
            tags=["DB Managment"],
        )
        def get_groups_db(db_type: DBType = DBType.TINYDB):
            """
            Endpoint to download the groups database file.
            """
            if db_type == DBType.PICKLE:
                filename = self._groups_db_path_pickle
            if db_type == DBType.TINYDB:
                filename = self._groups_db_path
            return FileResponse(
                path=filename,
                filename="groups.db",
                media_type="application/octet-stream",
            )

    async def migrate_groups_db(self):
        """
        Migrates data from a pickle file containing GroupMetadata_V1 objects to new
        TinyDB databases.

        Args:
            group_db_path (str): Path to the new groups database file.
            image_db_path (str): Path to the new images database file.
        """
        try:
            # Load groups from the existing pickle file
            data: List[GroupMetadata_V1] = [
                GroupMetadata_V1(**group)
                for group in load_groups_from_pickle_file(
                    db_location=self._groups_db_path_pickle
                )
            ]

            # Initialize new DB services
            group_service = self._groups_db_service
            image_service = self._image_db_service

            # Migrate data
            for old_group in tqdm(data, desc="Migrating groups"):
                # Migrate images
                for image in tqdm(
                    old_group.list_of_images,
                    desc=f"Migrating images for group {old_group.group_name}",
                    leave=False,
                ):
                    image_metadata = ImageMetadata(
                        name=image.name,
                        full_client_path=image.full_client_path,
                        size=image.size,
                        type=image.type,
                        camera=image.camera,
                        location=image.location,
                        creationDate=image.creationDate,
                        classification=image.classification,
                        ron_in_image=image.ron_in_image,
                        face_recognition_status=image.face_recognition_status,
                    )
                    image_service.add_image(image_metadata)

                # Migrate group
                group_metadata = GroupMetadata(
                    group_name=old_group.group_name,
                    group_thumbnail_url=old_group.group_thumbnail_url,
                    list_of_images=[
                        img.full_client_path for img in old_group.list_of_images
                    ],
                    selection=old_group.selection,
                )
                group_service.add_group(group_metadata)

            image_service.save_db()
            group_service.save_db()
            return {"message": "Migration completed successfully."}
        except FileNotFoundError as e:
            raise exceptions.HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        except Exception as e:
            logger.exception(e)
            raise exceptions.HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during migration: {e}",
            )

    async def update_group_field_in_images(self):
        groups = self._groups_db_service.get_groups()

        for group in tqdm(groups):
            if group.group_name.lower() == "unknown":
                # Clean images that exists in a different group
                new_list_of_images = []
                for image_path in tqdm(group.list_of_images):
                    image = self._image_db_service.get_images(
                        query={"full_client_path": image_path}
                    )
                    if image and image[0].group_name.lower == "":
                        new_list_of_images.append(image_path)
                        image[0].group_name = group.group_name
                        self._image_db_service.add_image(image[0])
                group.list_of_images = new_list_of_images
                self._groups_db_service.add_group(group, flush=True)
                continue

            # Update the image group_name
            images_details = self._image_db_service.get_images(
                query={"full_client_path": {"$in": group.list_of_images}}
            )
            for image in tqdm(images_details):
                image.group_name = group.group_name
                image.face_recognition_status = (
                    self._face_recognition_service.get_image_status(
                        image_full_path=image.full_client_path
                    )
                )
                if image.face_recognition_status == ImageFaceRecognitionStatus.FAILED:
                    image.face_recognition_status == ImageFaceRecognitionStatus.RETRY
                self._image_db_service.add_image(image)

        self._image_db_service.save_db()
        self._groups_db_service.save_db()
