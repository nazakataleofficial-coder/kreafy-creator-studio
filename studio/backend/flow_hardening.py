# Flow provider hardening (Slice 5) — pure logic, no browser, no DB.
#
# Why this module exists (research report A1–A6, videos 3/4/8 — Try AI
# Today / Flow Automator): bulk Flow generation hits exactly three
# failure modes, and the Studio should handle them instead of failing
# silently:
#   1. "Unusual Activity" — Flow blocks the account under bulk load.
#      Fix (Video 3 transcript, verified): clear on-device site data
#      for Flow -> reload -> resume queue, under 1 minute.
#   2. Rate limits (429) under parallel load — backoff, never a retry
#      storm.
#   3. One account = one quota — rotate up to 3 accounts (same idea
#      as multiple API keys).
# Plus the Automator's own UX: queue history + re-download as ZIP,
# persistent queue with pause/resume, a Ready indicator, and the
# #name / @name chaining syntax (linked to the Character Vault).
#
# Everything here is pure and white-box testable. The browser/DB
# wiring lives in flow_provider.py / google_browser.py / main.py.
# Nothing in this module is ever faked: detection returns what the
# text actually says, backoff is real sleeping (in the worker), and
# an unknown #/@ name is reported, never silently resolved.

from __future__ import annotations

import random
import re

# --- Slice 5: "Unusual Activity" ---------------------------------------
# Flow's own wording (Video 3, transcript-verified): "Unusual
# Activity". Google also shows "unusual traffic" / "suspicious
# activity" on the same class of block. Match case-insensitively;
# a page that merely mentions the words in a help article would
# also match — the provider only calls this on the live Flow
# workspace page text, where the words mean the block.

UNUSUAL_ACTIVITY_PATTERNS = [
    re.compile(r"unusual activity", re.IGNORECASE),
    re.compile(r"unusual traffic", re.IGNORECASE),
    re.compile(r"suspicious activity", re.IGNORECASE),
    re.compile(r"detected unusual", re.IGNORECASE),
]


def detect_unusual_activity(text: str | None) -> bool:
    """True when the text is Flow/Google's 'Unusual Activity' block.
    None / empty text is never a block — no guess from nothing."""
    if not text:
        return False
    return any(p.search(text) for p in UNUSUAL_ACTIVITY_PATTERNS)


# The guided 1-minute recovery (Video 3 transcript): stay signed in,
# clear on-device site data for Flow, reload, resume the queue. The
# in-app "Site data clear karein" button automates step 3 for the
# account's profile; the manual steps stay documented as the
# fallback, because the browser's own site-data UI is the version
# Google itself documents.
RECOVERY_STEPS = [
    "Flow tab me address bar ke left side wala site-info icon dabayein.",
    "'Cookies and site data' kholein, phir 'Manage on-device site data' dabayein.",
    "Flow ki har entry delete karein (site data clear) — ya Studio me 'Site data clear karein' dabayein, Studio khud kar dega.",
    "Flow page reload karein — Flow dobara naya khulega.",
    "Queue resume karein — ruki hui images wahin se dobara banengi.",
]
RECOVERY_TIP = (
    "Agar 'Unusual Activity' baar baar aaye to VPN use karein — "
    "kuch users ko is se farq para hai (Video 3)."
)
RECOVERY_MSG = (
    "Flow ne 'Unusual Activity' dikhaya — bulk load par Flow account"
    " ko rok deta hai. 1 minute ka fix: Flow ka site data clear"
    " karein, page reload karein, phir queue resume karein."
    " VisualForge me recovery steps dikh rahe hain."
)

# --- Slice 5: rate limits + backoff ------------------------------------
# 429 / quota text is a rate limit, never a content/policy failure:
# the same attempt may be retried after a backoff, up to 2 extra
# times. Anything else is decided by the retry ladder, not here.

RATE_LIMIT_PATTERNS = [
    re.compile(r"\b429\b"),
    re.compile(r"rate[ _]limit", re.IGNORECASE),
    re.compile(r"too[ _]many[ _]requests", re.IGNORECASE),
    re.compile(r"quota[ _]exceeded", re.IGNORECASE),
    re.compile(r"resource[ _]exhausted", re.IGNORECASE),
]


def is_rate_limit_error(text: str | None) -> bool:
    """True when the error text is a rate limit / quota error."""
    if not text:
        return False
    return any(p.search(text) for p in RATE_LIMIT_PATTERNS)


