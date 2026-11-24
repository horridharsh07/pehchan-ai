"""
Face detection — deep-scan edition.

Backends tried in order (strongest first):
  1. OpenCV YuNet (DNN, ONNX) — accurate on scanned documents, tolerant of
     tilt, low resolution and lighting variation.
  2. Haar cascade frontal + profile (OpenCV built-in) — 3 passes: original,
     CLAHE-enhanced, histogram-equalised.
  3. Known-layout crop — uses the MEASURED portrait region coordinates from
     photo_regions.py as a guaranteed fallback when face detection fails. This
     is the most important addition: even if the detector finds nothing (poor
     scan quality, unusual lighting), we still get the correct portrait crop
     for SFace to compare.

Deep-scan improvements:
  • YuNet confidence threshold 0.55 (was 0.70) — catches low-contrast prints.
  • 3-pass Haar: original + CLAHE + equalised grey — recovers dark/faded photos.
  • Known portrait-region crop as final fallback (never returns None for known
    document types).
  • detect_largest_face() pads the crop 10% so SFace sees forehead/chin context.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

_local = threading.local()


def _cascade() -> cv2.CascadeClassifier:
    if not hasattr(_local, "cascade"):
        _local.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _local.cascade


def _cascade_profile() -> cv2.CascadeClassifier:
    if not hasattr(_local, "cascade_profile"):
        _local.cascade_profile = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )
    return _local.cascade_profile


_YUNET_PATH = Path(__file__).resolve().parents[3] / "models" / "face" / "face_detection_yunet_2023mar.onnx"
_YUNET_MAX_SIDE = 1280
_YUNET_MIN_SCORE = 0.55   # lowered: document photos have lower contrast than selfies


def _yunet():
    from app.modules.provenance import model_trusted
    if not _YUNET_PATH.is_file() or not model_trusted("face_detector_yunet"):
        return None
    if not hasattr(_local, "yunet"):
        _local.yunet = cv2.FaceDetectorYN.create(
            str(_YUNET_PATH), "", (320, 320),
            score_threshold=_YUNET_MIN_SCORE,
            nms_threshold=0.3,
        )
    return _local.yunet


_MIN_TONAL_RANGE = 50   # lowered from 70: faded passport photos have low range


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    quality: float = 0.0
    tonal_range: float = 0.0
    sharpness: float = 0.0
    source: str = "detector"   # "detector" | "layout" — how the box was found


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _clahe_gray(gray: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)


def _iou(a: FaceBox, b: FaceBox) -> float:
    x1, y1 = max(a.x, b.x), max(a.y, b.y)
    x2, y2 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / float(a.w * a.h + b.w * b.h - inter or 1)


def _score(gray: np.ndarray, box: FaceBox) -> FaceBox:
    crop = gray[box.y: box.y + box.h, box.x: box.x + box.w]
    if crop.size == 0:
        return box
    p5, p95 = np.percentile(crop, (5, 95))
    box.tonal_range = float(p95 - p5)
    box.sharpness = float(cv2.Laplacian(cv2.resize(crop, (128, 128)), cv2.CV_64F).var())
    box.quality = round(
        min(1.0, box.tonal_range / 160) * 0.60
        + min(1.0, box.sharpness / 400) * 0.40,
        3,
    )
    return box


def _haar_pass(candidate: np.ndarray, found: list[FaceBox]) -> None:
    for (x, y, w, h) in _cascade().detectMultiScale(
        candidate, scaleFactor=1.08, minNeighbors=4, minSize=(30, 30)
    ):
        box = FaceBox(int(x), int(y), int(w), int(h))
        if not any(_iou(box, f) > 0.4 for f in found):
            found.append(box)
    for (x, y, w, h) in _cascade_profile().detectMultiScale(
        candidate, scaleFactor=1.08, minNeighbors=4, minSize=(30, 30)
    ):
        box = FaceBox(int(x), int(y), int(w), int(h))
        if not any(_iou(box, f) > 0.4 for f in found):
            found.append(box)


def detect_faces(image: np.ndarray) -> list[FaceBox]:
    """All face candidates, de-duplicated and quality-scored.

    Pass 1 — YuNet DNN (best on document scans)
    Pass 2 — Haar on original grey
    Pass 3 — Haar on CLAHE-enhanced grey (recovers dark/faded photos)
    Pass 4 — Haar on equalised grey (last resort)
    """
    gray = _gray(image)
    found: list[FaceBox] = []

    detector = _yunet() if image.ndim == 3 else None
    if detector is not None:
        h, w = image.shape[:2]
        scale = min(1.0, _YUNET_MAX_SIDE / max(h, w))
        small = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 1 else image
        detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = detector.detect(small)
        for row in faces if faces is not None else []:
            x, y, bw, bh = (row[:4] / scale).astype(int)
            box = FaceBox(max(0, int(x)), max(0, int(y)), int(bw), int(bh))
            if box.w >= 30 and box.h >= 30:
                found.append(box)
        if found:
            return [_score(gray, f) for f in found]

    clahe_gray = _clahe_gray(gray)
    eq_gray = cv2.equalizeHist(gray)
    for candidate in (gray, clahe_gray, eq_gray):
        _haar_pass(candidate, found)

    found = [f for f in found if f.w >= 30 and f.h >= 30]
    return [_score(gray, f) for f in found]


def pick_portrait(faces: list[FaceBox]) -> FaceBox | None:
    """Pick the holder's portrait from candidates: largest + best quality."""
    if not faces:
        return None
    real = [f for f in faces if f.tonal_range >= _MIN_TONAL_RANGE] or faces
    biggest = max(f.w * f.h for f in real)
    return max(real, key=lambda f: f.quality * 0.60 + (f.w * f.h / biggest) * 0.40)


