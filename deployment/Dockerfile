FROM python:3.12.7-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    VENV_PATH="/app/.venv"

RUN apt update && apt install git-all python3-opencv ffmpeg -y
RUN pip install poetry

# Copy necessary files
COPY pyproject.toml poetry.lock README.md /app/
# Install dependencies and set up pre-commit
RUN poetry install

COPY src /app/src

EXPOSE 8000

ENTRYPOINT ["poetry", "run", "python", "-m", "src.fastapi_server"]