"""Fetch the YuNet face detector (OpenCV Zoo) into models/.

Not committed, for the same reason the other weights are not (see
fetch_panns.py). video/tracker.py uses it to find the face inside a person's
box; without it, face refinement falls back to the Haar cascades.

    python scripts/fetch_yunet.py

face_detection_yunet_2023mar.onnx, MIT licence (OpenCV Zoo), ~230 KB.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "models" / "face_detection_yunet_2023mar.onnx"

URLS = [
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx",
]
SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if DEST.exists() and _sha256(DEST.read_bytes()) == SHA256:
        print(f"Already have {DEST.name} ({DEST.stat().st_size / 1e3:.0f} KB)")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    for url in URLS:
        print(f"Fetching YuNet from {url.split('/')[2]} ...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "clips-studio"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
        except Exception as e:
            print(f"  failed: {e.__class__.__name__}: {str(e)[:80]}")
            continue
        if _sha256(data) == SHA256:
            DEST.write_bytes(data)
            print(f"  wrote {DEST} ({len(data) / 1e3:.0f} KB)")
            return 0
        print("  the download doesn't match the pinned checksum, not keeping it")

    print(
        "\nCould not fetch the YuNet face detector.\n"
        "Clipping still works without it: face refinement falls back to the\n"
        "Haar cascades."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
