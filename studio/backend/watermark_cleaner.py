"""Watermark Cleaner — Gemini sparkle corner badge remover (Slice 6).

Local only, free, no API, no upload. The Gemini sparkle (Flow / Nano
Banana images) is a small white 4-point star in a corner, blended over
the picture at partial opacity. Removal is two steps, mirroring the
competitor's description ("located, reverse-blended, and inpainted"):

1. **Locate** — scan the four corners for a small, compact, bright,
   low-saturation cluster that stands out from its local background
   (median-blur background estimate). Large bright areas (sky, lamps)
   are rejected by size / compactness / corner-distance rules.
2. **Reverse-blend + inpaint** — the badge is white at alpha *a* over
   the background: obs = a*255 + (1-a)*bg. Per-pixel *a* is estimated
   from the local background, the blend is inverted, and OpenCV Telea
   inpaint smooths whatever is left.

`cv2` is imported lazily so the app still starts without it — the
endpoints then return an honest 503 telling the user to run Setup
(same pattern as the other optional deps). PIL does all file IO
(it is a hard dependency); cv2 is only used for inpaint, the median
background and connected components.

No ground truth is ever claimed: the reported "clean %" is the
reduction of the badge region's brightness contrast against its
surrounding ring (before vs after), measured on the same image.
"""

from __future__ import annotations

import io

import numpy as np

# Corner search: the badge sits within this square at each corner.
CORNER_SIZE = 170
# A badge component must be this close (px) to the corner point.
MAX_CORNER_DIST = 52
# Component size limits (px) — rejects sky, lamps, windows.
MIN_AREA = 25
MAX_AREA = 3200
MIN_SIDE = 7
MAX_SIDE = 95
# Detection thresholds on the residual (pixel minus local background).
RESIDUAL_MIN = 24
GRAY_MIN = 140
SAT_MAX = 55
FILL_MIN = 0.22

CORNERS = ("br", "bl", "tr", "tl")


def opencv_available() -> bool:
    """True when cv2 imports (lazy — never at module import time)."""
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return True


def _cv2():
    import cv2

    return cv2


# ---------------------------------------------------------------- IO

def load_image(data: bytes) -> np.ndarray:
    """Decode PNG/JPG/WebP bytes to an RGB uint8 array."""
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    return np.asarray(im)


def save_image(arr: np.ndarray, fmt: str) -> bytes:
    """Encode an RGB uint8 array as PNG/JPG/WebP bytes."""
    from PIL import Image

    fmt = (fmt or "png").lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in ("png", "jpeg", "webp"):
        fmt = "png"
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8"), mode="RGB").save(
        buf, fmt.upper(), quality=92
    )
    return buf.getvalue()


# ------------------------------------------------------------ detection

def _corner_rects(w: int, h: int) -> dict[str, tuple[int, int, int, int]]:
    s = min(CORNER_SIZE, w, h)
    return {
        "br": (w - s, h - s, w, h),
        "bl": (0, h - s, s, h),
        "tr": (w - s, 0, w, s),
        "tl": (0, 0, s, s),
    }


def _corner_point(corner: str, w: int, h: int) -> tuple[int, int]:
    return {
        "br": (w - 1, h - 1),
        "bl": (0, h - 1),
        "tr": (w - 1, 0),
        "tl": (0, 0),
    }[corner]


