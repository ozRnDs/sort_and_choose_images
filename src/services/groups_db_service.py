# # GroupDBService Overview

# Manage group-related data in a TinyDB instance.

# ## Methods

# - **`__init__(db_path: str = "groups_db.json")`**: Initialize with a database path.
# - **`add_group(group: GroupMetadata, flush: bool = False) -> int`**: Add or update a group.
# - **`get_groups(query: Optional[Dict[str, Any]] = None) -> List[GroupMetadata]`**: Retrieve all or filtered groups.
# - **`get_group(group_name: str) -> GroupMetadata`**: Fetch a group by name, raise `FileNotFoundError` if not found.
# - **`remove_group(group_name: str) -> bool`**: Delete a group by name.
# - **`count_groups() -> int`**: Count total groups.
# - **`add_image_to_group(group_name: str, image_path: str, flush: bool = False) -> bool`**: Add an image path to a group.
# - **`remove_image_from_group(group_name: str, image_path: str, flush: bool = False) -> bool`**: Remove an image path from a group.

# ## `GroupMetadata` Structure

# Represents the data structure for a group.

# - **`group_name: str`**: Name of the group.
# - **`group_thumbnail_url: str`**: URL of the group's thumbnail.
# - **`list_of_images: List[str]`**: List of image paths in the group.
# - **`selection: str`**: Group's status, can be:
#   - `"unprocessed"`
#   - `"interesting"`
#   - `"not interesting"`.


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

    def get_group(self, group_name: str) -> GroupMetadata:
        """
        Retrieves a single group document by name.

        Args:
            group_name (str): The name of the group to retrieve.

        Returns:
            GroupMetadata: The group document matching the name.

        Raises:
            FileNotFoundError: If the group does not exist in the database.
        """
        group_data = self.db.get(Query().group_name == group_name)
        if not group_data:
            logger.error(f"Group '{group_name}' not found.")
            raise FileNotFoundError(f"Group '{group_name}' not found.")
        return GroupMetadata(**group_data)

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
            if group.selection == "interesting":
                group.has_new_image = True
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

    def saw_group_images(self, group_name):
        group_data = self.db.get(Query().group_name == group_name)
        if group_data:
            group = GroupMetadata(**group_data)
            if group.selection == "interesting":
                group.has_new_image = False
            self.add_group(group)

    def save_db(self):
        self.db.storage.flush()

    def __del__(self):
        self.save_db()
