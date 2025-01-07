from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.routers.video_managment import GroupMetadata, VideoMetadata, VideosProcessing
from src.utils.model_pydantic import ImageFaceRecognitionStatus


@pytest.fixture(scope="session")
def group_db_service_fixture():
    return MagicMock()


@pytest.fixture(scope="session")
def video_db_service_fixture():
    return MagicMock()


@pytest.fixture(scope="session")
def video_service_fixture(group_db_service_fixture, video_db_service_fixture):
    return VideosProcessing(
        videos_base_path="/images",
        group_db_service=group_db_service_fixture,
        video_db_service=video_db_service_fixture,
    )


@pytest.mark.asyncio
async def test_extract_video_metadata(video_service_fixture):
    # Create a mock video location
    video_location = Path(
        "/workspaces/sort_and_choose_images/data/videos/20240215_111423.mp4"
    )

    # Use the async method correctly
    video_metadata = await video_service_fixture.extract_video_metadata(
        file_name=video_location.name,
        root=str(
            video_location.parent
        ),  # Pass the string representation of the directory
    )

    # Verify the result is an instance of VideoMetadata
    assert isinstance(video_metadata, VideoMetadata)
    # Additional assertions can be added here to verify specific fields in the metadata
    # Verify specific fields in the metadata
    assert video_metadata.name == video_location.name
    thumbnail_name = Path(video_metadata.thumbnail_full_path)
    assert thumbnail_name.exists()
    assert thumbnail_name.suffix.lower() == ".jpg"
    assert str(video_location.stem) in str(thumbnail_name)
    assert video_metadata.full_client_path == str(video_location)
    assert video_metadata.type == "MP4"
    assert video_metadata.camera == "Unknown"
    assert video_metadata.classification == "None"
    assert video_metadata.ron_in_image is False
    assert video_metadata.face_recognition_status == ImageFaceRecognitionStatus.PENDING
    assert video_metadata.group_name == "Unknown"


def test_determine_group_simple(video_service_fixture):
    # Mock the group database service
    video_service_fixture._group_db_service.get_group = MagicMock(return_value=None)
    video_service_fixture._group_db_service.add_group = MagicMock()

    # Test Case 1: Valid creationDate
    video_metadata_valid = VideoMetadata(
        name="video.mp4",
        thumbnail_full_path="/path/to/thumbnail.jpg",
        full_client_path="/path/to/video.mp4",
        size=12345,
        duration_seconds=60.0,
        type="MP4",
        camera="Unknown",
        creationDate="2025:01:07 22:26:51",
        classification="None",
        ron_in_image=False,
        face_recognition_status="pending",
        group_name="Unknown",
    )
    group_name = video_service_fixture._determine_group(video_metadata_valid)
    assert group_name == "2025-01-07"

    # Test Case 2: Invalid creationDate format
    video_metadata_invalid = VideoMetadata(
        name="video.mp4",
        thumbnail_full_path="/path/to/thumbnail.jpg",
        full_client_path="/path/to/video.mp4",
        size=12345,
        duration_seconds=60.0,
        type="MP4",
        camera="Unknown",
        creationDate="Invalid Date Format",
        classification="None",
        ron_in_image=False,
        face_recognition_status="pending",
        group_name="Unknown",
    )
    group_name = video_service_fixture._determine_group(video_metadata_invalid)
    assert group_name == "Unknown"

    # Test Case 3: Missing creationDate
    video_metadata_missing = VideoMetadata(
        name="video.mp4",
        thumbnail_full_path="/path/to/thumbnail.jpg",
        full_client_path="/path/to/video.mp4",
        size=12345,
        duration_seconds=60.0,
        type="MP4",
        camera="Unknown",
        creationDate=None,
        classification="None",
        ron_in_image=False,
        face_recognition_status="pending",
        group_name="Unknown",
    )
    group_name = video_service_fixture._determine_group(video_metadata_missing)
    assert group_name == "Unknown"

    # Ensure the group database service methods were called as expected
    video_service_fixture._group_db_service.get_group.assert_called()
    # video_service_fixture._group_db_service.add_group.assert_called_with(
    #     MagicMock(group_name=group_name), flush=True
    # )


def test_determine_group_different_group_states(video_service_fixture):
    video_service_fixture._group_db_service.get_group = MagicMock(return_value=None)
    video_service_fixture._group_db_service.add_group = MagicMock()

    # Test Case: Valid creationDate
    video_metadata_valid = VideoMetadata(
        name="video.mp4",
        thumbnail_full_path="/path/to/thumbnail.jpg",
        full_client_path="/path/to/video.mp4",
        size=12345,
        duration_seconds=60.0,
        type="MP4",
        camera="Unknown",
        creationDate="2025:01:07 22:26:51",
        classification="None",
        ron_in_image=False,
        face_recognition_status="pending",
        group_name="Unknown",
    )

    expected_new_group = GroupMetadata(
        group_name="2025-01-07",
        group_thumbnail_url=video_metadata_valid.thumbnail_full_path,
        list_of_images=[],
    )

    group_name = video_service_fixture._determine_group(video_metadata_valid)

    # Verify get_group is called
    video_service_fixture._group_db_service.get_group.assert_called_once_with(
        group_name
    )

    # Verify add_group is called because get_group returned None
    video_service_fixture._group_db_service.add_group.assert_called_once_with(
        expected_new_group,
        flush=True,
    )

    # Test Case: Existing group (get_group does not return None)
    video_service_fixture._group_db_service.get_group = MagicMock(
        return_value="ExistingGroup"
    )
    video_service_fixture._group_db_service.add_group.reset_mock()

    group_name_existing = video_service_fixture._determine_group(video_metadata_valid)

    # Verify get_group is called
    video_service_fixture._group_db_service.get_group.assert_called_with(
        group_name_existing
    )

    # Verify add_group is NOT called because get_group did not return None
    video_service_fixture._group_db_service.add_group.assert_not_called()
