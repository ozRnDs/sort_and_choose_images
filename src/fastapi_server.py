import asyncio
import io
import os
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException, Query, exceptions, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from PIL import Image

from src.routers import (
    classify_page_entrypoints,
    face_processing,
    groups_page_entrypoints,
    image_managment,
)

from .config import AppConfig
from .services.face_reid import FaceRecognitionService
from .services.faces_db_service import FaceDBService
from .services.groups_db import GROUPED_FILE
from .services.redis_service import RedisInterface
from .utils.model_pydantic import Face

app_config = AppConfig()
app_config = AppConfig()
app = FastAPI()

PICKLE_FILE = "/data/image_metadata.pkl"
FACE_DB = "/data/face_db.json"
STATIC_FOLDER_LOCATION = "src/static"
BASE_PATH = "/images"

redis_service = None
face_recognition_service = None


classify_router = classify_page_entrypoints.ClassifyRouter()
classify_router.create_entry_points(app)

groups_router = groups_page_entrypoints.GroupsRouter()
groups_router.create_entry_points(app)

image_router = image_managment.ImagesProcessing(
    images_base_path=BASE_PATH,
    pickle_file_path=PICKLE_FILE,
    group_file_path=GROUPED_FILE,
)
image_router.create_entry_points(app)
try:
    redis_service = RedisInterface(host=app_config.REDIS_URL)
    face_db_service = FaceDBService(db_path=FACE_DB)
    face_recognition_service = FaceRecognitionService(
        base_url=app_config.FACE_DETECTION_URL,
        redis_interface=redis_service,
        face_db_service=face_db_service,
        progress_file=f"{app_config.DATA_BASE_PATH}/face_recognition_progress.pkl",
        db_path=f"{app_config.DATA_BASE_PATH}/face_recognition_progress.json",
    )

    face_recognition_router = face_processing.FaceProcessingRouter(
        face_recognition_service=face_recognition_service
    )
    face_recognition_router.create_entry_points(app)

except Exception as err:
    logger.error(f"Failed to initialize redis or face recognition service: {err}")

# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_FOLDER_LOCATION), name="static")
app.mount("/images", StaticFiles(directory=BASE_PATH), name="images")


# Endpoint to serve the HTML file
@app.get("/", response_class=HTMLResponse, tags=["HTML"])
async def get_index(success: bool = False):
    if success:
        return HTMLResponse(
            content="<script>window.location.href='/get_groups_paginated';</script>",
            status_code=200,
        )
    # Read and serve the HTML file
    with open(os.path.join(STATIC_FOLDER_LOCATION, "groups.html")) as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/face/{face_id}/embedding", tags=["Face Recognition"])
def get_embedding_by_face_id(face_id: str) -> Face:
    if redis_service is None:
        raise exceptions.HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis DB is not available",
        )
    embedding = redis_service.get_embedding(face_id=face_id)
    faces = face_db_service.get_faces(query={"face_id": face_id})
    if faces:
        result_face = faces[0]
        result_face.embedding = embedding
        return result_face
    raise exceptions.HTTPException(
        status=status.HTTP_404_NOT_FOUND, detail="Face was not found"
    )


@app.get("/face/{face_id}/image", tags=["Face Management"])
async def get_image_for_face(face_id: str):
    """
    Get the cropped image for a face based on its bounding box (bbox).

    Args:
        face_id (str): The unique identifier for the face.

    Returns:
        Cropped image as a streaming response.
    """
    # Retrieve the face data
    faces = face_db_service.get_faces(query={"face_id": face_id})
    if not faces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Face was not found",
        )

    result_face = faces[0]
    image_path = result_face.image_full_path
    bbox = result_face.bbox  # bbox is expected to be a list of [x, y, width, height]

    # Load the image using Pillow
    try:
        image = Image.open(image_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image file not found: {image_path}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load image: {e}",
        )

    # Crop the face using bbox
    try:
        x1, y1, x2, y2 = bbox
        cropped_face = image.crop((x1, y1, x2, y2))  # Crop using x1, y1, x2, y2
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to crop image: {e}",
        )

    # Save the cropped face to an in-memory buffer
    buffer = io.BytesIO()
    cropped_face.save(buffer, format="JPEG")
    buffer.seek(0)

    # Return the cropped image as a streaming response
    return StreamingResponse(buffer, media_type="image/jpeg")


@app.get("/face/list/ron_in_image", tags=["Face Management"])
async def get_paginated_faces_with_ron_in_image(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
) -> List[Face]:
    """
    Paginated endpoint to get faces where 'ron_in_image' is True.

    Args:
        page (int): The page number to retrieve.
        page_size (int): The number of items per page.

    Returns:
        List[Face]: Paginated list of faces matching the rule.
    """
    # Retrieve all faces matching the rule
    faces = face_db_service.get_faces(query={"ron_in_image": True})

    # Handle no matches found
    if not faces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No faces found with 'ron_in_image' set to True",
        )

    # Implement pagination
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_faces = faces[start_index:end_index]

    # Handle case where page is out of range
    if not paginated_faces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No faces found for page {page}",
        )

    return paginated_faces


async def start_fastapi_server():
    # Import your FastAPI app (replace `app` with your FastAPI instance name)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    task_list = []
    if face_recognition_service:
        load_images_task = asyncio.create_task(face_recognition_service.load_progress())
        task_list.append(load_images_task)

    run_fast_api_server = asyncio.create_task(start_fastapi_server())
    task_list.append(run_fast_api_server)

    done, pending = await asyncio.wait(task_list)


# To run the FastAPI server, you can use:
# uvicorn backend:app --reload
if __name__ == "__main__":
    asyncio.run(main())
