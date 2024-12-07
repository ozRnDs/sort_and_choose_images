from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    PICKLE_FILE: str = "/data/image_metadata.pkl"
    GROUPED_FILE: str = "/data/grouped_metadata.pkl"
    STATIC_FOLDER_LOCATION: str = "src/static"
    IMAGE_BASE_PATH: str = "/images"
    DATA_BASE_PATH: str = "/data"
    BASE_URL: str = "http://localhost:8001/"
