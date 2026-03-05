"""
image_service.py — Draw bounding boxes + labels on a photo, return as base64 PNG.

We use Pillow (PIL) because it:
- Needs no display or window system (unlike OpenCV's imshow)
- Has excellent font/text rendering
- Is already a dependency of many libraries

The annotated image is returned as a base64-encoded PNG string so the frontend
can display it directly in an <img> tag: src="data:image/png;base64,..."
"""

import base64
import io
from pathlib import Path

import numpy as np
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

# Try to load a nicer system font; fall back to Pillow's built-in bitmap font.
# On Windows the Arial font is almost always available.
_FONT_PATH_CANDIDATES = [
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux fallback
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_PATH_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    # Ultimate fallback: Pillow's built-in font (tiny, but always works)
    return ImageFont.load_default()


def annotate_image(image_bytes: bytes, face_results: list[dict]) -> str:
    """
    Draw colored bounding boxes and labels for each detected face.

    Green box + "1 Arjun"  → recognized
    Red box   + "2 Unknown" → unknown

    Returns:
        Base64-encoded PNG string (no data: prefix — frontend adds that).
    """
    # Load image from bytes into Pillow
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Scale font size relative to image width — looks good on both small and large photos
    font_size = max(16, img.width // 60)
    font = _get_font(font_size)
    box_thickness = max(2, img.width // 300)

    for face in face_results:
        x1, y1, x2, y2 = face["bbox"]
        label = f"{face['face_index']} {face['name']}"
        color = "#22c55e" if face["status"] == "recognized" else "#ef4444"  # green / red

        # Draw rectangle
        for t in range(box_thickness):
            draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=color)

        # Draw label background so text is readable on any background
        text_bbox = draw.textbbox((x1, y1), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        label_y = y1 - text_h - 6
        if label_y < 0:
            label_y = y2 + 4  # put below box if no space above

        draw.rectangle(
            [x1, label_y, x1 + text_w + 6, label_y + text_h + 4],
            fill=color,
        )
        draw.text((x1 + 3, label_y + 2), label, fill="white", font=font)

    logger.debug(f"Annotated {len(face_results)} faces on {img.width}×{img.height} image")

    # Encode to PNG → base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
