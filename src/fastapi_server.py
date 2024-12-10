import asyncio
import os
import pickle
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import exifread
import uvicorn
from fastapi import FastAPI, HTTPException, Query, exceptions, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from .config import AppConfig
from .services.face_reid import FaceRecognitionService
from .services.faces_db_service import FaceDBService
from .services.groups_db import GROUPED_FILE, load_groups_from_file
from .services.redis_service import RedisInterface
from .utils.model_pydantic import Face, GroupMetadata, ImageMetadata

app_config = AppConfig()
app = FastAPI()

PICKLE_FILE = "/data/image_metadata.pkl"
FACE_DB = "/data/face_db.json"
STATIC_FOLDER_LOCATION = "src/static"
BASE_PATH = "/images"

redis_service = None
face_recognition_service = None
try:
    redis_service = RedisInterface()
    face_db_service = FaceDBService(db_path=FACE_DB)
    face_recognition_service = FaceRecognitionService(
        base_url=app_config.BASE_URL,
        redis_interface=redis_service,
        face_db_service=face_db_service,
        progress_file=f"{app_config.DATA_BASE_PATH}/face_recognition_progress.pkl",
    )
except Exception as err:
    logger.error(f"Failed to initialize redis or face recognition service: {err}")


# Define Pydantic model for paginated response
class PaginatedGroupsResponse(BaseModel):
    total_groups: int
    current_page: int
    page_size: int
    groups: List[GroupMetadata]


class ToggleGroupSelection(BaseModel):
    group_name: str
    selection: str


class UpdateClassificationRequest(BaseModel):
    group_name: str
    image_name: str
    classification: str


class UpdateRonInImageRequest(BaseModel):
    group_name: str
    image_name: str
    ron_in_image: bool


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


def extract_image_metadata(file: str, root: str) -> ImageMetadata:
    """
    Extracts metadata from a single image file.

    Args:
        file (str): The name of the image file.
        root (str): The directory path where the file is located.

    Returns:
        ImageMetadata: An object containing metadata of the image.
    """
    full_path = os.path.join(root, file)
    size = os.path.getsize(full_path)
    type_ = file.split(".")[-1].upper()
    creation_date = "Unknown"
    camera = "Unknown"

    # Extract EXIF metadata if available
    with open(full_path, "rb") as image_file:
        tags = exifread.process_file(
            image_file, stop_tag="DateTimeOriginal", details=False
        )
        if "EXIF DateTimeOriginal" in tags:
            creation_date = tags["EXIF DateTimeOriginal"].values
        if "Image Model" in tags:
            camera = tags["Image Model"].values

    # If creation_date is still unknown, use the file's last modified date
    if creation_date == "Unknown":
        modified_timestamp = os.path.getmtime(full_path)
        creation_date = datetime.fromtimestamp(modified_timestamp).strftime(
            "%Y:%m:%d %H:%M:%S"
        )

    # Check if the file name matches the WhatsApp image naming structure
    if camera == "Unknown":
        whatsapp_pattern = r"IMG-\d{8}-WA\d+"
        if re.match(whatsapp_pattern, file):
            camera = "whatsapp"

    return ImageMetadata(
        name=file,
        full_client_path=full_path.replace(BASE_PATH, "/images"),
        size=size,
        type=type_,
        camera=camera,
        creationDate=creation_date,
    )


def save_groups(groups: Dict[str, List[Dict]]):
    """
    Save the groups to the grouped metadata file after sorting by creation date.

    Args:
        groups (Dict[str, List[Dict]]): The dictionary of groups to save.
    """
    # Load existing grouped metadata if it exists
    if os.path.exists(GROUPED_FILE):
        with open(GROUPED_FILE, "rb") as f:
            grouped_metadata = pickle.load(f)
    else:
        grouped_metadata = []

    # Update or add new groups to grouped metadata
    existing_group_names = {group["group_name"]: group for group in grouped_metadata}
    for group_key, images in groups.items():
        # Sort images by creation date
        images.sort(key=lambda x: x.get("creationDate", "Unknown"))
        representative_image = images[0]  # Select the first image as representative
        group_thumbnail_url = representative_image.get("full_client_path")

        if group_key in existing_group_names:
            # Update existing group
            existing_group = existing_group_names[group_key]

            # Preserve existing group's selection field
            selection = existing_group.get("selection")

            # Update list_of_images, preserving classification and ron_in_image fields if they exist
            existing_images = {
                img.get("image_id"): img for img in existing_group["list_of_images"]
            }
            for image in images:
                image_id = image.get("image_id")
                if image_id in existing_images:
                    existing_image = existing_images[image_id]
                    image["classification"] = existing_image.get(
                        "classification", image.get("classification")
                    )
                    image["ron_in_image"] = existing_image.get(
                        "ron_in_image", image.get("ron_in_image")
                    )

            existing_group["list_of_images"] = images
            existing_group["selection"] = selection
        else:
            # Add new group
            group_metadata = GroupMetadata(
                group_name=group_key,
                group_thumbnail_url=group_thumbnail_url,
                list_of_images=images,
            )
            grouped_metadata.append(group_metadata.model_dump())

    # Save updated grouped metadata to a pickle file
    sort_and_save_groups(grouped_metadata)


