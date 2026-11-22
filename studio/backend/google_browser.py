# Shared Google browser profile for the Canvas + Flow providers —
# ONE Google sign-in opens both gemini.google.com (Canvas) and
# flow.google.com (Flow). Both providers run Playwright against the
# SAME persistent profile directory (studio/data/canvas-profile/),
# so the login cookies live in one place only and are never stored
# anywhere else. No password, key or credential is ever handled
# here — the user signs in once, in a visible browser window, and
# closes it; the profile keeps the session after that.
#
# This module owns the machinery the Canvas provider used to own
# alone: cached-Chromium resolution, launch options, the headless
# page helper, and the login-window lock. canvas_provider.py now
# delegates to it, and flow_provider.py uses the same calls, so a
# fix here fixes both providers. Nothing in this module knows
# about either app's page layout — the selectors live in the
# provider modules.
#
# Honest caveats (same as Canvas, recorded in PROJECT_STATE.md):
# - FRAGILE / ToS-grey: browser automation against Google's web
#   pages. If Google changes a page, that provider fails with a
#   plain "page badal gaya" message — never a fake success.
# - Two persistent Chromium contexts on the SAME profile directory
#   conflict (profile lock): a generation running while the login
#   window is open fails with a plain message. The login-window
#   lock below stops two login windows; it cannot stop a
#   generation that is already running, so the user is told to
#   close the login window before generating.

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# The account page the "Connect Google" button opens. Any Google
# sign-in page works (all redirect to accounts.google.com); the
# account home is the neutral one — it signs the profile into
# Google itself, not into one app, so Canvas and Flow both pick
# the session up afterwards.
GOOGLE_ACCOUNT_URL = "https://myaccount.google.com"

PLAYWRIGHT_MISSING_MSG = (
    "Playwright install nahi hai — launcher se dobara chalaiye"
    " (requirements.txt me hai), ya 'pip install playwright' karein"
)
BROWSER_MISSING_MSG = (
    "Chromium browser nahi mila — 'python -m playwright install"
    " chromium' ek dafa chalaiye, phir dobara try karein"
)

# The persistent browser profile: Google login cookies live here and
# nowhere else. Set by main.py at import (DATA_DIR / "canvas-profile"
# — the name stays, so an existing Canvas login keeps working).
PROFILE_DIR: Path | None = None


def set_profile_dir(path: Path) -> None:
    global PROFILE_DIR
    PROFILE_DIR = path


def get_profile_dir() -> Path | None:
    return PROFILE_DIR


def _profile_dir() -> Path:
    if PROFILE_DIR is None:
        raise RuntimeError("Google browser profile dir is not configured")
    return PROFILE_DIR


# --- browser resolution ---------------------------------------------------

def _playwright():
    """Import Playwright lazily — the app must still start without
    it, and the status endpoints must say so plainly."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        return sync_playwright
    except ImportError:
        return None


def _cached_chromium_executable() -> Path | None:
    """A Chromium binary Playwright already downloaded, newest first.
    Used when `playwright install chromium` was never run for the
    installed Playwright version (its default binary is missing) but
    an older cached build exists — the build VM is exactly this case.
    Only real files under the Playwright cache are considered."""
    cache = Path.home() / ".cache" / "ms-playwright"
    if not cache.is_dir():
        return None
    cands: list[Path] = []
    for d in cache.iterdir():
        if not d.is_dir():
            continue
        for exe in (
            d / "chrome-linux" / "chrome",
            d / "chrome-headless-shell-linux64" / "chrome-headless-shell",
        ):
            if exe.is_file() and os.access(exe, os.X_OK):
                cands.append(exe)
    if not cands:
        return None
    # Newest build first: chromium-1194 beats chromium-1148.
    return sorted(cands, reverse=True)[0]


def browser_available(
    playwright_msg: str = PLAYWRIGHT_MISSING_MSG,
    browser_msg: str = BROWSER_MISSING_MSG,
) -> tuple[bool, str]:
    """(available, reason). available=True means Playwright imports
    AND a Chromium binary can be launched — no browser is started
    here, so this is cheap enough for the status endpoints. Callers
    pass their own wording so each provider keeps its exact
    user-facing message."""
    if _playwright() is None:
        return False, playwright_msg
    if _cached_chromium_executable() is not None:
        return True, ""
    # No cached build: maybe Playwright's own default binary exists
    # (installed via `playwright install chromium`). Try a real
    # launch-free check through the driver metadata.
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if exe and Path(exe).is_file():
            return True, ""
    except Exception:
        pass
    return False, browser_msg


def _launch_kwargs() -> dict:
    """Launch options: prefer Playwright's default binary; fall back
    to a cached Chromium build (see _cached_chromium_executable)."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if exe and Path(exe).is_file():
            return {}
    except Exception:
        pass
    cached = _cached_chromium_executable()
    if cached is not None:
        return {"executable_path": str(cached)}
    return {}


