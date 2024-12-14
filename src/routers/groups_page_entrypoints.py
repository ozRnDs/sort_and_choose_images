from datetime import datetime
from typing import List

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from src.services.groups_db import load_groups_from_pickle_file, sort_and_save_groups
from src.utils.model_pydantic import (
    GroupMetadata,
    PaginatedGroupsResponse,
    ToggleGroupSelection,
)


class GroupsRouter:
    def __init__(self):
        pass

    def create_entry_points(self, app: FastAPI):
        # Endpoint to get grouped images for preview with pagination and filtering
        @app.get(
            "/get_groups_paginated",
            response_model=PaginatedGroupsResponse,
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