def sort_and_save_groups(grouped_metadata: List[Dict]):
    """
    Sort the groups by date and save them to the grouped metadata file.

    Args:
        grouped_metadata (List[Dict]): The list of grouped metadata to save.
    """
    grouped_metadata.sort(key=lambda x: x.get("group_name", "Unknown"))
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)


# Update the load_images function to use the new extract_image_metadata function
@app.get("/load_images", tags=["Admin"])
async def load_images():
    images: List[ImageMetadata] = []
    for root, _, files in os.walk(BASE_PATH):
        for file in files:
            if file.lower().endswith(
                (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")
            ):
                image_metadata = extract_image_metadata(file, root)
                images.append(image_metadata)

    # Convert Pydantic objects to a list of dictionaries for pickling
    images_data = [image.model_dump() for image in images]
    # Save the metadata to a pickle file
    with open(PICKLE_FILE, "wb") as f:
        pickle.dump(images_data, f)

    print("Loaded images and saved metadata to pickle file.")

    # Group images by date (e.g., per day)
    groups = defaultdict(list)
    for image in images_data:
        # Assuming 'creationDate' is in format 'YYYY:MM:DD HH:MM:SS'
        try:
            date_str = image.get("creationDate", "").split(" ")[
                0
            ]  # Extract the date part only
            date_obj = datetime.strptime(date_str, "%Y:%m:%d")
            group_key = date_obj.strftime("%Y-%m-%d")  # Group by date
        except ValueError:
            group_key = "Unknown"
        groups[group_key].append(image)

    # Save groups using the new function
    save_groups(groups)

    return JSONResponse(
        content={"message": "Images loaded and grouped successfully"}, status_code=200
    )


# Endpoint to get grouped images for preview with pagination and filtering
@app.get(
    "/get_groups_paginated", response_model=PaginatedGroupsResponse, tags=["Groups"]
)
async def get_groups_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    filter_selections: List[str] = Query(["unprocessed"]),
    start_date: str = Query(None),
    end_date: str = Query(None),
):
    # Load grouped metadata from pickle file
    grouped_metadata = load_groups_from_file()

    # Filter groups by selection
    grouped_metadata = [
        group for group in grouped_metadata if group["selection"] in filter_selections
    ]

    # Filter groups by date range if specified
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            temp_group_metadata = []
            for group in grouped_metadata:
                if (
                    group["group_name"] != "Unknown"
                    and datetime.strptime(group["group_name"], "%Y-%m-%d")
                    >= start_date_obj
                ):
                    temp_group_metadata.append(group)
            grouped_metadata = temp_group_metadata
        except ValueError:
            return JSONResponse(
                content={"error": "Invalid start_date format. Use YYYY-MM-DD."},
                status_code=400,
            )

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            grouped_metadata = [
                group
                for group in grouped_metadata
                if datetime.strptime(group["group_name"], "%Y-%m-%d") <= end_date_obj
            ]
        except ValueError:
            return JSONResponse(
                content={"error": "Invalid end_date format. Use YYYY-MM-DD."},
                status_code=400,
            )

    # Implement pagination
    total_groups = len(grouped_metadata)
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_groups = grouped_metadata[start_index:end_index]

    # Prepare response
    response_content = PaginatedGroupsResponse(
        total_groups=total_groups,
        current_page=page,
        page_size=page_size,
        groups=[GroupMetadata(**group) for group in paginated_groups],
    )

    return response_content


# Endpoint to toggle group selection
@app.post("/toggle_group_selection", tags=["Groups"])
async def toggle_group_selection(group_select: ToggleGroupSelection):
    # Load grouped metadata from pickle file
    grouped_metadata = load_groups_from_file()

    # Update the selection for the specified group
    group_found = False
    for group in grouped_metadata:
        if group["group_name"] == group_select.group_name:
            group["selection"] = group_select.selection
            group_found = True
            break

    if not group_found:
        return JSONResponse(content={"error": "Group not found"}, status_code=404)

    # Save updated grouped metadata to a pickle file
    sort_and_save_groups(grouped_metadata)

    return JSONResponse(
        content={"message": "Group selection updated successfully"}, status_code=200
    )