def detect_badge(arr: np.ndarray) -> dict | None:
    """Find the sparkle badge. Returns None when no badge is found.

    Result: {corner, bbox [x0,y0,x1,y1] (absolute), pixels, score,
    mask (full-size uint8 array, 255 = badge)}.
    """
    cv2 = _cv2()
    h, w = arr.shape[:2]
    if min(w, h) < 120:
        return None
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    # Local background: a big median blur erases the small star but
    # keeps the picture underneath.
    bg = cv2.medianBlur(gray, 21)
    resid = cv2.subtract(gray, bg).astype(np.int16)
    mx = arr.max(axis=2).astype(np.int16)
    mn = arr.min(axis=2).astype(np.int16)
    sat = mx - mn
    cand = (
        (resid > RESIDUAL_MIN)
        & (gray.astype(np.int16) > GRAY_MIN)
        & (sat < SAT_MAX)
    ).astype(np.uint8)
    cand = cv2.morphologyEx(
        cand, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)
    )
    best: dict | None = None
    for corner, (x0, y0, x1, y1) in _corner_rects(w, h).items():
        sub = cand[y0:y1, x0:x1]
        n, labels, stats, cents = cv2.connectedComponentsWithStats(
            sub, connectivity=8
        )
        px, py = _corner_point(corner, w, h)
        for i in range(1, n):
            x, y, bw, bh, area = (int(v) for v in stats[i])
            if area < MIN_AREA or area > MAX_AREA:
                continue
            if bw < MIN_SIDE or bh < MIN_SIDE or bw > MAX_SIDE or bh > MAX_SIDE:
                continue
            if area / max(1, bw * bh) < FILL_MIN:
                continue
            # The badge hugs the corner: its bbox must come close to it.
            cx, cy = x0 + x + bw / 2, y0 + y + bh / 2
            if abs(cx - px) > MAX_CORNER_DIST + bw / 2:
                continue
            if abs(cy - py) > MAX_CORNER_DIST + bh / 2:
                continue
            # Shape checks — the star is concave (thin arms, low
            # solidity and low fill); a solid bright blob (sky gap
            # between beams, a lamp) is convex and solid. A solid blob
            # is real picture content: cleaning it would DAMAGE the
            # image, so reject it even if it is bright and near the
            # corner. Measured: real badge solidity 0.69-0.79, fill
            # 0.38-0.45; sky-gap blobs solidity 0.90-1.00, fill
            # 0.61-0.87. Both gates must pass.
            comp = (labels == i).astype(np.uint8)
            if area / max(1, bw * bh) > 0.60:
                continue
            cnts, _ = cv2.findContours(
                comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not cnts:
                continue
            hull = cv2.convexHull(cnts[0])
            hull_mask = np.zeros_like(comp)
            cv2.fillPoly(hull_mask, [hull], 1)
            hull_area = int(hull_mask.sum())
            solidity = area / hull_area if hull_area else 1.0
            if solidity > 0.85:
                continue
            mean_resid = float(resid[y0 + y : y0 + y + bh, x0 + x : x0 + x + bw][
                labels[y : y + bh, x : x + bw] == i
            ].mean()) if area else 0.0
            score = area * max(0.0, mean_resid)
            if best is None or score > best["score"]:
                mask = np.zeros((h, w), np.uint8)
                mask[y0:y1, x0:x1][labels == i] = 255
                best = {
                    "corner": corner,
                    "bbox": [x0 + x, y0 + y, x0 + x + bw, y0 + y + bh],
                    "pixels": int(area),
                    "score": float(score),
                    "mask": mask,
                }
    if best is not None:
        # The thresholded core is smaller than the star (thin arm
        # tips fall below the residual cut). Dilate ~4px so the mask
        # covers the whole badge including its soft edge — the
        # reverse-blend + inpaint then work on the real badge, not
        # just its bright centre.
        best["mask"] = cv2.dilate(
            best["mask"], np.ones((9, 9), np.uint8)
        )
        ys, xs = np.where(best["mask"] > 0)
        best["bbox"] = [
            int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1,
        ]
        best["pixels"] = int((best["mask"] > 0).sum())
    return best


def _ring_contrast(gray: np.ndarray, mask: np.ndarray) -> float:
    """Mean brightness of the masked area minus its 6px ring.

    The ring is the picture right around the badge — the fairest
    "what should be there" reference. A visible badge makes this
    positive; a clean area is near zero.
    """
    cv2 = _cv2()
    ring = cv2.dilate(mask, np.ones((13, 13), np.uint8))
    ring = cv2.subtract(ring, mask)
    m = mask > 0
    r = ring > 0
    if not m.any() or not r.any():
        return 0.0
    return float(gray[m].mean() - gray[r].mean())


# ------------------------------------------------------------- cleaning

def clean_image(
    arr: np.ndarray, intensity: float = 1.0, extra_mask: np.ndarray | None = None
) -> tuple[np.ndarray, dict]:
    """Remove the detected badge (plus any painted extra mask).

    Returns (cleaned RGB array, report dict). When no badge is found
    and no extra mask is given, the image is returned unchanged and
    found=False — never a fake "cleaned" result.
    """
    cv2 = _cv2()
    intensity = max(0.5, min(2.0, float(intensity or 1.0)))
    found = detect_badge(arr)
    mask = np.zeros(arr.shape[:2], np.uint8)
    if found is not None:
        mask = cv2.bitwise_or(mask, found["mask"])
    if extra_mask is not None:
        extra = (extra_mask > 0).astype(np.uint8) * 255
        if found is None:
            # Manual-only pass (auto-clean already ran, or no badge
            # was detected): only touch pixels that STILL look like
            # watermark — bright vs their local background. Painting
            # over clean picture must not blur real content: a big
            # inpaint disc over clean detail makes the picture
            # worse, not better. Nothing bright in the painted area
            # means nothing to fix — say so, change nothing.
            gray0 = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            bg0 = cv2.medianBlur(gray0, 21)
            resid0 = cv2.subtract(gray0, bg0).astype(np.int16)
            mx = arr.max(axis=2).astype(np.int16)
            mn = arr.min(axis=2).astype(np.int16)
            bright = (
                (resid0 > 15)
                & (gray0.astype(np.int16) > 130)
                & ((mx - mn) < 80)
            ).astype(np.uint8)
            extra = cv2.bitwise_and(extra, bright * 255)
            extra = cv2.dilate(extra, np.ones((3, 3), np.uint8))
        mask = cv2.bitwise_or(mask, extra)
    if not (mask > 0).any():
        return arr.copy(), {
            "found": False,
            "manual": extra_mask is not None,
            "pixels": 0,
            "clean_pct": 0.0,
            "contrast_before": 0.0,
            "contrast_after": 0.0,
            "note": (
                "Painted area me koi watermark nahi mila — kuch nahi badla."
                if extra_mask is not None
                else None
            ),
        }
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    contrast_before = _ring_contrast(gray, mask)
    out = arr.copy().astype(np.float32)
    # Reverse-blend: estimate the local background with a big
    # median blur, then invert obs = a*255 + (1-a)*bg per pixel.
    bg = cv2.medianBlur(gray, 31).astype(np.float32)
    obs = gray.astype(np.float32)
    denom = np.maximum(255.0 - bg, 1.0)
    alpha = np.clip((obs - bg) / denom, 0.0, 0.92)
    for c in range(3):
        ch = out[:, :, c]
        a = alpha
        est = (ch - a * 255.0) / np.maximum(1.0 - a, 0.08)
        m = mask > 0
        ch[m] = np.clip(est[m], 0, 255)
    out = np.clip(out, 0, 255)
    # Inpaint what is left, radius follows the intensity slider.
    radius = max(2, int(round(3 * intensity)))
    dil = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    cleaned = cv2.inpaint(
        out.astype(np.uint8), dil, radius, cv2.INPAINT_TELEA
    )
    gray_after = cv2.cvtColor(cleaned, cv2.COLOR_RGB2GRAY)
    contrast_after = _ring_contrast(gray_after, mask)
    if contrast_before > 5:
        clean_pct = max(0.0, min(100.0, 100.0 * (1 - contrast_after / contrast_before)))
    else:
        clean_pct = 100.0 if contrast_after <= 5 else 0.0
    report = {
        "found": found is not None,
        "manual": extra_mask is not None,
        "corner": found["corner"] if found else None,
        "bbox": found["bbox"] if found else None,
        "pixels": int((mask > 0).sum()),
        "clean_pct": round(float(clean_pct), 1),
        "contrast_before": round(float(contrast_before), 1),
        "contrast_after": round(float(contrast_after), 1),
        "note": None,
    }
    return cleaned, report


def strokes_to_mask(
    w: int, h: int, strokes: list[dict], intensity: float = 1.0
) -> np.ndarray:
    """Painted strokes [{x, y, r}] in 0..1 coords -> uint8 mask.

    x/y are relative to the image; r is the brush radius, also
    relative (fraction of the image width). Dilation follows the
    intensity slider so a harder pass covers the badge's soft edge.
    """
    cv2 = _cv2()
    mask = np.zeros((h, w), np.uint8)
    for s in strokes or []:
        try:
            x = float(s.get("x", 0)) * w
            y = float(s.get("y", 0)) * h
            r = max(2.0, float(s.get("r", 0.02)) * w)
        except (TypeError, ValueError, AttributeError):
            continue
        cv2.circle(mask, (int(round(x)), int(round(y))), int(round(r)), 255, -1)
    dil = max(0, int(round(2 * float(intensity or 1.0))))
    if dil > 0:
        mask = cv2.dilate(mask, np.ones((2 * dil + 1, 2 * dil + 1), np.uint8))
    return mask
