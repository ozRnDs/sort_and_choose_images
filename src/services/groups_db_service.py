from typing import Any, Dict, List, Optional

from loguru import logger
from tinydb import Query, TinyDB
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage

from ..utils.model_pydantic import GroupMetadata


class GroupDBService:
    """
    GroupDBService.

    This class provides an interface to interact with a TinyDB instance to store
    and retrieve group-related documents for later use.

    Key Features:
        1. Document Storage:
           - Add, update, delete, and retrieve group documents.

        2. Querying:
           - Query the database for specific documents using flexible conditions.

        3. Persistence:
           - Stores data in a file-backed TinyDB instance for persistence.

    Attributes:
        db_path (str): Path to the TinyDB file.
        db (TinyDB): TinyDB instance.
    """

    def __init__(self, db_path: str = "groups_db.json"):
        """
        Initializes the GroupDBService.

        Args:
            db_path (str): Path to the TinyDB file.
        """
        self.db_path = db_path
        self.db = TinyDB(self.db_path, storage=CachingMiddleware(JSONStorage))

    def add_group(self, group: GroupMetadata, flush: bool = False) -> int:
        """
        Adds or updates a group document in the database.

        Args:
            group (GroupMetadata): A GroupMetadata object containing all necessary group data.
            flush (bool): Whether to flush the database storage after the operation.

        Returns:
            int: The ID of the inserted or updated document.
        """
        response = self.db.upsert(
            group.model_dump(), Query().group_name == group.group_name
        )
        if flush:
            self.db.storage.flush()
        return response

    def get_groups(self, query: Optional[Dict[str, Any]] = None) -> List[GroupMetadata]:
        """
        Retrieves group documents from the database.

        Args:
            query (dict, optional): Query conditions for filtering the results.
                                    If None, retrieves all documents.

        Returns:
            list: List of GroupMetadata objects matching the query.
        """
        if query:
            conditions = [Query()[key] == value for key, value in query.items()]
            results = self.db.search(conditions[0])
            for cond in conditions[1:]:
                results = [doc for doc in results if cond(doc)]
            return [GroupMetadata(**doc) for doc in results]
        else:
            return [GroupMetadata(**doc) for doc in self.db.all()]

    def remove_group(self, group_name: str) -> bool:
        """
        Removes a group document from the database.

        Args:
            group_name (str): The name of the group to remove.

        Returns:
            bool: True if the document was removed, False otherwise.
        """
        return bool(self.db.remove(Query().group_name == group_name))

    def count_groups(self) -> int:
        """
        Counts the total number of group documents in the database.

        Returns:
            int: The number of documents in the database.
        """
        return len(self.db)

    def add_image_to_group(
        self, group_name: str, image_path: str, flush: bool = False
    ) -> bool:
        """
        Adds an image path to a group's list of images.

        Args:
            group_name (str): The name of the group to update.
            image_path (str): The full path of the image to add.
            flush (bool): Whether to flush the database storage after the operation.

        Returns:
            bool: True if the image path was successfully added, False otherwise.
        """
        group_data = self.db.get(Query().group_name == group_name)
        if group_data:
            group = GroupMetadata(**group_data)
            if image_path in group.list_of_images:
                logger.info(
                    f"Image path '{image_path}' already exists in group '{group_name}'."
                )
                return False
            group.list_of_images.append(image_path)
            self.add_group(group, flush=flush)
            return True
        return False

    def remove_image_from_group(
        self, group_name: str, image_path: str, flush: bool = False
    ) -> bool:
        """
        Removes an image path from a group's list of images.

        Args:
            group_name (str): The name of the group to update.
            image_path (str): The full path of the image to remove.
            flush (bool): Whether to flush the database storage after the operation.

        Returns:
            bool: True if the image path was successfully removed, False otherwise.
        """
        group_data = self.db.get(Query().group_name == group_name)
        if group_data:
            group = GroupMetadata(**group_data)
            group.list_of_images = [
                img for img in group.list_of_images if img != image_path
            ]
            self.add_group(group, flush=flush)
            return True
        return False