def backoff_delay_s(attempt: int, base_s: float = 2.0,
                     cap_s: float = 60.0, jitter: bool = True) -> float:
    """Exponential backoff for one retry: base * 2**attempt, capped.
    attempt 0 -> base, 1 -> 2x base, 2 -> 4x base ... Jitter (+0-1 s)
    spreads simultaneous retries so they never storm together.
    jitter=False is for tests (deterministic)."""
    delay = min(cap_s, base_s * (2 ** max(0, attempt)))
    if jitter:
        delay += random.uniform(0, 1.0)
    return round(delay, 2)


# --- Slice 5: multi-account rotation ------------------------------------

FLOW_MAX_ACCOUNTS = 3
FLOW_FAST_MIN_CONCURRENCY = 1
FLOW_FAST_MAX_CONCURRENCY = 4
# A rate-limited account rests this long before rotation tries it
# again. Unusual-activity accounts do NOT auto-recover on a timer —
# they need the guided recovery (site data clear) first.
ACCOUNT_LIMIT_COOLDOWN_MIN = 15


def clamp_concurrency(value: int) -> int:
    """Fast-mode concurrency, clamped to the 1–4 the UI offers."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(FLOW_FAST_MIN_CONCURRENCY,
               min(FLOW_FAST_MAX_CONCURRENCY, n))


def effective_concurrency(requested: int, usable_accounts: int) -> int:
    """How many generations really run side by side: never more than
    the requested Fast-mode setting, never more than the connected
    accounts (one browser profile per account — two contexts on the
    SAME profile fight over the profile lock, so one account means
    sequential, however high the setting is)."""
    return max(1, min(clamp_concurrency(requested),
                      max(1, usable_accounts)))


# --- Slice 5: #name / @name chaining ------------------------------------
# Flow Automator syntax (Videos 4/8): #name names a character once,
# @name pulls that same character into every later prompt. Here the
# names come from the Character Vault: a Vault character IS a #name
# definition, and @name resolves to its locked description. Both
# markers resolve to the same text — the locked description — so the
# model sees the same face/outfit in every scene; the marker only
# records whether the scene DEFINED the character or REFERENCED it.
# Unknown names are left untouched and reported (never guessed),
# so a typo fails loudly in the preview instead of silently
# generating a stranger.

_MARKER_RE = re.compile(r"([#@])")


def resolve_chain_syntax(prompt: str, characters: list[dict]) -> dict:
    """Resolve #name / @name markers in a prompt against Vault
    characters ([{name, description}]). Returns {prompt, resolved,
    unknown}: resolved = [{marker: '#', name, kind: 'define' |
    'reference'}], unknown = [names the Vault does not have]. The
    resolved prompt replaces each known marker with
    "[Character LOCKED: Name — description]". An unknown marker is
    left exactly as written. No characters at all -> the prompt
    comes back unchanged (plain text, no markers to resolve)."""
    if not prompt:
        return {"prompt": "", "resolved": [], "unknown": []}
    known = {}
    for c in characters or []:
        name = (c.get("name") or "").strip()
        if name:
            known[name.lower()] = c
    if not known:
        return {"prompt": prompt, "resolved": [], "unknown": []}
    # Longest name first: "Old Pipe Smoker" must win over "Old".
    names_sorted = sorted(known, key=len, reverse=True)
    resolved: list[dict] = []
    unknown: list[str] = []
    out: list[str] = []
    i = 0
    n = len(prompt)
    while i < n:
        ch = prompt[i]
        if ch in "#@" and i + 1 < n and prompt[i + 1].isalpha():
            matched = None
            for name in names_sorted:
                end = i + 1 + len(name)
                if (
                    prompt[i + 1:end].lower() == name
                    and (end >= n or not prompt[end].isalnum())
                ):
                    matched = name
                    break
            if matched is not None:
                c = known[matched]
                desc = (c.get("description") or "").strip()
                replacement = (
                    f"[Character LOCKED: {c['name']} — {desc}]"
                    if desc
                    else f"[Character LOCKED: {c['name']}]"
                )
                out.append(replacement)
                resolved.append({
                    "marker": ch,
                    "name": c["name"],
                    "kind": "define" if ch == "#" else "reference",
                })
                i += 1 + len(matched)
                continue
            # Unknown name: leave the marker + first word as-is,
            # record the word so the UI can warn about it.
            j = i + 1
            while j < n and prompt[j].isalnum():
                j += 1
            word = prompt[i + 1:j].strip()
            unknown.append(word or prompt[i + 1:i + 2])
            out.append(prompt[i:j])
            i = j
            continue
        out.append(ch)
        i += 1
    return {"prompt": "".join(out), "resolved": resolved, "unknown": unknown}