# Endpoint to update the image classification
@app.post("/update_image_classification", tags=["Images"])
async def update_image_classification(request: UpdateClassificationRequest):
    grouped_metadata = load_groups_from_file()
    # Find the group and update the classification for the specific image
    group_found = False
    for group in grouped_metadata:
        if group["group_name"] == request.group_name:
            group_found = True
            for image in group["list_of_images"]:
                if image["name"] == request.image_name:
                    image["classification"] = request.classification
                    break
            break

    if not group_found:
        raise HTTPException(status_code=404, detail="Group not found")

    # Save updated metadata
    sort_and_save_groups(grouped_metadata)

    return {"message": "Image classification updated successfully"}


# Endpoint to update the 'Ron in the image' flag
@app.post("/update_ron_in_image", tags=["Images"])
async def update_ron_in_image(request: UpdateRonInImageRequest):
    # Load existing grouped metadata
    grouped_metadata = load_groups_from_file()

    # Find the group and update the 'Ron in image' flag for the specific image
    group_found = False
    for group in grouped_metadata:
        if group["group_name"] == request.group_name:
            group_found = True
            for image in group["list_of_images"]:
                if image["name"] == request.image_name:
                    image["ron_in_image"] = request.ron_in_image
                    break
            break

    if not group_found:
        raise HTTPException(status_code=404, detail="Group not found")

    # Save updated metadata
    sort_and_save_groups(grouped_metadata)

    return {"message": "Ron in image flag updated successfully"}


# Endpoint to get minimum and maximum dates in the groups
@app.get("/get_min_max_dates", tags=["Groups"])
async def get_min_max_dates():
    grouped_metadata = load_groups_from_file()

    dates = []
    for group in grouped_metadata:
        try:
            date_obj = datetime.strptime(group["group_name"], "%Y-%m-%d")
            dates.append(date_obj)
        except ValueError:
            continue

    if not dates:
        return JSONResponse(
            content={"error": "No valid dates found in groups"}, status_code=404
        )

    min_date = min(dates).strftime("%Y-%m-%d")
    max_date = max(dates).strftime("%Y-%m-%d")

    return JSONResponse(
        content={"min_date": min_date, "max_date": max_date}, status_code=200
    )


@app.post("/scripts/face_detection/load_images", tags=["Admin", "Face Recognition"])
async def face_detect():
    if face_recognition_service is None:
        raise exceptions.HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face Recognition Service is not available",
        )
    groups_metadata = load_groups_from_file()
    images = []
    for group in groups_metadata:
        group = GroupMetadata(**group)
        images += group.list_of_images

    loaded_images = face_recognition_service.load_images(images)
    await face_recognition_service.start()
    status_dict = face_recognition_service.get_status()
    # async with httpx.AsyncClient() as client:
    #     httpx_tasks = []
    #     done_tasks = []
    #     for image in images:
    #         if len(httpx_tasks)>10:
    #             done,pending = await asyncio.wait(httpx_tasks,return_when=asyncio.FIRST_COMPLETED)
    #             done_tasks += list(done)
    #             httpx_tasks=list(pending)
    #         with open(image,"rb") as file:
    #             httpx_tasks.append(asyncio.create_task(client.post(FACE_DETECTION_URL, files=("images",(os.path.basename(image),file,"image/jpeg")))))
    return {"number_of_loaded_images": loaded_images, "status": status_dict}


@app.get("/scripts/face_detection/status", tags=["Face Recognition"])
async def get_face_detection_status():
    if face_recognition_service is None:
        raise exceptions.HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face Recognition Service is not available",
        )
    status_dict = face_recognition_service.get_status()

    return status_dict


@app.post("/script/face_detection/restart", tags=["Face Recognition"])
async def restart_face_recognition():
    if face_recognition_service is None:
        raise exceptions.HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face Recognition Service is not available",
        )
    await face_recognition_service.start()
    return face_recognition_service.get_status()


@app.post("/script/face_detection/stop", tags=["Face Recognition"])
async def stop_face_recognition():
    if face_recognition_service is None:
        raise exceptions.HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face Recognition Service is not available",
        )
    face_recognition_service.stop()
    await asyncio.sleep(0.3)
    return face_recognition_service.get_status()


@app.get("/face/{face_id}/embedding", tags=["Face Recognition"])
async def get_embedding_by_face_id(face_id: str) -> Face:
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
