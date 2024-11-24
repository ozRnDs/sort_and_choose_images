FROM python:3.11.6-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    VENV_PATH="/app/.venv"

RUN apt update && apt install git-all -y
RUN pip install poetry
# COPY . /app
# RUN poetry install && poetry run pre-commit install
# ENTRYPOINT poetry run python main.py run chat_analyzer
