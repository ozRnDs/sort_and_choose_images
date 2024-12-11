from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    PICKLE_FILE: str = "/data/image_metadata.pkl"
    GROUPED_FILE: str = "/data/grouped_metadata.pkl"
    STATIC_FOLDER_LOCATION: str = "src/static"
    IMAGE_BASE_PATH: str = "/images"
    DATA_BASE_PATH: str = "/data"
    FACE_DETECTION_URL: str = "http://localhost:5010"
    REDIS_URL: str = "redis-stack"
    REDIS_PORT: int = 6379
