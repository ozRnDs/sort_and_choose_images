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
