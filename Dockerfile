# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 zlib1g && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

# don’t EXPOSE a fixed port; not required, but harmless if you do
# EXPOSE 8000

# Dockerfile (only the CMD matters here)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]