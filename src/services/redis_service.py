import numpy as np
import redis


class RedisInterface:
    def __init__(self, host="localhost", port=6379, db=0):
        """
        Initialize the Redis client.
        """
        self.client = redis.StrictRedis(
            host=host, port=port, db=db, decode_responses=True
        )

        # Create vector similarity search index
        self.create_vector_index()

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

    def add_embedding(self, image_name: str, face_bbox: list, embedding: list):
        """
        Store an embedding with its associated image name and bounding box.
        """
        key = f"embedding:{image_name}:{','.join(map(str, face_bbox))}"
        data = {
            "image_name": image_name,
            "face_bbox": face_bbox,
            "embedding": embedding,
        }
        self.client.json().set(key, "$", data)
        return key

    def process_redis_results(self, results):
        """
        Process Redis vector search results into a structured format.

        Args:
            results (list): Flat list of Redis search results.

        Returns:
            list: List of structured results with image names, face bounding boxes, and scores.
        """
        num_results = results[0]  # First item is the number of results
        structured_results = []

        for i in range(1, len(results), 2):  # Iterate over doc_id and fields pairs
            # Parse document ID
            doc_id = results[i]  # e.g., 'embedding:20230707_103839.jpg:1342.695...'
            doc_parts = doc_id.split(":")

            # Ensure the doc_id has expected format
            if len(doc_parts) < 2:
                continue  # Skip if format is invalid

            image_name = doc_parts[
                1
            ]  # Extract image name (e.g., 'embedding:20230707_103839.jpg')
            face_bbox = [
                int(float(item)) for item in doc_parts[2].split(",")
            ]  # Bounding box coordinates

            # Parse fields
            fields = results[i + 1]  # ['score', 'value']
            score = None
            for j in range(0, len(fields), 2):  # Extract key-value pairs
                if fields[j] == "score":
                    score = float(fields[j + 1])

            # Append structured result
            structured_results.append(
                {"image_name": image_name, "face_bbox": face_bbox, "score": score}
            )

        return num_results, structured_results

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
                "RETURN",
                "3",
                "image_name",
                "face_bbox",
                "score",
                "DIALECT",
                "2",
            )
        except redis.exceptions.ResponseError as e:
            raise ValueError(f"Redis search query failed: {e}")

        # Parse results
        num_results, structured_results = self.process_redis_results(results)

        return structured_results
