from fastapi import FastAPI
from fastapi.responses import FileResponse


class DbRouter:
    def __init__(self, image_db_path: str, groups_db_path: str):
        """
        Initialize the DbRouter with paths to the image and groups databases.
        """
        self._image_db = image_db_path
        self._groups_db = groups_db_path

    def create_entry_points(self, app: FastAPI):
        """
        Create the endpoints for downloading the image and groups databases.
        """

        @app.get(
            "/download/images_db",
            description="Download Images DB",
            response_class=FileResponse,
        )
        def get_images_db():
            """
            Endpoint to download the images database file.
            """
            return FileResponse(
                path=self._image_db,
                filename="images.db",
                media_type="application/octet-stream",
            )

        @app.get(
            "/download/groups_db",
            description="Download Groups DB",
            response_class=FileResponse,
        )
        def get_groups_db():
            """
            Endpoint to download the groups database file.
            """
            return FileResponse(
                path=self._groups_db,
                filename="groups.db",
                media_type="application/octet-stream",
            )


# Example usage:
# app = FastAPI()
# db_router = DbRouter(image_db_path="/path/to/images.db", groups_db_path="/path/to/groups.db")
# db_router.create_entry_points(app)
