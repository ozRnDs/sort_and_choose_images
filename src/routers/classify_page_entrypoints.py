from typing import List

from fastapi import FastAPI, exceptions, status

from src.services.faces_db_service import FaceDBService
from src.services.groups_db import load_groups_from_pickle_file, sort_and_save_groups
from src.utils.model_pydantic import (
    Face,
    UpdateClassificationRequest,
    UpdateRonInImageRequest,
)


class ClassifyRouter:
    def __init__(self, face_db_service: FaceDBService):
        self._face_db_service = face_db_service

    def create_entry_points(self, app: FastAPI):
        # Endpoint to update the image classification
        @app.post("/update_image_classification", tags=["Images"])
        async def update_image_classification(request: UpdateClassificationRequest):
            raise exceptions.HTTPException(
                status_code=status.HTTP_410_GONE, detail="This function is disabled"
            )
            grouped_metadata = load_groups_from_pickle_file()
            # Find the group and update the classification for the specific image
            group_found = False
            for group in grouped_metadata:
                if group["group_name"] == request.group_name:
                    group_found = True
                    for image in group["list_of_images"]:
                        if image["name"] == request.image_name:
                            image["classification"] = request.classification
                            break
                    break

            if not group_found:
                raise exceptions.HTTPException(
                    status_code=404, detail="Group not found"
                )

            # Save updated metadata
            sort_and_save_groups(grouped_metadata)

            return {"message": "Image classification updated successfully"}

        # Endpoint to update the 'Ron in the image' flag
        @app.post("/update_ron_in_image", tags=["Images"])
        async def update_ron_in_image(request: UpdateRonInImageRequest):
            raise exceptions.HTTPException(
                status_code=status.HTTP_410_GONE, detail="This function is disabled"
            )
            # Load existing grouped metadata
            grouped_metadata = load_groups_from_pickle_file()

            # Find the group and update the 'Ron in image' flag for the specific image
            group_found = False
            for group in grouped_metadata:
                if group["group_name"] == request.group_name:
                    group_found = True
                    for image in group["list_of_images"]:
                        if image["name"] == request.image_name:
                            image["ron_in_image"] = request.ron_in_image
                            image_full_path = image["full_client_path"]
                            break
                    break

            if not group_found:
                raise exceptions.HTTPException(
                    status_code=404, detail="Group not found"
                )
            self.update_images_face(
                image_full_path=image_full_path, ron_in_image=request.ron_in_image
            )
            # Save updated metadata
            sort_and_save_groups(grouped_metadata)
            return {"message": "Ron in image flag updated successfully"}

    def update_images_face(self, image_full_path: str, ron_in_image: bool):
        faces_to_update: List[Face] = self._face_db_service.get_faces(
            {"image_full_path": image_full_path}
        )

        for face in faces_to_update:
            face.ron_in_image = ron_in_image
            self._face_db_service.add_face(face)
