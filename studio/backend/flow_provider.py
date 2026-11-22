# Google Flow provider for VisualForge — free images through
# Google Flow (flow.google.com) driven by Playwright, on the SAME
# Google login + Gemini Pro quota as the Canvas provider.
#
# Why this exists (Ali's approval 2026-11-21, Connect Google slice):
# Flow is Google's AI filmmaking workspace — its image engine is
# Imagen (Nano Banana in the current UI) and image generation inside
# Flow is free under Ali's existing 18-month Gemini Pro (= Google AI
# Pro) subscription. No new payment, no billing route, no API key:
# the same one-time Google sign-in that opens Canvas opens Flow.
# Flow is the SECOND bulk route; Canvas stays the default free
# provider. If Flow fails on a scene, the worker retries that scene
# once on Canvas (same job) — Flow's failure never loses an image.
#
# Shared profile: all browser machinery lives in google_browser.py
# and is shared with the Canvas provider (same persistent profile
# directory, same login-window lock). This module keeps only the
# Flow page itself: its URL, messages, exceptions and selectors.
#
# Honest caveats (recorded in PROJECT_STATE.md — do not hide):
# - UNVERIFIED LIVE: no Google login exists in the build VM and
#   flow.google.com is not reachable from it, so neither the login
#   probe nor a real generation has ever run against Google's live
#   page here. The selectors below are best-effort, from Flow's
#   public UI descriptions (a prompt composer + Create action in
#   the workspace). If the live page differs, the job FAILS with
#   the plain message "Flow page badal gaya — provider update
#   chahiye" and the worker falls back to Canvas — never a fake
#   success, never a silent pass. The first real Flow generation
#   waits for Ali's one-time Google sign-in on his PC.
# - FRAGILE / ToS-grey: same as Canvas — browser automation
#   against Google's web page.
# - NO credentials are stored anywhere. The login cookies live
#   only in the shared profile folder. No password or OTP is ever
#   asked for by this code.
# - Flow's video generation (Veo) uses subscription credits and is
#   NOT part of this provider: this provider generates STILL
#   IMAGES only, the same 16:9 scene images VisualForge needs.

from __future__ import annotations

import re
import time
from pathlib import Path

import flow_hardening as _fh
import google_browser as _gb

FLOW_URL = "https://flow.google.com"

# Exact messages the user sees (Roman Urdu, plain).
FLOW_LOGIN_MSG = (
    "Flow ke liye Google login nahi hai — Settings me 'Connect Google'"
    " se ek dafa Google sign-in karein, phir dobara try karein"
)
FLOW_PAGE_CHANGED_MSG = (
    "Flow page badal gaya — provider update chahiye"
)
FLOW_BROWSER_MISSING_MSG = (
    "Flow browser nahi mila — ek dafa 'playwright install chromium'"
    " chalayein, phir dobara try karein"
)
FLOW_PLAYWRIGHT_MISSING_MSG = (
    "Flow ke liye Playwright chahiye — 'pip install playwright'"
    " chalayein, phir dobara try karein"
)

# How long one Flow image may take — same budget as Canvas: Flow
# image generation is the same class of web generation (tens of
# seconds to a few minutes); 5 minutes per image, one at a time.
GENERATE_TIMEOUT_S = 300
LOGIN_CHECK_TIMEOUT_S = 60


class FlowUnavailable(RuntimeError):
    """Playwright or the Chromium binary is missing on this PC."""


class FlowNotLoggedIn(RuntimeError):
    """No signed-in Google session in the shared profile."""


class FlowPageChanged(RuntimeError):
    """The Flow page no longer matches the selectors below."""


class FlowUnusualActivity(RuntimeError):
    """Flow showed its 'Unusual Activity' block (bulk load). The
    fix is the guided 1-minute recovery (clear Flow site data ->
    reload -> resume queue) — the worker treats this as 'blocked',
    never as a retryable generation failure, and marks the account
    so rotation tries another account instead of hammering this one."""


def set_profile_dir(path: Path) -> None:
    # The shared Google profile — the same directory Canvas uses.
    _gb.set_profile_dir(path)


