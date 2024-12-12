import asyncio
import os
import pickle
import time
from enum import Enum
from typing import List, Optional

import httpx
from loguru import logger
from tinydb import Query, TinyDB

from ..utils.model_pydantic import ImageFaceRecognitionStatus, ImageMetadata
from .faces_db_service import Face, FaceDBService
from .redis_service import (
    RedisInterface,  # Assuming this is the file where RedisInterface is defined
)


class ProcessStatus(str, Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    CRASHED = "CRASHED"
    DONE = "DONE"


class FaceRecognitionService:
    """
    FaceRecognitionService.

    This class handles the face recognition workflow by processing a list of images
    and interacting with the PixID API to extract face vectors. The extracted vectors
    are stored in a Redis database using RedisInterface.

    Key Features:
        1. Image Processing:
           - Iterates through a list of images and uses the PixID API to extract
             vectors for all detected faces.

        2. Data Storage:
           - Stores the extracted face vectors in Redis, using RedisInterface.

        3. Status Persistence:
           - Tracks the processing status of images to allow resumption in case
             of interruption.

        4. Status Reporting:
           - Provides a method to retrieve the current operational state of the service:
               - IDLE: The service is not actively processing.
               - WORKING: The service is actively processing images and progress details
                 are available.
               - CRASHED: An error has occurred, halting the process.
    """

    def __init__(
        self,
        base_url: str,
        redis_interface: RedisInterface,
        face_db_service: FaceDBService,
        progress_file="face_recognition_progress.pkl",
        db_path="face_recognition_progress.json",
    ):
        """
        Initializes the FaceRecognitionService.

        Args:
            redis_interface (RedisInterface): An instance of RedisInterface for data storage.
            db_path (str): Path to the TinyDB file for progress persistence.
            pickle_file (str): Path to the existing pickle file for migration.
        """
        self.redis_interface = redis_interface
        self._face_db_service = face_db_service

        self.status = ProcessStatus.IDLE
        self.progress = 0
        # self.images: List[ImageMetadata] = []
        self.processed_images_names = []
        self.failed_images_names = []
        self._progress_file = progress_file
        self._process_time = []

        self._httpx_client = httpx.AsyncClient()
        self._base_url = base_url
        self._terminate = False
        self._processing_task = None

        # Initialize TinyDB
        self._db = TinyDB(db_path)

    async def load_progress(self):
        """
        Loads progress data from TinyDB.
        """
        logger.info("Loading progress from TinyDB.")

        # Load metadata
        progress_query = Query()
        progress_data = self._db.get(progress_query.id == "progress_metadata")
        if progress_data:
            self.processed_images_names = progress_data.get("processed_images", [])
            self.progress = progress_data.get("progress", 0)
            self.failed_images_names = progress_data.get("failed_images", [])

        logger.info("Progress loaded successfully.")

    def get_images_count(self):
        return self._db.count(Query().full_client_path.exists())

    def migrate_pickle_to_tinydb(self):
        """
        Migrates data from the existing pickle file to the TinyDB database.
        """
        if not os.path.exists(self._progress_file):
            logger.info("No pickle file found. Migration skipped.")
            return

        logger.info("Starting migration from pickle to TinyDB.")
        try:
            with open(self._progress_file, "rb") as file:
                progress_data = pickle.load(file)

            # Load data into the service attributes
            images = [
                ImageMetadata(**image) for image in progress_data.get("images", [])
            ]
            self.processed_images_names = progress_data.get("processed_images", [])
            self.progress = progress_data.get("progress", 0)
            self.failed_images_names = progress_data.get("failed_images", [])

            # Use persist_progress to save data to TinyDB
            self.load_images(images)
            self.persist_progress()

            logger.info("Migration completed successfully.")
        except (pickle.PickleError, EOFError, FileNotFoundError) as e:
            logger.error(f"Failed to migrate data from pickle: {e}")

    def load_images(self, images: List[ImageMetadata]) -> int:
        """
        Loads the images to be processed.

        Args:
            images (list): List of image paths to be processed.
        """
        loaded_images = 0
        for image in images:
            if image.full_client_path in self.processed_images_names:
                image.face_recognition_status = ImageFaceRecognitionStatus.DONE
            if image.full_client_path in self.failed_images_names:
                image.face_recognition_status = ImageFaceRecognitionStatus.FAILED
            self._db.upsert(
                image.model_dump(), Query().full_client_path == image.full_client_path
            )
            loaded_images += 1
        return loaded_images

    def get_status(self) -> dict:
        """
        Returns the current status of the service.

        Returns:
            tuple: (Status, progress percentage)
        """
        images_in_queue = (
            self.get_images_count()
            - len(self.processed_images_names)
            - len(self.failed_images_names)
        )
        time_left = (
            images_in_queue * sum(self._process_time) / len(self._process_time)
            if len(self._process_time) > 0
            else -1
        )

        return {
            "status": self.status,
            "progress": self.progress,
            "time_left_seconds": time_left,
            "images": self.get_images_count(),
            "processed_images": len(self.processed_images_names),
            "failed_images": len(self.failed_images_names),
        }

    def stop(self):
        self._terminate = True

    async def start(self):
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._astart())
            await asyncio.sleep(2)

    async def retry(self):
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._astart(retry=True))
            await asyncio.sleep(2)

    async def _astart(self, retry: bool = False):
        """
        Starts processing the images using the PixID API, resuming if progress was
        previously saved.
        """
        if self.status == ProcessStatus.WORKING:
            raise RuntimeError("Service is already running.")

        self.status = ProcessStatus.WORKING

        try:
            while True:
                if self._terminate:
                    self.persist_progress()
                    break

                # Fetch one image to process
                image = self._get_remaining_image(retry)
                if not image:
                    # No remaining images to process
                    break
                logger.info(f"Process image {image.name}")
                image_process_status = await self._process_image(image)

                # Update progress dynamically
                self._update_progress(
                    image_name=image.full_client_path, image_status=image_process_status
                )
                self.update_image_status(
                    full_client_path=image.full_client_path,
                    new_status=image_process_status,
                )
                self.persist_progress()

            self.status = (
                ProcessStatus.DONE
                if not self._get_remaining_image(False)
                else ProcessStatus.IDLE
            )

        except Exception as e:
            self.status = ProcessStatus.CRASHED
            self.persist_progress()
            logger.error(f"Error occurred during processing: {e}")

        finally:
            self._processing_task = None

    def _get_remaining_image(self, retry: bool) -> Optional[ImageMetadata]:
        """
        Returns one image that still needs to be processed.
        """
        # logger.info("Fetching one remaining image with appropriate status.")
        query = Query()
        if not retry:
            # Fetch one image where status is PENDING
            result = self._db.get(
                query.face_recognition_status
                == ImageFaceRecognitionStatus.PENDING.value
            )
        else:
            # Fetch one image where status is PENDING or FAILED
            result = self._db.get(
                (
                    query.face_recognition_status
                    == ImageFaceRecognitionStatus.PENDING.value
                )
                | (
                    query.face_recognition_status
                    == ImageFaceRecognitionStatus.FAILED.value
                )
            )

        # Return the result as an ImageMetadata object or None if no match
        return ImageMetadata(**result) if result else None

    def _get_remaining_images(self, retry: bool) -> List[ImageMetadata]:
        """
        Returns the list of images that still need to be processed.
        """
        logger.info("Fetching remaining images with appropriate status.")
        query = Query()
        if not retry:
            # Fetch images where status is PENDING
            result = self._db.search(
                query.face_recognition_status
                == ImageFaceRecognitionStatus.PENDING.value
            )
        else:
            # Fetch images where status is PENDING or FAILED
            result = self._db.search(
                (query.face_recognition_status != ImageFaceRecognitionStatus.DONE.value)
                | (
                    query.face_recognition_status
                    == ImageFaceRecognitionStatus.FAILED.value
                )
            )

        # Convert the results back to ImageMetadata objects
        return [ImageMetadata(**doc) for doc in result]

    async def _process_image(self, image: ImageMetadata) -> ImageFaceRecognitionStatus:
        """
        Processes a single image and handles retries.
        """
        start_time = time.perf_counter()

        try:
            face_vectors = await self._retry_process_image(image)
            self._store_face_vectors(image, face_vectors)
            self.processed_images_names.append(image.full_client_path)
            logger.info(f"Processed {image.full_client_path} successfully.")
            return ImageFaceRecognitionStatus.DONE
        except RuntimeError as err:
            self.failed_images_names.append(image.full_client_path)
            logger.error(f"Failed to process image {image.full_client_path}: {err}")
            return ImageFaceRecognitionStatus.FAILED
        finally:
            process_time = time.perf_counter() - start_time
            self._update_process_time(process_time)

    def _update_progress(
        self, image_name: str, image_status: ImageFaceRecognitionStatus
    ):
        """
        Updates the overall progress percentage.
        """
        if image_status == ImageFaceRecognitionStatus.FAILED:
            self.failed_images_names.append(image_name)
        if image_status == ImageFaceRecognitionStatus.DONE:
            self.processed_images_names.append(image_name)

        processed_count = len(self.processed_images_names)
        self.progress = int(processed_count / self.get_images_count() * 100)

    def _store_face_vectors(self, image: ImageMetadata, face_vectors: dict):
        """
        Stores face vectors in Redis and the database.
        """
        for face in face_vectors["insights"]:
            face_object = Face(
                image_full_path=image.full_client_path,
                bbox=[int(coordinate) for coordinate in face["bbox"]],
                embedding=face["embedding"],
                ron_in_image=image.ron_in_image,
            )
            self.redis_interface.add_embedding(face_object)
            self._face_db_service.add_face(face_object)

    def _update_process_time(self, t: float):
        if len(self._process_time) > 10:
            self._process_time.pop(0)
        self._process_time.append(t)

    async def _retry_process_image(
        self, image: ImageMetadata, retries: int = 1
    ) -> dict:
        """
        Retries processing an image for a specified number of attempts.
        """
        for attempt in range(1, retries + 1):
            try:
                return await self.process_image(image.full_client_path)
            except RuntimeError as err:
                logger.warning(
                    f"Attempt {attempt} failed for {image.full_client_path}: {err}. Restarting HTTP client."
                )
                await self._httpx_client.aclose()
                self._httpx_client = httpx.AsyncClient()
        raise RuntimeError(
            f"Failed to process {image.full_client_path} after {retries} retries."
        )

    async def process_image(self, image: str):
        """
        Processes an image by uploading it to a POST endpoint.

        Args:
            image (str): Path to the image.

        Returns:
            list: List of dictionaries containing bounding boxes and embeddings.
        """
        if not os.path.exists(image):
            raise FileNotFoundError(f"Image file not found: {image}")

        # Define the API endpoint
        api_endpoint = httpx.URL(self._base_url).join(
            "/face/insight-recognize"
        )  # Replace with the actual endpoint URL

        # Read the image file
        with open(image, "rb") as file:
            image_data = file.read()

        # Send the image via POST request

        # Prepare the file for upload (mimicking UploadFile behavior)
        files = {"file": (os.path.basename(image), image_data)}

        try:
            response = await self._httpx_client.post(
                url=api_endpoint,
                files=files,
            )
            response.raise_for_status()  # Raise an error for HTTP status codes 4xx or 5xx
        # TODO: Catch error for service not available and close the main loop (without crashing)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP request failed: {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error: {e}")

        # Parse the response
        try:
            result = response.json()  # Ensure the response is JSON
        except ValueError:
            raise RuntimeError("Failed to parse JSON response from the API")

        # Return the result from the API
        if not isinstance(result, dict):
            raise RuntimeError(
                "API response format is incorrect. Expected a dict of data."
            )
        if "insights" not in result:
            raise RuntimeError(
                "API response format is incorrect. 'insights' field is missing"
            )
        if not isinstance(result["insights"], list):
            raise RuntimeError(
                "API response format is incorrect. Expected 'insights' field as list"
            )

        return result

    def update_image_status(
        self, full_client_path: str, new_status: ImageFaceRecognitionStatus
    ):
        """
        Updates the status of an image in TinyDB based on its full client path.

        Args:
            full_client_path (str): The unique path of the image to update.
            new_status (ImageFaceRecognitionStatus): The new status to set for the image.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        logger.info(f"Updating status for image: {full_client_path} to {new_status}.")

        query = Query()
        updated_count = self._db.update(
            {"face_recognition_status": new_status.value},
            query.full_client_path == full_client_path,
        )

        if updated_count[0] > 0:
            logger.info(f"Successfully updated status for image: {full_client_path}.")
            return True
        else:
            logger.warning(
                f"Failed to update status for image: {full_client_path}. Image not found."
            )
            return False

    def persist_progress(self):
        """
        Persists the current progress to TinyDB incrementally.
        """
        # logger.info("Persisting progress to TinyDB.")

        # Save metadata as a unique document
        progress_query = Query()
        self._db.upsert(
            {
                "id": "progress_metadata",  # Unique ID for progress metadata
                "processed_images": self.processed_images_names,
                "progress": self.progress,
                "failed_images": self.failed_images_names,
            },
            progress_query.id == "progress_metadata",
        )
        # # Save each image as a unique document
