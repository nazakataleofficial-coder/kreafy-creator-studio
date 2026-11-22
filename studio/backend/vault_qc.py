"""Character Vault auto-QC — what the software checks by itself
after a bulk batch, and what it honestly cannot check.

Slice 4 (Character Vault): after a bulk batch, the software itself
checks every generated image and regenerates broken ones — the
user never checks. This module is pure PIL, no network, no new
dependency (Pillow is already used by StickMan).

HONEST LIMIT, proven by calibration (see
/tmp/character-vault/calibrate_qc.py + calibrate_qc2.py, numbers
recorded in docs/PROJECT_STATE.md): a pixel-similarity score
CANNOT tell a right character from a wrong one. All 7 niches
share one style and palette, so a generated scene scores the
same against its own sheet (0.329-0.428) as against another
niche's sheet (0.286-0.472) — the distributions overlap
completely. A threshold would flag good images as drift and pass
wrong-niche images. So the score is RECORDED for the record
only, and never triggers a regenerate on its own.

What auto-QC DOES do (proven by the same calibration):
- broken bytes (unreadable / under 2 KB) -> regenerate once.
- blank images (solid black: score 0.23-0.26; solid white:
  mean brightness > 250 with std < 5) -> regenerate once.
Character drift itself is prevented UPSTREAM, not by QC: the
locked description + reference image ride in every prompt
(Slice 3 auto rules, now sourced from the Vault), and every
generated image still shows in the verification view for the
user to approve / reject. A vision-model judge (Gemini with
image input) is the real future path for true drift detection —
it needs a real-key billing check on Ali's PC first, so it is
NOT built here.
"""

from __future__ import annotations

import io
import statistics

from PIL import Image

# A generated image under 2 KB is not a real scene — it is a
# broken/empty response.
_QC_MIN_BYTES = 2048


def _open_rgb(image_bytes: bytes) -> Image.Image:
    """Bytes -> RGB PIL image. Raises on bad bytes (caller treats it
    as broken, never as a pass)."""
    with Image.open(io.BytesIO(image_bytes)) as im:
        return im.convert("RGB")


def _hist_similarity(a: Image.Image, b: Image.Image) -> float:
    """Colour-histogram intersection, 0..1 (1 = identical palette).
    Recorded only — see the module docstring for why it never
    triggers a regenerate."""
    size = (128, 128)
    ha = a.resize(size).histogram()
    hb = b.resize(size).histogram()
    total = 0.0
    inter = 0.0
    for ch in range(3):
        for b32 in range(32):
            sa = sum(ha[ch * 256 + b32 * 8 : ch * 256 + b32 * 8 + 8])
            sb = sum(hb[ch * 256 + b32 * 8 : ch * 256 + b32 * 8 + 8])
            inter += min(sa, sb)
            total += max(sa, sb)
    if total == 0:
        return 0.0
    return max(0.0, min(1.0, inter / total))


def _dhash(image: Image.Image) -> int:
    """64-bit difference hash: 9x8 grayscale, bit set where a pixel
    is brighter than its right neighbour."""
    g = image.convert("L").resize((9, 8))
    px = list(g.tobytes())
    bits = 0
    for y in range(8):
        for x in range(8):
            if px[y * 9 + x] > px[y * 9 + x + 1]:
                bits |= 1 << (y * 8 + x)
    return bits


def _dhash_similarity(a: Image.Image, b: Image.Image) -> float:
    """1 - (Hamming distance / 64). 1 = identical structure."""
    ha = _dhash(a)
    hb = _dhash(b)
    dist = bin(ha ^ hb).count("1")
    return 1.0 - dist / 64.0


def qc_score(generated_bytes: bytes, sheet_bytes: bytes) -> float:
    """Similarity between a generated image and its locked sheet,
    0..1 (1 = identical). Recorded for the record only — it cannot
    distinguish drift (see module docstring). Raises on unreadable
    bytes."""
    gen = _open_rgb(generated_bytes)
    sheet = _open_rgb(sheet_bytes)
    hist = _hist_similarity(gen, sheet)
    dh = _dhash_similarity(gen, sheet)
    return round(0.6 * hist + 0.4 * dh, 4)


def _is_blank(image: Image.Image) -> str | None:
    """'black' / 'white' when the image is (near-)solid, else None.
    Mean brightness + standard deviation on a small grayscale
    copy: a real scene always has spread-out pixels."""
    g = image.convert("L").resize((64, 64))
    px = list(g.tobytes())
    mean = sum(px) / len(px)
    std = statistics.pstdev(px) if len(px) > 1 else 0.0
    if mean < 8 and std < 5:
        return "black"
    if mean > 250 and std < 5:
        return "white"
    return None


def qc_check(
    generated_bytes: bytes, sheet_bytes: bytes | None = None
) -> dict:
    """Check one generated image. Returns a plain dict:

    {score, hist, dhash, blank, broken, needs_regen, reason}
    - score/hist/dhash: similarity vs the sheet (None when no
      sheet was given); recorded only, never triggers a regen.
    - blank: 'black' / 'white' / None.
    - broken: True when the bytes are unreadable or under 2 KB.
    - needs_regen: True ONLY for broken or blank images.
    - reason: short plain text for the summary / job record.
    """
    if not generated_bytes or len(generated_bytes) < _QC_MIN_BYTES:
        return {
            "score": None,
            "hist": None,
            "dhash": None,
            "blank": None,
            "broken": True,
            "needs_regen": True,
            "reason": "broken image (too small / empty)",
        }
    try:
        gen = _open_rgb(generated_bytes)
    except Exception:  # noqa: BLE001 - unreadable bytes = broken
        return {
            "score": None,
            "hist": None,
            "dhash": None,
            "blank": None,
            "broken": True,
            "needs_regen": True,
            "reason": "broken image (unreadable bytes)",
        }
    blank = _is_blank(gen)
    score = hist = dh = None
    if sheet_bytes:
        try:
            sheet = _open_rgb(sheet_bytes)
            hist = round(_hist_similarity(gen, sheet), 4)
            dh = round(_dhash_similarity(gen, sheet), 4)
            score = round(0.6 * hist + 0.4 * dh, 4)
        except Exception:  # noqa: BLE001 - sheet unreadable: score skipped
            pass
    if blank:
        return {
            "score": score,
            "hist": hist,
            "dhash": dh,
            "blank": blank,
            "broken": False,
            "needs_regen": True,
            "reason": f"blank {blank} image",
        }
    return {
        "score": score,
        "hist": hist,
        "dhash": dh,
        "blank": None,
        "broken": False,
        "needs_regen": False,
        "reason": "ok",
    }