# ---------------------------------------------------------------------------
# Layout-guided fallback crop — the most important fix
# ---------------------------------------------------------------------------

def crop_portrait_region(image: np.ndarray, document_type: str) -> tuple[np.ndarray, FaceBox] | None:
    """
    Extract the portrait region using the MEASURED layout coordinates from
    photo_regions.py for the given document type.

    This is the guaranteed fallback: even when face detection fails completely
    (very low contrast, unusual lighting, scanner artefacts), we know exactly
    where the portrait sits on each document type and can still extract it for
    SFace comparison.

    Returns the portrait crop and a synthetic FaceBox, or None if the document
    type has no measured portrait region.
    """
    try:
        from app.modules.localization.photo_regions import portraits_for
    except ImportError:
        return None

    portraits = portraits_for(document_type)
    if not portraits:
        return None

    h, w = image.shape[:2]
    region = portraits[0]   # primary portrait (sorted: photo before ghost_photo)
    x0, y0, x1, y1 = region.bbox_norm

    # Add 5% padding around the measured region
    pad_x = (x1 - x0) * 0.05
    pad_y = (y1 - y0) * 0.05
    x0 = max(0.0, x0 - pad_x)
    y0 = max(0.0, y0 - pad_y)
    x1 = min(1.0, x1 + pad_x)
    y1 = min(1.0, y1 + pad_y)

    px = int(x0 * w)
    py = int(y0 * h)
    pw = int((x1 - x0) * w)
    ph = int((y1 - y0) * h)

    if pw < 20 or ph < 20:
        return None

    crop = image[py: py + ph, px: px + pw]
    if crop.size == 0:
        return None

    gray = _gray(image)
    box = FaceBox(px, py, pw, ph, source="layout")
    box = _score(gray, box)
    return crop, box


def detect_largest_face(image: np.ndarray,
                         document_type: str | None = None) -> tuple[np.ndarray, FaceBox] | None:
    """
    Returns the portrait crop (with 10% contextual border) and its FaceBox.

    Strategy:
    1. Run detect_faces() — YuNet DNN + 3-pass Haar
    2. If found, return best portrait with 10% padding
    3. If not found AND document_type is known, fall back to layout-guided crop
    4. If still nothing, return None
    """
    chosen = pick_portrait(detect_faces(image))

    if chosen is not None:
        ph, pw = image.shape[:2]
        pad_y = int(chosen.h * 0.10)
        pad_x = int(chosen.w * 0.10)
        y1 = max(0, chosen.y - pad_y)
        y2 = min(ph, chosen.y + chosen.h + pad_y)
        x1 = max(0, chosen.x - pad_x)
        x2 = min(pw, chosen.x + chosen.w + pad_x)
        crop = image[y1:y2, x1:x2]
        return crop, chosen

    # Fallback: layout-guided crop for known document types
    if document_type:
        layout = crop_portrait_region(image, document_type)
        if layout is not None:
            return layout

    return None
