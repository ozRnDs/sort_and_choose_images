# # ImageDBService Overview

# Manage image metadata in a TinyDB instance.

# ## Methods

# - **`__init__(db_path: str = "images_db.json")`**: Initialize with a database path.
# - **`add_image(image: ImageMetadata, flush: bool = False) -> int`**: Add or update an image document.
# - **`get_images(query: Optional[Dict[str, Any]] = None) -> List[ImageMetadata]`**: Retrieve all or filtered image documents.
# - **`remove_image(image_name: str) -> bool`**: Delete an image document by name.
# - **`count_images() -> int`**: Count total image documents.

# ## `ImageMetadata` Structure

# Represents the data structure for an image.

# - **`name: str`**: Name of the image.
# - **`full_client_path: str`**: Full path of the image.
# - **`size: int`**: Size of the image in bytes.
# - **`type: str`**: Type of the image (e.g., JPEG, PNG).
# - **`camera: Optional[str]`**: Camera used to capture the image, default is `"Unknown"`.
# - **`location: Optional[str]`**: Location where the image was captured, default is `"Unknown"`.
# - **`creationDate: Optional[str]`**: Creation date of the image, default is `"Unknown"`.
# - **`classification: str`**: Classification of the image, default is `"None"`.
# - **`ron_in_image: bool`**: Whether "Ron" is in the image, default is `False`.
# - **`face_recognition_status: Optional[ImageFaceRecognitionStatus]`**: Status of face recognition, default is `ImageFaceRecognitionStatus.PENDING`.


from functools import reduce  # For combining multiple conditions
from operator import and_  # Logical AND operation for combining conditions
from typing import Any, Dict, List, Optional

from loguru import logger
from tinydb import Query, TinyDB
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage

from ..utils.model_pydantic import ImageMetadata


class ImageDBService:
    """
    ImageDBService.

    This class provides an interface to interact with a TinyDB instance to store
    and retrieve image metadata documents.

    Key Features:
        1. Document Storage:
           - Add, update, delete, and retrieve image metadata documents.

        2. Querying:
           - Query the database for specific documents using flexible conditions.

        3. Persistence:
           - Stores data in a file-backed TinyDB instance for persistence.

    Attributes:
        db_path (str): Path to the TinyDB file.
        db (TinyDB): TinyDB instance.
    """

    def __init__(self, db_path: str = "images_db.json"):
        """
        Initializes the ImageDBService.

        Args:
            db_path (str): Path to the TinyDB file.
        """
        self.db_path = db_path
        self.db = TinyDB(self.db_path, storage=CachingMiddleware(JSONStorage))

    def add_image(self, image: ImageMetadata, flush: bool = False) -> int:
        """
        Adds or updates an image document in the database.

        Args:
            image (ImageMetadata): An ImageMetadata object containing all necessary image data.
            flush (bool): Whether to flush the database storage after the operation.

        Returns:
            int: The ID of the inserted or updated document.
        """
        response = self.db.upsert(image.model_dump(), Query().name == image.name)
        if flush:
            self.db.storage.flush()
        return response

    def get_images(self, query: Optional[Dict[str, Any]] = None) -> List[ImageMetadata]:
        """
        Retrieves image documents from the database.

        Args:
            query (dict, optional): Query conditions for filtering the results.
                                    If None, retrieves all documents.

        Returns:
            list: List of ImageMetadata objects matching the query.
        """
        if query:
            conditions = []
            for key, value in query.items():
                if isinstance(value, dict) and "$in" in value:
                    # Handle '$in' operator
                    conditions.append(Query()[key].one_of(value["$in"]))
                else:
                    # Default equality
                    conditions.append(Query()[key] == value)
            if len(conditions) == 1:
                results = self.db.search(conditions[0])
            else:
                results = self.db.search(reduce(and_, conditions))
            for cond in conditions[1:]:
                results = [doc for doc in results if cond(doc)]
            return [ImageMetadata(**doc) for doc in results]
        else:
            return [ImageMetadata(**doc) for doc in self.db.all()]

    def remove_image(self, image_name: str) -> bool:
        """
        Removes an image document from the database.

        Args:
            image_name (str): The name of the image to remove.

        Returns:
            bool: True if the document was removed, False otherwise.
        """
        return bool(self.db.remove(Query().name == image_name))

    def count_images(self) -> int:
        """
        Counts the total number of image documents in the database.

        Returns:
            int: The number of documents in the database.
        """
        return len(self.db)

    def save_db(self):
        logger.info("Saving DB")
        self.db.storage.flush()

    def __del__(self):
        self.save_db()
