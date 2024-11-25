# sort_and_choose_images
System to help screen thousands of images and choosing the best for book/video projects


# README

## Building and Running the Docker Image

### Build the Docker Image
To create the Docker image for your FastAPI application, use the following command:

```bash
docker build -f deployment/Dockerfile -t sort_images:0.1 .
```

- `my-fastapi-app`: The name/tag for the Docker image.
- `.`: Refers to the current directory where the `Dockerfile` is located.

### Run the Docker Container
To run the Docker container with mounted volumes for `/data` and `/images`, use the following command:

```bash
docker run -v /path/to/data:/data -v /path/to/images:/images -p 8000:8000 my-fastapi-app
```

- `-v /path/to/data:/data`: Mounts the `/data` folder from the host machine to the container.
- `-v /path/to/images:/images`: Mounts the `/images` folder from the host machine to the container.
- `-p 8000:8000`: Maps port `8000` of the container to port `8000` on the host.
- `my-fastapi-app`: The name of the Docker image to run.

Make sure to replace `/path/to/data` and `/path/to/images` with the actual paths on your host machine.

### Notes
- The `Dockerfile` provided uses [Poetry](https://python-poetry.org/) to manage dependencies.
- The entry point for the application uses `Uvicorn` to serve the FastAPI application, with `--reload` enabled for hot-reloading during development.