def clear_site_data(profile_dir: str | Path | None = None) -> dict:
    """Slice 5 recovery step: clear Flow's on-device site data in
    one account's profile (site-scoped cookies + storage — the
    Google sign-in stays). See google_browser.clear_site_data."""
    return _gb.clear_site_data(FLOW_URL, profile_dir=profile_dir)


def flow_available() -> tuple[bool, str]:
    """(available, reason). available=True means Playwright imports
    AND a Chromium binary can be launched — no browser is started
    here, so this is cheap enough for the status endpoints."""
    return _gb.browser_available(
        FLOW_PLAYWRIGHT_MISSING_MSG, FLOW_BROWSER_MISSING_MSG
    )


# --- login state ----------------------------------------------------------

# Selector candidates, best first. Flow's workspace has a prompt
# composer for new generations and a Create action; the Google
# account avatar is the same header as Gemini's. BEST-EFFORT:
# Flow's DOM was never probed live in this VM (see the header) —
# if none of these match, check_login reports the page as
# unrecognised (never a guess), and the worker blocks the jobs
# with the plain login message.
_COMPOSER_SELECTORS = [
    'textarea[placeholder*="Describe"]',
    'div[contenteditable="true"][role="textbox"]',
    '[aria-label*="prompt" i]',
    'div[contenteditable="true"]',
    "textarea",
]
_CREATE_SELECTORS = [
    'button:has-text("Create")',
    '[aria-label*="Create"]',
]
_SIGNIN_SELECTORS = [
    'a:has-text("Sign in")',
    'button:has-text("Sign in")',
]
_AVATAR_SELECTORS = [
    'button[aria-label*="Google Account"]',
    'img[alt*="Google Account"]',
]


def _first_visible(page, selectors: list[str], timeout_ms: int = 5000):
    """First selector that becomes visible, or None."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except Exception:
            continue
    return None


def _project_fragment(url: str) -> str | None:
    """Best-effort: the open Flow project's ID fragment from the
    page URL (Flow Automator shows the same thing — green Ready +
    first 4 characters of the project ID). None when the URL carries
    no project — the indicator then honestly shows 'project unknown',
    never a guessed ID."""
    for pattern in (
        r"/projects/([A-Za-z0-9_-]{4,})",
        r"[?&]project=([A-Za-z0-9_-]{4,})",
    ):
        m = re.search(pattern, url or "")
        if m:
            return m.group(1)[:4]
    return None


def _page_unusual(page) -> bool:
    """Best-effort: does the loaded Flow page show the 'Unusual
    Activity' block? A read failure is not a block (False)."""
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    return _fh.detect_unusual_activity(text)


def check_login(timeout_s: int = LOGIN_CHECK_TIMEOUT_S,
                profile_dir: str | Path | None = None) -> dict:
    """Open flow.google.com in the shared profile (headless) and
    report whether a signed-in Google session exists. Returns
    {"logged_in": bool, "detail": str, "project_id_fragment": str |
    None, "unusual_activity": bool}. Raises FlowUnavailable when
    Playwright / Chromium is missing; any other browser failure is a
    plain RuntimeError, never a guessed login state. Slice 5:
    profile_dir overrides the shared profile (one dir per Flow
    account, for rotation)."""
    ok, reason = flow_available()
    if not ok:
        raise FlowUnavailable(reason)
    try:
        with _gb.headless_page(
            FLOW_URL, timeout_s, profile_dir=profile_dir
        ) as (page, _ctx):
            page.wait_for_timeout(3000)
            url = page.url or ""
            unusual = _page_unusual(page)
            fragment = _project_fragment(url)
            base = {
                "project_id_fragment": fragment,
                "unusual_activity": unusual,
            }
            if unusual:
                # The block shows even when a session exists — the
                # login is real, but Flow will not generate until
                # the recovery runs. Report it as its own state.
                return {
                    "logged_in": True,
                    "detail": _fh.RECOVERY_MSG,
                    **base,
                }
            if "accounts.google.com" in url:
                return {
                    "logged_in": False,
                    "detail": "Google sign-in page khula — login nahi hai",
                    **base,
                }
            if _first_visible(page, _SIGNIN_SELECTORS, 5000) is not None:
                return {
                    "logged_in": False,
                    "detail": "Sign in button dikh raha hai — login nahi hai",
                    **base,
                }
            if _first_visible(page, _COMPOSER_SELECTORS, 8000) is not None:
                return {"logged_in": True, "detail": "Flow composer khula hai", **base}
            if _first_visible(page, _CREATE_SELECTORS, 5000) is not None:
                return {"logged_in": True, "detail": "Flow Create button dikh raha hai", **base}
            if _first_visible(page, _AVATAR_SELECTORS, 5000) is not None:
                return {"logged_in": True, "detail": "Google account avatar dikh raha hai", **base}
            return {
                "logged_in": False,
                "detail": "Flow page pehchana nahi gaya — login state unclear",
                **base,
            }
    except (FlowUnavailable, RuntimeError):
        raise
    except Exception as exc:
        # The page itself never loaded (network / proxy / browser
        # crash) — that is not a login verdict, so it is a plain
        # error, never a guessed "logged in" or "not logged in".
        raise RuntimeError(
            "Flow page nahi khul saki — network ya browser issue hai,"
            " is PC par check karein"
        )


