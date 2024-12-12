## 0.9.0 (2024-12-12)

### Feat

- **images.js**: Sort images based on resolution

### Fix

- **images**: Fix the sidebar and adjust the rest of the items accordinally

## 0.8.1 (2024-12-12)

### Perf

- **FaceRecognitionService**: Add cache middleware to TinyDB

## 0.8.0 (2024-12-12)

### Feat

- **FaceRecognitionService**: Improve the service data handling with tinydb
- **fastapi_server**: Add migrate_db entry point
- **ImageMetadata**: Add face_recognition_status field to easily get next image to process
- **fastapi_server**: Pass new envs to the FaceRecognitionService and RedisInterface
- **AppConfig**: Add FACE_DETECTION_URL, REDIS_URL, REDIS_PORT variables

### Refactor

- **FaceRecognitionService**: Adjust the TinyDB to work with documents instead of tables. Add migration code from progress.pkl to TinyDB
- **FaceRecognitionService**: Use TinyDB to persist progress information, to improve performances

## 0.7.1 (2024-12-11)

### Fix

- **RedisInterface**: Set the redis-stack host as default

## 0.7.0 (2024-12-11)

### Feat

- **fastapi_server**: Add face-recognition retry entrypoint
- **FaceRecognitionService**: Add retry logic for failed images

## 0.6.0 (2024-12-10)

### Feat

- **ron.html**: Create new page to display all the face from images marked as ron
- **groups.html,images.html**: Add ron.html to the navbar
- **fastapi_server**: Add get_image_for_face and get_paginated_faces_with_ron_in_image entry points
- **fastapi_server**: Add face_db_service integration. Add stop_face_recognition and get_embedding_by_face_id entry points
- **FaceRecognitionService**: Add typings to the Image objects. Save faces to db and send face_id to redis with the embeddings. Add time logging and calculations
- **RedisInterface**: Send to redis face_id and embeddings. Add get_embedding function (by face_id)
- **FaceDBService**: Create basic DB Service to save, update and search faces in a TinyDB (json)

### Refactor

- **groups_db**: Create centralized function to get grouped_metadata from pickle file
- **utils.model_pydantic**: Move ImageMetadata and GroupMetadata to utils.model_pydantic
- **fastapi_server**: Create shared load groups from file function and use it in all entrypoints

## 0.5.0 (2024-12-07)

### Feat

- **fastapi_server**: Integrate the redis interface and the face recognition service into the server
- **FaceRecognitionService**: Create a service that extract faces from all the images (using API) and saves the vectors to redis
- **RedisInterface**: Add an API to the redis server, create index for vector searches
- **AppConfig**: Add a class that loads env files as configuration to the program

### Fix

- **fastapi_service**: Handle cases that Redis server is not available

## 0.4.0 (2024-11-27)

### Feat

- **images**: Add the classification buttons, tag button and navigation buttons to the enlarged image mode (#8)

### Fix

- **groups.html**: Set currentPage=1 when dateslider changes (#6)

## 0.3.0 (2024-11-26)
