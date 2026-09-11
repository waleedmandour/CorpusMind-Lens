# lens-engine self-hosted image (§15 Phase 4). OCR language packs included.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY lens_engine ./lens_engine
RUN pip install --no-cache-dir .

# Frameworks are normally mounted read-only by docker-compose; provide the
# baked-in copy as a fallback for bare `docker run`.
COPY reference-data/frameworks /app/reference-data/frameworks

ENV LENS_HOST=0.0.0.0 \
    LENS_PORT=8765 \
    LENS_DATA_DIR=/data \
    LENS_FRAMEWORKS_DIR=/app/reference-data/frameworks

VOLUME ["/data"]
EXPOSE 8765

CMD ["uvicorn", "lens_engine.main:app", "--host", "0.0.0.0", "--port", "8765"]
