# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend .
RUN npm run build

# Stage 2: Runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEIBOLIVE_HOST=0.0.0.0 \
    WEIBOLIVE_PORT=8887 \
    WEIBOLIVE_HEADLESS=1

WORKDIR /app/backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    fonts-noto-core \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

# Copy backend code
COPY backend /app/backend

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create data directories
RUN mkdir -p /app/backend/data/cookies \
    /app/backend/data/videos \
    /app/backend/data/covers \
    /app/backend/data/watermarks

EXPOSE 8887

CMD ["python", "run.py"]
