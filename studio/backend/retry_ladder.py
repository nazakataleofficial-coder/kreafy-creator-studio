# Retry Ladder + Fallback (Slice 3 PATCH — fail image ka professional
# tareeqa: kabhi skip nahi, kabhi gap nahi, sab automatic).
#
# Pure module: no DB, no network, no new dependency (PIL only, for the
# fallback crop). The worker in main.py calls it; the tests in
# /tmp/retry-ladder/ exercise it directly.
#
# Background (asli test se sabit): Flow ka "Dynamic Anchor Batch" tool
# 9/10 timecode images ek run me banata hai; #0:20 policy par fail hui,
# reword ("high above" -> "scaffolding par workers") se ban gayi — 10/10.
# Gemini Create me bulk paste kaam NAHI karta (0 images), is liye Canvas
# bulk background me ek-ek prompt chalata hai — aur har fail ke liye ye
# ladder chahiye.
#
# Ladder (har step automatic, user se kuch manual nahi):
#   attempt 1 "same"     — prompt jaisa hai waisa (pre-check ke baad)
#   attempt 2 "reword"   — policy-trigger lafz hatao / badlo
#   attempt 3 "simplify" — wahi timecode, simple scene, close-up
#   fallback             — pichli / agli shot ki image, alag crop/zoom
#                          (Ken Burns), shot "fallback used" mark
#
# Non-retryable (dobara chalane ka koi faida nahi): key nahi hai, daily
# limit khatam. Ye errors attempt 1 par hi 'failed' rehte hain.

from __future__ import annotations

import io
import re

# Policy-trigger phrase -> safe replacement. Curated list, not
# exhaustive: ye wahi lafz hain jo image providers ki policy aksar
# flag karti hai (oonchai / khatra / tashaddud / khoon). Case-insensitive
# substring match; lambi phrase pehle (taake "high above" se pehle
# "above" na khaye — is list me "above" akela hai hi nahi).
# Har replacement scene ki jagah + mood bachata hai, sirf risky lafz
# badalta hai. "riveting" -> "securing" aur "high above" -> "on
# scaffolding" wahi reword hai jo #0:20 par kaam kar gaya tha.
POLICY_TRIGGERS: list[tuple[str, str]] = [
    ("high above", "on scaffolding"),
    ("hanging from", "standing on"),
    ("hanging off", "standing on"),
    ("riveting", "securing"),
    ("cliff edge", "cliff viewpoint"),
    ("rooftop edge", "rooftop"),
    ("on the edge of", "near"),
    ("dangerous", "careful"),
    ("falling", "leaning"),
    ("crash", "sudden stop"),
    ("blood", "red paint"),
    ("gunfire", "loud sound"),
    ("shooting", "the incident"),
    ("knife attack", "confrontation"),
    ("explosion", "bright flash"),
    ("weapon", "tool"),
]

# Ye do errors retryable NAHI hain — dobara chalao to wahi error aayega.
# (main.py ke GEMINI_KEY_MISSING_MSG / GEMINI_LIMIT_MSG ke wahi lafz.)
_NON_RETRYABLE_FRAGMENTS = (
    "bina key ke image nahi ban sakti",
    "aaj ki free images khatam",
)

LADDER_STEPS = ("same", "reword", "simplify", "fallback")


def find_triggers(prompt: str) -> list[str]:
    """Policy-trigger phrases jo prompt me maujood hain (map ki order
    me, har phrase ek dafa). Case-insensitive."""
    text = (prompt or "").lower()
    return [trig for trig, _ in POLICY_TRIGGERS if trig in text]


def _replace_all(prompt: str) -> tuple[str, list[str]]:
    """Saare trigger replacements lagao. Returns (new prompt, applied
    triggers)."""
    applied: list[str] = []
    out = prompt or ""
    for trig, repl in POLICY_TRIGGERS:
        if trig in out.lower():
            out = re.sub(re.escape(trig), repl, out, flags=re.IGNORECASE)
            applied.append(trig)
    return out, applied


def precheck_prompt(prompt: str) -> dict:
    """Generate karne SE PEHLE scan: policy-trigger lafz hon to pehle
    hi auto-reword karo — retry se behtar hai rokna. Returns
    {prompt, changed, triggers}."""
    triggers = find_triggers(prompt)
    if not triggers:
        return {"prompt": prompt, "changed": False, "triggers": []}
    new_prompt, applied = _replace_all(prompt)
    return {
        "prompt": new_prompt,
        "changed": new_prompt != prompt,
        "triggers": applied,
    }


