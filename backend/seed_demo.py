"""
seed_demo.py — Populate a "Demo" class using faces from the LFW benchmark.

Subjects are the 7 politicians that appear most often in LFW (≥70 images each),
which are also the standard benchmark classes used by scikit-learn.

Usage (from the backend/ directory, with the backend server running):
    uv run python seed_demo.py

The script streams the LFW .tgz archive (~173 MB), extracts only the seven
target folders, picks the clearest photo per person (highest Laplacian variance
= least blur), then calls POST /api/students/bulk-enroll.

The backend must be running at BASE_URL below.  If it's on a different port
or host, adjust that constant before running.
"""

# /// script
# dependencies = ["requests", "Pillow", "numpy"]
# ///

import csv
import io
import tarfile
import urllib.request
import zipfile

import numpy as np
import requests
from PIL import Image

BASE_URL = "http://localhost:8000"
CLASS_NAME = "Demo"
LFW_TGZ_URL = "http://vis-www.cs.umass.edu/lfw/lfw.tgz"

# The 7 LFW subjects with ≥70 images — standard benchmark classes.
# Keys are the directory names inside the archive (underscores, as-is).
SUBJECTS = {
    "Ariel_Sharon":       {"name": "Ariel Sharon",       "roll": "DEMO-01"},
    "Colin_Powell":       {"name": "Colin Powell",        "roll": "DEMO-02"},
    "Donald_Rumsfeld":    {"name": "Donald Rumsfeld",     "roll": "DEMO-03"},
    "George_W_Bush":      {"name": "George W. Bush",      "roll": "DEMO-04"},
    "Gerhard_Schroeder":  {"name": "Gerhard Schroeder",   "roll": "DEMO-05"},
    "Hugo_Chavez":        {"name": "Hugo Chavez",         "roll": "DEMO-06"},
    "Tony_Blair":         {"name": "Tony Blair",          "roll": "DEMO-07"},
}


def laplacian_variance(img_bytes: bytes) -> float:
    """Sharpness score: variance of the Laplacian. Higher = sharper."""
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    arr = np.array(img, dtype=float)
    # 3×3 Laplacian kernel
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=float)
    from numpy.lib.stride_tricks import sliding_window_view
    h, w = arr.shape
    windows = sliding_window_view(arr, (3, 3))
    lap = (windows * kernel).sum(axis=(-2, -1))
    return float(lap.var())


def stream_lfw_images() -> dict[str, list[tuple[str, bytes]]]:
    """
    Stream the LFW .tgz from UMass and collect images for our target subjects.
    Returns { subject_key: [(filename, bytes), ...] }
    """
    collected: dict[str, list[tuple[str, bytes]]] = {k: [] for k in SUBJECTS}

    print(f"Streaming LFW archive from {LFW_TGZ_URL} …")
    print("(~173 MB download — this may take a minute on a slow connection)\n")

    req = urllib.request.urlopen(LFW_TGZ_URL, timeout=120)

    with tarfile.open(fileobj=req, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            # Path format: lfw/Person_Name/Person_Name_XXXX.jpg
            parts = member.name.split("/")
            if len(parts) < 3:
                continue
            subject_key = parts[1]
            if subject_key not in SUBJECTS:
                continue

            f = tar.extractfile(member)
            if f is None:
                continue
            img_bytes = f.read()
            filename = parts[2]  # e.g. George_W_Bush_0001.jpg
            collected[subject_key].append((filename, img_bytes))

            total = sum(len(v) for v in collected.values())
            done = sum(1 for v in collected.values() if v)
            print(f"\r  Collected {total} photos across {done}/7 subjects …", end="", flush=True)

    print()
    return collected


def pick_best(images: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    """Return the sharpest image (highest Laplacian variance)."""
    scored = [(laplacian_variance(b), fname, b) for fname, b in images]
    scored.sort(reverse=True)
    _, fname, best_bytes = scored[0]
    return fname, best_bytes


def build_csv_and_zip(
    selections: dict[str, tuple[str, bytes]],
) -> tuple[bytes, bytes]:
    """Build in-memory CSV and ZIP from the selected photos."""
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["name", "roll_number", "class_name", "photo"])

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for subject_key, (filename, img_bytes) in selections.items():
            meta = SUBJECTS[subject_key]
            # Normalise filename to something clean: DEMO-01.jpg etc.
            clean_filename = f"{meta['roll']}.jpg"
            writer.writerow([meta["name"], meta["roll"], CLASS_NAME, clean_filename])
            zf.writestr(clean_filename, img_bytes)

    return csv_buf.getvalue().encode(), zip_buf.getvalue()


def enroll(csv_bytes: bytes, zip_bytes: bytes) -> dict:
    """POST to the bulk-enroll endpoint and return the JSON response."""
    resp = requests.post(
        f"{BASE_URL}/api/students/bulk-enroll",
        files={
            "csv_file":   ("roster.csv", csv_bytes, "text/csv"),
            "photos_zip": ("photos.zip", zip_bytes, "application/zip"),
        },
        timeout=300,  # face encoding can be slow on first run (model download)
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    # 1. Download & collect
    collected = stream_lfw_images()
    missing = [k for k, v in collected.items() if not v]
    if missing:
        print(f"\nWARNING: No images found for: {', '.join(missing)}")

    available = {k: v for k, v in collected.items() if v}
    if not available:
        print("ERROR: No images collected. Check your internet connection.")
        return

    # 2. Pick the sharpest photo per person
    print(f"\nSelecting sharpest photo for each of {len(available)} subjects …")
    selections: dict[str, tuple[str, bytes]] = {}
    for subject_key, images in available.items():
        fname, img_bytes = pick_best(images)
        selections[subject_key] = (fname, img_bytes)
        print(f"  {SUBJECTS[subject_key]['name']:25s}  →  {fname}  ({len(images)} candidates)")

    # 3. Build CSV + ZIP
    print("\nBuilding CSV roster and photo ZIP …")
    csv_bytes, zip_bytes = build_csv_and_zip(selections)

    # 4. Send to backend
    print(f"Posting to {BASE_URL}/api/students/bulk-enroll …")
    print("(Face model loads on first use — may take ~30 s)\n")
    result = enroll(csv_bytes, zip_bytes)

    # 5. Print summary
    print(f"{'─' * 50}")
    print(f"  Total:     {result['total']}")
    print(f"  Enrolled:  {result['succeeded']}")
    print(f"  Failed:    {result['failed']}")
    print(f"{'─' * 50}")
    for r in result["results"]:
        status = "OK" if r["status"] == "ok" else f"FAIL — {r['detail']}"
        print(f"  {r['name']:25s}  {status}")

    if result["succeeded"] > 0:
        print(f"\nDemo class '{CLASS_NAME}' is ready. Open the Students page and filter by '{CLASS_NAME}'.")


if __name__ == "__main__":
    main()
