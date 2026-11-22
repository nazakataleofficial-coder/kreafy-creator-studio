# Gemini Canvas provider for VisualForge — free images through the
# Gemini web app (gemini.google.com) driven by Playwright, on the
# user's own Google login + Gemini Pro quota.
#
# Why this exists (Ali's decision 2026-11-21 ~09:42 PKT, "Canvas wala
# free rasta banao"): the Gemini API image models have a free-tier
# limit of 0 on Ale's key (verified live: gemini-2.5-flash-image and
# gemini-3.1-flash-image both return 429 RESOURCE_EXHAUSTED), so API
# images need billing. The inspiration tools (AutoCut / StickFilm /
# FrameLoom, see VIDEO_NOTES.md) get their "free" images from the
# Gemini Canvas web app on the user's own Google login — this provider
# is Kreafy's own route to the same place, against gemini.google.com
# directly. It does NOT depend on Mr Hasnain's third-party Canvas app
# or any third-party Canvas link.
#
# Shared profile: the browser machinery (cached-Chromium lookup,
# launch options, headless page, login-window lock) lives in
# google_browser.py and is SHARED with the Flow provider — one
# Google sign-in opens Canvas and Flow both. This module keeps only
# the Canvas page itself: its URL, messages, exceptions and
# selectors. The public names below (messages, exceptions,
# canvas_available / check_login / generate_image /
# open_login_window / login_window_open / login_window_opened) are
# unchanged — the worker and the endpoints call them exactly as
# before.
#
# Honest caveats (told to Ali, recorded in PROJECT_STATE.md):
# - FRAGILE / ToS-grey: this drives Google's web page with browser
#   automation. If Google changes the page, the selectors below miss
#   and the job FAILS with the plain message "Canvas page badal gaya
#   — provider update chahiye" — never a fake success, never a
#   silent pass.
# - NO credentials are stored anywhere. The route uses a persistent
#   Playwright browser profile (studio/data/canvas-profile/) that the
#   user signs into ONCE with their own Google account; the login
#   cookies live in that profile folder only. No password or OTP is
#   ever asked for by this code.
# - The live generation path is UNVERIFIED in the build VM: no Google
#   login exists there (Ali is on mobile, laptop dead), so the worker
#   is verified only up to the login gate. The first real generation
#   happens on Ali's PC after his one-time sign-in.
#
# Selectors below are best-effort, from the gemini.google.com DOM as
# known in 2026. Every lookup has a short timeout and falls through
# to the next candidate; when none match, the caller raises
# CanvasPageChanged instead of guessing.

from __future__ import annotations

import time
from pathlib import Path

import google_browser as _gb

CANVAS_URL = "https://gemini.google.com/app"

# Exact messages the user sees (Roman Urdu, plain). These strings are
# part of the provider's contract — the login-gate test asserts them.
CANVAS_LOGIN_MSG = (
    "Canvas ke liye Google login nahi hai — VisualForge me 'Canvas login"
    " kholein' se ek dafa Google sign-in karein, phir dobara try karein"
)
CANVAS_PAGE_CHANGED_MSG = (
    "Canvas page badal gaya — provider update chahiye"
)
CANVAS_BROWSER_MISSING_MSG = (
    "Canvas browser nahi mila — ek dafa 'playwright install chromium'"
    " chalayein, phir dobara try karein"
)
CANVAS_PLAYWRIGHT_MISSING_MSG = (
    "Canvas ke liye Playwright chahiye — 'pip install playwright'"
    " chalayein, phir dobara try karein"
)

# How long one Canvas image may take. Gemini web generation is slow
# (tens of seconds to a few minutes); 5 minutes per image, one image
# at a time, like the API worker.
GENERATE_TIMEOUT_S = 300
LOGIN_CHECK_TIMEOUT_S = 60

# The persistent browser profile: Google login cookies live here and
# nowhere else. Set by main.py at import (DATA_DIR / "canvas-profile").
PROFILE_DIR: Path | None = None


class CanvasUnavailable(RuntimeError):
    """Playwright or the Chromium binary is missing on this PC."""


class CanvasNotLoggedIn(RuntimeError):
    """No signed-in Google session in the Canvas profile."""


