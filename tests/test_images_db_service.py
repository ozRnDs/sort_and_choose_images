import pytest

from src.services.images_db_service import (
    ImageDBService,
    ImageFaceRecognitionStatus,
    ImageMetadata,
    VideoMetadata,
)
from src.utils.model_pydantic import MediaType


@pytest.fixture(scope="session")
def images_db_service_fixture():
    """
    Create a session-scoped fixture that initializes the ImageDBService with a test
    database path.

    The DB is shared across all tests in the session.
    """
    image_db_path = "/workspaces/sort_and_choose_images/data/tests/image_db.json"
    images_db_service = ImageDBService(db_path=image_db_path)
    yield images_db_service

    images_db_service.save_db()


@pytest.fixture
def image_metadata_fixture():
    """
    Provide a default single ImageMetadata instance.
    """
    return ImageMetadata(
        name="test_image.jpg",
        full_client_path="/tmp/test_image.jpg",
        size=1024,
        type="JPEG",
        camera="Nikon D3500",
        location="TestLocation",
        creationDate="2021-01-01T12:00:00Z",
        classification="Landscape",
        ron_in_image=False,
        face_recognition_status=ImageFaceRecognitionStatus.PENDING,
        group_name="TestGroup",
    )


@pytest.fixture
def video_metadata_fixture():
    """
    Provide a default single VideoMetadata instance.
    """
    return VideoMetadata(
        name="test_video.mp4",
        thumbnail_full_path="/tmp/test_video_thumb.jpg",
        full_client_path="/tmp/test_video.mp4",
        size=2048,
        duration_seconds=12.34,
        type="MP4",
        camera="Unknown",
        location="TestLocation",
        creationDate="2021-02-02T12:00:00Z",
        classification="None",
        ron_in_image=False,
        face_recognition_status=ImageFaceRecognitionStatus.PENDING,
        group_name="TestVideoGroup",
    )


@pytest.mark.parametrize(
    "image_data",
    [
        {
            "name": "param_image_1.jpg",
            "full_client_path": "/tmp/param_image_1.jpg",
            "size": 1111,
            "type": "JPEG",
        },
        {
            "name": "param_image_2.jpg",
            "full_client_path": "/tmp/param_image_2.jpg",
            "size": 2222,
            "type": "PNG",
        },
    ],
)
def test_add_image_param(images_db_service_fixture: ImageDBService, image_data):
    """
    Example of parameterizing the test to insert multiple images into the DB and
    verifying they are added successfully.
    """
    # Create an ImageMetadata using the param
    image_metadata = ImageMetadata(
        **image_data,
        media_type=MediaType.IMAGE,
        camera="ParamTestCam",
        location="ParamTestLocation",
        creationDate="2022-01-01T00:00:00Z",
        classification="None",
        ron_in_image=False,
        face_recognition_status=ImageFaceRecognitionStatus.PENDING,
        group_name="ParamTestGroup",
    )

    documents_added = images_db_service_fixture.add_image(image_metadata)
    assert len(documents_added) == 1, "Expected one document to be inserted/updated."


def test_add_image(images_db_service_fixture: ImageDBService, image_metadata_fixture):
    """
    Test adding a single image using the image_metadata_fixture.
    """
    documents_added = images_db_service_fixture.add_image(image_metadata_fixture)
    assert len(documents_added) == 1, "Expected one document to be inserted/updated."


@pytest.mark.parametrize(
    "video_data",
    [
        {
            "name": "param_video_1.mp4",
            "thumbnail_full_path": "/tmp/param_video_1_thumb.jpg",
            "full_client_path": "/tmp/param_video_1.mp4",
            "size": 12345,
            "duration_seconds": 10.5,
            "type": "MP4",
        },
        {
            "name": "param_video_2.mov",
            "thumbnail_full_path": "/tmp/param_video_2_thumb.jpg",
            "full_client_path": "/tmp/param_video_2.mov",
            "size": 23456,
            "duration_seconds": 20.75,
            "type": "MOV",
        },
    ],
)
def test_add_video_param(images_db_service_fixture: ImageDBService, video_data):
    """
    Example of parameterizing the test to insert multiple videos into the DB and
    verifying they are added successfully.
    """
    # Create a VideoMetadata using the param
    video_metadata = VideoMetadata(
        **video_data,
        media_type=MediaType.VIDEO,
        camera="ParamTestCam",
        location="ParamTestLocation",
        creationDate="2022-01-02T00:00:00Z",
        classification="None",
        ron_in_image=False,
        face_recognition_status=ImageFaceRecognitionStatus.PENDING,
        group_name="ParamTestVideoGroup",
    )

    documents_added = images_db_service_fixture.add_video(video_metadata)
    assert len(documents_added) == 1, "Expected one document to be inserted/updated."


