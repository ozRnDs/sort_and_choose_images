import io
from typing import List

from fastapi import FastAPI, Query, exceptions, responses, status
from PIL import Image

from src.services.face_reid import FaceDBService, FaceRecognitionService
from src.services.redis_service import RedisInterface
from src.utils.model_pydantic import Face


class FaceManagmentRouter:
    def __init__(
        self,
        face_recognition_service: FaceRecognitionService,
        redis_service: RedisInterface,
        face_db_Service: FaceDBService,
    ):
        self._face_recognition_service = face_recognition_service
        self._redis_service = redis_service
        self._face_db_Service = face_db_Service

    def create_entry_points(self, app: FastAPI):
        @app.get("/face/{face_id}/embedding", tags=["Face Recognition"])
        def get_embedding_by_face_id(face_id: str) -> Face:
            if self._redis_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Redis DB is not available",
                )
            embedding = self._redis_service.get_embedding(face_id=face_id)
            faces = self._face_db_Service.get_faces(query={"face_id": face_id})
            if faces:
                result_face = faces[0]
                result_face.embedding = embedding
                return result_face
            raise exceptions.HTTPException(
                status=status.HTTP_404_NOT_FOUND, detail="Face was not found"
            )

        @app.get("/face/{face_id}/image", tags=["Face Management"])
        async def get_image_for_face(face_id: str):
            """
            Get the cropped image for a face based on its bounding box (bbox).

            Args:
                face_id (str): The unique identifier for the face.

            Returns:
                Cropped image as a streaming response.
            """
            # Retrieve the face data
            faces = self._face_db_Service.get_faces(query={"face_id": face_id})
            if not faces:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Face was not found",
                )

            result_face = faces[0]
            image_path = result_face.image_full_path
            bbox = (
                result_face.bbox
            )  # bbox is expected to be a list of [x, y, width, height]

            # Load the image using Pillow
            try:
                image = Image.open(image_path)
            except FileNotFoundError:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Image file not found: {image_path}",
                )
            except Exception as e:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load image: {e}",
                )

            # Crop the face using bbox
            try:
                x1, y1, x2, y2 = bbox
                cropped_face = image.crop((x1, y1, x2, y2))  # Crop using x1, y1, x2, y2
            except Exception as e:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to crop image: {e}",
                )

            # Save the cropped face to an in-memory buffer
            buffer = io.BytesIO()
            cropped_face.save(buffer, format="JPEG")
            buffer.seek(0)

            # Return the cropped image as a streaming response
            return responses.StreamingResponse(buffer, media_type="image/jpeg")

        @app.get("/face/list/ron_in_image", tags=["Face Management"])
        async def get_paginated_faces_with_ron_in_image(
            page: int = Query(1, ge=1, description="Page number"),
            page_size: int = Query(
                10, ge=1, le=100, description="Number of items per page"
            ),
        ) -> List[Face]:
            """
            Paginated endpoint to get faces where 'ron_in_image' is True.

            Args:
                page (int): The page number to retrieve.
                page_size (int): The number of items per page.

            Returns:
                List[Face]: Paginated list of faces matching the rule.
            """
            # Retrieve all faces matching the rule
            faces = self._face_db_Service.get_faces(query={"ron_in_image": True})

            # Handle no matches found
            if not faces:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No faces found with 'ron_in_image' set to True",
                )

            # Implement pagination
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_faces = faces[start_index:end_index]

            # Handle case where page is out of range
            if not paginated_faces:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No faces found for page {page}",
                )

            return paginated_faces
