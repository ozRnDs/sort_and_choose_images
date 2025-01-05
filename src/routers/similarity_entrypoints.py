from typing import List

from fastapi import FastAPI, Query
from pydantic import BaseModel
from tqdm import tqdm

from src.services.faces_db_service import FaceDBService
from src.services.groups_db_service import GroupDBService
from src.services.redis_service import RedisInterface
from src.utils.model_pydantic import GroupMetadata, PaginatedGroupsResponseV2


class SimilarityStatus(BaseModel):
    number_of_recognized_vectors: int
    number_of_groups: int
    number_of_processes_groups: int = 0
    number_of_groups_with_ron: int = 0
    number_of_new_groups_with_ron: int = 0
    running: bool = True


class SimilarityRouter:
    def __init__(
        self,
        redis_service: RedisInterface,
        face_db_service: FaceDBService,
        group_db_service: GroupDBService,
    ):
        self._redis_service = redis_service
        self._face_db_service = face_db_service
        self._group_db_service = group_db_service
        self._similarity_calculation_status: SimilarityStatus = None

    def create_entry_points(self, app: FastAPI):
        @app.get(
            "/similarity/ron/groups",
            tags=["Similarities"],
            response_model=PaginatedGroupsResponseV2,
        )
        def get_groups_with_images_similar_to_ron(
            threshold: float = 0.8,
            page: int = Query(1, ge=1),
            page_size: int = Query(10, ge=1),
        ) -> PaginatedGroupsResponseV2:
            return_groups = self._group_db_service.get_groups({"ron_in_group": True})

            # Implement pagination
            total_groups = len(return_groups)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_groups = return_groups[start_index:end_index]

            response_content = PaginatedGroupsResponseV2(
                total_groups=total_groups,
                current_page=page,
                page_size=page_size,
                groups=paginated_groups,
            )

            return response_content

    def calculate_groups_with_target(self, threshold=0.7) -> List[GroupMetadata]:
        ron_faces_ids = [
            face.face_id
            for face in self._face_db_service.get_faces({"ron_in_face": True})
        ]
        return_groups = []
        # Get all groups
        list_of_groups = self._group_db_service.get_groups()
        self._similarity_calculation_status = SimilarityStatus(
            number_of_groups=len(list_of_groups),
            number_of_recognized_vectors=len(ron_faces_ids),
        )
        # For each group, get images
        for group in tqdm(list_of_groups):
            self._similarity_calculation_status.number_of_processes_groups += 1

            if group.ron_in_group:
                self._similarity_calculation_status.number_of_groups_with_ron = +1
                continue
            list_of_faces = self._face_db_service.get_faces(
                {"image_full_path": {"$in": group.list_of_images}}
            )
            for face in tqdm(list_of_faces):
                face_search_embedding = self._redis_service.get_embedding(
                    face_id=face.face_id
                )
                if not face_search_embedding:
                    continue
                results = self._redis_service.vector_search(
                    face_search_embedding, k=100
                )
                faces_ids = [
                    result["face_id"]
                    for result in results
                    if result["score"] < threshold
                ]
                if bool(set(ron_faces_ids) & set(faces_ids)):
                    group.ron_in_group = True
                    self._group_db_service.add_group(group)
                    return_groups.append(group)
                    self._similarity_calculation_status.number_of_groups_with_ron = +1
                    self._similarity_calculation_status.number_of_new_groups_with_ron = (
                        +1
                    )
                    break

        self._similarity_calculation_status.running = False

        return return_groups
