"""
Download the ONNX face model weights required by the ML engine.
Run once after cloning:
    python scripts/download_models.py

Models downloaded:
  - face_detection_yunet_2023mar.onnx  (YuNet face detector, 121 KB)
  - face_recognition_sface_2021dec.onnx  (SFace face recogniser, 36.9 MB)

Source: OpenCV Zoo (Apache-2.0 license)
"""
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")  # suppress InsecureRequestWarning

MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models"
        "/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models"
        "/face_recognition_sface/face_recognition_sface_2021dec.onnx"
    ),
}

DEST = pathlib.Path(__file__).resolve().parent.parent / "models" / "face"
DEST.mkdir(parents=True, exist_ok=True)


def download(name: str, url: str) -> None:
    dest = DEST / name
    if dest.is_file():
        print(f"  ✓ {name} already present ({dest.stat().st_size:,} bytes) — skipping.")
        return
    print(f"  ↓ Downloading {name} ...")
    try:
        import requests
        resp = requests.get(url, verify=False, stream=True, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  ✓ {name} saved ({dest.stat().st_size:,} bytes)")
    except ImportError:
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        urllib.request.urlretrieve(url, dest)
        print(f"  ✓ {name} saved ({dest.stat().st_size:,} bytes)")
    except Exception as exc:
        print(f"  ✗ Failed to download {name}: {exc}")
        print(f"    Please download manually from:\n    {url}")
        print(f"    and place it at: {dest}")


def update_manifest() -> None:
    """Rewrite model_manifest.json with the new hashes."""
    manifest_path = pathlib.Path(__file__).resolve().parent.parent / "model_manifest.json"
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    try:
        # Clear lru_cache so new files are picked up
        from app.modules.provenance import write_manifest, model_hashes
        model_hashes.cache_clear()
        write_manifest()
    except Exception as exc:
        print(f"  ⚠ Could not update manifest (run manually): {exc}")


if __name__ == "__main__":
    print("Pehchaan — downloading face model weights")
    for model_name, model_url in MODELS.items():
        download(model_name, model_url)
    print("\nUpdating model_manifest.json ...")
    update_manifest()
    print("\nDone! Restart the ML engine to use the new models.")
