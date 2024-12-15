from datetime import datetime
from typing import List

from fastapi import FastAPI, Query, exceptions, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.services.groups_db import load_groups_from_pickle_file, sort_and_save_groups
from src.services.groups_db_service import GroupDBService
from src.services.images_db_service import ImageDBService
from src.utils.model_pydantic import (
    GroupMetadata_V1,
    ImageMetadata,
    PaginatedGroupsResponseV1,
    PaginatedGroupsResponseV2,
    ToggleGroupSelection,
)


class GroupsRouterV1:
    def __init__(self):
        pass

    def create_entry_points(self, app: FastAPI):
        # Endpoint to get grouped images for preview with pagination and filtering
        @app.get(
            "/get_groups_paginated",
            response_model=PaginatedGroupsResponseV1,
            tags=["Groups"],
        )
        async def get_groups_paginated(
            page: int = Query(1, ge=1),
            page_size: int = Query(10, ge=1),
            filter_selections: List[str] = Query(["unprocessed"]),
            start_date: str = Query(None),
            end_date: str = Query(None),
        ):
            # Load grouped metadata from pickle file
            grouped_metadata = load_groups_from_pickle_file()

            # Filter groups by selection
            grouped_metadata = [
                group
                for group in grouped_metadata
                if group["selection"] in filter_selections
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
                        if datetime.strptime(group["group_name"], "%Y-%m-%d")
                        <= end_date_obj
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
            response_content = PaginatedGroupsResponseV1(
                total_groups=total_groups,
                current_page=page,
                page_size=page_size,
                groups=[GroupMetadata_V1(**group) for group in paginated_groups],
            )

            return response_content

        # Endpoint to toggle group selection
        @app.post("/toggle_group_selection", tags=["Groups"])
        async def toggle_group_selection(group_select: ToggleGroupSelection):
            raise exceptions.HTTPException(
                status_code=status.HTTP_410_GONE, detail="This function is disabled"
            )
            # Load grouped metadata from pickle file
            grouped_metadata = load_groups_from_pickle_file()

            # Update the selection for the specified group
            group_found = False
            for group in grouped_metadata:
                if group["group_name"] == group_select.group_name:
                    group["selection"] = group_select.selection
                    group_found = True
                    break

            if not group_found:
                return JSONResponse(
                    content={"error": "Group not found"}, status_code=404
                )

            # Save updated grouped metadata to a pickle file
            sort_and_save_groups(grouped_metadata)

            return JSONResponse(
                content={"message": "Group selection updated successfully"},
                status_code=200,
            )

        @app.get("/get_min_max_dates", tags=["Groups"])
        async def get_min_max_dates():
            # Endpoint to get minimum and maximum dates in the groups
            grouped_metadata = load_groups_from_pickle_file()

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


class GroupsRouterV2(GroupsRouterV1):
    def __init__(
        self, group_db_service: GroupDBService, image_db_service: ImageDBService
    ):
        self._group_db_service = group_db_service
        self._image_db_service = image_db_service

    def create_entry_points(self, app: FastAPI):
        # Endpoint to get grouped images for preview with pagination and filtering
        @app.get(
            "/get_groups_paginated",
            response_model=PaginatedGroupsResponseV2,
            tags=["Groups"],
        )
        async def get_groups_paginated(
            page: int = Query(1, ge=1),
            page_size: int = Query(10, ge=1),
            filter_selections: List[str] = Query(["unprocessed"]),
            start_date: str = Query(None),
            end_date: str = Query(None),
        ):
            grouped_metadata = self._group_db_service.get_groups()

            # Filter groups by selection
            grouped_metadata = [
                group
                for group in grouped_metadata
                if group.selection in filter_selections
            ]

            # Filter groups by date range if specified
            if start_date:
                try:
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                    grouped_metadata = [
                        group
                        for group in grouped_metadata
                        if group.group_name != "Unknown"
                        and datetime.strptime(group.group_name, "%Y-%m-%d")
                        >= start_date_obj
                    ]
                except ValueError as err:
                    logger.exception(err)
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
                        if group.group_name != "Unknown"
                        and datetime.strptime(group.group_name, "%Y-%m-%d")
                        <= end_date_obj
                    ]
                except ValueError as err:
                    logger.exception(err)
                    return JSONResponse(
                        content={"error": "Invalid end_date format. Use YYYY-MM-DD."},
                        status_code=400,
                    )

            # Implement pagination
            total_groups = len(grouped_metadata)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_groups = grouped_metadata[start_index:end_index]

            response_content = PaginatedGroupsResponseV2(
                total_groups=total_groups,
                current_page=page,
                page_size=page_size,
                groups=paginated_groups,
            )

            return response_content

        # Endpoint to toggle group selection
        @app.post("/v2/toggle_group_selection", tags=["Groups"])
        async def toggle_group_selection(group_select: ToggleGroupSelection):
            group = self._group_db_service.get_group(group_select.group_name)

            if not group:
                return JSONResponse(
                    content={"error": "Group not found"}, status_code=404
                )

            group.selection = group_select.selection
            self._group_db_service.add_group(group, flush=True)

            return JSONResponse(
                content={"message": "Group selection updated successfully"},
                status_code=200,
            )

        # Endpoint to get minimum and maximum dates in the groups
        @app.get("/get_min_max_dates", tags=["Groups"])
        async def get_min_max_dates():
            grouped_metadata = self._group_db_service.get_groups()

            dates = []
            for group in grouped_metadata:
                try:
                    date_obj = datetime.strptime(group.group_name, "%Y-%m-%d")
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

        @app.get("/get_group_images", tags=["Groups"])
        async def get_group_images(group_name: str = Query(...)) -> List[ImageMetadata]:
            """
            Fetch the list of image details for a specific group by its name.
            """
            try:
                # Fetch the group metadata by name
                group = self._group_db_service.get_group(group_name)

                # If the group has no images, return an empty list
                if not group.list_of_images:
                    return JSONResponse(content={"images": []}, status_code=200)

                # Fetch the detailed metadata for all images in the group
                images_details = self._image_db_service.get_images(
                    query={"full_client_path": {"$in": group.list_of_images}}
                )

                # Return the list of image details
                return images_details

            except FileNotFoundError:
                return JSONResponse(
                    content={"error": f"Group '{group_name}' not found."},
                    status_code=404,
                )
            except Exception as err:
                logger.exception(
                    f"Error fetching images for group '{group_name}': {err}"
                )
                return JSONResponse(
                    content={"error": "An unexpected error occurred."}, status_code=500
                )

        @app.get("/check_group_has_classification", tags=["Groups"])
        async def check_group_has_classification(group_name: str = Query(...)):
            """
            Check if a group has any classified images.
            """
            try:
                # Fetch the group metadata by name
                group = self._group_db_service.get_group(group_name)

                # If the group has no images, return False
                if not group.list_of_images:
                    return JSONResponse(
                        content={"has_classification": False}, status_code=200
                    )

                # Fetch detailed metadata for all images in the group
                images = self._image_db_service.get_images(
                    query={"full_client_path": {"$in": group.list_of_images}}
                )

                # Check if any image has a classification other than "None"
                has_classification = any(
                    image.classification != "None" for image in images
                ) or any(image.ron_in_image for image in images)

                # Return the result
                return JSONResponse(
                    content={"has_classification": has_classification}, status_code=200
                )

            except FileNotFoundError:
                return JSONResponse(
                    content={"error": f"Group '{group_name}' not found."},
                    status_code=404,
                )
            except Exception as err:
                logger.exception(
                    f"Error checking classification for group '{group_name}': {err}"
                )
                return JSONResponse(
                    content={"error": "An unexpected error occurred."}, status_code=500
                )