def reword_prompt(prompt: str, error: str = "") -> dict:
    """Retry 2: prompt ke lafz badlo. Pehle trigger map lagao; phir
    agar error me koi lafz quotes me likha ho ("...") aur wo prompt
    me ho to use bhi hatao (provider aksar wahi lafz batata hai jo
    us ne flag kiya). Returns {prompt, changed, applied}."""
    new_prompt, applied = _replace_all(prompt)
    quoted = re.findall(r'"([^"]{3,60})"', error or "")
    for phrase in quoted:
        if phrase.lower() in new_prompt.lower():
            new_prompt = re.sub(
                re.escape(phrase), "", new_prompt, flags=re.IGNORECASE
            )
            applied.append(f"error-word: {phrase}")
    # Double spaces / stray punctuation saaf karo, text ka order na badlo.
    new_prompt = re.sub(r"\s{2,}", " ", new_prompt).strip()
    return {
        "prompt": new_prompt,
        "changed": new_prompt != prompt,
        "applied": applied,
    }


def simplify_prompt(prompt: str) -> str:
    """Retry 3: wahi timecode, simple scene. Template prompt ka
    "Scene: ..." hissa chhota karo (trigger lafz hatao, pehla clause
    rakho) aur close-up framing jodo — wide dangerous scene ki jagah
    usi jagah ka close-up / doosra angle. Style, character, pose aur
    scene rule bits waisi ki waisi rehti hain (consistency na toote)."""
    text = (prompt or "").strip()
    if not text:
        return "Close-up view, same location, calm and safe scene."
    bits = [b.strip() for b in text.split(". ") if b.strip()]
    scene_idx = next(
        (i for i, b in enumerate(bits) if b.startswith("Scene: ")), None
    )
    if scene_idx is None:
        # Template shape nahi hai: pehla jumla lo, trigger hatao.
        first, _ = _replace_all(bits[0])
        return (
            f"{first.rstrip('.')}. Close-up view, same location,"
            " calm and safe scene."
        )
    scene_bit = bits[scene_idx][len("Scene: "):]
    scene_bit, _ = _replace_all(scene_bit)
    # Pehla clause rakho (comma se pehle) jab scene lambi ho.
    if len(scene_bit) > 90 and "," in scene_bit:
        scene_bit = scene_bit.split(",", 1)[0].strip()
    bits[scene_idx] = f"Scene: {scene_bit.rstrip('.')}"
    close_up = "Close-up view, same location, calm and safe scene"
    # "No photorealism" bit se pehle jodo, warna aakhir me.
    insert_at = next(
        (i for i, b in enumerate(bits) if b.startswith("No photorealism")),
        len(bits),
    )
    bits.insert(insert_at, close_up)
    return ". ".join(bits) + "."


def is_retryable_error(error: str | None) -> bool:
    """Kya is error par dobara chalana faida dega? Key nahi / limit
    khatam -> False (wahi error dobara aayega). Baaki sab (policy,
    transient, page-changed) -> True."""
    if not error:
        return True
    err = error.lower()
    return not any(frag in err for frag in _NON_RETRYABLE_FRAGMENTS)


def fallback_variant(image_bytes: bytes, variant: int = 0) -> bytes | None:
    """Pichli / agli shot ki image ko ALAG crop/zoom se dobara banao
    (Ken Burns jaisa farq — viewer ko wahi frame dobara nazar na
    aaye). variant 0 = centre 80% zoom-in, 1 = left 70%, 2 = right
    70%; resize wapas original size par. Returns PNG bytes, ya None
    (bytes kharab hon to — fallback kabhi crash nahi karta)."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        if variant == 1:
            box = (0, 0, int(w * 0.70), h)
        elif variant == 2:
            box = (int(w * 0.30), 0, w, h)
        else:
            box = (
                int(w * 0.10), int(h * 0.10),
                int(w * 0.90), int(h * 0.90),
            )
        cropped = img.crop(box).resize((w, h), Image.LANCZOS)
        out = io.BytesIO()
        cropped.save(out, format="PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 - fallback must never crash the batch
        return None
