# Lean screening engine for Render/Koyeb/Railway free tier.
# No PyTorch — the document classifier and region detector are disabled.
# OCR, field extraction, face detection (YuNet+SFace), tampering forensics,
# and risk scoring all work at full strength.

FROM python:3.11-slim

# System dependencies: Tesseract OCR + OpenCV requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-nep \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (no PyTorch — saves ~600 MB)
COPY deploy/render/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
COPY backend/app app/
COPY backend/run_engine.py ./

# Copy model manifest (if present)
COPY backend/model_manifest.jso[n] ./

# Copy reference data
COPY backend/data/reference data/reference/

# Copy face models (required for face detection/comparison)
COPY backend/models/face models/face/

# Copy training metrics (small JSON files, no .pth weights)
COPY backend/training/document_classifier_metrics.json backend/training/region_detector_metrics.json backend/training/region_ocr_eval.json training/

# Create directories that the app expects but may be empty
RUN mkdir -p models/localization training data/registry uploads

# Non-root user for security
RUN useradd -m -u 1000 engine && chown -R engine /app
USER engine

ENV ENGINE_ALLOW_PLAINTEXT=true \
    LOCALIZATION_DEVICE=cpu \
    CLASSIFIER_DEVICE=cpu \
    ENGINE_TLS=off \
    PYTHONUNBUFFERED=1

EXPOSE 10000
CMD ["python", "run_engine.py", "--host", "0.0.0.0", "--port", "10000"]
