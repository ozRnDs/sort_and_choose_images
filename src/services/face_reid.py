import asyncio
import os
import pickle
import time
from enum import Enum
from typing import List

import httpx
from loguru import logger

from ..utils.model_pydantic import ImageMetadata
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
    ):
        """
        Initializes the FaceRecognitionService.

        Args:
            redis_interface (RedisInterface): An instance of RedisInterface for data storage.
            progress_file (str): Path to the pickle file for progress persistence.
        """
        self.redis_interface = redis_interface
        self._face_db_service = face_db_service

        self.status = ProcessStatus.IDLE
        self.progress = 0
        self.images: List[ImageMetadata] = []
        self.processed_images_names = []
        self.failed_images_names = []
        self._progress_file = progress_file
        self._process_time = []

        self._httpx_client = httpx.AsyncClient()
        self._base_url = base_url
        self._terminate = False
        self._processing_task = None

    async def load_progress(self):
        logger.info("Start loading recognition progress data")
        if os.path.exists(self._progress_file):
            try:
                with open(self._progress_file, "rb") as file:
                    progress_data = pickle.load(file)
                    self.images = [
                        ImageMetadata(**image)
                        for image in progress_data.get("images", [])
                    ]
                    self.processed_images_names = progress_data.get(
                        "processed_images", []
                    )
                    self.progress = progress_data.get("progress", 0)
                    self.failed_images_names = progress_data.get("failed_images", [])
                    logger.info("Progress loaded. Resuming from the last saved state.")
            except (pickle.PickleError, EOFError) as e:
                print(f"Failed to load progress file: {e}")

    def load_images(self, images: List[ImageMetadata]) -> int:
        """
        Loads the images to be processed.

        Args:
            images (list): List of image paths to be processed.
        """
        new_images = [image for image in images if image not in self.images]
        self.images.extend(new_images)
        self.persist_progress()
        return len(new_images)

    def get_status(self) -> dict:
        """
        Returns the current status of the service.

        Returns:
            tuple: (Status, progress percentage)
        """
        images_in_queue = (
            len(self.images)
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
            "images": len(self.images),
            "time_left_seconds": time_left,
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
            if retry:
                remaining_images: List[ImageMetadata] = [
                    img
                    for img in self.images
                    if img.full_client_path not in self.processed_images_names
                ]
            else:
                remaining_images: List[ImageMetadata] = [
                    img
                    for img in self.images
                    if img.full_client_path not in self.processed_images_names
                    and img.full_client_path not in self.failed_images_names
                ]
            index = 0
            while index < len(remaining_images):
                if self._terminate:
                    self.persist_progress()
                    break
                start_time = time.perf_counter()
                image = remaining_images[index]

                for i in range(1):
                    try:
                        face_vectors = await self.process_image(image.full_client_path)
                        break
                    except RuntimeError as err:
                        logger.warning(
                            f"Failed to process image: {image.full_client_path} Attempt {i+1}. {err}. Restarting the httpx client"
                        )
                        await self._httpx_client.aclose()
                        self._httpx_client = httpx.AsyncClient()
                else:  # If all retries fail, execute this block
                    logger.error(
                        f"Failed to process image {image.full_client_path} after {i+1} attempts. Skipping image"
                    )
                    self.failed_images_names.append(image.full_client_path)
                    self.persist_progress()
                    index += 1
                    continue

                for face in face_vectors["insights"]:
                    # Extract image details and embedding
                    face_object = Face(
                        image_full_path=image.full_client_path,
                        bbox=[int(coordinate) for coordinate in face["bbox"]],
                        embedding=face["embedding"],
                        ron_in_image=image.ron_in_image,
                    )
                    self.redis_interface.add_embedding(face_object)
                    self._face_db_service.add_face(face_object)

                self.processed_images_names.append(image.full_client_path)
                logger.info(
                    f"Processed {image.full_client_path} and extracted {len(face_vectors['insights'])} faces"
                )
                process_time = time.perf_counter() - start_time
                self._update_process_time(process_time)
                # Update progress
                processed_count = len(self.processed_images_names)
                self.progress = int(processed_count / len(self.images) * 100)
                self.persist_progress()

                # Recompute remaining_images to reflect changes dynamically
                remaining_images = [
                    img for img in self.images if img not in self.processed_images_names
                ]
                index += 1

            if len(remaining_images) == 0:
                self.status = ProcessStatus.DONE
            else:
                self.status = ProcessStatus.IDLE
        except Exception as e:
            self.status = ProcessStatus.CRASHED
            self.persist_progress()
            print(f"Error: {e}")
        finally:
            self._processing_task = None

    def _update_process_time(self, t: float):
        if len(self._process_time) > 10:
            self._process_time.pop(0)
        self._process_time.append(t)

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

    def persist_progress(self):
        """
        Persists the current progress to a pickle file.
        """
        progress_data = {
            "images": [image.model_dump() for image in self.images],
            "processed_images": self.processed_images_names,
            "progress": self.progress,
            "failed_images": self.failed_images_names,
        }
        with open(self._progress_file, "wb") as file:
            pickle.dump(progress_data, file)
