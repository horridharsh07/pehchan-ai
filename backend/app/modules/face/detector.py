"""
Face detection using OpenCV YuNet with single-pass landmark preservation
and robust portrait quality gating for travel documents.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

_YUNET_PATH = Path(__file__).resolve().parents[3] / "models" / "face" / "face_detection_yunet_2023mar.onnx"
_YUNET_MAX_SIDE = 1280
_YUNET_MIN_SCORE = 0.6  # Calibrated for document photos with halftones
_MIN_TONAL_RANGE = 35   # Lowered from 65: Aadhaar small halftone portraits legitimately have low contrast

_lock = threading.Lock()
_yunet_detector = None

def _yunet():
    # Neural face detector (OpenCV YuNet) when its model file is present;
    # far fewer false faces on guilloche patterns and watermarks than Haar.
    global _yunet_detector
    from app.modules.provenance import model_trusted

    if not _YUNET_PATH.is_file() or not model_trusted("face_detector_yunet"):
        return None
    with _lock:
        if _yunet_detector is None:
            _yunet_detector = cv2.FaceDetectorYN.create(str(_YUNET_PATH), "", (320, 320), _YUNET_MIN_SCORE)
        return _yunet_detector


def _cascade():
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
        return None
    try:
        xml = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        return cv2.CascadeClassifier(str(xml)) if xml.is_file() else None
    except Exception:
        return None


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    quality: float = 0.0  # 0..1, higher = more like a real photograph
    tonal_range: float = 0.0
    sharpness: float = 0.0


@dataclass
class FaceCandidate:
    box: FaceBox
    raw_yunet_row: np.ndarray | None = None  # Full 15-float detection vector for alignCrop
    detection_method: str = "yunet"          # "yunet" | "haar" | "manual"
    image_shape: tuple[int, int] = (0, 0)


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _iou(a: FaceBox, b: FaceBox) -> float:
    x1, y1 = max(a.x, b.x), max(a.y, b.y)
    x2, y2 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / float(a.w * a.h + b.w * b.h - inter or 1)


def _score(gray: np.ndarray, box: FaceBox) -> FaceBox:
    crop = gray[box.y:box.y + box.h, box.x:box.x + box.w]
    if crop.size == 0:
        return box
    p5, p95 = np.percentile(crop, (5, 95))
    box.tonal_range = float(p95 - p5)
    box.sharpness = float(cv2.Laplacian(cv2.resize(crop, (128, 128)), cv2.CV_64F).var())
    box.quality = round(min(1.0, box.tonal_range / 160) * 0.6 + min(1.0, box.sharpness / 400) * 0.4, 3)
    return box


def detect_face_candidates(image: np.ndarray) -> list[FaceCandidate]:
    """Single-pass detector that preserves the full 15-value landmark row
    required by OpenCV alignCrop, properly mapped to original image coordinates."""
    gray = _gray(image)
    candidates: list[FaceCandidate] = []
    detector = _yunet() if image.ndim == 3 else None
    
    if detector is not None:
        h, w = image.shape[:2]
        scale = min(1.0, _YUNET_MAX_SIDE / max(h, w))
        target_img = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 1.0 else image
        
        # Thread-safe local detector sizing
        detector.setInputSize((target_img.shape[1], target_img.shape[0]))
        _, faces = detector.detect(target_img)
        
        if faces is not None:
            for row in faces:
                orig_row = row.copy()
                if scale < 1.0:
                    orig_row[:14] = orig_row[:14] / scale
                    
                x, y, bw, bh = orig_row[:4].astype(int)
                box = FaceBox(max(0, x), max(0, y), int(bw), int(bh))
                if box.w >= 20 and box.h >= 20:  # Lowered from 35: Aadhaar small portrait can be ~30px wide
                    scored_box = _score(gray, box)
                    candidates.append(FaceCandidate(
                        box=scored_box,
                        raw_yunet_row=orig_row,
                        detection_method="yunet",
                        image_shape=(h, w)
                    ))
            if candidates:
                return candidates

    # Optional Haar fallback if cascade classifier is built into OpenCV
    cascade = _cascade()
    if cascade is not None:
        for candidate_img in (gray, cv2.equalizeHist(gray)):
            try:
                for (x, y, w, h) in cascade.detectMultiScale(candidate_img, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)):
                    box = FaceBox(int(x), int(y), int(w), int(h))
                    if not any(_iou(box, c.box) > 0.4 for c in candidates):
                        scored_box = _score(gray, box)
                        candidates.append(FaceCandidate(
                            box=scored_box,
                            raw_yunet_row=None,
                            detection_method="haar",
                            image_shape=image.shape[:2]
                        ))
            except Exception:
                pass

    return candidates


def detect_faces(image: np.ndarray) -> list[FaceBox]:
    """Backward-compatible helper returning legacy FaceBox list."""
    candidates = detect_face_candidates(image)
    return [c.box for c in candidates]


def select_document_portrait(candidates: list[FaceCandidate]) -> FaceCandidate | None:
    """The holder's photograph: among candidates that meet genuine contrast
    criteria, selects the primary portrait based on quality and prominence.
    Rejects faint watermarks and logos; returns None if quality is insufficient.
    
    For document scans (Aadhaar, PAN, DL), small halftone photos can have
    low tonal range; we use a relaxed fallback for the largest detected face
    when no candidate passes the full quality gate.
    """
    if not candidates:
        return None
    
    # 1. Full quality gate: tonal range >= _MIN_TONAL_RANGE (35 for documents)
    valid = [c for c in candidates if c.box.tonal_range >= _MIN_TONAL_RANGE]
    if valid:
        biggest = max(c.box.w * c.box.h for c in valid)
        # Blend photographic quality (60%) and relative size (40%)
        return max(valid, key=lambda c: c.box.quality * 0.6 + (c.box.w * c.box.h / biggest) * 0.4)

    # 2. Relaxed fallback for genuinely small document photos (e.g., Aadhaar mini portrait):
    # Accept the largest detected face even if tonal range is low, as long as it
    # is not trivially small (< 30x30). This prevents silent skip on halftone prints.
    significant = [c for c in candidates if c.box.w >= 30 and c.box.h >= 30]
    if significant:
        return max(significant, key=lambda c: c.box.w * c.box.h)

    return None


def pick_portrait(faces: list[FaceBox]) -> FaceBox | None:
    """Legacy helper for backward compatibility."""
    if not faces:
        return None
    real = [f for f in faces if f.tonal_range >= _MIN_TONAL_RANGE]
    if not real:
        return None
    biggest = max(f.w * f.h for f in real)
    return max(real, key=lambda f: f.quality * 0.7 + (f.w * f.h / biggest) * 0.3)


def detect_largest_face(image: np.ndarray) -> tuple[np.ndarray, FaceBox] | None:
    """Returns the primary portrait crop and its box, or None if no valid face found."""
    candidates = detect_face_candidates(image)
    chosen = select_document_portrait(candidates)
    if chosen is None:
        return None
    box = chosen.box
    crop = image[box.y:box.y + box.h, box.x:box.x + box.w]
    return crop, box


def detect_primary_candidate(image: np.ndarray) -> tuple[FaceCandidate | None, str]:
    """Returns the selected FaceCandidate with full 15-float landmarks,
    or (None, reason) if validation fails."""
    candidates = detect_face_candidates(image)
    if not candidates:
        return None, "NO_FACE_DETECTED"
    
    chosen = select_document_portrait(candidates)
    if chosen is None:
        return None, "QUALITY_INSUFFICIENT_LOW_CONTRAST"
        
    return chosen, "SUCCESS"
