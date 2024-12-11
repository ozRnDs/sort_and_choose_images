from unittest.mock import MagicMock, patch

import pytest
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from src.services.face_reid import (
    FaceRecognitionService,  # Replace with the actual import
)
from src.utils.model_pydantic import ImageMetadata


@pytest.fixture
def setup_service():
    """
    Fixture to create a FaceRecognitionService instance with an in-memory TinyDB for
    testing.
    """
    redis_mock = MagicMock()
    face_db_mock = MagicMock()

    service = FaceRecognitionService(
        base_url="http://example.com",
        redis_interface=redis_mock,
        face_db_service=face_db_mock,
        db_path="test_progress.json",
        progress_file="test_progress.pkl",
    )

    # Use in-memory storage for TinyDB
    service._db = TinyDB(storage=MemoryStorage)
    service._progress_table = service._db.table("progress")
    return service


@patch("os.path.exists")
@patch("builtins.open", new_callable=MagicMock)
def test_migrate_pickle_to_tinydb(mock_open, mock_exists, setup_service):
    """
    Test the migrate_pickle_to_tinydb method.
    """
    service = setup_service

    image1 = ImageMetadata(
        name="image1.jpg",
        full_client_path="image1.jpg",
        size=12345,
        type="jpg",
        camera="Camera1",
        location="Location1",
        creationDate="2023-01-01",
        classification="Portrait",
        ron_in_image=True,
    )
    image2 = ImageMetadata(
        name="image2.jpg",
        full_client_path="image2.jpg",
        size=67890,
        type="jpg",
        camera="Camera2",
        location="Location2",
        creationDate="2023-02-01",
        classification="Landscape",
        ron_in_image=False,
    )

    # Mock data for the pickle file
    mock_pickle_data = {
        "images": [image1.model_dump(), image2.model_dump()],
        "processed_images": ["image1.jpg"],
        "progress": 50,
        "failed_images": ["image3.jpg"],
    }

    # Mock file existence and pickle.load behavior
    mock_exists.return_value = True
    mock_open.return_value.__enter__.return_value.read = MagicMock()
    with patch("pickle.load", return_value=mock_pickle_data):
        service.migrate_pickle_to_tinydb()

    # Assertions to verify TinyDB updates
    progress_query = Query()
    progress_data = service._db.get(progress_query.id == "progress_metadata")
    assert progress_data is not None
    assert progress_data["processed_images"] == mock_pickle_data["processed_images"]
    assert progress_data["progress"] == mock_pickle_data["progress"]
    assert progress_data["failed_images"] == mock_pickle_data["failed_images"]


@patch("os.path.exists")
def test_migrate_pickle_to_tinydb_no_file(mock_exists, setup_service):
    """
    Test the migrate_pickle_to_tinydb method when no pickle file exists.
    """
    service = setup_service

    # Mock file existence
    mock_exists.return_value = False

    service.migrate_pickle_to_tinydb()

    # Verify no progress data was written
    assert service._progress_table.all() == []
