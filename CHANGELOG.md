## 0.14.1 (2025-01-05)

### Fix

- **fastapi_server**: Update the DB's file names

## 0.14.0 (2025-01-05)

### Feat

- **fastapi_server**: Add fix_whatsapp_images_group to the migration tasks

### Fix

- **fastapi_server**: Don't run similarity calculation if the router is false
- **ImagesProcessingV2**: Migrate whatsapp images to their real groups
- **ImageProcessingV2**: Improve the image_metadata and groupings
- **DbRouter**: Add fix_missing_classification_for_images
- **fastapi_server.py**: Fix missing classification for images on startup
- **ImageDBService**: Add images to db based on full_client_path field and not name

### Refactor

- **explore_pickle_file**: Search for duplicate images, that appear in more that one group
- **fastapi_server**: Update migration version to 0.13.1

## 0.13.1 (2024-12-18)

### Fix

- **fastapi_server**: Disable migrations

## 0.13.0 (2024-12-15)

### Feat

- **ImageDBService**: Add counting functions and update all failed images
- **FaceRecognitionService**: Add get_image_status to support migrations

### Fix

- **FaceRecognitionService**: Work with the image_db_service instead of seperate db for images status
- **FaceDBService**: Add missing save_db function

### Refactor

- **fastapi_server**: Pass image_db_service to the fastapi_server
- **FaceProcessingRouter**: Deprecate old entrypoints

## 0.12.0 (2024-12-15)

### Feat

- **images.css,images.js**: Show new_images flag in the UI

## 0.11.0 (2024-12-15)

### Feat

- **fastapi_server**: Run migration script at startup
- **GroupsRouterV2**: Add check_group_has_classification entrypoint to check if the group has classification
- **images.js**: Adjust to call new entrypoint to get details about the images
- **GroupsRouterV2**: Add get_group_images entry point
- **ImageProcessingV2**: Create new loading process for images
- **fastapi_server**: Inject the new image and group db to all the new entrypoints
- **PaginatedGroupsResponseV2**: Create new PaginatedGroups response to support the new db
- **GroupsRouterV2**: Create new GroupsRouterV2 class to support the new db
- **ClassifyRouterV2**: Add new classify entry points that support the new db type
- **DbRouter**: Add migrate entry point to switch from pickle file to TinyDB
- **GroupMetadata_V1**: Create old version of the class - to load from pickle file
- **GroupDBService**: Add get_group function
- **ImageDBService**: Create new ImageDBService
- **GroupDBService**: Create new GroupDBService to manage groups
- **DbRouter**: Create entry points to download dbs for group and images (#20)

### Fix

- **images.js**: Update group classification also when ron_in_image is changed
- **ClassifyRouterV2**: Add missing face_db_service
- **ImageDBService**: Improve the query mechanism in get_images, to support  operator
- **fastapi_service**: Pass image_db_service to GroupsRouterV2
- **groups.html**: Adjust the page to fix the V2 for groups
- **DbRouter**: Inject db services to share them with the rest of the app. Add db type to the download entrypoints, to gain access to all the db files
- **ImageDBService,GroupDBService**: Add db save when object is deleted
- **ClassifyRouter,GroupsRouterV1,ImagesProcessing_V1**: Disable entrypoints that change the old db
- **ClassifyRouter,GroupsRouterV1,ImagesProcessing_V1**: Disable entrypoints that change the old db
- **ClassifyRouter,GroupsRouterV1,ImagesProcessing_V1**: Disable entrypoints that change the old db
- **DbRouter**: Fix group db migration entry point and adjust it to fit fastapi

### Refactor

- **DbRouter**: Enable access to migrate groups db script through the software
- **images.js**: Get group classification from an entry point
- **GroupsRouterV1,ImagesProcessing_V1,PaginatedGroupsResponseV1**: Set old services and entrypoints as V1
- **fastapi_server**: Pass new db locations to the db_router
- **load_groups_from_pickle_file**: Add db_location as input to the function (to control the loading process)
- **entire_project**: Rename load_groups_from_file to load_groups_from_pickle_file

## 0.9.1 (2024-12-13)

### Fix

- **FaceRecognitionService**: Set self._terminate=False when the command was processed by the _astart loop (#16)

## 0.4.0 (2024-11-27)

### Feat

- **images**: Add the classification buttons, tag button and navigation buttons to the enlarged image mode (#8)

### Fix

- **groups.html**: Set currentPage=1 when dateslider changes (#6)

## 0.3.0 (2024-11-26)
