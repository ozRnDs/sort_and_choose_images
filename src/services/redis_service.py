from enum import Enum

import numpy as np
import redis

from ..utils.model_pydantic import Face


class VectorIndexType(str, Enum):
    EMBEDDING = "embedding"
    TARGET_OBJECT = "target_object"


class RedisInterface:
    def __init__(self, host="redis-stack", port=6379, db=0):
        """
        Initialize the Redis client.
        """
        self.client = redis.StrictRedis(
            host=host, port=port, db=db, decode_responses=True
        )

        # Create vector similarity search index
        self.create_vector_index()
        self.create_target_object_index()

    def create_vector_index(self):
        """
        Create an index for vector similarity search using Redis's module.
        """
        try:
            self.client.execute_command(
                "FT.CREATE",
                "embedding_index",  # Index name
                "ON",
                "JSON",  # Use JSON data type
                "PREFIX",
                "1",
                "embedding:",  # Key prefix for the embeddings
                "SCHEMA",
                "$.embedding",
                "AS",
                "embedding",
                "VECTOR",
                "FLAT",
                "6",  # Vector type and arguments count
                "TYPE",
                "FLOAT32",  # Data type of the vector
                "DIM",
                "512",  # Dimension of the vector
                "DISTANCE_METRIC",
                "COSINE",  # Similarity metric
            )
        except redis.exceptions.ResponseError as e:
            if "Index already exists" not in str(e):
                raise

    def create_target_object_index(self):
        """
        Create an index for target objects using Redis's module.
        """
        try:
            self.client.execute_command(
                "FT.CREATE",
                "target_object_index",  # Index name
                "ON",
                "JSON",  # Use JSON data type
                "PREFIX",
                "1",
                "target_object:",  # Key prefix for the target objects
                "SCHEMA",
                "$.target_id",  # Path to the target object ID in JSON
                "AS",
                "target_id",  # Alias for the field
                "TAG",  # Use TAG for categorical values
                "$.embedding",
                "AS",
                "embedding",
                "VECTOR",
                "FLAT",
                "6",  # Vector type and arguments count
                "TYPE",
                "FLOAT32",  # Data type of the vector
                "DIM",
                "512",  # Dimension of the vector
                "DISTANCE_METRIC",
                "COSINE",  # Similarity metric
            )
        except redis.exceptions.ResponseError as e:
            if "Index already exists" not in str(e):
                raise

    def add_embedding(self, index_type: VectorIndexType, face: Face):
        """
        Store an embedding with its associated face_id.
        """
        # Extract data from the Face object
        face_id = face.face_id
        embedding = face.embedding

        # Construct a Redis key using the face_id
        key = f"{index_type.value}:{face_id}"

        # Construct the data to store in Redis
        data = {
            "face_id": face_id,
            "embedding": embedding,
        }

        # Store the data in Redis using JSON format
        self.client.json().set(key, "$", data)

        return key

    def process_redis_results(self, results):
        """
        Process Redis vector search results into a structured format.

        Args:
            results (list): Flat list of Redis search results.

        Returns:
            list: List of structured results with face_id and scores.
        """
        num_results = results[0]  # First item is the number of results
        structured_results = []

        for i in range(1, len(results), 2):  # Iterate over doc_id and fields pairs
            # Parse document ID
            doc_id = results[i]  # e.g., 'embedding:face_id'
            doc_parts = doc_id.split(":")

            # Ensure the doc_id has the expected format
            if len(doc_parts) != 2:
                continue  # Skip if format is invalid

            face_id = doc_parts[1]  # Extract face_id

            # Parse fields
            fields = results[i + 1]  # ['score', 'value']
            score = None
            for j in range(0, len(fields), 2):  # Extract key-value pairs
                if fields[j] == "score":
                    score = float(fields[j + 1])

            # Append structured result
            structured_results.append({"face_id": face_id, "score": score})

        return num_results, structured_results

    def get_embedding(self, face_id: str):
        """
        Retrieve the embedding for a given face_id.

        Args:
            face_id (str): The unique identifier for the face.

        Returns:
            list: The embedding vector for the face, or None if not found.
        """
        key = f"embedding:{face_id}"

        try:
            # Retrieve the stored data for the given face_id
            data = self.client.json().get(key)

            # Check if the embedding exists
            if data and "embedding" in data:
                return data["embedding"]
            else:
                return None
        except redis.exceptions.ResponseError as e:
            raise ValueError(f"Failed to retrieve embedding for face_id {face_id}: {e}")

    def vector_search(self, query_embedding: list, k: int = 5):
        """
        Perform a vector similarity search.
        """
        # Convert embedding to bytes
        query_vector = np.array(query_embedding, dtype=np.float32).tobytes()

        # Prepare query: KNN requires embedding field and similarity metric
        query = f"*=>[KNN {k} @embedding $query_vec AS score]"

        # Execute the FT.SEARCH command
        try:
            results = self.client.execute_command(
                "FT.SEARCH",
                "embedding_index",
                query,
                "PARAMS",
                "2",
                "query_vec",
                query_vector,
                "SORTBY",
                "score",
                "ASC",
                "LIMIT",  # Add the LIMIT clause
                "0",  # Offset
                str(k),  # Number of results to return
                "RETURN",
                "2",
                "face_id",
                "score",
                "DIALECT",
                "2",
            )
        except redis.exceptions.ResponseError as e:
            raise ValueError(f"Redis search query failed: {e}")

        # Parse results
        num_results, structured_results = self.process_redis_results(results)

        return structured_results
