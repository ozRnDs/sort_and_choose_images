import asyncio
import os
import pickle
from enum import Enum

import httpx
from loguru import logger

from .redis_service import (
    RedisInterface,  # Assuming this is the file where RedisInterface is defined
)


class ProcessStatus(str, Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    CRASHED = "CRASHED"


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
        progress_file="face_recognition_progress.pkl",
    ):
        """
        Initializes the FaceRecognitionService.

        Args:
            redis_interface (RedisInterface): An instance of RedisInterface for data storage.
            progress_file (str): Path to the pickle file for progress persistence.
        """
        self.redis_interface = redis_interface
        self.status = ProcessStatus.IDLE
        self.progress = 0
        self.images = []
        self.processed_images = []
        self.failed_images = []
        self._progress_file = progress_file

        self._httpx_client = httpx.AsyncClient()
        self._base_url = base_url
        self._terminate = False
        self._processing_task = None

    async def load_progress(self):
        if os.path.exists(self._progress_file):
            try:
                with open(self._progress_file, "rb") as file:
                    progress_data = pickle.load(file)
                    self.images = progress_data.get("images", [])
                    self.processed_images = progress_data.get("processed_images", [])
                    self.progress = progress_data.get("progress", 0)
                    self.failed_images = progress_data.get("failed_images", [])
                    print("Progress loaded. Resuming from the last saved state.")
            except (pickle.PickleError, EOFError) as e:
                print(f"Failed to load progress file: {e}")

    def load_images(self, images: list) -> int:
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
        return {
            "status": self.status,
            "progress": self.progress,
            "images": len(self.images),
        }

    def stop(self):
        self._terminate = True

    async def start(self):
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._astart())
            await asyncio.sleep(2)

    async def _astart(self):
        """
        Starts processing the images using the PixID API, resuming if progress was
        previously saved.
        """
        if self.status == ProcessStatus.WORKING:
            raise RuntimeError("Service is already running.")

        self.status = ProcessStatus.WORKING
        try:
            remaining_images = [
                img
                for img in self.images
                if img not in self.processed_images and img not in self.failed_images
            ]
            index = 0
            while index < len(remaining_images):
                if self._terminate:
                    self.persist_progress()
                    break
                image = remaining_images[index]

                for i in range(1):
                    try:
                        face_vectors = await self.process_image(image)
                        break
                    except RuntimeError as err:
                        logger.warning(
                            f"Failed to process image: {image} Attempt {i+1}. {err}. Restarting the httpx client"
                        )
                        await self._httpx_client.aclose()
                        self._httpx_client = httpx.AsyncClient()
                else:  # If all retries fail, execute this block
                    logger.error(
                        f"Failed to process image {image} after {i+1} attempts. Skipping image"
                    )
                    self.failed_images.append(image)
                    self.persist_progress()
                    index += 1
                    continue

                for face in face_vectors["insights"]:
                    # Extract image details and embedding
                    bbox = face["bbox"]
                    embedding = face["embedding"]
                    self.redis_interface.add_embedding(image, bbox, embedding)

                self.processed_images.append(image)
                logger.info(
                    f"Processed {image} and extracted {len(face_vectors['insights'])} faces"
                )

                # Update progress
                processed_count = len(self.processed_images)
                self.progress = int(processed_count / len(self.images) * 100)
                self.persist_progress()

                # Recompute remaining_images to reflect changes dynamically
                remaining_images = [
                    img for img in self.images if img not in self.processed_images
                ]
                index += 1

            self.status = ProcessStatus.IDLE
        except Exception as e:
            self.status = ProcessStatus.CRASHED
            self.persist_progress()
            print(f"Error: {e}")
        finally:
            self._processing_task = None

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
            "images": self.images,
            "processed_images": self.processed_images,
            "progress": self.progress,
            "failed_images": self.failed_images,
        }
        with open(self._progress_file, "wb") as file:
            pickle.dump(progress_data, file)