# --- image generation -----------------------------------------------------

def _image_urls(page) -> list[str]:
    """Image URLs in the workspace. Flow serves generated images
    from Google's image hosts (googleusercontent.com among them);
    anything http(s) in an <img> counts — the before/after diff is
    what proves a NEW image arrived."""
    urls: list[str] = []
    try:
        for img in page.locator("img[src^='http']").all():
            src = img.get_attribute("src") or ""
            if src.startswith("http"):
                urls.append(src)
    except Exception:
        pass
    return urls


def _looks_like_image(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" or (
        data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    )


def _mime_of(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _attach_reference(page, ref_path: str | None) -> bool:
    """Best-effort: attach the character sheet image to the Flow
    composer (it accepts an image alongside the prompt) so the model
    sees the locked face/outfit. No file input on the page, a missing
    file, or an upload error means prompt-only generation — the
    prompt still carries the name, description and negative
    constraint. Never raises: a failed attach must not fail the
    image. Live attach is NOT verified in this VM (no Google login
    here); the first real attach waits for Ali's PC sign-in."""
    if not ref_path:
        return False
    try:
        path = Path(ref_path)
        if not path.is_file():
            return False
        for inp in page.locator('input[type="file"]').all():
            try:
                inp.set_input_files(str(path))
                page.wait_for_timeout(1500)
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def generate_image(
    prompt: str,
    timeout_s: int = GENERATE_TIMEOUT_S,
    ref_path: str | None = None,
    profile_dir: str | Path | None = None,
) -> tuple[bytes, str]:
    """Generate one image in Google Flow and return
    (image_bytes, mime). Same contract as the Canvas provider, so
    the worker calls it the same way. Raises FlowNotLoggedIn (no
    Google session), FlowPageChanged (the page no longer matches
    the selectors), FlowUnusualActivity (Flow's bulk-load block —
    guided recovery needed), FlowUnavailable (Playwright / Chromium
    missing) or RuntimeError (generation failed or timed out).
    Never returns a placeholder or a fake image.
    Slice 5: profile_dir picks the account's browser profile
    (rotation); None = the shared profile.

    BEST-EFFORT (see the header): Flow's exact image flow — which
    composer mode makes a still image vs a video clip — was never
    probed live here. The provider types the prompt into the
    workspace composer and submits it; if the live UI needs a mode
    switch first, the composer lookup misses, FlowPageChanged is
    raised, and the worker falls back to Canvas on the same job."""
    ok, reason = flow_available()
    if not ok:
        raise FlowUnavailable(reason)
    # Slice 3 (Magic Mode): the aspect the prompt already carries
    # (9:16 / 1:1 note from build_image_prompt) decides the shape
    # line — a 9:16 run must not ask Flow for a 16:9 landscape.
    if "Vertical 9:16" in prompt:
        shape_line = (
            "Generate this exact scene as a 9:16 vertical still image."
        )
    elif "Square 1:1" in prompt:
        shape_line = (
            "Generate this exact scene as a 1:1 square still image."
        )
    else:
        shape_line = (
            "Generate this exact scene as a 16:9 landscape still image."
        )
    full_prompt = prompt.strip() + "\n\n" + shape_line
    try:
        with _gb.headless_page(
            FLOW_URL, LOGIN_CHECK_TIMEOUT_S, profile_dir=profile_dir
        ) as (page, ctx):
            page.wait_for_timeout(3000)
            if "accounts.google.com" in (page.url or ""):
                raise FlowNotLoggedIn(FLOW_LOGIN_MSG)
            if _page_unusual(page):
                raise FlowUnusualActivity(_fh.RECOVERY_MSG)
            composer = _first_visible(page, _COMPOSER_SELECTORS, 15000)
            if composer is None:
                if _first_visible(page, _SIGNIN_SELECTORS, 3000) is not None:
                    raise FlowNotLoggedIn(FLOW_LOGIN_MSG)
                raise FlowPageChanged(FLOW_PAGE_CHANGED_MSG)
            before = set(_image_urls(page))
            # Slice 3 auto-consistency: attach the character sheet
            # when one is given (best-effort — no file input on the
            # page means prompt-only generation, never a failure).
            if ref_path:
                _attach_reference(page, ref_path)
            composer.click()
            try:
                composer.fill(full_prompt)
            except Exception:
                # Rich-text editors sometimes reject fill — type it.
                page.keyboard.type(full_prompt, delay=5)
            page.wait_for_timeout(500)
            create = _first_visible(page, _CREATE_SELECTORS, 3000)
            if create is not None:
                create.click()
            else:
                # Enter submits in the Flow composer.
                page.keyboard.press("Enter")
            deadline = time.monotonic() + timeout_s
            last_text = ""
            while time.monotonic() < deadline:
                page.wait_for_timeout(5000)
                now = [u for u in _image_urls(page) if u not in before]
                if now:
                    resp = ctx.request.get(now[-1], timeout=60000)
                    if resp.ok:
                        data = resp.body()
                        if len(data) > 10_000 and _looks_like_image(data):
                            return data, _mime_of(data)
                        raise RuntimeError(
                            "Flow se image download hui lekin file"
                            " image nahi lagi — dobara try karein"
                        )
                    raise RuntimeError(
                        f"Flow image download fail ({resp.status})"
                        " — dobara try karein"
                    )
                # The model sometimes answers in text that it cannot
                # generate the image — surface that instead of waiting
                # out the whole timeout. Only the latest text is
                # checked, so an old generation cannot trip this.
                try:
                    body_text = page.locator("body").inner_text(timeout=3000)
                    last_text = body_text[-2000:]
                    lowered = last_text.lower()
                    # Slice 5: Flow's bulk-load block can appear
                    # mid-generation — stop at once with the guided
                    # recovery, instead of waiting out the timeout
                    # and reporting a plain timeout.
                    if _fh.detect_unusual_activity(last_text):
                        raise FlowUnusualActivity(_fh.RECOVERY_MSG)
                    if ("can't generate images" in lowered
                            or "cannot generate images" in lowered
                            or "i can't create images" in lowered):
                        raise RuntimeError(
                            "Flow ne image banane se mana kar diya:"
                            f" {last_text[-200:].strip()}"
                        )
                except (RuntimeError, FlowUnusualActivity):
                    raise
                except Exception:
                    pass
            raise RuntimeError(
                "Flow ne time par image nahi banayi"
                f" ({timeout_s}s) — dobara try karein"
            )
    except (
        FlowUnavailable,
        FlowNotLoggedIn,
        FlowPageChanged,
        RuntimeError,
    ):
        raise
    except Exception as exc:
        # Browser / network failure mid-generation — a plain error,
        # never a half-made image or a silent pass.
        raise RuntimeError(
            "Flow browser me masla — network ya browser issue hai,"
            f" dobara try karein ({exc.__class__.__name__})"
        )
