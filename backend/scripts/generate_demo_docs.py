#!/usr/bin/env python3
"""
Generate demonstration documents into sample-data/ for testing and live presentations.
"""
from pathlib import Path
import cv2
import sys

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.localization.synthetic_generator import create_generator

def main():
    out_dir = BACKEND_ROOT.parent / "sample-data"
    out_dir.mkdir(exist_ok=True)
    generator = create_generator()

    docs_to_generate = [
        ("passport", 42, "demo_passport_clear.jpg"),
        ("passport", 101, "demo_passport_evaluation.jpg"),
        ("national_id", 123, "demo_national_id.jpg"),
        ("driving_license", 456, "demo_driving_license.jpg"),
        ("visa", 789, "demo_visa.jpg"),
        ("permit", 999, "demo_permit.jpg"),
    ]

    print("Generating demo presentation documents into sample-data/...")
    for doc_type, seed, filename in docs_to_generate:
        doc = generator.generate(doc_type, seed=seed)
        dest = out_dir / filename
        cv2.imwrite(str(dest), doc.image)
        print(f"  -> Generated {filename} ({doc_type}, {len(doc.annotations)} annotated regions)")

    print(f"Done! {len(docs_to_generate)} demo files created in {out_dir}")

if __name__ == "__main__":
    main()
