import io
from typing import List

import cv2
from fastapi import FastAPI, Query, exceptions, responses, status
from pydantic import BaseModel

from src.services.face_reid import FaceDBService, FaceRecognitionService
from src.services.redis_service import RedisInterface
from src.utils.model_pydantic import Face


class FacePageResponse(BaseModel):
    page_index: int
    faces_in_page: int
    faces: List[Face]
    number_of_total_faces: int


class SimilarImagesResponse(BaseModel):
    full_client_path: str
    similarity: float


class SimilarFacesResponse(BaseModel):
    face_id: str
    similarity: float


class FaceManagmentRouter:
    def __init__(
        self,
        face_recognition_service: FaceRecognitionService,
        redis_service: RedisInterface,
        face_db_service: FaceDBService,
    ):
        self._face_recognition_service = face_recognition_service
        self._redis_service = redis_service
        self._face_db_service = face_db_service

    def create_entry_points(self, app: FastAPI):
        @app.get("/face/{face_id}/embedding", tags=["Face Recognition"])
        def get_embedding_by_face_id(face_id: str) -> Face:
            if self._redis_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Redis DB is not available",
                )
            embedding = self._redis_service.get_embedding(face_id=face_id)
            faces = self._face_db_service.get_faces(query={"face_id": face_id})
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
            faces = self._face_db_service.get_faces(query={"face_id": face_id})
            if not faces:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Face was not found",
                )

            result_face = faces[0]
            image_path = result_face.image_full_path
            bbox = result_face.bbox  # bbox is expected to be a list of [x1, y1, x2, y2]

            # Load the image using OpenCV
            try:
                image = cv2.imread(image_path)
                if image is None:
                    raise FileNotFoundError(f"Image file not found: {image_path}")
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
                x1, y1, x2, y2 = bbox  # Assuming bbox is in the format [x1, y1, x2, y2]
                cropped_face = image[y1:y2, x1:x2]  # Crop the image using NumPy slicing
                if cropped_face.size == 0:
                    raise ValueError("Cropping resulted in an empty image")
            except Exception as e:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to crop image: {e}",
                )

            # Encode the cropped image to JPEG
            try:
                success, buffer = cv2.imencode(".jpg", cropped_face)
                if not success:
                    raise ValueError("Failed to encode the cropped image")
                cropped_image_bytes = io.BytesIO(buffer.tobytes())
            except Exception as e:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to encode image: {e}",
                )

            # Return the cropped image as a streaming response
            return responses.StreamingResponse(
                cropped_image_bytes, media_type="image/jpeg"
            )

        @app.get("/face/list/ron_in_image", tags=["Face Management"])
        async def get_paginated_faces_with_ron_in_image(
            page: int = Query(1, ge=1, description="Page number"),
            page_size: int = Query(
                10, ge=1, le=100, description="Number of items per page"
            ),
            show_hidden_images: bool = Query(False, description="Show hidden images"),
        ) -> FacePageResponse:
            """
            Paginated endpoint to get faces where 'ron_in_image' is True.

            Args:
                page (int): The page number to retrieve.
                page_size (int): The number of items per page.

            Returns:
                FacePageResponse: Paginated list of faces matching the rule.
            """
            # Retrieve all faces matching the rule
            query = {"ron_in_image": True}
            if not show_hidden_images:
                query["hide_face"] = False
            faces = self._face_db_service.get_faces(query=query)

            # Handle no matches found
            if not faces:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No faces found with 'ron_in_image' set to True",
                )
            number_of_faces = len(faces)
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

            return FacePageResponse(
                page_index=page,
                faces_in_page=page_size,
                faces=paginated_faces,
                number_of_total_faces=number_of_faces,
            )

        @app.post("/face/{face_id}/ron_in_face", tags=["Face Management"])
        async def update_ron_in_face(face_id: str) -> bool:
            selected_face = self._face_db_service.get_faces(query={"face_id": face_id})[
                0
            ]
            selected_face.ron_in_face = not selected_face.ron_in_face
            self._face_db_service.add_face(selected_face, flush=True)
            # TODO: Update image and face with the information
            return selected_face.ron_in_face

        @app.post("/face/{face_id}/hide", tags=["Face Management"])
        async def update_hide_face(face_id: str) -> bool:
            selected_face = self._face_db_service.get_faces(query={"face_id": face_id})[
                0
            ]
            selected_face.hide_face = not selected_face.hide_face
            self._face_db_service.add_face(selected_face, flush=True)
            return selected_face.hide_face

        @app.post("/scripts/face_db/migrate", tags=["Admin"])
        async def migrate_face_db():
            self._face_db_service.migrate_faces_table_to_documents()
            return

        @app.get("/face/get_similar_faces", tags=["Face Similarity"])
        async def get_similar_faces(
            threshold: float = 0.8,
        ) -> List[SimilarFacesResponse]:
            target_faces = self._face_db_service.get_faces({"ron_in_face": True})

            response_list = []

            for face in target_faces:
                search_embeddings = self._redis_service.get_embedding(face.face_id)
                if not search_embeddings:
                    continue
                results = self._redis_service.vector_search(search_embeddings, k=1000)

                for result in results:
                    if 0.01 < result["score"] < threshold:
                        similar_face = SimilarFacesResponse(
                            similarity=1 - result["score"], face_id=result["face_id"]
                        )
                        response_list.append(similar_face)
            return response_list
