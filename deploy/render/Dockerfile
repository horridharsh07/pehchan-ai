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

# Copy the backend code and available model files
COPY backend/app app/
COPY backend/run_engine.py backend/model_manifest.json ./
COPY backend/data data/
COPY backend/models models/
COPY backend/training training/

# Non-root user for security
RUN useradd -m -u 1000 engine && chown -R engine /app
USER engine

ENV ENGINE_ALLOW_PLAINTEXT=true \
    LOCALIZATION_DEVICE=cpu \
    CLASSIFIER_DEVICE=cpu \
    PYTHONUNBUFFERED=1

EXPOSE 10000
CMD ["python", "run_engine.py", "--host", "0.0.0.0", "--port", "10000"]
