import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import ffmpeg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from loguru import logger
from tqdm import tqdm

from src.services.groups_db_service import GroupDBService
from src.services.images_db_service import ImageDBService
from src.utils.model_pydantic import GroupMetadata, VideoMetadata

# from src.services.video_db_service import VideoDBService  # Example import


class VideosProcessing:
    def __init__(
        self,
        videos_base_path: Path,
        group_db_service: GroupDBService,
        media_db_service: ImageDBService,
    ):
        """
        Args:
            videos_base_path (Path): Base path where videos are located.
            group_db_service: A service to handle group operations (similar to image grouping).
            video_db_service: A service to handle video metadata persistence.
        """
        self._videos_base_path = videos_base_path
        self._group_db_service = group_db_service
        self._media_db_service = media_db_service

    def create_entry_points(self, app: FastAPI):
        @app.get("/v2/load_videos", tags=["Admin"])
        async def load_videos(rewrite: bool = False):
            """
            Walk through the base path to find videos, extract metadata, and store them.

            If `rewrite` is True, update existing entries with new metadata fields.
            """
            # 1. Count total video files for progress tracking
            valid_extensions = (".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv")
            total_files = sum(
                sum(1 for file in files if file.lower().endswith(valid_extensions))
                for _, _, files in os.walk(self._videos_base_path)
            )

            # 2. Use tqdm for progress visualization
            with tqdm(
                total=total_files, desc="Processing Videos", unit="video"
            ) as pbar:
                # 3. Walk through the videos_base_path to find video files
                for root, _, files in os.walk(self._videos_base_path):
                    for file in files:
                        if file.lower().endswith(valid_extensions):
                            # Extract metadata (including thumbnail creation)
                            full_path = Path(root) / file

                            # Check if the video is already in the database
                            existing_videos = self._media_db_service.get_videos(
                                query={"full_client_path": str(full_path)}
                            )
                            video_metadata = None
                            if existing_videos:
                                if rewrite:
                                    video_metadata = await self.extract_video_metadata(
                                        file, root
                                    )
                                    # Overwrite certain fields if rewriting
                                    old_video = existing_videos[0]
                                    video_metadata.classification = (
                                        old_video.classification
                                    )
                                    video_metadata.ron_in_image = old_video.ron_in_image
                                    video_metadata.face_recognition_status = (
                                        old_video.face_recognition_status
                                    )
                                else:
                                    # Update progress for each file encountered
                                    pbar.update(1)
                                    # Skip if we are not rewriting
                                    continue

                            if video_metadata is None:
                                video_metadata = await self.extract_video_metadata(
                                    file, root
                                )
                            # 4. Determine a group name (e.g., based on creation date)
                            group_name = self._determine_group(video_metadata)
                            video_metadata.group_name = group_name

                            # 5. Add video to its group
                            self._group_db_service.add_video_to_group(
                                group_name, video_metadata.full_client_path
                            )

                            # 6. Add or update the video in the DB
                            self._media_db_service.add_video(video_metadata)

                            # Update the progress bar
                            pbar.update(1)

            # 7. Save the databases
            self._group_db_service.save_db()
            self._media_db_service.save_db()

            return JSONResponse(
                content={"message": "Videos processed successfully"},
                status_code=200,
            )

    async def extract_video_metadata(self, file_name: str, root: str) -> VideoMetadata:
        """
        Extract metadata from a single video file using ffmpeg-python, generate a
        thumbnail at the midpoint using ffmpeg, and return a VideoMetadata object.
        """
        full_path = Path(root) / file_name
        size = full_path.stat().st_size
        file_extension = full_path.suffix[1:].upper()  # e.g., "MP4", "MOV", "AVI"...

        # 1. Get the video duration (in seconds)
        duration_seconds = await self._get_video_duration(full_path)

        # 2. Determine the midpoint time
        midpoint_seconds = max(duration_seconds / 2, 0.0)

        # 3. Generate a thumbnail from that midpoint
        thumbnail_full_path = await self._generate_thumbnail(
            full_path, midpoint_seconds
        )

        # 4. Build creation date
        creation_date = "Unknown"
        camera = "Unknown"
        try:
            modified_timestamp = full_path.stat().st_mtime
            creation_date = datetime.fromtimestamp(modified_timestamp).strftime(
                "%Y:%m:%d %H:%M:%S"
            )
            wa_creation_date = self._get_whatsapp_video_date(file_name)
            if wa_creation_date:
                creation_date = wa_creation_date
                camera = "whatsapp"
        except Exception:
            pass

        # 6. Return a VideoMetadata object
        return VideoMetadata(
            name=file_name,
            thumbnail_full_path=str(thumbnail_full_path),
            full_client_path=str(full_path),
            size=size,
            duration_seconds=duration_seconds,
            type=file_extension,
            camera=camera,
            creationDate=creation_date,
        )

    async def _get_video_duration(self, video_path: Path) -> float:
        """
        Use ffmpeg.probe to get the duration (in seconds) of a video file.

        Returns 0.0 if the duration could not be determined.
        """
        try:
            metadata = await asyncio.to_thread(lambda: ffmpeg.probe(str(video_path)))
            return float(metadata["format"]["duration"])
        except (KeyError, ValueError, ffmpeg.Error):
            return 0.0

    async def _generate_thumbnail(self, video_path: Path, time_seconds: float) -> Path:
        """
        Generate a thumbnail at the specified time (in seconds).

        Save the thumbnail with the same filename + "_thumbnail" in the same directory.
        Returns the full path to the thumbnail file.
        """
        thumbnail_path = video_path.parent / f"{video_path.stem}_thumbnail.jpg"

        ffmpeg_command = ffmpeg.input(str(video_path), ss=time_seconds).output(
            str(thumbnail_path),
            vframes=1,
            format="image2",
            vcodec="mjpeg",
            qscale=2,
        )
        try:
            await asyncio.to_thread(
                ffmpeg_command.run, overwrite_output=True, quiet=True
            )
        except Exception as err:
            logger.exception(err)

        return thumbnail_path

    def _determine_group(self, video_metadata: VideoMetadata) -> str:
        """
        Determine a group name for the video (e.g., based on its creation date). Creates
        the group if it doesn't exist.

        Returns:
            str: The name of the group the video belongs to.
        """
        try:
            date_str = video_metadata.creationDate.split(" ")[0]
            date_obj = datetime.strptime(date_str, "%Y:%m:%d")
            group_name = date_obj.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            group_name = "Unknown"

        # If group does not exist, create it
        existing_group = self._group_db_service.get_group(group_name)
        if not existing_group:
            group_metadata = GroupMetadata(
                group_name=group_name,
                group_thumbnail_url=video_metadata.thumbnail_full_path,
                list_of_images=[],
            )
            self._group_db_service.add_group(
                group_metadata,
                flush=True,
            )
        return group_name

    def _get_whatsapp_video_date(self, video_name: str):
        whatsapp_pattern = r"VID-(\d{8})-WA\d+"
        match = re.match(whatsapp_pattern, video_name)
        if match:
            # Extract the date from the file name
            file_date = match.group(1)  # The "20201212" part

            # Convert the file date into a datetime object
            creation_date = datetime.strptime(file_date, "%Y%m%d").strftime(
                "%Y:%m:%d %H:%M:%S"
            )
            return creation_date
        return None
