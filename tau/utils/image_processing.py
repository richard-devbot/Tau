from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

# Provider limits — 4.5 MB gives headroom below Anthropic's 5 MB hard limit
_DEFAULT_MAX_WIDTH = 2000
_DEFAULT_MAX_HEIGHT = 2000
_DEFAULT_MAX_BYTES = int(4.5 * 1024 * 1024)

_DEFAULT_JPEG_QUALITY = 80
_JPEG_QUALITY_STEPS = [80, 85, 70, 55, 40]
_SCALE_STEP = 0.75


@dataclass
class ProcessedImage:
    data: bytes
    mime_type: str
    original_width: int
    original_height: int
    display_width: int
    display_height: int

    @property
    def was_resized(self) -> bool:
        return (self.display_width, self.display_height) != (
            self.original_width,
            self.original_height,
        )

    def dimension_note(self) -> str | None:
        """Coordinate-mapping hint for the LLM when the image was scaled down."""
        if not self.was_resized:
            return None
        scale_x = self.original_width / max(1, self.display_width)
        scale_y = self.original_height / max(1, self.display_height)
        scale = round((scale_x + scale_y) / 2, 2)
        return (
            f"[Image: original {self.original_width}x{self.original_height}, "
            f"displayed at {self.display_width}x{self.display_height}. "
            f"Multiply coordinates by {scale} to map to original image.]"
        )


def process_image(
    data: bytes,
    max_width: int = _DEFAULT_MAX_WIDTH,
    max_height: int = _DEFAULT_MAX_HEIGHT,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    auto_resize: bool = True,
    to_png: bool = False,
    jpeg_quality: int = _DEFAULT_JPEG_QUALITY,
) -> ProcessedImage:
    """
    Full image processing pipeline:
      1. EXIF orientation correction
      2. Resize to fit max_width × max_height (if auto_resize)
      3. Try both PNG and JPEG, pick whichever is smaller and fits max_bytes;
         if still too large, reduce JPEG quality then scale dimensions down
      4. Optionally force PNG output (required for Kitty graphics protocol)

    Returns a ProcessedImage with the processed bytes and dimension metadata.
    """
    img = Image.open(io.BytesIO(data))

    # 1. EXIF orientation — one call handles all 8 rotations
    img = ImageOps.exif_transpose(img)

    original_width, original_height = img.size

    # 2. Resize to fit provider limits
    if auto_resize:
        img = _resize_to_fit(img, max_width, max_height)

    display_width, display_height = img.size

    # 3. Encode, picking the best format within the byte budget
    encoded, mime_type = _encode_best(img, max_bytes, jpeg_quality, force_png=to_png)

    return ProcessedImage(
        data=encoded,
        mime_type=mime_type,
        original_width=original_width,
        original_height=original_height,
        display_width=display_width,
        display_height=display_height,
    )


def convert_to_png(data: bytes) -> bytes:
    """Convert any supported image format to PNG bytes (for Kitty protocol)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    return _encode_png(img)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _resize_to_fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = img.size
    if w <= max_w and h <= max_h:
        return img
    scale = min(max_w / w, max_h / h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def _as_rgb(img: Image.Image) -> Image.Image:
    if img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    return img


def _encode_png(img: Image.Image) -> bytes:

    if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    _as_rgb(img).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _encode_best(
    img: Image.Image,
    max_bytes: int,
    jpeg_quality: int,
    force_png: bool,
) -> tuple[bytes, str]:
    """
    Try PNG and JPEG at each candidate size and pick whichever is smaller
    and fits within max_bytes.  Mirrors tryEncodings strategy.
    """
    qualities = list(dict.fromkeys([jpeg_quality] + _JPEG_QUALITY_STEPS))

    current = img
    while True:
        png = _encode_png(current)
        jpegs = [_encode_jpeg(current, q) for q in qualities]

        # Collect all candidates that fit, pick the smallest
        candidates: list[tuple[bytes, str]] = []
        if not force_png:
            for j in jpegs:
                if len(j) <= max_bytes:
                    candidates.append((j, "image/jpeg"))
        if len(png) <= max_bytes:
            candidates.append((png, "image/png"))

        if candidates:
            best = min(candidates, key=lambda c: len(c[0]))
            return best

        # Nothing fit — scale down and retry
        w, h = current.size
        if w <= 1 and h <= 1:
            break
        nw = max(1, int(w * _SCALE_STEP))
        nh = max(1, int(h * _SCALE_STEP))
        if nw == w and nh == h:
            break
        current = img.resize((nw, nh), Image.LANCZOS)

    # Last resort: return whatever PNG we have
    return _encode_png(img), "image/png"
