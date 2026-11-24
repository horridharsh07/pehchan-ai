"""
Tests for Face Verification Subsystem (YuNet + SFace single-pass canonical pipeline).
Validates calibration thresholds, identical-image consistency, and quality gating.
"""
from pathlib import Path
import cv2
import numpy as np
import pytest

from app.modules.face.detector import (
    FaceBox,
    FaceCandidate,
    detect_face_candidates,
    select_document_portrait,
)
from app.modules.face.verifier import (
    _sface,
    active_backend,
    backend_bands,
    compare_candidates,
    compare_faces,
)

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample-data"


def _solid_face(color: tuple[int, int, int], size: int = 160) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:, :] = color
    img[40:60, 40:120] = (color[0] // 2, color[1] // 2, color[2] // 2)
    img[100:120, 30:130] = (255 - color[0], 255 - color[1], 255 - color[2])
    return img


def test_identical_synthetic_faces_score_high_similarity():
    face = _solid_face((180, 150, 120))
    result = compare_faces(face, face.copy())
    assert result.document_face_found is True
    assert result.live_face_found is True
    assert result.similarity > 0.70
    assert result.is_match is True


def test_missing_faces_handled_gracefully():
    face = _solid_face((180, 150, 120))
    res_no_doc = compare_faces(None, face)
    assert res_no_doc.document_face_found is False
    assert res_no_doc.is_match is False

    res_no_live = compare_faces(face, None)
    assert res_no_live.live_face_found is False
    assert res_no_live.is_match is False


def test_sface_active_backend():
    assert active_backend() == "sface"
    match_t, mismatch_t = backend_bands("sface")
    # Calibrated thresholds must separate genuine and impostor distributions
    assert 0.40 <= match_t <= 0.65
    assert 0.20 <= mismatch_t <= 0.35


def test_single_pass_identical_real_face_consistency():
    face_a_path = SAMPLE_DIR / "real_face_a.jpg"
    if not face_a_path.is_file():
        pytest.skip("real_face_a.jpg not found")

    img_a = cv2.imread(str(face_a_path))
    candidates = detect_face_candidates(img_a)
    assert len(candidates) > 0

    portrait = select_document_portrait(candidates)
    assert portrait is not None
    assert portrait.raw_yunet_row is not None

    # Compare identical image passes
    result = compare_candidates(img_a, portrait, img_a, portrait)
    assert result.document_face_found is True
    assert result.live_face_found is True
    assert result.similarity >= 0.99
    assert result.decision == "match"
    assert result.is_match is True
    assert "yunet_5_point_aligned" in result.alignment_method_doc
    assert "yunet_5_point_aligned" in result.alignment_method_live


def test_real_different_faces_mismatch():
    face_a_path = SAMPLE_DIR / "real_face_a.jpg"
    face_b_path = SAMPLE_DIR / "real_face_b.jpg"
    if not face_a_path.is_file() or not face_b_path.is_file():
        pytest.skip("Test sample images missing")

    img_a = cv2.imread(str(face_a_path))
    img_b = cv2.imread(str(face_b_path))

    cand_a = select_document_portrait(detect_face_candidates(img_a))
    cand_b = select_document_portrait(detect_face_candidates(img_b))

    assert cand_a is not None
    assert cand_b is not None

    result = compare_candidates(img_a, cand_a, img_b, cand_b)
    # Different people must score below calibrated mismatch threshold (0.308)
    assert result.similarity < 0.31
    assert result.decision == "mismatch"
    assert result.is_match is False