@contextmanager
def headless_page(url: str, timeout_s: int = 60,
                  profile_dir: str | Path | None = None):
    """Yield (page, context) in a headless persistent-context browser
    on the shared Google profile, and close everything on exit.
    The caller owns the page checks; any Playwright failure (page
    never loaded, browser crash) propagates as-is — the provider
    turns it into its own plain message, never a guessed state.
    Slice 5 (multi-account rotation): profile_dir overrides the
    shared profile, so each Flow account runs on its own profile
    directory — two contexts on the SAME profile fight over the
    profile lock, so rotation needs separate dirs. None = the
    shared profile (unchanged behaviour)."""
    sync_playwright = _playwright()
    profile = (
        Path(profile_dir) if profile_dir is not None else _profile_dir()
    )
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=True,
            **_launch_kwargs(),
        )
        try:
            page = ctx.new_page()
            page.goto(url, timeout=timeout_s * 1000,
                      wait_until="domcontentloaded")
            yield page, ctx
        finally:
            ctx.close()


# --- one-time login window ------------------------------------------------

_login_lock = threading.Lock()
_login_open = False
# Set once the login window has really opened (page loaded) — the
# endpoint waits for this, not just for the "launch started" flag, so
# a failed launch is never reported as an opened browser.
_login_opened = threading.Event()


def open_login_window(url: str, timeout_s: int = 60,
                      profile_dir: str | Path | None = None) -> None:
    """Open `url` in the shared profile with a VISIBLE browser
    window, so the user signs into Google once. Blocks until the
    user closes the window; the profile keeps the login after that.
    The lock is shared by Canvas and Google login windows — two
    persistent contexts on the same profile directory would fight
    over the profile lock, so the second caller gets a plain
    RuntimeError instead. Run in a thread: the endpoint returns
    while this waits for the window to close.
    Slice 5: profile_dir overrides the shared profile, so a 2nd/3rd
    Flow account signs in on its own profile directory (None = the
    shared profile, unchanged behaviour)."""
    global _login_open
    with _login_lock:
        if _login_open:
            raise RuntimeError("Google login browser pehle se khula hai")
        _login_open = True
    _login_opened.clear()
    try:
        sync_playwright = _playwright()
        if sync_playwright is None:
            raise RuntimeError(PLAYWRIGHT_MISSING_MSG)
        profile = (
            Path(profile_dir) if profile_dir is not None
            else _profile_dir()
        )
        profile.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile),
                headless=False,
                **_launch_kwargs(),
            )
            try:
                page = ctx.new_page()
                page.goto(url, timeout=timeout_s * 1000)
                _login_opened.set()
                # Wait until the user closes the window (or the page
                # is gone). Poll: the context closes when the last
                # page/window closes.
                while ctx.pages:
                    time.sleep(2)
            finally:
                ctx.close()
    finally:
        with _login_lock:
            _login_open = False
        _login_opened.clear()


def login_window_open() -> bool:
    with _login_lock:
        return _login_open


def login_window_opened() -> bool:
    """True once the login window has actually opened (page loaded)."""
    return _login_opened.is_set()


# --- Slice 5: "Unusual Activity" recovery --------------------------------
# Flow's 1-minute fix (Video 3 transcript): clear Flow's on-device
# site data, reload, resume the queue. This automates the site-data
# half IN the account's profile: Flow's cookies (site-scoped only —
# never all cookies, so the Google sign-in itself stays) + Flow's
# local/session storage on the Flow page. Best-effort per step: a
# step that fails is reported, never hidden, and the caller decides
# (the manual browser steps stay documented in the UI as fallback).

def clear_site_data(url: str, profile_dir: str | Path | None = None,
                    timeout_s: int = 60) -> dict:
    """Clear one site's data in a profile. Returns {cleared, detail}.
    Raises RuntimeError when Playwright / Chromium is missing or the
    page never loads — the caller turns that into a plain message."""
    from urllib.parse import urlparse

    sync_playwright = _playwright()
    if sync_playwright is None:
        raise RuntimeError(PLAYWRIGHT_MISSING_MSG)
    profile = (
        Path(profile_dir) if profile_dir is not None else _profile_dir()
    )
    profile.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).hostname or ""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=True,
            **_launch_kwargs(),
        )
        try:
            page = ctx.new_page()
            page.goto(url, timeout=timeout_s * 1000,
                      wait_until="domcontentloaded")
            cleared: list[str] = []
            try:
                page.evaluate(
                    "() => { localStorage.clear();"
                    " sessionStorage.clear(); }"
                )
                cleared.append("site storage")
            except Exception:
                pass
            # Site-scoped cookies only: clearing ALL cookies would
            # sign the user out of Google — the video's fix keeps
            # the sign-in and deletes only the Flow entries.
            for domain in (host, f".{host}"):
                try:
                    ctx.clear_cookies(domain=domain)
                    cleared.append(f"cookies ({domain})")
                except Exception:
                    continue
            if not cleared:
                return {
                    "cleared": False,
                    "detail": (
                        "site data clear nahi ho saka — browser me"
                        " manual steps se karein (site-info icon →"
                        " Cookies and site data → Manage on-device"
                        " site data → Flow entries delete karein)"
                    ),
                }
            return {
                "cleared": True,
                "detail": (
                    "Flow ka site data clear ho gaya"
                    f" ({', '.join(cleared)}) — page reload karein"
                    " aur queue resume karein"
                ),
            }
        finally:
            ctx.close()
