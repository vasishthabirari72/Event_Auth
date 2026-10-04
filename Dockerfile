FROM node:22-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir -e .
COPY assets/ ./assets/
COPY scripts/download_models.py ./scripts/download_models.py
RUN python scripts/download_models.py
COPY alembic.ini ./
COPY --from=frontend /ui/dist ./frontend/dist/
COPY scripts/cloud_start.sh ./scripts/cloud_start.sh
ENV PYTHONUNBUFFERED=1 EVENT_AUTH_COOKIE_SECURE=true
CMD ["sh", "scripts/cloud_start.sh"]