class CanvasPageChanged(RuntimeError):
    """The Gemini page no longer matches the selectors below."""


def set_profile_dir(path: Path) -> None:
    global PROFILE_DIR
    PROFILE_DIR = path
    # The same directory is the shared Google profile — the Flow
    # provider (and the Connect Google button) use it too, so one
    # sign-in covers both.
    _gb.set_profile_dir(path)


def _profile_dir() -> Path:
    if PROFILE_DIR is None:
        raise CanvasUnavailable("Canvas profile dir is not configured")
    return PROFILE_DIR


def canvas_available() -> tuple[bool, str]:
    """(available, reason). available=True means Playwright imports
    AND a Chromium binary can be launched — no browser is started
    here, so this is cheap enough for the status endpoint."""
    return _gb.browser_available(
        CANVAS_PLAYWRIGHT_MISSING_MSG, CANVAS_BROWSER_MISSING_MSG
    )


# --- login state ----------------------------------------------------------

# Selector candidates, best first. The Gemini composer is a rich-text
# box; the send button and the account avatar are the other stable
# anchors. If Google changes any of these, check_login falls through
# to "not logged in" only when a sign-in control is actually visible;
# otherwise it reports the page as unrecognised (never a guess).
_COMPOSER_SELECTORS = [
    'div[contenteditable="true"][role="textbox"]',
    '[aria-label*="Ask Gemini"]',
    'div[contenteditable="true"]',
    "textarea",
]
_SEND_SELECTORS = [
    'button[aria-label="Send message"]',
    'button[aria-label*="Send"]',
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


def check_login(timeout_s: int = LOGIN_CHECK_TIMEOUT_S) -> dict:
    """Open gemini.google.com in the persistent profile (headless) and
    report whether a signed-in Google session exists. Returns
    {"logged_in": bool, "detail": str}. Raises CanvasUnavailable when
    Playwright / Chromium is missing; any other browser failure is a
    plain RuntimeError, never a guessed login state."""
    ok, reason = canvas_available()
    if not ok:
        raise CanvasUnavailable(reason)
    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    try:
        with _gb.headless_page(CANVAS_URL, timeout_s) as (page, _ctx):
            page.wait_for_timeout(3000)
            url = page.url or ""
            if "accounts.google.com" in url:
                return {
                    "logged_in": False,
                    "detail": "Google sign-in page khula — login nahi hai",
                }
            if _first_visible(page, _SIGNIN_SELECTORS, 5000) is not None:
                return {
                    "logged_in": False,
                    "detail": "Sign in button dikh raha hai — login nahi hai",
                }
            if _first_visible(page, _COMPOSER_SELECTORS, 8000) is not None:
                return {"logged_in": True, "detail": "Gemini composer khula hai"}
            if _first_visible(page, _AVATAR_SELECTORS, 5000) is not None:
                return {"logged_in": True, "detail": "Google account avatar dikh raha hai"}
            return {
                "logged_in": False,
                "detail": "Canvas page pehchana nahi gaya — login state unclear",
            }
    except (CanvasUnavailable, RuntimeError):
        raise
    except Exception as exc:
        # The page itself never loaded (network / proxy / browser
        # crash) — that is not a login verdict, so it is a plain
        # error, never a guessed "logged in" or "not logged in".
        raise RuntimeError(
            "Canvas page nahi khul saki — network ya browser issue hai,"
            " is PC par check karein"
        )


# --- image generation -----------------------------------------------------

def _image_urls(page) -> list[str]:
    """Image URLs in the conversation (Gemini serves generated images
    from googleusercontent.com)."""
    urls: list[str] = []
    try:
        for img in page.locator('img[src*="googleusercontent.com"]').all():
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
    """MIME type from the magic bytes — the worker saves by mime, so
    a wrong guess would mislabel the file."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _attach_reference(page, ref_path: str | None) -> bool:
    """Best-effort: attach the character sheet image to the Gemini
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
    """Generate one image in the Gemini web app and return
    (image_bytes, mime). Raises CanvasNotLoggedIn (no Google
    session), CanvasPageChanged (the page no longer matches the
    selectors), CanvasUnavailable (Playwright / Chromium missing) or
    RuntimeError (generation failed or timed out). Never returns a
    placeholder or a fake image.

    NOTE (2026-11-21, Connect Google slice): this used to return
    bare bytes while the worker unpacked TWO values
    (image_bytes, mime) — the Canvas success path could never have
    run. The tuple return matches the API provider and the worker;
    the white-box worker test in this slice proves it."""
    ok, reason = canvas_available()
    if not ok:
        raise CanvasUnavailable(reason)
    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    # Slice 3 (Magic Mode): the aspect the prompt already carries
    # (9:16 / 1:1 note from build_image_prompt) decides the shape
    # line — a 9:16 run must not ask Canvas for a 16:9 landscape.
    if "Vertical 9:16" in prompt:
        shape_line = "Generate this exact scene as a 9:16 vertical image."
    elif "Square 1:1" in prompt:
        shape_line = "Generate this exact scene as a 1:1 square image."
    else:
        shape_line = "Generate this exact scene as a 16:9 landscape image."
    full_prompt = prompt.strip() + "\n\n" + shape_line
    try:
        with _gb.headless_page(CANVAS_URL, LOGIN_CHECK_TIMEOUT_S, profile_dir=profile_dir) as (page, ctx):
            page.wait_for_timeout(3000)
            if "accounts.google.com" in (page.url or ""):
                raise CanvasNotLoggedIn(CANVAS_LOGIN_MSG)
            composer = _first_visible(page, _COMPOSER_SELECTORS, 15000)
            if composer is None:
                if _first_visible(page, _SIGNIN_SELECTORS, 3000) is not None:
                    raise CanvasNotLoggedIn(CANVAS_LOGIN_MSG)
                raise CanvasPageChanged(CANVAS_PAGE_CHANGED_MSG)
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
            send = _first_visible(page, _SEND_SELECTORS, 3000)
            if send is not None:
                send.click()
            else:
                # Enter sends in the Gemini composer.
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
                            "Canvas se image download hui lekin file"
                            " image nahi lagi — dobara try karein"
                        )
                    raise RuntimeError(
                        f"Canvas image download fail ({resp.status})"
                        " — dobara try karein"
                    )
                # The model sometimes answers in text that it cannot
                # generate the image — surface that instead of waiting
                # out the whole timeout. Only the latest text is
                # checked, so an old conversation cannot trip this.
                try:
                    body_text = page.locator("body").inner_text(timeout=3000)
                    last_text = body_text[-2000:]
                    lowered = last_text.lower()
                    if ("can't generate images" in lowered
                            or "cannot generate images" in lowered
                            or "i can't create images" in lowered):
                        raise RuntimeError(
                            "Canvas ne image banane se mana kar diya:"
                            f" {last_text[-200:].strip()}"
                        )
                except RuntimeError:
                    raise
                except Exception:
                    pass
            raise RuntimeError(
                "Canvas ne time par image nahi banayi"
                f" ({timeout_s}s) — dobara try karein"
            )
    except (
        CanvasUnavailable,
        CanvasNotLoggedIn,
        CanvasPageChanged,
        RuntimeError,
    ):
        raise
    except Exception as exc:
        # Browser / network failure mid-generation — a plain error,
        # never a half-made image or a silent pass.
        raise RuntimeError(
            "Canvas browser me masla — network ya browser issue hai,"
            f" dobara try karein ({exc.__class__.__name__})"
        )


# --- one-time login window ------------------------------------------------

def open_login_window() -> None:
    """Open gemini.google.com in the persistent profile with a VISIBLE
    browser window, so the user signs into Google once. Blocks until
    the user closes the window; the profile keeps the login after
    that. Raises CanvasUnavailable (no Playwright / Chromium) or
    RuntimeError (already open, or no display to open a window on —
    e.g. a headless server). Run in a thread: the endpoint returns
    immediately while this waits for the window to close."""
    if login_window_open():
        raise RuntimeError("Canvas login browser pehle se khula hai")
    ok, reason = canvas_available()
    if not ok:
        raise CanvasUnavailable(reason)
    _gb.open_login_window(CANVAS_URL)


def login_window_open() -> bool:
    return _gb.login_window_open()


def login_window_opened() -> bool:
    """True once the login window has actually opened (page loaded)."""
    return _gb.login_window_opened()
