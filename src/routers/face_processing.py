import time

from fastapi import FastAPI, exceptions, status

from src.services.face_reid import FaceRecognitionService
from src.services.groups_db import load_groups_from_file
from src.utils.model_pydantic import GroupMetadata


class FaceProcessingRouter:
    def __init__(self, face_recognition_service=FaceRecognitionService):
        self._face_recognition_service = face_recognition_service

    def create_entry_points(self, app: FastAPI):
        @app.post(
            "/scripts/face_detection/load_images", tags=["Admin", "Face Recognition"]
        )
        async def face_detect():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            groups_metadata = load_groups_from_file()
            images = []
            for group in groups_metadata:
                group = GroupMetadata(**group)
                images += group.list_of_images

            loaded_images = self._face_recognition_service.load_images(images)
            await self._face_recognition_service.start()
            status_dict = self._face_recognition_service.get_status()
            return {"number_of_loaded_images": loaded_images, "status": status_dict}

        @app.get("/scripts/face_detection/status", tags=["Face Recognition"])
        def get_face_detection_status():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            status_dict = self._face_recognition_service.get_status()

            return status_dict

        @app.post("/script/face_detection/restart", tags=["Face Recognition"])
        async def restart_face_recognition():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            await self._face_recognition_service.start()
            return self._face_recognition_service.get_status()

        @app.post("/script/face_detection/retry", tags=["Face Recognition"])
        async def retry_face_recognition():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            await self._face_recognition_service.retry()
            return self._face_recognition_service.get_status()

        @app.post("/script/face_detection/stop", tags=["Face Recognition"])
        def stop_face_recognition():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            self._face_recognition_service.stop()
            time.sleep(0.3)
            return self._face_recognition_service.get_status()

        @app.post("/script/face_detection/migrate_db", tags=["Face Recognition"])
        def migrate_db():
            if self._face_recognition_service is None:
                raise exceptions.HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Face Recognition Service is not available",
                )
            self._face_recognition_service.migrate_pickle_to_tinydb()
            time.sleep(0.3)
            return self._face_recognition_service.get_status()
