from typing import List

from fastapi import FastAPI, exceptions, status
from fastapi.responses import FileResponse
from loguru import logger
from tqdm import tqdm

from src.services.groups_db import load_groups_from_pickle_file
from src.services.groups_db_service import GroupDBService
from src.services.images_db_service import ImageDBService
from src.utils.model_pydantic import GroupMetadata, GroupMetadata_V1, ImageMetadata


class DbRouter:
    def __init__(
        self,
        image_db_path: str,
        group_db_path: str,
        image_db_path_pickle: str,
        groups_db_path_pickle: str,
    ):
        """
        Initialize the DbRouter with paths to the image and groups databases.
        """
        self._image_db_path = image_db_path
        self._groups_db_path = group_db_path
        self._image_db_path_pickle = image_db_path_pickle
        self._groups_db_path_pickle = groups_db_path_pickle

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
        def get_images_db():
            """
            Endpoint to download the images database file.
            """
            return FileResponse(
                path=self._image_db_path_pickle,
                filename="images.db",
                media_type="application/octet-stream",
            )

        @app.get(
            "/download/groups_db",
            description="Download Groups DB",
            response_class=FileResponse,
            tags=["DB Managment"],
        )
        def get_groups_db():
            """
            Endpoint to download the groups database file.
            """
            return FileResponse(
                path=self._groups_db_path_pickle,
                filename="groups.db",
                media_type="application/octet-stream",
            )

        @app.post("/scripts/migrate/groups_db", tags=["DB Managment"])
        def migrate_groups_db():
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
                group_service = GroupDBService(db_path=self._groups_db_path)
                image_service = ImageDBService(db_path=self._image_db_path)

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


# Example usage:
# app = FastAPI()
# db_router = DbRouter(image_db_path="/path/to/images.db", groups_db_path="/path/to/groups.db")
# db_router.create_entry_points(app)
