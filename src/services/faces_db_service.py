from typing import Any, Dict, List

from tinydb import Query, TinyDB

from ..utils.model_pydantic import Face


class FaceDBService:
    """
    TinyDBService.

    This class provides an interface to interact with a TinyDB instance to store
    and retrieve face-related documents for later use.

    Key Features:
        1. Document Storage:
           - Add, update, delete, and retrieve face documents.

        2. Querying:
           - Query the database for specific documents using flexible conditions.

        3. Persistence:
           - Stores data in a file-backed TinyDB instance for persistence.

    Attributes:
        db_path (str): Path to the TinyDB file.
        db (TinyDB): TinyDB instance.
    """

    def __init__(self, db_path: str = "faces_db.json"):
        """
        Initializes the TinyDBService.

        Args:
            db_path (str): Path to the TinyDB file.
        """
        self.db_path = db_path
        self.db = TinyDB(self.db_path)
        self.faces_table = self.db.table("faces")

    def add_face(self, face: Face) -> int:
        """
        Adds a new face document to the database.

        Args:
            face (Face): A Face object containing all necessary face data.

        Returns:
            int: The ID of the inserted document.
        """
        db_face = face.model_copy(update={"embedding": []})
        return self.faces_table.insert(db_face.model_dump())

    def get_faces(self, query: Dict[str, Any] = None) -> List[Face]:
        """
        Retrieves face documents from the database.

        Args:
            query (dict): Query conditions for filtering the results.
                         If None, retrieves all documents.

        Returns:
            list: List of Face objects matching the query.
        """
        if query:
            conditions = [Query()[key] == value for key, value in query.items()]
            results = self.faces_table.search(conditions[0])
            for cond in conditions[1:]:
                results = [doc for doc in results if cond(doc)]
            return [Face(**doc) for doc in results]
        else:
            return [Face(**doc) for doc in self.faces_table.all()]

    def update_face(self, face_id: str, updates: Dict[str, Any]) -> bool:
        """
        Updates a face document in the database.

        Args:
            face_id (str): The face_id of the document to update.
            updates (dict): The fields to update with their new values.

        Returns:
            bool: True if the document was updated, False otherwise.
        """
        return self.faces_table.update(updates, Query().face_id == face_id)

    def remove_face(self, face_id: str) -> bool:
        """
        Removes a face document from the database.

        Args:
            face_id (str): The face_id of the document to remove.

        Returns:
            bool: True if the document was removed, False otherwise.
        """
        return bool(self.faces_table.remove(Query().face_id == face_id))

    def clear_all_faces(self):
        """
        Clears all face documents from the database.
        """
        self.faces_table.truncate()

    def count_faces(self) -> int:
        """
        Counts the total number of face documents in the database.

        Returns:
            int: The number of documents in the database.
        """
        return len(self.faces_table)


# Example Usage
if __name__ == "__main__":
    db_service = FaceDBService()

    # Add a face document
    face = Face(
        image_full_path="/images/image1.jpg",
        bbox=[100, 150, 50, 50],
        embedding=[0.1, 0.2, 0.3, 0.4],
        ron_in_image=True,
    )
    doc_id = db_service.add_face(face)
    print(f"Document ID: {doc_id}")

    # Retrieve all documents
    faces = db_service.get_faces()
    print(faces)

    # Update a document
    db_service.update_face(face.face_id, {"ron_in_image": False})

    # Count documents
    print(f"Total faces: {db_service.count_faces()}")

    # Remove a document
    db_service.remove_face(face.face_id)
    print(f"Total faces after removal: {db_service.count_faces()}")
