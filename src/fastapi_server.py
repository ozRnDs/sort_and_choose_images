import os
import pickle
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import exifread
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .models.images import ImageMetadata

app = FastAPI()

PICKLE_FILE = "/data/image_metadata.pkl"
GROUPED_FILE = "/data/grouped_metadata.pkl"
STATIC_FOLDER_LOCATION = "src/static"
BASE_PATH = "/images"


# Define Pydantic model for grouped information
class GroupMetadata(BaseModel):
    group_name: str
    group_thumbnail_url: str
    list_of_images: List[Dict]
    selection: str = (
        "unprocessed"  # Can be "unprocessed", "interesting", or "not interesting"
    )

    @property
    def image_count(self):
        return len(self.list_of_images)


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
@app.get("/", response_class=HTMLResponse)
async def get_index(success: bool = False):
    if success:
        return HTMLResponse(
            content="<script>window.location.href='/get_groups_paginated';</script>",
            status_code=200,
        )
    # Read and serve the HTML file
    with open(os.path.join(STATIC_FOLDER_LOCATION, "groups.html")) as f:
        return HTMLResponse(content=f.read(), status_code=200)


# Endpoint to load images from the base path
@app.get("/load_images")
async def load_images():
    images = []
    for root, _, files in os.walk(BASE_PATH):
        for file in files:
            if file.lower().endswith(
                (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")
            ):
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

                image_metadata = ImageMetadata(
                    name=file,
                    full_client_path=full_path.replace(BASE_PATH, "/images"),
                    size=size,
                    type=type_,
                    camera=camera,
                    creationDate=creation_date,
                )
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

    # Load existing grouped metadata if it exists
    if os.path.exists(GROUPED_FILE):
        with open(GROUPED_FILE, "rb") as f:
            grouped_metadata = pickle.load(f)
    else:
        grouped_metadata = []

    # Update or add new groups to grouped metadata
    existing_group_names = {group["group_name"]: group for group in grouped_metadata}
    for group_key, images in groups.items():
        representative_image = images[0]  # Select the first image as representative
        group_thumbnail_url = representative_image.get("full_client_path")

        if group_key in existing_group_names:
            # Update existing group
            existing_group = existing_group_names[group_key]
            existing_group["list_of_images"] = images
        else:
            # Add new group
            group_metadata = GroupMetadata(
                group_name=group_key,
                group_thumbnail_url=group_thumbnail_url,
                list_of_images=images,
            )
            grouped_metadata.append(group_metadata.model_dump())

    # Save updated grouped metadata to a pickle file
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)

    return JSONResponse(
        content={"message": "Images loaded and grouped successfully"}, status_code=200
    )


# Endpoint to get grouped images for preview with pagination and filtering
@app.get("/get_groups_paginated", response_model=PaginatedGroupsResponse)
async def get_groups_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    filter_selections: List[str] = Query(["unprocessed"]),
    start_date: str = Query(None),
    end_date: str = Query(None),
):
    # Load grouped metadata from pickle file
    if not os.path.exists(GROUPED_FILE):
        return JSONResponse(
            content={"error": "No grouped metadata found"}, status_code=404
        )

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

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
@app.post("/toggle_group_selection")
async def toggle_group_selection(group_select: ToggleGroupSelection):
    # Load grouped metadata from pickle file
    if not os.path.exists(GROUPED_FILE):
        return JSONResponse(
            content={"error": "No grouped metadata found"}, status_code=404
        )

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

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
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)

    return JSONResponse(
        content={"message": "Group selection updated successfully"}, status_code=200
    )


# Endpoint to update the image classification
@app.post("/update_image_classification")
async def update_image_classification(request: UpdateClassificationRequest):
    # Load existing grouped metadata
    if not os.path.exists(GROUPED_FILE):
        raise HTTPException(status_code=404, detail="Grouped metadata not found")

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

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
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)

    return {"message": "Image classification updated successfully"}


# Endpoint to update the 'Ron in the image' flag
@app.post("/update_ron_in_image")
async def update_ron_in_image(request: UpdateRonInImageRequest):
    # Load existing grouped metadata
    if not os.path.exists(GROUPED_FILE):
        raise HTTPException(status_code=404, detail="Grouped metadata not found")

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

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
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)

    return {"message": "Ron in image flag updated successfully"}


# Endpoint to get minimum and maximum dates in the groups
@app.get("/get_min_max_dates")
async def get_min_max_dates():
    if not os.path.exists(GROUPED_FILE):
        return JSONResponse(
            content={"error": "No grouped metadata found"}, status_code=404
        )

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

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


# To run the FastAPI server, you can use:
# uvicorn backend:app --reload
