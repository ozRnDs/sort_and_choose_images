from fastapi import FastAPI, exceptions

from src.services.groups_db import load_groups_from_file, sort_and_save_groups
from src.utils.model_pydantic import (
    UpdateClassificationRequest,
    UpdateRonInImageRequest,
)


class ClassifyRouter:
    def __init__(self):
        pass

    def create_entry_points(self, app: FastAPI):
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
                raise exceptions.HTTPException(
                    status_code=404, detail="Group not found"
                )

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
                raise exceptions.HTTPException(
                    status_code=404, detail="Group not found"
                )

            # Save updated metadata
            sort_and_save_groups(grouped_metadata)

            return {"message": "Ron in image flag updated successfully"}