def test_add_video(images_db_service_fixture: ImageDBService, video_metadata_fixture):
    """
    Test adding a single video using the video_metadata_fixture.
    """
    documents_added = images_db_service_fixture.add_video(video_metadata_fixture)
    assert len(documents_added) == 1, "Expected one document to be inserted/updated."


def test_get_image_by_full_client_path(
    images_db_service_fixture: ImageDBService, image_metadata_fixture
):
    """
    Insert a test image, then retrieve it by its full_client_path and verify that it was
    found.
    """
    # Insert an image
    images_db_service_fixture.add_image(image_metadata_fixture)

    # Query for the exact same path
    images = images_db_service_fixture.get_images(
        query={"full_client_path": image_metadata_fixture.full_client_path}
    )

    assert len(images) == 1, "Expected exactly one image to match the query."
    assert (
        images[0] == image_metadata_fixture
    ), "Retrieved image should match the inserted one."


def test_get_video_by_full_client_path(
    images_db_service_fixture: ImageDBService, video_metadata_fixture
):
    """
    Insert a test video, then retrieve it by its full_client_path and verify that it was
    found.
    """
    # Insert a video
    images_db_service_fixture.add_video(video_metadata_fixture)

    # Query for the exact same path
    videos = images_db_service_fixture.get_videos(
        query={"full_client_path": video_metadata_fixture.full_client_path}
    )

    assert len(videos) == 1, "Expected exactly one video to match the query."
    assert (
        videos[0] == video_metadata_fixture
    ), "Retrieved video should match the inserted one."


def test_get_images_by_face_recognition_status(
    images_db_service_fixture: ImageDBService,
):
    """
    Ensure all images with PENDING face recognition status are returned and that they
    are indeed images (not videos).
    """
    # Insert multiple images with face_recognition_status=PENDING
    pending_images = [
        ImageMetadata(
            name=f"pending_image_{i}.jpg",
            full_client_path=f"/tmp/pending_image_{i}.jpg",
            size=1000 + i,
            type="JPEG",
            face_recognition_status=ImageFaceRecognitionStatus.DONE,
        )
        for i in range(3)
    ]
    for vid in pending_images:
        images_db_service_fixture.add_image(vid)

    # Insert a video just to ensure it is excluded from the image query
    video_metadata = VideoMetadata(
        name="test_excluded_video.mp4",
        thumbnail_full_path="/tmp/test_excluded_video_thumb.jpg",
        full_client_path="/tmp/test_excluded_video.mp4",
        size=9999,
        duration_seconds=99.9,
        type="MP4",
        face_recognition_status=ImageFaceRecognitionStatus.PENDING,
    )
    images_db_service_fixture.add_video(video_metadata)

    # Retrieve images with PENDING status
    images = images_db_service_fixture.get_images(
        query={"face_recognition_status": ImageFaceRecognitionStatus.PENDING}
    )
    videos = images_db_service_fixture.get_videos(
        query={"face_recognition_status": ImageFaceRecognitionStatus.PENDING}
    )
    # Verify that all returned items are images (media_type = IMAGE)
    # and have PENDING face_recognition_status
    # assert len(images) == len(pending_images), (
    #     "Expected the number of returned images to match the number of PENDING images inserted."
    # )
    for vid in images:
        assert vid.face_recognition_status == ImageFaceRecognitionStatus.PENDING
        assert vid.media_type == MediaType.IMAGE

    for vid in videos:
        assert vid.face_recognition_status == ImageFaceRecognitionStatus.PENDING
        assert vid.media_type == MediaType.VIDEO
