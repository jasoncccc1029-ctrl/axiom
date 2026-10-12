# Build from repo root: docker build -f backend/Dockerfile .
# Or set Railway root directory to `backend` and use the alternate COPY paths below.

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Prefer monorepo root context (Railway default when dockerfilePath=backend/Dockerfile)
COPY backend/requirements.txt ./requirements.txt
COPY backend/app ./app

RUN pip install -r requirements.txt

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
