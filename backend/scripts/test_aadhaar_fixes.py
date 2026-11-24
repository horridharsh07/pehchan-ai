"""
Test the two bug fixes against the Aadhaar card from didi.pdf:
1. Name extraction: should return "Shelika Anand" (not father/guardian's name)
2. Face detection: should detect the portrait on the Aadhaar card
"""
import sys
import os
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
if "HTTP_PROXY" in os.environ: del os.environ["HTTP_PROXY"]
if "http_proxy" in os.environ: del os.environ["http_proxy"]

from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import json
from starlette.testclient import TestClient
from app.main import app
from app.config import get_settings
from app.modules.ocr.indian_extractors import extract_aadhaar_fields

settings = get_settings()
headers = {"x-engine-key": settings.ENGINE_API_KEY}
client = TestClient(app)

# 1. Test OCR name extraction with simulated Aadhaar OCR text
print("=" * 60)
print("TEST 1: Aadhaar Name Extraction (Punjabi letter format)")
print("=" * 60)

# This simulates the OCR output from a Punjabi/UIDAI letter-format Aadhaar
# (like didi.pdf which has "To\nShelika Anand\nD/O Ram Anand" layout)
simulated_ocr = """
ਭਾਰਤ ਸਰਕਾਰ
Government of India
ਭਾਰਤੀ ਵਿਲੱਖਣ ਪਛਾਣ ਅਥਾਰਟੀ
Unique Identification Authority of India

Enrolment No.: 0013/78001/01799

To
Shelika Anand
D/O Ram Anand,
H NO. 48,
Block L,
Bhai Randhir Singh Nagar,
VTC: LUDHIANA,
District: Ludhiana,
State: Punjab,
PIN Code: 141012,
Mobile: 7508866862

Your Aadhaar No.: 9974 0716 4156
VID: 9139 6997 1342 8316
DOB: 25/09/2000
FEMALE
"""

fields = extract_aadhaar_fields(simulated_ocr)
print(f"Extracted name:   {fields.get('name', '*** NOT FOUND ***')}")
print(f"DOB:              {fields.get('date_of_birth', 'not found')}")
print(f"Gender:           {fields.get('gender', 'not found')}")
print(f"Aadhaar number:   {fields.get('id_number', 'not found')}")
print(f"Aadhaar valid:    {fields.get('aadhaar_valid', False)}")
print(f"State:            {fields.get('state', 'not found')}")

name_ok = fields.get("name") == "Shelika Anand"
print(f"\n{'✓ PASS' if name_ok else '✗ FAIL'}: Name is {'Shelika Anand' if name_ok else fields.get('name')}")

# 2. Test live endpoint with the uploaded Aadhaar image
print("\n" + "=" * 60)
print("TEST 2: Face Detection on Aadhaar Card (uploaded PNG)")
print("=" * 60)

aadhaar_png = Path(r"C:\Users\DELL\.gemini\antigravity\brain\0af0859b-eb3b-4070-b6f9-7ed5cf1ddbf2\.user_uploaded\media_1795448888017_4abf9255.png")
live_jpg = Path(r"C:\Users\DELL\.gemini\antigravity\brain\0af0859b-eb3b-4070-b6f9-7ed5cf1ddbf2\.user_uploaded\media_1795448888017_82ced491.jpg")

# Test face detection on the Aadhaar card directly
import cv2
import numpy as np
from app.modules.face.detector import detect_face_candidates, select_document_portrait

aadhaar_img = cv2.imread(str(aadhaar_png))
if aadhaar_img is not None:
    h, w = aadhaar_img.shape[:2]
    print(f"Aadhaar card image size: {w}x{h}px")
    candidates = detect_face_candidates(aadhaar_img)
    print(f"Detected {len(candidates)} face candidate(s):")
    for i, c in enumerate(candidates):
        print(f"  Candidate {i+1}: box=({c.box.x},{c.box.y},{c.box.w}x{c.box.h}) | tonal_range={c.box.tonal_range:.1f} | quality={c.box.quality:.3f} | method={c.detection_method}")
    portrait = select_document_portrait(candidates)
    if portrait:
        print(f"\n✓ PASS: Portrait selected: box=({portrait.box.x},{portrait.box.y},{portrait.box.w}x{portrait.box.h})")
    else:
        print("\n✗ FAIL: No portrait selected (face still not found on Aadhaar card)")
else:
    print("Aadhaar PNG not found — skipping face detection test")

# 3. Full scan via API: Aadhaar card + live photo
print("\n" + "=" * 60)
print("TEST 3: Full API Scan (Aadhaar + Live Photo)")
print("=" * 60)
if aadhaar_png.exists() and live_jpg.exists():
    with open(aadhaar_png, "rb") as f_doc, open(live_jpg, "rb") as f_live:
        r = client.post(
            "/api/documents/scan",
            headers=headers,
            data={"document_type": "aadhar"},
            files={
                "document": ("aadhaar.png", f_doc, "image/png"),
                "live_face": ("live.jpg", f_live, "image/jpeg"),
            },
        )
    result = r.json()
    print(f"Status: {r.status_code}")
    print(f"Extracted Name:   {result['identity']['name']}")
    print(f"Aadhaar Number:   {result['identity']['document_number']}")
    print(f"DOB:              {result['identity']['date_of_birth']}")
    print(f"Face attempted:   {result['face']['attempted']}")
    print(f"Doc face found:   {result['face']['document_face_found']}")
    print(f"Live face found:  {result['face']['live_face_found']}")
    print(f"Face decision:    {result['face']['decision']}")
    print(f"Face similarity:  {result['face']['similarity']}")
    print(f"Risk score:       {result['risk']['risk_score']}/100 ({result['risk']['verdict']})")
else:
    print("Uploaded images not found — skipping full API test")
