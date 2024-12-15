import asyncio
import os
import shutil
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.routers import (
    classify_page_entrypoints,
    db_router,
    face_managment,
    face_processing,
    groups_page_entrypoints,
    image_managment,
)

from .config import AppConfig
from .services.face_reid import FaceRecognitionService
from .services.faces_db_service import FaceDBService
from .services.groups_db import GROUPED_FILE
from .services.groups_db_service import GroupDBService
from .services.images_db_service import ImageDBService
from .services.redis_service import RedisInterface

app_config = AppConfig()
app = FastAPI()

PICKLE_FILE = "/data/image_metadata.pkl"  # OLD and deprecated

STATIC_FOLDER_LOCATION = "src/static"

BASE_PATH = "/images"

FACE_DB = "/data/face_db.json"
GROUP_DB = "/data/group_db.json"
IMAGE_DB = "/data/image_db.json"

redis_service = None
face_recognition_service = None

group_db_service = GroupDBService(db_path=GROUP_DB)
image_db_service = ImageDBService(db_path=IMAGE_DB)
face_db_service = FaceDBService(db_path=FACE_DB)

db_router = db_router.DbRouter(
    image_db_path=IMAGE_DB,
    group_db_path=GROUP_DB,
    image_db_path_pickle=PICKLE_FILE,
    groups_db_path_pickle=GROUPED_FILE,
    image_db_service=image_db_service,
    group_db_service=group_db_service,
)
db_router.create_entry_points(app)

classify_router = classify_page_entrypoints.ClassifyRouterV2(
    group_db_service=group_db_service,
    image_db_service=image_db_service,
    face_db_service=face_db_service,
)

classify_router.create_entry_points(app)

groups_router = groups_page_entrypoints.GroupsRouterV2(
    group_db_service=group_db_service, image_db_service=image_db_service
)
groups_router.create_entry_points(app)

image_router = image_managment.ImagesProcessingV2(
    images_base_path=BASE_PATH,
    group_db_service=group_db_service,
    image_db_service=image_db_service,
)
image_router.create_entry_points(app)
try:
    redis_service = RedisInterface(host=app_config.REDIS_URL)
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

    face_managment_router = face_managment.FaceManagmentRouter(
        face_recognition_service=face_recognition_service,
        redis_service=redis_service,
        face_db_service=face_db_service,
    )
    face_managment_router.create_entry_points(app)

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


async def start_fastapi_server():
    # Import your FastAPI app (replace `app` with your FastAPI instance name)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def perform_migration():
    # Check if both files exist, exit if either is missing
    group_db = Path(GROUP_DB)
    pickle_file = Path(IMAGE_DB)
    if not (pickle_file.exists() and group_db.exists()):
        return
    backup_path = Path("/data") / "backup-0.11.0"
    if backup_path.exists():
        return
    logger.info("Updating software databases...")

    backup_group_path = backup_path / "group_db.json"
    backup_images_path = backup_path / "image_db.json"

    logger.info("Backing up old db...")
    # Create backup_path as a folder
    backup_path.mkdir(parents=True, exist_ok=True)

    # Copy PICKLE_FILE to backup_images_path
    shutil.copy(pickle_file, backup_images_path)

    # Copy GROUP_DB to backup_group_path
    shutil.copy(group_db, backup_group_path)
    logger.info("Starting migration...")
    # Perform database migration
    await db_router.update_group_field_in_images()

    logger.info("Finished Migration")


async def main():
    await perform_migration()

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
