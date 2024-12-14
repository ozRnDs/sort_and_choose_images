from typing import Any, Dict, List, Optional

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
            conditions = [Query()[key] == value for key, value in query.items()]
            results = self.db.search(conditions[0])
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
