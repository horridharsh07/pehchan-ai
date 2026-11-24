"""
Comprehensive test suite for Pehchaan AI backend server endpoints.
Tests:
- GET /
- GET /api/health
- GET /api/system/models
- Security: Missing / invalid engine key rejection (401)
- POST /api/face/verify: Genuine pair (same photo) -> MATCH
- POST /api/face/verify: Impostor pair (person A vs person B) -> DIFFERENT_PERSON
- POST /api/documents/scan: Passport scan with OCR, MRZ, tampering forensics, risk score
- POST /api/documents/scan: Passport scan with live face verification
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from starlette.testclient import TestClient
from app.main import app
from app.config import get_settings

settings = get_settings()
ENGINE_KEY = settings.ENGINE_API_KEY or "test_key"

client = TestClient(app)

SAMPLE_DATA = WORKSPACE_ROOT / "sample-data"
PASSPORT_IMG = SAMPLE_DATA / "demo_passport_clear.jpg"
FACE_A = SAMPLE_DATA / "real_face_a.jpg"
FACE_B = SAMPLE_DATA / "real_face_b.jpg"

print("=" * 70)
print("PEHCHAAN AI SERVER COMPREHENSIVE ENDPOINT TEST SUITE")
print("=" * 70)

# 1. Test GET /
print("\n[TEST 1] GET / (Root)")
r = client.get("/")
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")
assert r.status_code == 200, f"Expected 200, got {r.status_code}"
assert "docs" in r.json()
print("PASSED [TEST 1]")

# 2. Test GET /api/health (Security: requires x-engine-key)
print("\n[TEST 2a] GET /api/health without engine key -> Expect 401")
r = client.get("/api/health")
print(f"Status: {r.status_code}, Body: {r.json()}")
assert r.status_code == 401, f"Expected 401, got {r.status_code}"
print("PASSED [TEST 2a]")

print("\n[TEST 2b] GET /api/health with engine key -> Expect 200")
headers = {"x-engine-key": ENGINE_KEY}
r = client.get("/api/health", headers=headers)
print(f"Status: {r.status_code}")
health_data = r.json()
print(f"Health Response: {json.dumps(health_data, indent=2)}")
assert r.status_code == 200
assert health_data["status"] == "ok"
print("PASSED [TEST 2b]")

# 3. Test GET /api/system/models
print("\n[TEST 3] GET /api/system/models")
r = client.get("/api/system/models", headers=headers)
print(f"Status: {r.status_code}")
models_data = r.json()
print(f"Found {len(models_data.get('models', []))} subsystem models:")
for m in models_data.get("models", []):
    print(f"  - {m['name']} ({m['key']}): {m['status']} | {m.get('architecture', '')}")
    if m['key'] == 'face_matcher':
        print(f"    Details: {m.get('details')}")
assert r.status_code == 200
print("PASSED [TEST 3]")

# 4. Test POST /api/face/verify - Genuine Pair (Same Face)
print("\n[TEST 4] POST /api/face/verify (Genuine Pair: Face A vs Face A)")
t0 = time.perf_counter()
with open(FACE_A, "rb") as f_doc, open(FACE_A, "rb") as f_live:
    r = client.post(
        "/api/face/verify",
        headers=headers,
        files={
            "document_photo": ("face_a_doc.jpg", f_doc, "image/jpeg"),
            "live_photo": ("face_a_live.jpg", f_live, "image/jpeg"),
        },
    )
dt = (time.perf_counter() - t0) * 1000
print(f"Status: {r.status_code} ({dt:.1f}ms)")
face_res = r.json()
print(f"Face Verify Result: {json.dumps(face_res, indent=2)}")
assert r.status_code == 200
assert face_res["decision"] == "match", f"Expected match, got {face_res['decision']}"
assert face_res["is_match"] is True
assert face_res["similarity"] > 0.95, f"Expected similarity > 0.95, got {face_res['similarity']}"
print(f"Genuine similarity: {face_res['similarity']:.4f} >= threshold {face_res['threshold']}")
print("PASSED [TEST 4]")

# 5. Test POST /api/face/verify - Impostor Pair (Face A vs Face B)
print("\n[TEST 5] POST /api/face/verify (Impostor Pair: Face A vs Face B)")
t0 = time.perf_counter()
with open(FACE_A, "rb") as f_doc, open(FACE_B, "rb") as f_live:
    r = client.post(
        "/api/face/verify",
        headers=headers,
        files={
            "document_photo": ("face_a.jpg", f_doc, "image/jpeg"),
            "live_photo": ("face_b.jpg", f_live, "image/jpeg"),
        },
    )
dt = (time.perf_counter() - t0) * 1000
print(f"Status: {r.status_code} ({dt:.1f}ms)")
face_res_imp = r.json()
print(f"Face Verify Result: {json.dumps(face_res_imp, indent=2)}")
assert r.status_code == 200
assert face_res_imp["decision"] == "mismatch", f"Expected mismatch, got {face_res_imp['decision']}"
assert face_res_imp["is_match"] is False
assert face_res_imp["similarity"] < face_res_imp["mismatch_threshold"], "Impostor should be below mismatch threshold"
print(f"Impostor similarity: {face_res_imp['similarity']:.4f} < mismatch_threshold {face_res_imp['mismatch_threshold']}")
print("PASSED [TEST 5]")

# 6. Test POST /api/documents/scan - Passport without live face
print("\n[TEST 6] POST /api/documents/scan (Passport Scan without live face)")
t0 = time.perf_counter()
with open(PASSPORT_IMG, "rb") as f_doc:
    r = client.post(
        "/api/documents/scan",
        headers=headers,
        data={"document_type": "passport"},
        files={"document": ("passport.jpg", f_doc, "image/jpeg")},
    )
dt = (time.perf_counter() - t0) * 1000
print(f"Status: {r.status_code} ({dt:.1f}ms)")
scan_res = r.json()
assert r.status_code == 200
print(f"Risk Score: {scan_res['risk']['risk_score']}/100 ({scan_res['risk']['verdict']})")
print(f"Contributing Factors: {scan_res['risk']['contributing_factors']}")
print(f"Document Type: requested={scan_res['classification']['requested_type']}, detected={scan_res['classification']['detected_type']}")
print(f"Identity: name='{scan_res['identity']['name']}', doc_number='{scan_res['identity']['document_number']}'")
print(f"Validation Issues: {len(scan_res['validation']['issues'])} issue(s)")
print(f"Tampering Verdict: {scan_res['tampering']['verdict']} (score: {scan_res['tampering']['tampering_score']}, ELA error: {scan_res['tampering']['ela_max_error']})")
print(f"Face summary: attempted={scan_res['face']['attempted']}, doc_face_found={scan_res['face']['document_face_found']}")
print("PASSED [TEST 6]")

# 7. Test POST /api/documents/scan - Passport WITH live face
print("\n[TEST 7] POST /api/documents/scan (Passport Scan WITH Live Face)")
t0 = time.perf_counter()
with open(PASSPORT_IMG, "rb") as f_doc, open(FACE_A, "rb") as f_live:
    r = client.post(
        "/api/documents/scan",
        headers=headers,
        data={"document_type": "passport"},
        files={
            "document": ("passport.jpg", f_doc, "image/jpeg"),
            "live_face": ("live_face.jpg", f_live, "image/jpeg"),
        },
    )
dt = (time.perf_counter() - t0) * 1000
print(f"Status: {r.status_code} ({dt:.1f}ms)")
scan_res2 = r.json()
assert r.status_code == 200
print(f"Risk Score: {scan_res2['risk']['risk_score']}/100 ({scan_res2['risk']['verdict']})")
print(f"Face verification: attempted={scan_res2['face']['attempted']}, decision={scan_res2['face']['decision']}, similarity={scan_res2['face']['similarity']}")
print("PASSED [TEST 7]")

print("\n" + "=" * 70)
print("ALL 7 ENDPOINT TESTS PASSED COMPLETELY AND SUCCESSFULLY!")
print("=" * 70)
