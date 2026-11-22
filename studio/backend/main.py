"""Kreafy Creator Studio — Phase 1 Foundation + Phase 2 CineCut + Phase 3
Documentary Director slices 1-3 (scripts + scene breakdown, one-click run,
per-scene regenerate + deliverables) + Phase 4 VisualForge slices 1-3
(prompt list, bulk image generation + queue with daily limit, image
verification + use) + Phase 5 VoiceForge slices 1-3 (free voice library,
local Whisper transcription, HeyGen clone integration) + Phase 6 ClipForge
slices 1-4 (upload + transcribe, moment detection, 9:16 reframe +
captions, approval gating + final render) + Phase 7 slice 2 (Motion presets + atmosphere, Asset Vault search/tags,
render queue + 720p/1080p/two-pass-4K) + Phase 7 slice 3 (Hardening:
multi-API-key rotation, pluggable voice providers, job checkpoints/resume,
backup + restore, clear errors; Gemini script model gemini-3.5-flash)
+ Canvas free image route (VisualForge Gemini Canvas provider — free
images via gemini.google.com browser automation on the user's own Google
login + Gemini Pro quota; API provider stays the reliable paid route).

Localhost-only FastAPI service. Binds to 127.0.0.1, stores projects,
assets, jobs, settings, Style DNA and caption styles in a local SQLite
database (studio.db, gitignored). Uploaded media lives under
studio/data/ (gitignored) and is served back at /files/ for previews.

Free-first rules (from the inspiration-video review):
- Transcription defaults to local Whisper; a Groq key is NEVER required.
- No endpoint in this service calls any paid API — except HeyGen, the
  one exception: it is a paid/credit service, needs the user's own key,
  and only ever runs with Ale's say-so each time. The HeyGen worker
  never runs without a key, and no live HeyGen call was made in the
  build VM (error paths only — see docs/PROJECT_STATE.md).
- API keys are stored locally only and are never returned in full.
- Edge-TTS is best-effort only: it is blocked in some networks (it was
  blocked in the build VM). If it fails, the TTS endpoint returns
  HTTP 503 and the upload-a-voiceover path always works instead.

Run:
    pip install -r requirements.txt
    python -m uvicorn main:app --host 127.0.0.1 --port 8000
"""

import asyncio
import base64
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from seed_data import (
    CAPTION_RENDER_SPECS,
    CAPTION_STYLES,
    DEFAULT_SETTINGS,
    MASTER_PROMPT_SEEDS,
    NICHE_SEEDS,
    SHEET_ORDER,
    STICKMAN_POSES,
    STYLE_DNA,
    VAULT_SEEDS,
    VAULT_SLUGS,
)

# Canvas provider (Gemini Canvas web app, Playwright) + Google Flow
# provider + the shared Google browser profile (google_browser.py).
# The modules are stdlib-only at import time — Playwright itself is
# imported lazily inside them — so the app still starts when
# Playwright is not installed; the status endpoints then say so
# plainly. Canvas and Flow share ONE profile directory, so one
# Google sign-in opens both.
import canvas_provider as _canvas_provider
import flow_provider as _flow_provider
import google_browser as _google_browser

# Slice 4 (Character Vault) auto-QC: pure-PIL similarity + blank /
# broken checks. No network, no new dependency.
import vault_qc as _vault_qc

# Slice 3 PATCH (Retry Ladder + Fallback): pre-check, reword, simplify,
# fallback crop. Pure module, no DB, no network.
import retry_ladder as _retry_ladder
import flow_hardening as _flow_hardening

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "studio.db"
# Uploaded media + renders live one level up, under studio/data/.
DATA_DIR = BASE_DIR.parent / "data"
PROJECTS_DIR = DATA_DIR / "projects"
RENDERS_DIR = DATA_DIR / "renders"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

# --- Release Packaging (v0.14.0): layout-agnostic paths ------------------
# Dev layout:  <repo>/studio/backend/main.py  (APP_DIR = studio/)
# Packaged:    <install>/app/backend/main.py  (APP_DIR = app/)
# Dono me paths __file__ se nikalte hain, is liye code dono jagah
# waisa hi chalta hai. Final videos <install>/output/YYYY-MM-DD/ me
# jati hain — output/ install root par hai, app/ ke andar nahi, taake
# update kabhi videos ko na chhoo sake.
ROOT_DIR = BASE_DIR.parent.parent
APP_DIR = BASE_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
TMP_DIR = DATA_DIR / "tmp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _read_version() -> str:
    """VERSION file (package me app/VERSION, dev me repo root VERSION)."""
    for cand in (APP_DIR / "VERSION", ROOT_DIR / "VERSION"):
        try:
            v = cand.read_text(encoding="utf-8").strip()
            if v:
                return v if v.startswith("v") else f"v{v}"
        except OSError:
            continue
    return "v0.14.1"


APP_VERSION = _read_version()
APP_VERSION_NUM = APP_VERSION.lstrip("v")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now_hhmm() -> str:
    return datetime.now().strftime("%H%M")


def _slugify(text: str, fallback: str = "project") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:40] or fallback)


def output_dir_for_today() -> Path:
    d = OUTPUT_DIR / _today_str()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dated_name(slug: str, ext: str) -> str:
    """<slug>_YYYY-MM-DD_HHMM.<ext> — naam takraye to _2, _3 lagta hai."""
    base = f"{slug}_{_today_str()}_{_now_hhmm()}"
    folder = output_dir_for_today()
    name = f"{base}.{ext}"
    i = 2
    while (folder / name).exists():
        name = f"{base}_{i}.{ext}"
        i += 1
    return name


def media_path(rel: str | None) -> Path | None:
    """Stored rel path -> disk path. 'output/...' = install root ke
    output/ me; baaki sab = studio/data/ me (purana layout)."""
    if rel is None:
        return None
    p = Path(rel)
    if p.parts and p.parts[0] == "output":
        return ROOT_DIR / p
    return DATA_DIR / p


def media_url(rel: str | None) -> str | None:
    """Stored rel path -> public URL. 'output/...' = /output-files/,
    baaki = /files/ (purana layout)."""
    if not rel:
        return None
    if Path(rel).parts and Path(rel).parts[0] == "output":
        return f"/output-files/{rel[len('output/'):]}"
    return f"/files/{rel}"


def _project_slug(conn, project_id: int) -> str:
    row = conn.execute(
        "SELECT name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return _slugify(row["name"] if row else "", f"project-{project_id}")


def migrate_media(conn, rel: str | None) -> str | None:
    """Purani jagah (data/renders, data/clip-finals,
    data/projects/*/thumbnails) ki final file ko aaj ke output/
    folder me le jao — naam wahi rehta hai, sirf jagah badalti hai —
    aur DB ki har row jo purana rel rakhti hai, usay naya rel likh
    do. File nahi mili, ya rel pehle se output/ ka hai, to kuch nahi
    hota. Returns the (possibly new) rel."""
    if not rel:
        return rel
    if Path(rel).parts and Path(rel).parts[0] == "output":
        return rel
    src = DATA_DIR / rel
    if not src.is_file():
        return rel
    parts = Path(rel).parts
    migratable = (
        (len(parts) >= 2 and parts[0] == "renders")
        or (len(parts) >= 2 and parts[0] == "clip-finals")
        or (
            len(parts) >= 4
            and parts[0] == "projects"
            and parts[2] == "thumbnails"
        )
    )
    if not migratable:
        return rel
    dest_dir = output_dir_for_today()
    dest = dest_dir / src.name
    if dest.exists():
        i = 2
        while (dest_dir / f"{src.stem}_{i}{src.suffix}").exists():
            i += 1
        dest = dest_dir / f"{src.stem}_{i}{src.suffix}"
    new_rel = f"output/{_today_str()}/{dest.name}"
    try:
        shutil.move(str(src), str(dest))
    except OSError:
        return rel
    for table, col in (
        ("jobs", "output_path"),
        ("runs", "output_path"),
        ("runs", "srt_path"),
        ("assets", "path"),
        ("thumbnails", "path"),
    ):
        try:
            conn.execute(
                f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
                (new_rel, rel),
            )
        except Exception:
            pass
    return new_rel

# Canvas browser profile: the user's Google login cookies live here
# (studio/data/canvas-profile/, gitignored) and nowhere else. The
# name stays "canvas-profile" so an existing Canvas login keeps
# working — it is now the SHARED Google profile: the same directory
# serves Canvas, Flow and the Connect Google button, so one sign-in
# opens both providers.
CANVAS_PROFILE_DIR = DATA_DIR / "canvas-profile"
_canvas_provider.set_profile_dir(CANVAS_PROFILE_DIR)
_flow_provider.set_profile_dir(CANVAS_PROFILE_DIR)
_google_browser.set_profile_dir(CANVAS_PROFILE_DIR)

# Slice 5 (Flow provider hardening): extra Flow accounts get their
# own browser profile directories under studio/data/flow-profiles/
# (account-2, account-3) — one profile per Google account, so
# rotation never fights the profile lock and Fast mode can really
# run generations side by side. Account 1 IS the shared profile
# above (Canvas + Flow + Connect Google), never a second copy.
FLOW_PROFILES_DIR = DATA_DIR / "flow-profiles"

# Bold font for burned-in captions (Bold White caption style).
# DejaVu Sans Bold ships with most Linux desktops; fall back to any
# DejaVu bold font found on the system, else drawtext is skipped.
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if not Path(FONT_PATH).exists():
    for _cand in sorted(Path("/usr/share/fonts").rglob("*Sans-Bold*.ttf")):
        FONT_PATH = str(_cand)
        break
    else:
        FONT_PATH = ""
SECRET_KEYS = {
    "gemini_api_key",
    "groq_api_key",
    "heygen_api_key",
    "openai_api_key",
    "deepgram_api_key",
    "pexels_api_key",
    "pixabay_api_key",
    # Release Packaging (Free keys): naye slots — kabhi pre-filled
    # nahi hote, har user apni key khud lagata hai.
    "openrouter_api_key",
    "huggingface_api_key",
    "elevenlabs_api_key",
}

app = FastAPI(title="Kreafy Creator Studio API", version=APP_VERSION_NUM)

# Frontend dev server only; the API never accepts non-localhost traffic
# because uvicorn is started with --host 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    # PATCH + DELETE are real methods here too: final clips are
    # renamed (PATCH) and deleted (DELETE) from the UI.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Uploaded media served back for preview only (same localhost origin).
app.mount("/files", StaticFiles(directory=DATA_DIR, html=False), name="files")
# Release Packaging: finished videos live in install-root output/ and
# are served here, so /files/ never has to reach outside DATA_DIR.
app.mount(
    "/output-files",
    StaticFiles(directory=OUTPUT_DIR, html=False),
    name="output-files",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_cast_sheets(conn: sqlite3.Connection) -> None:
    """v0.14.1 fix round 2 — built-in cast sheets ship WITH the app
    (studio/backend/reference/cast-sheets/) so every install has them.
    Before this, the sheets lived only in this VM's data/ — on Ali's PC
    sheet_path was empty and the Vault cards showed no pictures at all.
    Copies missing sheets into data/, cuts one thumbnail per character
    (each sheet is a single row of 10 — SHEET_ORDER maps each column to
    its character, read off the actual sheets by viewing all 7), and
    backfills thumb_path on the built-in v1 rows (fresh + existing DBs).
    A missing tile only hides a thumbnail — it never breaks boot."""
    ref_dir = DATA_DIR / "reference" / "stick-direction"
    crops_dir = ref_dir / "crops"
    ref_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
    shipped = Path(__file__).resolve().parent / "reference" / "cast-sheets"
    try:
        from PIL import Image  # noqa: PLC0415 - only needed for tiles
    except ImportError:
        Image = None
    for niche_name, slug in VAULT_SLUGS.items():
        sheet = ref_dir / f"{slug}-cast-sheet.webp"
        if not sheet.is_file():
            src = shipped / f"{slug}-cast-sheet.webp"
            if src.is_file():
                shutil.copyfile(src, sheet)
        order = SHEET_ORDER.get(slug, [])
        if sheet.is_file() and Image is not None and len(order) == 10:
            try:
                im = Image.open(sheet)
                w, h = im.size
                col = w / 10
                for i, _name in enumerate(order):
                    tile = crops_dir / f"{slug}-{i:02d}.webp"
                    if tile.is_file():
                        continue
                    box = (
                        int(i * col) + 6,
                        0,
                        int((i + 1) * col) - 6,
                        h,
                    )
                    thumb = im.crop(box)
                    thumb.thumbnail((180, 912))
                    thumb.save(tile, "WEBP", quality=80)
            except Exception:  # noqa: BLE001 - tiles are best-effort
                pass
    niches = {
        r["id"]: r["name"]
        for r in conn.execute("SELECT id, name FROM niches").fetchall()
    }
    rows = conn.execute(
        "SELECT id, niche_id, name FROM vault_characters"
        " WHERE version = 1 AND source = 'builtin'"
    ).fetchall()
    for row in rows:
        slug = VAULT_SLUGS.get(niches.get(row["niche_id"], ""), "")
        order = SHEET_ORDER.get(slug, [])
        if row["name"] in order:
            i = order.index(row["name"])
            tile = crops_dir / f"{slug}-{i:02d}.webp"
            if tile.is_file():
                conn.execute(
                    "UPDATE vault_characters SET thumb_path = ? WHERE id = ?",
                    (
                        f"reference/stick-direction/crops/{slug}-{i:02d}.webp",
                        row["id"],
                    ),
                )


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS style_dna (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                master_prompt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS caption_styles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                language TEXT NOT NULL
            );
            -- Phase 2: CineCut sync timelines. A timeline belongs to one
            -- project; its clips point at image assets in order.
            CREATE TABLE IF NOT EXISTS timelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                style_dna_id INTEGER REFERENCES style_dna(id),
                caption_style_id INTEGER REFERENCES caption_styles(id),
                vo_duration_s REAL NOT NULL DEFAULT 0,
                vo_asset_id INTEGER REFERENCES assets(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeline_id INTEGER NOT NULL REFERENCES timelines(id),
                asset_id INTEGER NOT NULL REFERENCES assets(id),
                position INTEGER NOT NULL,
                start_s REAL NOT NULL,
                end_s REAL NOT NULL,
                caption_text TEXT NOT NULL DEFAULT ''
            );
            -- Phase 2 slice 2: one main character per project, so the
            -- same person stays consistent across every scene/image
            -- prompt. The reference image lives under
            -- studio/data/projects/{id}/character/.
            CREATE TABLE IF NOT EXISTS project_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE REFERENCES projects(id),
                name TEXT NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            -- Phase 3 slice 1: scripts + scene breakdown (Documentary
            -- Director). A script is pasted/typed text, or text generated
            -- from a topic with the optional Gemini free-tier key.
            -- Each scene carries its narration text, a template-built
            -- image prompt and an estimated duration.
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                topic TEXT NOT NULL DEFAULT '',
                full_text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'pasted',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL REFERENCES scripts(id),
                position INTEGER NOT NULL,
                text TEXT NOT NULL,
                image_prompt TEXT NOT NULL DEFAULT '',
                duration_s REAL NOT NULL DEFAULT 0
            );
            -- Phase 3 slice 2: one-click runs (Documentary Director).
            -- A run orchestrates script -> voice -> images -> timeline
            -- -> captions -> render. Each step is a jobs row linked by
            -- run_id, so the Jobs list and the run-progress view show
            -- the same honest per-step state; a failed step stops the
            -- run and is never marked done.
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                script_id INTEGER NOT NULL REFERENCES scripts(id),
                timeline_id INTEGER REFERENCES timelines(id),
                vo_asset_id INTEGER REFERENCES assets(id),
                caption_style_id INTEGER REFERENCES caption_styles(id),
                voice_text TEXT NOT NULL DEFAULT '',
                voice TEXT NOT NULL DEFAULT 'en-US-AriaNeural',
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                output_path TEXT,
                srt_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            -- Phase 3 slice 3: deliverables. YouTube metadata is drafted
            -- from the real script (template only, no AI call) and edited
            -- by hand; thumbnails are real frames pulled from the real
            -- rendered MP4, never a stock or generated picture.
            CREATE TABLE IF NOT EXISTS project_metadata (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id),
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS thumbnails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                path TEXT NOT NULL,
                timestamp_s REAL NOT NULL,
                source_job_id INTEGER REFERENCES jobs(id),
                created_at TEXT NOT NULL
            );
            -- Phase 4 slice 3: image verification (StickFilm-style
            -- mandatory check). A scene's candidate image — generated
            -- by Gemini or attached from an upload — is linked here,
            -- and Ale's verdict (approved / rejected) is recorded per
            -- image. Nothing enters a timeline as a VisualForge image
            -- until it is approved; no verdict means "pending", never
            -- silently approved.
            CREATE TABLE IF NOT EXISTS scene_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene_id INTEGER NOT NULL REFERENCES scenes(id),
                asset_id INTEGER NOT NULL REFERENCES assets(id),
                source TEXT NOT NULL DEFAULT 'generated',
                created_at TEXT NOT NULL,
                UNIQUE(scene_id, asset_id)
            );
            CREATE TABLE IF NOT EXISTS image_verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL UNIQUE REFERENCES assets(id),
                scene_id INTEGER REFERENCES scenes(id),
                verdict TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                decided_at TEXT NOT NULL
            );
            -- Phase 5 slice 2: local Whisper transcription (VoiceForge).
            -- A transcription is the full text of one audio/video file
            -- plus its word-level timestamps (words_json) and the
            -- segment boundaries (segments_json) used for SRT/VTT export.
            -- Free, offline, no key; the model is whatever is already
            -- cached on this PC — nothing is ever downloaded.
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                job_id INTEGER REFERENCES jobs(id),
                model TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT '',
                source_filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                duration_s REAL NOT NULL DEFAULT 0,
                full_text TEXT NOT NULL DEFAULT '',
                words_json TEXT NOT NULL DEFAULT '[]',
                segments_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            -- Phase 5 slice 3: HeyGen clone voices (VoiceForge). One row
            -- per finished generation: which clone voice, which language,
            -- whether the 106 Hz pitch lock was applied (hi only), and
            -- the VO asset it produced. The HeyGen API key itself is
            -- never stored here — only in settings (masked).
            CREATE TABLE IF NOT EXISTS heygen_voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                job_id INTEGER REFERENCES jobs(id),
                asset_id INTEGER REFERENCES assets(id),
                voice_id TEXT NOT NULL,
                language TEXT NOT NULL,
                pitch_applied INTEGER NOT NULL DEFAULT 0,
                pitch_factor REAL NOT NULL DEFAULT 1.0,
                duration_s REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            -- Phase 6 slice 1: ClipForge source videos. One row per
            -- uploaded long video: the video asset, the source-video
            -- job, and the local Whisper transcription it produced.
            -- Moment detection (slice 2) reads the transcription's
            -- word timestamps from here.
            CREATE TABLE IF NOT EXISTS source_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                asset_id INTEGER REFERENCES assets(id),
                job_id INTEGER REFERENCES jobs(id),
                transcription_id INTEGER REFERENCES transcriptions(id),
                duration_s REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            -- Phase 6 slice 2: ClipForge moments. One row per scored
            -- moment of a source video: start/end in seconds, the total
            -- score, and the score breakdown as JSON so the number is
            -- explainable (density / keywords / silence / length — all
            -- measured from the real transcription's word timestamps).
            -- No audio-energy column: energy is not measured here, so
            -- it is not invented either. Approval gating + rendering
            -- arrive in slice 4; this slice only finds and scores.
            CREATE TABLE IF NOT EXISTS moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_video_id INTEGER NOT NULL REFERENCES source_videos(id),
                start_s REAL NOT NULL,
                end_s REAL NOT NULL,
                score REAL NOT NULL,
                score_breakdown TEXT NOT NULL DEFAULT '{}',
                title TEXT NOT NULL DEFAULT '',
                excerpt TEXT NOT NULL DEFAULT '',
                word_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            -- Phase 6 slice 3: ClipForge 9:16 reframes. One row per
            -- vertical preview of a moment: the moment it came from,
            -- the caption style burned in (by name, so the row says
            -- what it is), the 1080x1920 output, and the job + asset
            -- that carry its progress and file. asset_id stays NULL
            -- until the render succeeds — a failed reframe has a job
            -- error, never a fake clip. Approval gating + final
            -- render arrive in slice 4; this slice is previews only.
            CREATE TABLE IF NOT EXISTS reframes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moment_id INTEGER NOT NULL REFERENCES moments(id),
                job_id INTEGER REFERENCES jobs(id),
                asset_id INTEGER REFERENCES assets(id),
                caption_style TEXT NOT NULL DEFAULT 'Bold White',
                width INTEGER NOT NULL DEFAULT 1080,
                height INTEGER NOT NULL DEFAULT 1920,
                duration_s REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            -- Phase 6 slice 4: ClipForge final clips. One row per
            -- APPROVED moment (one final clip per moment): the
            -- reframe whose caption style was used, the final
            -- 1080x1920 MP4, and its job + asset. asset_id stays NULL
            -- until a render succeeds — a failed render has a job
            -- error, never a fake clip. Nothing renders as final
            -- without approval (the moment's approval column gates
            -- the render endpoint). A re-render reuses this row: the
            -- old file is deleted only after the new render succeeds.
            CREATE TABLE IF NOT EXISTS final_clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moment_id INTEGER NOT NULL REFERENCES moments(id),
                reframe_id INTEGER REFERENCES reframes(id),
                job_id INTEGER REFERENCES jobs(id),
                asset_id INTEGER REFERENCES assets(id),
                title TEXT NOT NULL DEFAULT '',
                caption_style TEXT NOT NULL DEFAULT 'Bold White',
                width INTEGER NOT NULL DEFAULT 1080,
                height INTEGER NOT NULL DEFAULT 1920,
                duration_s REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            -- Phase 7 slice 1: StickMan poses. The pose library lives
            -- in the DB (seeded from seed_data.py) so descriptions are
            -- editable; the drawing geometry for each pose name lives
            -- in the stickman renderer in this file.
            CREATE TABLE IF NOT EXISTS stickman_poses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL
            );
            -- Phase 7 slice 1: StickMan prompts. One row per scene:
            -- the template-built stick-figure animation prompt (pose,
            -- action, expression, props, background) derived from the
            -- scene's own words. No AI call, no key — the prompt is
            -- built from the scene text plus a pose picked by keyword
            -- (with a rotating fallback so neighbours differ).
            CREATE TABLE IF NOT EXISTS stickman_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene_id INTEGER NOT NULL REFERENCES scenes(id),
                pose TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT '',
                expression TEXT NOT NULL DEFAULT '',
                props TEXT NOT NULL DEFAULT '',
                background TEXT NOT NULL DEFAULT '',
                prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(scene_id)
            );
            -- Phase 7 slice 1: StoryCraft Master Prompt library.
            -- Reusable master prompts reverse-engineered from the
            -- inspiration videos (see seed_data.py MASTER_PROMPT_SEEDS
            -- for the source of each seed). style_dna_id is NULL when
            -- the video's style has no Style DNA entry yet.
            CREATE TABLE IF NOT EXISTS master_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                template TEXT NOT NULL,
                style_dna_id INTEGER REFERENCES style_dna(id),
                source TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            -- Phase 7 slice 1: StoryCraft research notes. Free-form
            -- research pasted per project; "write script from
            -- research" reuses the existing Gemini script path (no key
            -- -> the same plain 400, no fake script).
            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Phase 2 migration: render jobs record their output file.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "output_path" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN output_path TEXT")
        # Phase 3 slice 2 migrations: step jobs link to their run, and
        # placeholder title-card images are flagged on the asset so the
        # UI can say "real image needed" instead of showing them as
        # ordinary uploads.
        if "run_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN run_id INTEGER")
        asset_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()
        ]
        if "placeholder" not in asset_cols:
            conn.execute(
                "ALTER TABLE assets ADD COLUMN placeholder INTEGER NOT NULL DEFAULT 0"
            )
        # Phase 3 slice 3 migration: a clip remembers when its image
        # was swapped by per-scene regenerate, so the UI can say so.
        clip_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(clips)").fetchall()
        ]
        if "image_replaced" not in clip_cols:
            conn.execute(
                "ALTER TABLE clips ADD COLUMN image_replaced INTEGER NOT NULL DEFAULT 0"
            )
        # Sentence-level visuals migration: a clip remembers its Ken
        # Burns effect (zoom-in / zoom-out / pan-left / pan-right), so
        # the render is reproducible and the UI can say which effect
        # each clip has. Empty means "decided by position" (old clips).
        if "effect" not in clip_cols:
            conn.execute(
                "ALTER TABLE clips ADD COLUMN effect TEXT NOT NULL DEFAULT ''"
            )
        # Phase 4 slice 2 migration: an image-generate job belongs to
        # one scene, so the VisualForge status view can show per-scene
        # queued / running / done / failed honestly.
        if "scene_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN scene_id INTEGER")
        # Phase 5 slice 2 migration: a transcribe job points at the
        # transcription it produced, so the Jobs list and the
        # transcription view stay linked.
        if "transcription_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN transcription_id INTEGER")
        # Phase 6 slice 4 migration: a moment remembers its approval
        # state — 'pending' (default, never rendered as final),
        # 'approved' (may render as a final clip), 'rejected' (never
        # renders). The render endpoint checks this column; nothing
        # else in the app writes it except the approve/reject
        # endpoints.
        moment_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(moments)").fetchall()
        ]
        if "approval" not in moment_cols:
            conn.execute(
                "ALTER TABLE moments ADD COLUMN approval TEXT NOT NULL"
                " DEFAULT 'pending'"
            )
        # Phase 7 slice 2 migrations: a render job records the options
        # it was queued with (quality + atmosphere), so the render
        # queue can say what each job actually produced; and assets
        # get user tags (Asset Vault search/filter).
        if "options_json" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN options_json TEXT")
        # Canvas route migration: an image-generate job remembers
        # which provider queued it — 'api' (Gemini API, the reliable
        # paid route) or 'canvas' (Gemini Canvas web app, free via
        # the user's Gemini Pro quota). Old jobs predate the column
        # and are API jobs, hence the 'api' default.
        if "provider" not in cols:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN provider TEXT NOT NULL"
                " DEFAULT 'api'"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL REFERENCES assets(id)
                    ON DELETE CASCADE,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(asset_id, tag)
            );
            """
        )
        # Slice 5 (Flow provider hardening): a bulk run's jobs share
        # one batch id, so Queue History can list past queues and
        # re-download one batch as a ZIP. Old jobs predate the column
        # and belong to no batch (NULL).
        if "batch_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN batch_id TEXT")
        # Phase 7 slice 3: several Gemini API keys, tried in order
        # (rotation) so one dead key never stops the work; and voice
        # providers added separately (custom slots for future providers
        # like A123 Pro — no credentials are ever seeded here).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gemini_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL DEFAULT '',
                key_value TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                test_status TEXT NOT NULL DEFAULT 'not-tested',
                test_message TEXT NOT NULL DEFAULT '',
                test_at TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        # Cross-check slice: niches (AutoCut Writer / Video 7 parity).
        # A niche is a topic family (e.g. "Faceless History"); each can
        # carry a default Style DNA, and "Suggest topics" asks Gemini
        # for fresh video topics in that niche (no key -> plain 400).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS niches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                default_style_dna_id INTEGER REFERENCES style_dna(id),
                created_at TEXT NOT NULL
            );
            """
        )
        # Stick-Figure Direction Pack: a niche carries its MAIN
        # characters (newline-separated, 4-5 per niche, 100%
        # consistent in every scene). Added as a migration so
        # existing DBs get the column on restart.
        _niche_cols = [
            r[1]
            for r in conn.execute("PRAGMA table_info(niches)").fetchall()
        ]
        if "main_characters" not in _niche_cols:
            conn.execute(
                "ALTER TABLE niches ADD COLUMN main_characters TEXT"
                " NOT NULL DEFAULT ''"
            )
        # Slice 4 (Character Vault): one locked character sheet per
        # niche character, versioned. A character is a row per
        # version: status draft -> approved -> locked; only one
        # locked version is active (is_active=1) per (niche, name).
        # The active locked version is what bulk prompts + the
        # reference attach use, so a video never mixes v1/v2.
        # sheet_path is relative to studio/data/ (the cast-sheet
        # image; all 10 characters of a niche share one sheet
        # image). poses_json is the character's 4-5 fixed poses.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche_id INTEGER NOT NULL REFERENCES niches(id),
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                signature_prop TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'secondary',
                poses_json TEXT NOT NULL DEFAULT '[]',
                sheet_path TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(niche_id, name, version)
            );
            """
        )
        # Slice 4: a Magic run can carry a Vault niche (its mains
        # auto-select, its sheets lock the prompts). Migration lives
        # AFTER the CREATE TABLE magic_runs below — a fresh DB has no
        # table yet when init_db starts, so an ALTER here would crash
        # startup ("no such table").
        # Release Packaging (My Main Character): a Vault entry can
        # be user-uploaded (source='user') instead of one of the 70
        # shipped characters (source='builtin'), and exactly one
        # locked character can be the user's main (is_main=1).
        # Migration so existing DBs get the columns on restart.
        _vault_cols = [
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(vault_characters)"
            ).fetchall()
        ]
        if "source" not in _vault_cols:
            conn.execute(
                "ALTER TABLE vault_characters ADD COLUMN"
                " source TEXT NOT NULL DEFAULT 'builtin'"
            )
        if "is_main" not in _vault_cols:
            conn.execute(
                "ALTER TABLE vault_characters ADD COLUMN"
                " is_main INTEGER NOT NULL DEFAULT 0"
            )
        # v0.14.1 fix round 2: one thumbnail per built-in character,
        # cut from the niche's cast-sheet image (see _ensure_cast_sheets).
        if "thumb_path" not in _vault_cols:
            conn.execute(
                "ALTER TABLE vault_characters ADD COLUMN"
                " thumb_path TEXT NOT NULL DEFAULT ''"
            )
        # Slice 2 (StoryCraft Deep Research): a research note can be
        # linked to a script; a script can be written from a note.
        # a Deep Research result — kind 'deep-research' with its
        # parsed facts as JSON, so the UI can list facts + sources
        # and the script step can use them. Plain notes stay kind
        # 'note' with an empty facts list.
        _note_cols = [
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(research_notes)"
            ).fetchall()
        ]
        if "kind" not in _note_cols:
            conn.execute(
                "ALTER TABLE research_notes ADD COLUMN kind TEXT"
                " NOT NULL DEFAULT 'note'"
            )
        if "facts_json" not in _note_cols:
            conn.execute(
                "ALTER TABLE research_notes ADD COLUMN facts_json TEXT"
                " NOT NULL DEFAULT ''"
            )
        # Cross-check slice: reframe / final-clip render options are
        # stored on the row so a final render can inherit the preview
        # the user already saw (aspect, caption size/position, on/off).
        for _table in ("reframes", "final_clips"):
            _cols = [
                r[1]
                for r in conn.execute(
                    f"PRAGMA table_info({_table})"
                ).fetchall()
            ]
            if "aspect" not in _cols:
                conn.execute(
                    f"ALTER TABLE {_table} ADD COLUMN aspect TEXT"
                    " NOT NULL DEFAULT '9:16'"
                )
            if "caption_size_pct" not in _cols:
                conn.execute(
                    f"ALTER TABLE {_table} ADD COLUMN caption_size_pct"
                    " INTEGER NOT NULL DEFAULT 100"
                )
            if "caption_position" not in _cols:
                conn.execute(
                    f"ALTER TABLE {_table} ADD COLUMN caption_position"
                    " TEXT NOT NULL DEFAULT 'bottom'"
                )
            if "captions" not in _cols:
                conn.execute(
                    f"ALTER TABLE {_table} ADD COLUMN captions"
                    " INTEGER NOT NULL DEFAULT 1"
                )
        # Slice 3 (Magic Mode): one row per Magic run — the six
        # stages (Script -> Images -> Voice -> Timeline -> Captions
        # -> Render) live in stages_json, the end counts in
        # summary_json. run_id links the one-click run the Magic
        # worker delegates timeline/captions/render to. Added as a
        # CREATE TABLE (new table) + migrations on runs so existing
        # DBs get the columns on restart.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS magic_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                topic TEXT NOT NULL DEFAULT '',
                script_text TEXT NOT NULL DEFAULT '',
                script_id INTEGER REFERENCES scripts(id),
                run_id INTEGER REFERENCES runs(id),
                language TEXT NOT NULL DEFAULT 'en',
                aspect TEXT NOT NULL DEFAULT '16:9',
                caption_style_id INTEGER REFERENCES caption_styles(id),
                style_dna_id INTEGER REFERENCES style_dna(id),
                voice_kind TEXT NOT NULL DEFAULT 'upload',
                voice_id TEXT NOT NULL DEFAULT '',
                vo_asset_id INTEGER REFERENCES assets(id),
                status TEXT NOT NULL DEFAULT 'queued',
                stages_json TEXT NOT NULL DEFAULT '{}',
                summary_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Slice 4 migration (AFTER CREATE TABLE — a fresh DB has no
        # table yet when init_db starts, so an ALTER before this
        # point would crash startup with "no such table"):
        # existing DBs get the Vault-niche columns on restart.
        _magic_cols = [
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(magic_runs)"
            ).fetchall()
        ]
        if "niche_id" not in _magic_cols:
            conn.execute(
                "ALTER TABLE magic_runs ADD COLUMN niche_id INTEGER"
                " REFERENCES niches(id)"
            )
        if "scene_characters_json" not in _magic_cols:
            conn.execute(
                "ALTER TABLE magic_runs ADD COLUMN"
                " scene_characters_json TEXT NOT NULL DEFAULT '{}'"
            )
        # Slice 5 (Flow provider hardening): up to 3 Flow accounts,
        # each on its own browser profile (rotation + Fast mode).
        # Account 1 is the shared profile (CANVAS_PROFILE_DIR) —
        # its row is seeded below; accounts 2/3 live under
        # FLOW_PROFILES_DIR. status: 'active' (usable), 'limited'
        # (rate limit — rests until limited_until), 'unusual'
        # (Flow's 'Unusual Activity' block — needs the guided
        # recovery, never auto-retried), 'not_logged_in' (no Google
        # session in that profile yet). No password/token is ever
        # stored: the login lives only in the profile directory.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flow_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                profile_dir TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                last_used_at TEXT,
                limited_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Slice 5: persistent queue state per script — pause/resume
        # survives a restart (a paused queue is NOT lost when the
        # app closes; resume re-runs the same queued jobs).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flow_queue_state (
                script_id INTEGER PRIMARY KEY,
                paused INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        _run_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()
        ]
        if "style_dna_id" not in _run_cols:
            conn.execute(
                "ALTER TABLE runs ADD COLUMN style_dna_id INTEGER"
                " REFERENCES style_dna(id)"
            )
        if "aspect" not in _run_cols:
            conn.execute(
                "ALTER TABLE runs ADD COLUMN aspect TEXT"
                " NOT NULL DEFAULT '16:9'"
            )
        # Slice 3 (Magic Mode auto-consistency): the character's
        # locked description - one line set once at upload
        # (optional); the prompt builder injects it into every
        # image prompt automatically, so no per-scene work.
        _char_cols = [
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(project_characters)"
            ).fetchall()
        ]
        if "description" not in _char_cols:
            conn.execute(
                "ALTER TABLE project_characters ADD COLUMN description"
                " TEXT NOT NULL DEFAULT ''"
            )
        for name, description, master_prompt in (
            (s["name"], s["description"], s["master_prompt"]) for s in STYLE_DNA
        ):
            conn.execute(
                "INSERT OR IGNORE INTO style_dna (name, description, master_prompt)"
                " VALUES (?, ?, ?)",
                (name, description, master_prompt),
            )
        # Stick-Figure Direction Pack: seed the 7 approved niches
        # with their main characters; the default Style DNA is the
        # new StickFilm + Stick-Figure Touch preset (seeded above).
        for niche in NICHE_SEEDS:
            style_id = None
            if niche.get("default_style_dna_name"):
                row = conn.execute(
                    "SELECT id FROM style_dna WHERE name = ?",
                    (niche["default_style_dna_name"],),
                ).fetchone()
                style_id = row["id"] if row else None
            conn.execute(
                "INSERT OR IGNORE INTO niches (name, description,"
                " main_characters, default_style_dna_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    niche["name"],
                    niche["description"],
                    "\n".join(niche["main_characters"]),
                    style_id,
                    utcnow(),
                ),
            )
        # Slice 4 (Character Vault): seed the 70 approved
        # characters (7 niches x 10) as locked v1, sharing each
        # niche's cast-sheet image. INSERT OR IGNORE keeps user
        # edits (new versions, locks) intact on restart. When a
        # seeded row exists but its sheet file was re-copied since
        # (Ali's PC), the sheet path is repaired — the file lives
        # in studio/data/reference/stick-direction/, gitignored,
        # so it is NOT in the push/ZIP.
        # v0.14.1 fix round 2: shipped cast sheets + per-character
        # thumbnails, before the Vault seed (which only stores a
        # sheet_path when the file actually exists).
        _ensure_cast_sheets(conn)
        for group in VAULT_SEEDS:
            nrow = conn.execute(
                "SELECT id FROM niches WHERE name = ?",
                (group["niche"],),
            ).fetchone()
            if nrow is None:
                continue
            niche_id = nrow["id"]
            slug = VAULT_SLUGS.get(group["niche"], "")
            sheet_path = (
                f"reference/stick-direction/{slug}-cast-sheet.webp"
                if slug
                else ""
            )
            sheet_ok = bool(sheet_path) and (
                DATA_DIR / sheet_path
            ).is_file()
            # v0.14.1 fix round 2: per-character thumbnail (SHEET_ORDER
            # maps the sheet column to the character). _ensure_cast_sheets
            # already cut the tiles above; store the path only when the
            # tile file actually exists.
            order = SHEET_ORDER.get(slug, [])
            for ch in group["characters"]:
                poses = _vault_default_poses(
                    ch["name"], ch["signature_prop"]
                )
                thumb_path = (
                    f"reference/stick-direction/crops/{slug}-"
                    f"{order.index(ch['name']):02d}.webp"
                    if slug and ch["name"] in order
                    else ""
                )
                thumb_ok = bool(thumb_path) and (
                    DATA_DIR / thumb_path
                ).is_file()
                conn.execute(
                    "INSERT OR IGNORE INTO vault_characters"
                    " (niche_id, name, description, signature_prop,"
                    " role, poses_json, sheet_path, thumb_path, version, status,"
                    " is_active, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'locked', 1,"
                    " ?, ?)",
                    (
                        niche_id,
                        ch["name"],
                        ch["description"],
                        ch["signature_prop"],
                        ch["role"],
                        json.dumps(poses),
                        sheet_path if sheet_ok else "",
                        thumb_path if thumb_ok else "",
                        utcnow(),
                        utcnow(),
                    ),
                )
                if sheet_ok:
                    conn.execute(
                        "UPDATE vault_characters SET sheet_path = ?,"
                        " updated_at = ? WHERE niche_id = ? AND"
                        " name = ? AND version = 1 AND sheet_path = ''",
                        (sheet_path, utcnow(), niche_id, ch["name"]),
                    )
                if thumb_ok:
                    conn.execute(
                        "UPDATE vault_characters SET thumb_path = ?,"
                        " updated_at = ? WHERE niche_id = ? AND"
                        " name = ? AND version = 1 AND thumb_path = ''",
                        (thumb_path, utcnow(), niche_id, ch["name"]),
                    )
        for name, description, language in (
            (c["name"], c["description"], c["language"]) for c in CAPTION_STYLES
        ):
            conn.execute(
                "INSERT OR IGNORE INTO caption_styles (name, description, language)"
                " VALUES (?, ?, ?)",
                (name, description, language),
            )
        for key, value, note in DEFAULT_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value, note) VALUES (?, ?, ?)",
                (key, value, note),
            )
        # Slice 5 (Flow provider hardening): seed Flow account 1 —
        # the shared Google profile (Canvas + Flow + Connect Google),
        # so rotation starts from the login Ale already has. No
        # UNIQUE constraint on profile_dir, so the guard is an
        # explicit SELECT — re-seeding must never duplicate it;
        # accounts 2/3 are added from the UI only.
        _acct1 = conn.execute(
            "SELECT id FROM flow_accounts WHERE profile_dir = ?",
            (str(CANVAS_PROFILE_DIR),),
        ).fetchone()
        if _acct1 is None:
            conn.execute(
                "INSERT INTO flow_accounts"
                " (name, profile_dir, status, created_at, updated_at)"
                " VALUES (?, ?, 'active', ?, ?)",
                (
                    "Account 1 (pehla)",
                    str(CANVAS_PROFILE_DIR),
                    utcnow(),
                    utcnow(),
                ),
            )
        # Phase 7 slice 3: seed the keys table once from the legacy
        # single setting, so setups from before this slice keep their
        # key and nothing is lost in the move to rotation.
        legacy = conn.execute(
            "SELECT value FROM settings WHERE key = 'gemini_api_key'"
        ).fetchone()
        key_count = conn.execute(
            "SELECT COUNT(*) AS n FROM gemini_api_keys"
        ).fetchone()["n"]
        if key_count == 0 and legacy and legacy["value"].strip():
            conn.execute(
                "INSERT INTO gemini_api_keys (label, key_value, position,"
                " created_at) VALUES ('Key 1', ?, 0, ?)",
                (legacy["value"].strip(), utcnow()),
            )
            # v0.14.1: migrate hone ke baad legacy setting CLEAR kar do —
            # warna wahi key Settings me do jagah dikhti hai (rotation +
            # purani setting) aur user confuse hota hai ke asal me kaun
            # si use ho rahi hai. Rotation hi source of truth hai.
            conn.execute(
                "UPDATE settings SET value = '' WHERE key = 'gemini_api_key'"
            )
        for name, description in (
            (p["name"], p["description"]) for p in STICKMAN_POSES
        ):
            conn.execute(
                "INSERT OR IGNORE INTO stickman_poses (name, description)"
                " VALUES (?, ?)",
                (name, description),
            )
        for seed in MASTER_PROMPT_SEEDS:
            style_id = None
            if seed.get("style_dna_name"):
                row = conn.execute(
                    "SELECT id FROM style_dna WHERE name = ?",
                    (seed["style_dna_name"],),
                ).fetchone()
                style_id = row["id"] if row else None
            conn.execute(
                "INSERT OR IGNORE INTO master_prompts"
                " (name, category, template, style_dna_id, source,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    seed["name"],
                    seed["category"],
                    seed["template"],
                    style_id,
                    seed.get("source", ""),
                    utcnow(),
                ),
            )


# Phase 7 slice 3: what a job shows when its worker died with it.
INTERRUPTED_MSG = (
    "backend band ho gaya tha — job adhoori reh gayi."
    " Resume karein ya dobara chalayen."
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Jobs are in-process BackgroundTasks, so any job still 'queued'
    # or 'running' when the backend starts has no live worker — it
    # would sit there forever. Mark it interrupted with a plain
    # message instead; the user resumes it explicitly from the Jobs
    # list. This also cleans up stale jobs like render job 70 from
    # Phase 7 slice 2 (a dead backend left it 'queued').
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
            " WHERE status IN ('queued', 'running')",
            ("interrupted", INTERRUPTED_MSG, utcnow()),
        )


def ffmpeg_info() -> dict:
    path = shutil.which("ffmpeg")
    if not path:
        return {"available": False, "version": None, "path": None}
    try:
        out = subprocess.run(
            [path, "-version"], capture_output=True, text=True, timeout=10
        )
        first = out.stdout.splitlines()[0] if out.stdout else ""
        return {"available": True, "version": first, "path": path}
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "version": None, "path": path}


def mask_value(key: str, value: str) -> str:
    if key in SECRET_KEYS and value:
        return "••••••••" + value[-4:]
    return value


# --- request models -------------------------------------------------------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AssetIn(BaseModel):
    project_id: int
    kind: str = Field(min_length=1, max_length=50)
    path: str = Field(min_length=1, max_length=1000)


class AssetTagIn(BaseModel):
    """One user tag for an asset (Phase 7 slice 2, Asset Vault).
    Tags are lowercased and trimmed; 1–30 chars of letters, digits,
    spaces, hyphens and underscores."""

    tag: str = Field(min_length=1, max_length=30)


class JobIn(BaseModel):
    project_id: int
    kind: str = Field(min_length=1, max_length=50)
    status: str = Field(default="queued", max_length=50)


class SettingIn(BaseModel):
    value: str = Field(default="", max_length=2000)


class GeminiKeyIn(BaseModel):
    """One Gemini API key for the rotation list (Phase 7 slice 3)."""

    label: str = Field(default="", max_length=100)
    key: str = Field(min_length=1, max_length=2000)


class GeminiKeyMoveIn(BaseModel):
    direction: str = Field(default="up", max_length=10)


class VoiceProviderIn(BaseModel):
    """A separately-added voice provider (Phase 7 slice 3). The base
    URL is probed by the Test button; the key is stored like every
    other secret and is never returned in full."""

    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(default="", max_length=1000)
    api_key: str = Field(default="", max_length=2000)


class ClipUpdate(BaseModel):
    start_s: float | None = None
    end_s: float | None = None
    caption_text: str | None = Field(default=None, max_length=500)
    position: int | None = None
    # Ken Burns motion preset for this clip (one of CLIP_EFFECTS).
    effect: str | None = None


class RenderIn(BaseModel):
    """Render options (Phase 7 slice 2). quality is 720p / 1080p /
    4K; atmosphere flags are real ffmpeg filters, applied once on
    the whole video after captions. Cross-check slice: a named
    atmosphere_preset (one of ATMOSPHERE_PRESETS) replaces / extends
    the three bools; caption_size_pct scales the burned caption font
    (50–150, 100 = the style's own size); caption_position is
    bottom / center / top; captions=False burns no captions at all
    (ClipNova's "Captions: None")."""

    quality: str = "1080p"
    vignette: bool = False
    grain: bool = False
    warm: bool = False
    atmosphere_preset: str = Field(default="", max_length=50)
    caption_size_pct: int = Field(default=100, ge=50, le=150)
    caption_position: str = Field(default="bottom", max_length=10)
    captions: bool = True


class ApplyStyleIn(BaseModel):
    style_dna_id: int | None = None
    caption_style_id: int | None = None


class AutoSyncIn(BaseModel):
    """Script-beat sync input. captions[i] is the scene text for image i
    (in upload order); clip durations follow word counts. mode="equal"
    forces the old equal split; the default is script-beats when captions
    are given, equal split when they are not."""

    captions: list[str] | None = None
    mode: str = "script-beats"


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    # Empty = not specified: the endpoint uses the saved default voice
    # (VoiceForge favourite, setting default_tts_voice).
    voice: str = Field(default="", max_length=100)


class HeyGenSpeakIn(BaseModel):
    """HeyGen clone voiceover: text in Ale's own cloned voice. Language
    'en' (English, used as-is) or 'hi' (Urdu/Hindi — the 106 Hz pitch
    lock applies). voice_id empty = the saved clone voice (setting
    heygen_voice_id). HeyGen's speech endpoint takes at most 5000
    characters per request."""

    text: str = Field(min_length=1, max_length=5000)
    language: str = Field(default="en", max_length=10)
    voice_id: str = Field(default="", max_length=64)


class ScriptIn(BaseModel):
    """Create a script: paste/type full_text, or give only a topic and
    let the optional Gemini free-tier key generate the text. Slice 2:
    thinking_level + model pick the Thinking Level and the Gemini
    model for topic-only generation; pasted text ignores them."""

    topic: str = Field(default="", max_length=300)
    full_text: str = Field(default="", max_length=50000)
    thinking_level: str = Field(default="medium", max_length=20)
    model: str = Field(default="fast", max_length=20)


class SceneUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=5000)
    image_prompt: str | None = Field(default=None, max_length=5000)
    duration_s: float | None = None


class RunIn(BaseModel):
    """One-click run input. Voice comes from an uploaded voiceover
    asset, or from voice_text via free Edge-TTS (best-effort — it
    fails honestly with a clear error where Edge-TTS is blocked).
    caption_style_id overrides the timeline's current caption style."""

    script_id: int
    voiceover_asset_id: int | None = None
    voice_text: str | None = Field(default=None, max_length=5000)
    # Empty = not specified: the run uses the saved default voice
    # (VoiceForge favourite, setting default_tts_voice).
    voice: str = Field(default="", max_length=100)
    caption_style_id: int | None = None
    # Slice 3 (Magic Mode): aspect + Style DNA preset for the run.
    # Empty aspect = 16:9 (the old behaviour); empty style_dna_id =
    # the project's last used Style DNA, as before.
    aspect: str = Field(default="16:9", max_length=10)
    style_dna_id: int | None = None


class ReframeIn(BaseModel):
    """9:16 reframe input (Phase 6 slice 3): the caption style to
    burn in, by name — must be one of the styles in
    CAPTION_RENDER_SPECS, or "One Word Pop" (word-level, ClipForge
    only — real Whisper word timestamps, one word at a time). Anything
    else is a plain 400, never a silent fallback. Cross-check slice:
    aspect is 9:16 / 1:1 / 4:5 / 3:4; caption_size_pct scales the font
    (50–150, 100 = style default); caption_position is bottom /
    center / top; captions=False burns no captions."""

    caption_style: str = Field(default="Bold White", max_length=100)
    aspect: str = Field(default="9:16", max_length=10)
    caption_size_pct: int = Field(default=100, ge=50, le=150)
    caption_position: str = Field(default="bottom", max_length=10)
    captions: bool = True


class RenderFinalIn(BaseModel):
    """Final-clip render input (Phase 6 slice 4): the caption style
    to burn in, by name. Empty = reuse the latest done reframe's
    style (the preview the user already saw), or "Bold White" when
    there is no preview yet. Must be one of the styles in
    CAPTION_RENDER_SPECS, or "One Word Pop"; anything else is a plain
    400. Cross-check slice: aspect / caption_size_pct /
    caption_position / captions behave the same way — empty aspect
    reuses the latest done reframe's aspect, and the size/position/
    captions fields reuse the reframe's values when they are left at
    their defaults (size 100, position bottom, captions True) and a
    reframe exists."""

    caption_style: str = Field(default="", max_length=100)
    aspect: str = Field(default="", max_length=10)
    caption_size_pct: int | None = Field(default=None, ge=50, le=150)
    caption_position: str = Field(default="", max_length=10)
    captions: bool | None = None


class DetectMomentsIn(BaseModel):
    """Moment detection controls (cross-check slice, ClipNova parity):
    max_moments (1–10, default 5) caps how many moments come back;
    target_length_s (None = the old 20–45 s ideal; 15/25/30/40/60/90)
    moves the length-score peak to the chosen clip length. The window
    range stays 15–60 s — a target only re-weights, it never invents
    a window outside the real word timestamps."""

    max_moments: int = Field(default=5, ge=1, le=10)
    target_length_s: float | None = Field(default=None, ge=15, le=90)


class RenameFinalIn(BaseModel):
    """Rename a final clip (Phase 6 slice 4): the new title shown
    in the Approved clips list. Empty is a plain 400."""

    title: str = Field(default="", max_length=200)


class ThumbnailIn(BaseModel):
    """Thumbnail frame time in seconds. None = middle of the first
    clip of the latest timeline (the video's opening image). Slice 3
    (Magic Mode): width/height let a vertical/square video get a
    matching thumbnail instead of a letterboxed 1280x720 one."""

    timestamp_s: float | None = None
    width: int = Field(default=1280, ge=320, le=2160)
    height: int = Field(default=720, ge=320, le=3840)


class MetadataIn(BaseModel):
    """YouTube title / description / tags, hand-edited (YouTube's own
    limits: title 100 chars, description 5000, tags 500)."""

    title: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: str = Field(default="", max_length=500)


class AttachImageIn(BaseModel):
    """Attach an uploaded image to a scene, so it enters the same
    approve / reject verification flow as a generated image."""

    asset_id: int


class RejectImageIn(BaseModel):
    """Reject an image, with an optional short reason for the record."""

    reason: str = Field(default="", max_length=300)


class GenerateImagesIn(BaseModel):
    """Bulk image generation. provider is 'api' (Gemini API — the
    reliable paid route, default), 'canvas' (Gemini Canvas web app
    — free via the user's Gemini Pro quota, needs a Google login in
    the shared profile first) or 'flow' (Google Flow web app —
    free via the same Gemini Pro quota and the same login; if Flow
    fails on a scene the worker retries it once on Canvas).
    Cross-check slice: character_match (False = do not attach the
    character reference image) and style_match (False = drop the
    "Style: …" prefix from the prompt) are the AutoCut Gemini Bulk
    toggles — both default True, which is the locked-look behaviour
    the app already had."""

    provider: str = "api"
    character_match: bool = True
    style_match: bool = True
    # Slice 4 (Character Vault): niche_id pins the bulk run to
    # that niche's locked cast — the guard blocks the run when
    # the niche's mains are not locked yet, the locked
    # descriptions + poses are auto-injected into every scene
    # prompt, and the cast-sheet rides as the reference image.
    # scene_characters is an optional per-scene override
    # {scene_id: character name} — the name must be one of the
    # niche's 10 locked characters, else a plain 400.
    niche_id: int | None = None
    scene_characters: dict | None = None


class StickmanPromptUpdate(BaseModel):
    """Edit a generated stickman prompt (any field optional)."""

    pose: str | None = Field(default=None, max_length=50)
    action: str | None = Field(default=None, max_length=500)
    expression: str | None = Field(default=None, max_length=50)
    props: str | None = Field(default=None, max_length=300)
    background: str | None = Field(default=None, max_length=300)
    prompt: str | None = Field(default=None, max_length=5000)


class StickmanFrameIn(BaseModel):
    """Render a stickman frame for a scene. pose empty = the pose of
    the scene's stickman prompt (or 'standing' when there is none);
    props empty = the prompt's props. A named pose must be in the
    pose library, otherwise a plain 400."""

    pose: str = Field(default="", max_length=50)
    props: str = Field(default="", max_length=300)


class StickmanPoseUpdate(BaseModel):
    """Edit a pose's description (the pose name itself never changes
    — it is the contract with the renderer)."""

    description: str = Field(default="", max_length=500)


class MasterPromptIn(BaseModel):
    """A master prompt for the StoryCraft library. category must be
    one of hook / story / style-dna / viral-short; style_dna_id is
    optional and must name a real Style DNA row when given."""

    name: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=50)
    template: str = Field(default="", max_length=20000)
    style_dna_id: int | None = None
    source: str = Field(default="", max_length=300)


class MasterPromptUpdate(BaseModel):
    """Edit a master prompt (any field optional)."""

    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    template: str | None = Field(default=None, max_length=20000)
    style_dna_id: int | None = None
    source: str | None = Field(default=None, max_length=300)


class NicheIn(BaseModel):
    """A niche (AutoCut Writer / Video 7 parity): a topic family
    with an optional default Style DNA. Niches are the starting
    point for topic ideas, not a schedule — the app never auto-runs
    while the PC is off."""

    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)
    main_characters: str = Field(
        default="",
        max_length=2000,
        description="Main characters, one per line — 100% consistent in every scene.",
    )
    default_style_dna_id: int | None = None


class NicheUpdate(BaseModel):
    """Edit a niche (any field optional)."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    main_characters: str | None = Field(default=None, max_length=2000)
    default_style_dna_id: int | None = None


class VaultCharacterIn(BaseModel):
    """A Vault character: name + locked description + signature
    prop + role. poses empty = the 5 default poses (standing,
    pointing, walking, sitting, signature). A new character is
    always a draft v1 — it must be approved, then locked, before
    any bulk run may use it."""

    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)
    signature_prop: str = Field(default="", max_length=200)
    role: str = Field(default="secondary", max_length=20)
    poses: list | None = None
    sheet_path: str = Field(default="", max_length=500)


class VaultCharacterUpdate(BaseModel):
    """Edit a Vault character: creates a NEW version (draft vN+1),
    never edits the locked version in place — a video that used
    v1 must always find v1 again."""

    description: str | None = Field(default=None, max_length=1000)
    signature_prop: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=20)
    poses: list | None = None
    sheet_path: str | None = Field(default=None, max_length=500)


class StyleDnaFromDescriptionIn(BaseModel):
    """Style DNA from a plain-language description (StickFilm 'New
    category' parity): Gemini writes the style description + the
    master prompt; the row is saved. No key -> plain 400."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)


class ReverseEngineerIn(BaseModel):
    """Reverse-engineer a viral short into a master prompt (WAPCut
    Master Prompt Studio parity): paste what you saw (hook, visual
    style, pacing, captions, CTA) and Gemini writes the locked
    master prompt. No key -> plain 400."""

    name: str = Field(default="", max_length=200)
    notes: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="viral-short", max_length=50)


class TranscriptionUpdateIn(BaseModel):
    """Edit a transcript's full text (ClipNova 'Edit transcript'
    parity). Only full_text changes — words and segments stay as
    transcribed, so SRT/VTT keep the original timings."""

    full_text: str = Field(min_length=1, max_length=50000)


class ReuseFinalClipIn(BaseModel):
    """Reuse a final clip in another project (ClipNova Library
    'Reuse' parity): the clip file is COPIED into the target
    project (a real asset row there), never shared by path — so a
    delete in one project never breaks the other."""

    project_id: int


class ResearchNoteIn(BaseModel):
    """A StoryCraft research note for a project."""

    title: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=50000)


class DeepResearchIn(BaseModel):
    """Slice 2: run Deep Research on a topic before the script."""

    topic: str = Field(default="", max_length=300)


class WriteScriptIn(BaseModel):
    """Slice 2: options for writing a script — Thinking Level +
    model picker. Empty = defaults (Medium + Fast), so old callers
    that POST with no body keep working."""

    thinking_level: str = Field(default="medium", max_length=20)
    model: str = Field(default="fast", max_length=20)


# --- Phase 2 helpers ------------------------------------------------------

VOICE_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_CLIP_S = 3.0  # seconds per image when there is no voiceover


def safe_filename(name: str) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return base[:120] or "file"


def probe_duration(path: Path) -> float:
    """Media duration in seconds via ffprobe; 0.0 if it cannot be read."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        out = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        return float(data.get("format", {}).get("duration") or 0.0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def probe_video_dims(path: Path) -> tuple[int, int]:
    """Video width/height via ffprobe; (0, 0) if it cannot be read."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return (0, 0)
    try:
        out = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        streams = data.get("streams") or []
        if not streams:
            return (0, 0)
        return (
            int(streams[0].get("width") or 0),
            int(streams[0].get("height") or 0),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return (0, 0)


def get_character(conn, project_id: int) -> dict | None:
    """The project's main character, if one was uploaded."""
    row = conn.execute(
        "SELECT * FROM project_characters WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


# --- Phase 3: scripts + scene breakdown ---------------------------------

# Narration is estimated at ~150 words per minute for scene durations.
# The timeline re-derives exact timings from the real voiceover, so this
# is only a planning estimate.
WORDS_PER_MINUTE = 150.0


ABBREVIATIONS = (
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "st.",
    "vs.",
    "e.g.",
    "i.e.",
    "u.s.",
    "u.k.",
    "no.",
    "etc.",
)


def _sentences(block: str) -> list[str]:
    """Split a block into sentences. A fragment ending in a common
    abbreviation (Mr., Dr., e.g.) is glued to the next fragment, so
    titles do not become their own 'sentence'."""
    parts = [
        s.strip()
        for s in re.split(r"(?<=[.!?…])\s+|\n+", block)
        if s.strip()
    ]
    out: list[str] = []
    for p in parts:
        if out and out[-1].lower().endswith(ABBREVIATIONS):
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return out


def split_script(text: str) -> list[str]:
    """Split narration into scenes — one scene per sentence, so the
    visual changes on every sentence, not every paragraph (Ale's
    requirement: har sentence ke saath visual change). A single
    sentence over 60 words is chunked into 40-word pieces. Empty
    input -> []."""
    text = (text or "").strip()
    if not text:
        return []
    scenes: list[str] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]
    for para in paragraphs:
        for sent in _sentences(para):
            words = sent.split()
            if len(words) <= 60:
                scenes.append(sent)
            else:
                for i in range(0, len(words), 40):
                    scenes.append(" ".join(words[i : i + 40]))
    return scenes


def estimate_duration_s(text: str) -> float:
    """Rough scene length from word count, minimum 2 s."""
    return round(max(2.0, len(text.split()) / WORDS_PER_MINUTE * 60), 1)


def resolve_script_style(conn, project_id: int) -> dict | None:
    """The project's Style DNA for image prompts: the timeline's style
    when one is applied, else the first Style DNA row (the default look)."""
    row = conn.execute(
        "SELECT style_dna_id FROM timelines WHERE project_id = ?"
        " AND style_dna_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    style_id = row["style_dna_id"] if row else None
    if style_id is not None:
        s = conn.execute(
            "SELECT * FROM style_dna WHERE id = ?", (style_id,)
        ).fetchone()
        if s is not None:
            return dict(s)
    first = conn.execute(
        "SELECT * FROM style_dna ORDER BY id LIMIT 1"
    ).fetchone()
    return dict(first) if first else None


def build_image_prompt(
    scene_text: str,
    style: dict | None,
    character_name: str | None,
    aspect: str | None = None,
    character_description: str | None = None,
    pose: str | None = None,
    character_description_verbatim: bool = False,
) -> str:
    """Template-built image prompt (no AI call): scene + Style DNA +
    main character by name, so every scene keeps the same look.
    Slice 3 (Magic Mode): aspect adds a composition note (9:16 /
    1:1) so the provider frames for the target shape; 16:9 adds
    nothing, keeping the old prompts byte-identical.
    Slice 3 auto-consistency (Ali's rule: the user does nothing
    manual): the Style DNA block is always on; the locked
    character description + name are injected; a negative
    constraint ("do not change face, beard, clothes or style")
    rides with the character bit; and a scene rule caps the
    scene at 2-3 main characters with simple, generic background
    characters. All of it is automatic - no prompt writing, no
    reference picking, no pose writing from the user.
    Slice 4 (Character Vault): pose is an optional pose line
    ("Pose: ...") appended after the character bit. None keeps
    the old output byte-identical — the Vault pose pick calls
    this with the picked pose, and no other caller passes it."""
    bits: list[str] = []
    if style:
        bit = f"Style: {style['name']}"
        if style.get("description"):
            bit += f" — {style['description'].rstrip('.')}"
        bits.append(bit)
    bits.append(f"Scene: {scene_text.rstrip('.')}")
    if aspect and aspect != "16:9":
        if aspect == "9:16":
            bits.append(
                "Vertical 9:16 composition, tall frame, subject centred"
            )
        else:
            bits.append("Square 1:1 composition, subject centred")
    bits.append(
        "Scene rule: at most 2-3 main characters in this scene;"
        " background characters stay simple and generic, with no"
        " distinctive face, beard or costume"
    )
    if character_name:
        desc = (character_description or "").strip()
        if character_description_verbatim:
            # Main character (Char Reference method): the FULL
            # description goes in VERBATIM, word for word, as its
            # own sentence — never collapsed. The Character Match
            # strip helper still removes the whole block: its
            # regex looks ahead to "No photorealism", so inner
            # periods do not break it.
            char_bit = f"Main character: {character_name}"
            char_bit += (
                " — same face, outfit and colours in every scene;"
                " do not change face, beard, clothes or style"
            )
            bits.append(char_bit)
            if desc:
                bits.append(f"Character description: {desc.rstrip('.')}")
        else:
            # One sentence, no inner periods: the Character Match
            # strip helper expects the character bit to end right
            # before "No photorealism".
            desc = desc.rstrip(".").replace(". ", ", ")
            char_bit = f"Main character: {character_name}"
            if desc:
                char_bit += f" ({desc})"
            char_bit += (
                " — same face, outfit and colours in every scene;"
                " do not change face, beard, clothes or style"
            )
            bits.append(char_bit)
        if pose:
            bits.append(f"Pose: {pose.strip().rstrip('.')}")
    bits.append("No photorealism, no 3D, no text in the image")
    return ". ".join(bits) + "."


# ----------------------------------------------------------------------
# Slice 4 — Character Vault helpers
# ----------------------------------------------------------------------
# A niche's Vault is its 7 x 10 approved characters, locked and
# versioned. Everything below is automatic (Ali's rule: the user
# does nothing manual): niche select -> mains auto-select; the
# locked description + sheet reference ride every bulk prompt;
# the pose is picked from the script's action; the version is
# always the active locked one; a niche without a locked cast
# blocks bulk (guard).
# ----------------------------------------------------------------------

_VAULT_POSE_TEMPLATES = [
    ("standing", "{name} standing upright, facing forward"),
    ("pointing", "{name} pointing forward with one hand"),
    ("walking", "{name} walking forward"),
    ("sitting", "{name} sitting down"),
    ("signature", "{name} with {prop} clearly visible"),
]

# Action keywords -> pose name. First match wins; no match is
# "standing". These are plain words, not a model call, so the pick
# is deterministic and free.
_VAULT_POSE_KEYWORDS = [
    (("point", "show", "look", "there"), "pointing"),
    (("walk", "go", "leave", "arrive", "march", "run", "sail"), "walking"),
    (("sit", "rest", "eat", "drink", "talk", "listen"), "sitting"),
    (("crown", "hat", "cap", "prop", "show"), "signature"),
]


def _vault_default_poses(name: str, signature_prop: str) -> list[dict]:
    """The 5 fixed poses for a character, built from the template
    (name + signature prop filled in). Used at seed time and when
    a new character is created without an explicit poses list."""
    prop = signature_prop.strip() or "signature item"
    return [
        {"name": pose_name, "description": template.format(name=name, prop=prop)}
        for pose_name, template in _VAULT_POSE_TEMPLATES
    ]


def _vault_pick_pose(scene_text: str, poses: list[dict]) -> dict | None:
    """Pick a pose from the script action: first keyword match
    wins, else the 'standing' pose, else the first pose. Returns
    the pose dict, or None when the character has no poses at
    all."""
    if not poses:
        return None
    text = (scene_text or "").lower()
    for keywords, pose_name in _VAULT_POSE_KEYWORDS:
        if any(k in text for k in keywords):
            for pose in poses:
                if pose.get("name") == pose_name:
                    return pose
    for pose in poses:
        if pose.get("name") == "standing":
            return pose
    return poses[0]


def _niche_main_names(main_characters: str) -> list[str]:
    """The niche's main character NAMES. main_characters stores
    one line per main in the form 'Name (description)' (the
    Direction Pack format), so the name is the part before the
    first ' (' — a bare line without a description is its own
    name."""
    names = []
    for line in (main_characters or "").splitlines():
        line = line.strip()
        if not line:
            continue
        names.append(line.split(" (", 1)[0].strip())
    return names


def _vault_row(row: sqlite3.Row) -> dict:
    """One vault_characters row as the API shape."""
    return {
        "id": row["id"],
        "niche_id": row["niche_id"],
        "name": row["name"],
        "description": row["description"],
        "signature_prop": row["signature_prop"],
        "role": row["role"],
        "poses": json.loads(row["poses_json"] or "[]"),
        "sheet_path": row["sheet_path"],
        "sheet_url": media_url(row["sheet_path"]) if row["sheet_path"] else None,
        "thumb_path": row["thumb_path"] if "thumb_path" in row.keys() else "",
        "thumb_url": (
            media_url(row["thumb_path"])
            if "thumb_path" in row.keys() and row["thumb_path"]
            else None
        ),
        "version": row["version"],
        "status": row["status"],
        "is_active": bool(row["is_active"]),
        "source": row["source"] if "source" in row.keys() else "builtin",
        "is_main": bool(row["is_main"]) if "is_main" in row.keys() else False,
    }


def _vault_main(conn: sqlite3.Connection) -> dict | None:
    """The user's locked main character (is_main=1, status='locked'),
    or None. At most one row ever has is_main=1 — set-main clears
    the others first. Built-in characters can be a main too; the
    usual case is the user's own uploaded sheet."""
    row = conn.execute(
        "SELECT * FROM vault_characters WHERE is_main = 1"
        " AND status = 'locked' AND is_active = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    return _vault_row(row) if row is not None else None


def _vault_locked(conn: sqlite3.Connection, niche_id: int) -> list[dict]:
    """The niche's ACTIVE locked characters (the cast a bulk run
    may use). Only is_active=1 + status='locked' rows count."""
    rows = conn.execute(
        "SELECT * FROM vault_characters WHERE niche_id = ?"
        " AND status = 'locked' AND is_active = 1 ORDER BY"
        " CASE role WHEN 'main' THEN 0 ELSE 1 END, name",
        (niche_id,),
    ).fetchall()
    return [_vault_row(r) for r in rows]


def _vault_resolve(conn: sqlite3.Connection, niche_id: int) -> dict:
    """Resolve a niche to its Vault cast: niche row + locked
    characters split into mains / secondaries + the sheet path
    (the first locked character's sheet; all 10 of a niche share
    one cast-sheet image). Raises HTTPException 404 for an
    unknown niche."""
    niche = conn.execute(
        "SELECT * FROM niches WHERE id = ?", (niche_id,)
    ).fetchone()
    if niche is None:
        raise HTTPException(status_code=404, detail="Niche not found")
    locked = _vault_locked(conn, niche_id)
    mains = [c for c in locked if c["role"] == "main"]
    secondaries = [c for c in locked if c["role"] != "main"]
    sheet_path = locked[0]["sheet_path"] if locked else ""
    return {
        "niche_id": niche["id"],
        "niche_name": niche["name"],
        "main_characters": [c["name"] for c in mains],
        "mains": mains,
        "secondaries": secondaries,
        "character_count": len(locked),
        "sheet_path": sheet_path,
        "sheet_url": media_url(sheet_path) if sheet_path else None,
        "sheet_exists": bool(sheet_path)
        and (DATA_DIR / sheet_path).is_file(),
    }


def _vault_guard(conn: sqlite3.Connection, niche_id: int) -> dict:
    """Guard: bulk may only run on a niche whose mains are all
    locked. A new niche (sheet -> approve -> lock) has no locked
    mains, so bulk is blocked with a plain 400 saying why. The
    mains come from the niche's own main_characters list (the
    Direction Pack), not from the Vault — the Vault must cover
    them, not define them."""
    resolved = _vault_resolve(conn, niche_id)
    niche = conn.execute(
        "SELECT main_characters FROM niches WHERE id = ?", (niche_id,)
    ).fetchone()
    expected = _niche_main_names(niche["main_characters"])
    locked_names = {c["name"] for c in resolved["mains"]}
    missing = [n for n in expected if n not in locked_names]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Niche '{resolved['niche_name']}' has no locked"
                f" character sheet yet — lock these mains first:"
                f" {', '.join(missing)}. Upload a sheet, approve"
                " it, then lock it."
            ),
        )
    return resolved


def _vault_pin(resolved: dict, main: dict | None = None) -> dict:
    """Snapshot a resolved Vault cast for one batch: the batch
    pins the locked versions it started with, so a re-lock
    mid-batch can never mix v1/v2 inside one video. The pin
    rides in the job options_json. When the user's locked main
    character belongs to THIS niche, it rides as main_character
    (its sheet becomes the reference image) and every scene uses
    it — that is the competitor's Char Reference method: full
    description verbatim + reference image, every prompt."""
    pin = {
        "niche_id": resolved["niche_id"],
        "niche_name": resolved["niche_name"],
        "sheet_path": resolved["sheet_path"],
        "characters": [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "signature_prop": c["signature_prop"],
                "role": c["role"],
                "version": c["version"],
                "poses": c["poses"],
            }
            for c in resolved["mains"] + resolved["secondaries"]
        ],
        "main_character": None,
    }
    if main is not None and main["niche_id"] == resolved["niche_id"]:
        pin["main_character"] = {
            "id": main["id"],
            "name": main["name"],
            "description": main["description"],
            "signature_prop": main["signature_prop"],
            "role": main["role"],
            "version": main["version"],
            "poses": main["poses"],
            "sheet_path": main["sheet_path"],
        }
        if main["sheet_path"]:
            pin["sheet_path"] = main["sheet_path"]
    return pin


def _vault_pin_for_main(main: dict, niche_name: str) -> dict:
    """A pin from the user's main character alone — for Magic/bulk
    runs with NO niche selected. The main IS the cast: one
    character, every scene, its sheet as the reference."""
    return {
        "niche_id": main["niche_id"],
        "niche_name": niche_name,
        "sheet_path": main["sheet_path"],
        "characters": [
            {
                "id": main["id"],
                "name": main["name"],
                "description": main["description"],
                "signature_prop": main["signature_prop"],
                "role": main["role"],
                "version": main["version"],
                "poses": main["poses"],
            }
        ],
        "main_character": {
            "id": main["id"],
            "name": main["name"],
            "description": main["description"],
            "signature_prop": main["signature_prop"],
            "role": main["role"],
            "version": main["version"],
            "poses": main["poses"],
            "sheet_path": main["sheet_path"],
        },
    }


def _vault_prompt_aspect(stored_prompt: str) -> str:
    """The aspect a stored scene prompt was built for: the
    9:16 / 1:1 composition note is inside the prompt text."""
    if "Vertical 9:16 composition" in (stored_prompt or ""):
        return "9:16"
    if "Square 1:1 composition" in (stored_prompt or ""):
        return "1:1"
    return "16:9"


def _vault_apply_to_scenes(
    conn: sqlite3.Connection,
    script_id: int,
    pin: dict,
    style: dict | None,
    aspect: str,
    scene_characters: dict | None = None,
) -> dict[int, dict]:
    """Rebuild a script's scene prompts from the pinned Vault
    cast: each scene gets a main character (rotating through the
    mains in scene order, or the user's per-scene override from
    scene_characters — scene id -> character name), the locked
    description, and the pose the script action picks. The
    rebuilt prompt is written back to scenes.image_prompt, so
    the worker (which only reads the stored prompt) needs no
    change. Returns scene_id -> {character, pose, version} for
    the job options / summary. A scene's override names a
    character outside the 10 -> 400, never a silent generic."""
    scenes = conn.execute(
        "SELECT id, text, image_prompt FROM scenes WHERE script_id = ?"
        " ORDER BY position",
        (script_id,),
    ).fetchall()
    characters = pin["characters"]
    mains = [c for c in characters if c["role"] == "main"] or characters
    by_name = {c["name"]: c for c in characters}
    overrides = scene_characters or {}
    # Release Packaging (My Main Character): a locked main
    # character is THE character of every scene — its full
    # description goes in verbatim (Char Reference method). An
    # explicit per-scene override still wins: it is a deliberate
    # pick, not an accident.
    main_char = pin.get("main_character")
    mapping: dict[int, dict] = {}
    for idx, scene in enumerate(scenes):
        sid = scene["id"]
        override = overrides.get(str(sid)) or overrides.get(sid)
        verbatim = False
        if override is not None:
            char = by_name.get(override)
            if char is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Character '{override}' is not in the"
                        f" locked cast of '{pin['niche_name']}'"
                        " — pick one of the 10 locked characters."
                    ),
                )
        elif main_char is not None:
            char = main_char
            verbatim = True
        else:
            char = mains[idx % len(mains)]
        pose = _vault_pick_pose(scene["text"], char.get("poses") or [])
        prompt = build_image_prompt(
            scene["text"],
            style,
            char["name"],
            aspect=aspect,
            character_description=char["description"],
            pose=pose["description"] if pose else None,
            character_description_verbatim=verbatim,
        )
        conn.execute(
            "UPDATE scenes SET image_prompt = ? WHERE id = ?",
            (prompt, sid),
        )
        mapping[sid] = {
            "character": char["name"],
            "pose": pose["name"] if pose else None,
            "version": char["version"],
        }
    return mapping


# Slice 2 (StoryCraft Deep Research + Thinking Levels): the script
# model picker — Fast / Deep / Code. All three were verified live
# 2026-11-21 on Ale's key with a one-word probe:
# - fast: gemini-3.5-flash (the app's script model since Phase 7
#   slice 3; ~16 s for a test hook, ~76 s for one word in a later
#   probe — free-tier latency varies, so the timeout is generous).
# - deep: gemini-3.8-flash (works, ~218 s for a hook — genuinely
#   slower and deeper, hence the 300 s timeout; the old 60 s timeout
#   would have killed every Deep call).
# - code: gemini-3.6-flash (works; used with a structured, precise
#   prompt — tight factual beats, no filler).
# NOT used: gemini-2.5-pro (404, "no longer available to new users"),
# gemini-3.1-pro-preview (free-tier input-token quota exhausted),
# gemini-3.7-flash (503, high demand). No new provider, no billing.
GEMINI_SCRIPT_MODELS = {
    "fast": {"model": "gemini-3.5-flash", "timeout_s": 120},
    "deep": {"model": "gemini-3.8-flash", "timeout_s": 300},
    "code": {"model": "gemini-3.6-flash", "timeout_s": 180},
}
GEMINI_SCRIPT_MODEL = "gemini-3.5-flash"

# Slice 2: Thinking Levels — Low (tez draft), Medium (balanced),
# High (gehri script). The effect is real, not a label: each level
# changes the prompt (length, depth, structure), the temperature and
# the token budget. Medium is byte-for-byte the prompt the app has
# used since Phase 3, so existing behaviour is unchanged.
THINKING_LEVELS = {
    "low": {
        "label": "Low — tez draft",
        "temperature": 0.5,
        "max_tokens": 600,
        "prompt": (
            "Write a short, fast 1-minute documentary narration draft"
            " in English about: {topic}. About 80-100 words. Pure"
            " narration only — no brackets, no stage directions, no"
            " headings, no scene labels. Short, direct sentences,"
            " one story beat per paragraph."
        ),
    },
    "medium": {
        "label": "Medium — balanced",
        "temperature": 0.7,
        "max_tokens": 1200,
        "prompt": (
            "Write a 1-minute documentary narration script in English"
            " about: {topic}. About 140-160 words. Pure narration"
            " only — no brackets, no stage directions, no headings,"
            " no scene labels. Split it into short paragraphs, one"
            " story beat per paragraph."
        ),
    },
    "high": {
        "label": "High — gehri script",
        "temperature": 0.9,
        "max_tokens": 2000,
        "prompt": (
            "Write a deep, cinematic 1-minute documentary narration"
            " script in English about: {topic}. About 200-260 words."
            " Open with a strong hook, build a clear conflict, add a"
            " twist, and end with an open loop or a strong closing"
            " line. Pure narration only — no brackets, no stage"
            " directions, no headings, no scene labels. Split it"
            " into short paragraphs, one story beat per paragraph."
        ),
    },
}


def _validate_thinking_level(level: str) -> str:
    level = (level or "").strip().lower() or "medium"
    if level not in THINKING_LEVELS:
        raise ValueError(
            "thinking level 'low', 'medium' ya 'high' hona chahiye"
        )
    return level


def _validate_script_model(model: str) -> str:
    model = (model or "").strip().lower() or "fast"
    if model not in GEMINI_SCRIPT_MODELS:
        raise ValueError(
            "model 'fast', 'deep' ya 'code' hona chahiye"
        )
    return model


def _script_prompt(
    topic: str,
    thinking_level: str = "medium",
    model: str = "fast",
    language: str = "en",
) -> tuple:
    """Shared narration-script prompt for Gemini AND OpenRouter: same
    words, same thinking level, same language. Returns
    (prompt, thinking_cfg, model_spec)."""
    level = _validate_thinking_level(thinking_level)
    model_key = _validate_script_model(model)
    language = magic_validate_language(language)
    spec = GEMINI_SCRIPT_MODELS[model_key]
    cfg = THINKING_LEVELS[level]
    prompt = cfg["prompt"].format(topic=topic)
    if language == "ur":
        prompt += (
            " Write the script in Roman Urdu — simple spoken Roman"
            " Urdu in Latin letters, no Devanagari script, no Hindi"
            " words."
        )
    if model_key == "code":
        # Code = structured + precise: every sentence carries one
        # verifiable fact, no filler — the narration stays pure
        # (no beat labels in the spoken text).
        prompt += (
            " Keep every sentence tight and factual — one verifiable"
            " fact per sentence, no filler words, no repetition."
        )
    return prompt, cfg, spec


def _setting_value(conn, key: str) -> str:
    """One settings value, stripped; "" when the row is missing."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return (row["value"].strip() if row else "")


OPENROUTER_TEXT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_FREE_MODEL = "meta-llama/llama-3.1-8b-instruct:free"


def openrouter_generate_script(
    api_key: str,
    topic: str,
    thinking_level: str = "medium",
    model: str = "fast",
    language: str = "en",
) -> str:
    """Generate narration text from a topic via OpenRouter's FREE
    models — the fallback when the user has NO Gemini key at all
    (never a silent switch when Gemini keys exist). Same prompt as
    Gemini, same language rule. stdlib only; the key is the user's
    own free OpenRouter key, never logged. Any provider failure is
    raised as a plain error."""
    import urllib.error
    import urllib.request

    prompt, cfg, _spec = _script_prompt(topic, thinking_level, model, language)
    payload = {
        "model": OPENROUTER_FREE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    req = urllib.request.Request(
        OPENROUTER_TEXT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "Kreafy Creator Studio",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenRouter API error ({exc.code}): {body}")
    except OSError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}")
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("OpenRouter returned no script text")
    text = (text or "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned no script text")
    return text


def _generate_script_text(
    conn, topic: str, thinking_level: str = "medium",
    model: str = "fast", language: str = "en",
) -> tuple:
    """Script text + source ("gemini" | "openrouter"). Gemini keys
    (rotation) first; only when the user has NO Gemini key at all does
    the free OpenRouter model run. Neither key -> plain RuntimeError
    naming both free options — never a fake script."""
    keys = _gemini_keys(conn)
    if keys:
        text, _attempts = _gemini_try_keys(
            keys,
            lambda k: gemini_generate_script(
                k, topic, thinking_level=thinking_level,
                model=model, language=language,
            ),
        )
        return text, "gemini"
    or_key = _setting_value(conn, "openrouter_api_key")
    if or_key:
        return (
            openrouter_generate_script(
                or_key, topic, thinking_level=thinking_level,
                model=model, language=language,
            ),
            "openrouter",
        )
    raise RuntimeError(
        "Script ke liye key chahiye — apni Gemini key"
        " (aistudio.google.com, FREE) ya OpenRouter key"
        " (openrouter.ai, FREE) Settings → Free keys me add karein"
    )


def gemini_generate_script(
    api_key: str,
    topic: str,
    thinking_level: str = "medium",
    model: str = "fast",
    language: str = "en",
) -> str:
    """Generate narration text from a topic via the Gemini free tier.

    stdlib only (urllib) — no new dependency. The key is the user's own
    AI Studio free-tier key from Settings; it is never logged or put in
    an error message. Any provider failure is raised as a plain error.
    thinking_level changes the prompt + temperature + token budget;
    model picks the Gemini model (fast/deep/code) and its timeout.
    A bad level/model is a ValueError, never a silent fallback.
    Slice 3 (Magic Mode): language='ur' writes the script in Roman
    Urdu (Latin letters, no Devanagari).

    KEY TRANSPORT (v0.14.1 — live verified 2026-11-22): the key goes
    in the `x-goog-api-key` header, NEVER in the URL. AI Studio keys
    since 28 May 2026 start with `AQ.` (AIza is legacy) and Google
    answers `?key=<AQ-key>` with 400 API_KEY_INVALID while the SAME
    key via the header returns 200. Keys are never validated by
    prefix or length — AQ. and AIza are both accepted.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    prompt, cfg, spec = _script_prompt(topic, thinking_level, model, language)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": cfg["temperature"],
            "maxOutputTokens": cfg["max_tokens"],
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{spec['model']}:generateContent"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=spec["timeout_s"]) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise GeminiProviderError(
            f"Gemini API error ({exc.code}): {body}", exc.code, body
        )
    except OSError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}")
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no script text")
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned no script text")
    return text


def _parse_research_facts(text: str) -> list[dict]:
    """Parse a deep-research answer into [{fact, source}] pairs.

    The research prompt asks for a strict format — 'Fact: ...' then
    'Source: ...' per fact, blank line between facts. Lines that do
    not fit the format are never turned into facts; a badly formatted
    answer parses to an empty list (the raw text is still saved on
    the note, so nothing is lost and nothing is invented).
    """
    facts: list[dict] = []
    current: dict | None = None
    for raw in (text or "").splitlines():
        line = raw.strip().strip("*").strip()
        low = line.lower()
        if low.startswith("fact:") or low.startswith("fact :"):
            if current and current.get("fact"):
                facts.append(current)
            current = {"fact": line.split(":", 1)[1].strip(), "source": ""}
        elif low.startswith("source:") or low.startswith("source :"):
            if current is not None:
                current["source"] = line.split(":", 1)[1].strip()
        elif current is not None and line and not low.startswith("fact"):
            # A fact that wraps over two lines — keep it together.
            if not current.get("source"):
                current["fact"] = (current["fact"] + " " + line).strip()
    if current and current.get("fact"):
        facts.append(current)
    return [f for f in facts if f.get("fact")]


def gemini_deep_research(
    api_key: str, topic: str, language: str = "en"
) -> tuple[str, list[dict]]:
    """Research a topic before the script is written (Slice 2).

    One gemini-3.5-flash call (the connected free-tier script model),
    low temperature so the facts stay factual. The prompt demands
    4-6 key facts with a source per fact, and tells the model not to
    invent dates or numbers it is unsure of. Returns (raw text,
    parsed facts); a badly formatted answer still returns its raw
    text with an empty facts list — never a fake fact.
    Slice 3 (Magic Mode): language='ur' asks for the facts in
    Roman Urdu (Latin letters, no Devanagari).
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    language = magic_validate_language(language)
    prompt = (
        "Research this topic for a 1-minute documentary video:"
        f" {topic}. Give 4-6 key facts a viewer must know, each"
        " fact one or two sentences, each with its source (the"
        " website or publication the fact comes from, e.g."
        " Wikipedia, Britannica, BBC, History.com, an official"
        " site). If you are unsure of a date or number, say so —"
        " do not invent dates, numbers or sources. Use exactly"
        " this format, one fact per block:\n\n"
        "Fact: <the fact>\nSource: <where it comes from>\n\n"
        "Fact: <the fact>\nSource: <where it comes from>"
    )
    if language == "ur":
        prompt += (
            " Write the facts in Roman Urdu — simple spoken Roman"
            " Urdu in Latin letters, no Devanagari script, no Hindi"
            " words."
        )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_SCRIPT_MODEL}:generateContent"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise GeminiProviderError(
            f"Gemini API error ({exc.code}): {body}", exc.code, body
        )
    except OSError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}")
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no research text")
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned no research text")
    return text, _parse_research_facts(text)


def gemini_generate_text(
    api_key: str, prompt: str, max_tokens: int = 1200
) -> str:
    """Generic free-tier text call (same stdlib urllib pattern as
    gemini_generate_script, but the caller supplies the full prompt).
    Used by the cross-check slice for topic ideas, Style DNA from a
    description, and master-prompt reverse-engineering. The key is
    never logged or put in an error message."""
    import urllib.error
    import urllib.parse
    import urllib.request

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_SCRIPT_MODEL}:generateContent"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise GeminiProviderError(
            f"Gemini API error ({exc.code}): {body}", exc.code, body
        )
    except OSError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}")
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no text")
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned no text")
    return text


# --- Phase 4 slice 2: bulk image generation (VisualForge) --------------

# Gemini native image generation (REST, stdlib only — same pattern as
# gemini_generate_script). The key is the user's own AI Studio key from
# Settings; it is never logged or put in an error message. Honest caveat
# (verified live 2026-11-21): Google documents this image model as a
# paid-tier model, and on Ale's key the free-tier limit is 0 — both
# gemini-2.5-flash-image and gemini-3.1-flash-image return 429. So API
# image generation needs billing on the Google Cloud project; the free
# image route is the Gemini Canvas provider (a later slice), and the
# upload-your-own-image path already works. The model name below stays
# as-is until billing is enabled — it is also retired for new keys,
# so it must be updated to gemini-3.1-flash-image at that point.
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"
GEMINI_KEY_MISSING_MSG = (
    "Gemini key Settings me lagayen — bina key ke image nahi ban sakti"
)
GEMINI_LIMIT_MSG = "aaj ki free images khatam — kal dobara"

# Phase 5 slice 3: HeyGen clone voice (VoiceForge). The speech endpoint
# is POST https://api.heygen.com/v3/models/audio/tts with an X-Api-Key
# header (HeyGen docs, developers.heygen.com — Text to Speech). The
# request body carries model + voice_id + text + language; the response
# is a JSON with an audio URL (44.1 kHz WAV by default). Model
# heygen-voice-1-turbo: the Eiffel Tower VO was made with it (the
# server rejects heygen-voice-1-turbo-free for this clone path).
# expressivenessBoost 1.0 is the locked value from the Urdu VO recipe.
# NOTE: no live HeyGen call was made in the build VM — the endpoint and
# payload are from HeyGen's own docs + the verified MCP usage in this
# workspace, and the first real run with Ale's key will prove them.
HEYGEN_TTS_URL = "https://api.heygen.com/v3/models/audio/tts"
HEYGEN_VOICE_MODEL = "heygen-voice-1-turbo"
# Release Packaging (scrub): koi personal clone voice_id ya naam yahan
# HARDCODED nahi hota. Har user apni HeyGen key + apni clone voice_id
# Settings me lagata hai (settings.heygen_voice_id); khaali ho to
# HeyGen wale features saaf "apni voice_id lagayen" kehte hain.
# (Purani installs me jo voice_id local DB me saved hai, wo wahin
# rehti hai — seed badalne se kisi ki saved voice nahi jati.)
HEYGEN_KEY_MISSING_MSG = (
    "HeyGen key Settings me lagayen — bina key ke awaz nahi ban sakti"
)
HEYGEN_VOICE_MISSING_MSG = (
    "apni HeyGen clone voice_id Settings me lagayen — bina voice_id"
    " ke awaz nahi ban sakti"
)
# 106 Hz lock (Urdu/Hindi only): pitch x1.0495, tempo untouched. The
# locked recipe measures the raw F0 median per text (106 / raw); 1.0495
# is the verified factor for the 1-minute Urdu VO (raw 101 Hz). English
# is never pitch-shifted.
HEYGEN_PITCH_FACTOR = 1.0495

# One worker at a time processes image-generate jobs, so the daily
# quota counter can never be overrun by two parallel runs.
_IMAGE_GEN_LOCK = asyncio.Lock()
# The exact request body of the first generation of a bulk run is saved
# here (local, gitignored) so the call is provably correct even before
# any key exists to run it against. The API key is in the URL query, so
# it is never part of this file.
IMAGE_REQUEST_SAMPLE_PATH = DATA_DIR / "gemini-image-request-sample.json"

_REF_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _gemini_key(conn) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'gemini_api_key'"
    ).fetchone()
    return (row["value"].strip() if row else "")


# --- Phase 7 slice 3: multi-API-key rotation --------------------------

class GeminiProviderError(RuntimeError):
    """A Gemini HTTP failure that keeps its status code and body, so
    the rotation helper can tell a dead key (401/403/429, or a 400
    that names the API key) from a dead model or a bad request —
    only a dead key moves to the next key."""

    def __init__(self, message: str, code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.body = body


def _mask_secret(value: str) -> str:
    """Dots + LAST 4 chars — a key is never returned in full, and
    the first chars (which identify the key type) stay hidden too."""
    if not value:
        return ""
    return "••••••••" + value[-4:]


def _is_key_error(code: int | None, body: str) -> bool:
    """True when the failure is about the key, not the request: auth
    failures, quota exhaustion, or a 400 that names the API key
    (Google answers an invalid key with 400 'API key not valid')."""
    if code in (401, 403, 429):
        return True
    return code == 400 and "api key" in (body or "").lower()


def _gemini_keys(conn) -> list[str]:
    """All configured Gemini keys in rotation order (position, then
    id). Falls back to the legacy single setting when the keys table
    is empty, so setups from before this slice keep working."""
    rows = conn.execute(
        "SELECT key_value FROM gemini_api_keys ORDER BY position, id"
    ).fetchall()
    keys = [r["key_value"].strip() for r in rows if r["key_value"].strip()]
    if keys:
        return keys
    legacy = _gemini_key(conn)
    return [legacy] if legacy else []


def _gemini_try_keys(keys: list[str], fn) -> tuple:
    """Try fn(key) against each key in order. A dead key moves to the
    next one; any other failure stops immediately. Returns (result,
    attempts) where attempts is [(key_no, code)] for the keys that
    failed first. When every key is dead, raises RuntimeError naming
    every attempt — never a fake success, never a silent skip."""
    attempts: list[tuple[int, int | None]] = []
    for i, key in enumerate(keys, start=1):
        try:
            return fn(key), attempts
        except GeminiProviderError as exc:
            attempts.append((i, exc.code))
            if _is_key_error(exc.code, exc.body):
                continue
            raise
    if not keys:
        raise RuntimeError("no Gemini key configured")
    detail = ", ".join(f"key {i}: {code}" for i, code in attempts)
    raise RuntimeError(
        f"saari Gemini keys fail ho gayin ({detail})"
        " — Settings me keys check karein ya nayi key add karein"
    )


def _daily_image_limit(conn) -> int:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'gemini_free_limit_per_day'"
    ).fetchone()
    try:
        return int((row["value"] if row else "20").strip())
    except ValueError:
        return 20


def _image_quota(conn) -> dict:
    """Real daily image-generation quota — for the API provider only.
    used_today counts finished images; reserved also counts queued +
    running ones, so a bulk queue can never promise more than the
    limit allows. Canvas jobs run on the user's Gemini Pro quota, not
    on the API key, so they are counted separately and never consume
    this limit."""
    daily_limit = _daily_image_limit(conn)
    counts = conn.execute(
        "SELECT status, COUNT(*) AS n FROM jobs WHERE kind = 'image-generate'"
        " AND COALESCE(provider, 'api') = 'api'"
        " AND date(created_at) = date('now') GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: int(r["n"]) for r in counts}
    used = by_status.get("done", 0)
    reserved = (
        used + by_status.get("running", 0) + by_status.get("queued", 0)
    )
    canvas = conn.execute(
        "SELECT status, COUNT(*) AS n FROM jobs WHERE kind = 'image-generate'"
        " AND provider = 'canvas'"
        " AND date(created_at) = date('now') GROUP BY status"
    ).fetchall()
    canvas_by_status = {r["status"]: int(r["n"]) for r in canvas}
    return {
        "daily_limit": daily_limit,
        "used_today": used,
        "running_today": by_status.get("running", 0),
        "queued_today": by_status.get("queued", 0),
        "reserved_today": reserved,
        "remaining": max(0, daily_limit - used),
        "canvas_done_today": canvas_by_status.get("done", 0),
        "canvas_blocked_today": canvas_by_status.get("blocked", 0),
    }


def build_gemini_image_request(
    prompt: str,
    ref_bytes: bytes | None,
    ref_mime: str | None,
    character_name: str | None,
) -> dict:
    """The exact Gemini image-generation request body. The scene prompt
    is the text; the main character's reference image (when one exists)
    rides along as inlineData so the same face/outfit stays in every
    scene. 16:9 frames, because the videos are 1920x1080."""
    text = prompt.strip()
    if character_name:
        text += (
            f" Use the attached reference image for the main character"
            f" {character_name}: keep the same face, outfit and colours"
            " as the reference in this scene."
        )
    parts: list[dict] = [{"text": text}]
    if ref_bytes:
        parts.append(
            {
                "inlineData": {
                    "mimeType": ref_mime or "image/jpeg",
                    "data": base64.b64encode(ref_bytes).decode("ascii"),
                }
            }
        )
    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "16:9"},
        },
    }


def gemini_generate_image(
    api_key: str,
    prompt: str,
    ref_bytes: bytes | None,
    ref_mime: str | None,
    character_name: str | None,
) -> tuple[bytes, str]:
    """Call the Gemini image model once. Returns (image bytes, mime
    type). Any provider failure is a plain RuntimeError — the caller
    turns it into a failed job, never a fake image."""
    import urllib.error
    import urllib.parse
    import urllib.request

    payload = build_gemini_image_request(
        prompt, ref_bytes, ref_mime, character_name
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise GeminiProviderError(
            f"Gemini API error ({exc.code}): {body}", exc.code, body
        )
    except OSError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}")
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no image")
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return (
                base64.b64decode(inline["data"]),
                inline.get("mimeType", "image/png"),
            )
    raise RuntimeError("Gemini returned no image")


def scene_generation_status(conn, scene_id: int) -> dict:
    """Honest per-scene generation state from the latest image-generate
    job for that scene. No job yet -> 'pending' (slice 1's state)."""
    job = conn.execute(
        "SELECT * FROM jobs WHERE kind = 'image-generate' AND scene_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (scene_id,),
    ).fetchone()
    if job is None:
        return {
            "status": "pending",
            "job_id": None,
            "error": None,
            "image_path": None,
            "asset_id": None,
        }
    job = dict(job)
    asset_id = None
    if job.get("output_path"):
        asset = conn.execute(
            "SELECT id FROM assets WHERE path = ?", (job["output_path"],)
        ).fetchone()
        asset_id = asset["id"] if asset else None
    # Slice 3 PATCH (Retry Ladder): the job's retry history rides
    # along, so the UI can show "retry se bani" / "fallback used"
    # per scene (and the exact error that started the ladder).
    try:
        job_opts = json.loads(job.get("options_json") or "{}")
    except (TypeError, ValueError):
        job_opts = {}
    retry_history = job_opts.get("retry_history") or []
    return {
        "status": job["status"],
        "job_id": job["id"],
        "error": job.get("error"),
        "image_path": job.get("output_path"),
        "asset_id": asset_id,
        "retry_fixed_by": job_opts.get("retry_fixed_by"),
        "fallback_used": bool(job_opts.get("retry_fixed_by") == "fallback"),
        "retry_steps": len(retry_history),
        "precheck_reworded": bool((job_opts.get("precheck") or {}).get("reworded")),
        # Slice 5 (#/@ chaining): which Vault names this scene's
        # prompt resolved, and which it could not find.
        "chain_resolved": job_opts.get("chain_resolved") or [],
        "chain_unknown": job_opts.get("chain_unknown") or [],
    }


def generation_status_detail(conn, script_id: int) -> dict:
    """Per-scene generation status + quota for one script."""
    script = conn.execute(
        "SELECT * FROM scripts WHERE id = ?", (script_id,)
    ).fetchone()
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    scenes = conn.execute(
        "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
        (script_id,),
    ).fetchall()
    return {
        "script_id": script["id"],
        "topic": script["topic"],
        "project_id": script["project_id"],
        "quota": _image_quota(conn),
        "scenes": [
            {
                "scene_id": s["id"],
                "position": s["position"],
                "text": s["text"],
                "image_prompt": s["image_prompt"],
                "duration_s": s["duration_s"],
                **scene_generation_status(conn, s["id"]),
            }
            for s in scenes
        ],
    }


# --- Phase 4 slice 3: image verification -------------------------------

GEMINI_REGENERATE_MSG = "dobara generate ke liye queue me hai"


def _verdict_for_asset(conn, asset_id: int) -> dict | None:
    """Ale's verdict for one image asset, or None (still pending)."""
    row = conn.execute(
        "SELECT * FROM image_verdicts WHERE asset_id = ?", (asset_id,)
    ).fetchone()
    return dict(row) if row else None


def _scene_images_detail(conn, scene_id: int) -> list[dict]:
    """A scene's candidate images (generated or attached uploads),
    each with its verdict and its generation job's state. The latest
    link first, so the newest image is what Ale sees first."""
    rows = conn.execute(
        """
        SELECT si.id AS link_id, si.source, si.created_at AS linked_at,
               a.id AS asset_id, a.path AS asset_path
        FROM scene_images si JOIN assets a ON a.id = si.asset_id
        WHERE si.scene_id = ? ORDER BY si.id DESC
        """,
        (scene_id,),
    ).fetchall()
    out = []
    for r in rows:
        r = dict(r)
        verdict = _verdict_for_asset(conn, r["asset_id"])
        job = conn.execute(
            "SELECT status, error FROM jobs WHERE kind = 'image-generate'"
            " AND output_path = ? ORDER BY id DESC LIMIT 1",
            (r["asset_path"],),
        ).fetchone()
        out.append(
            {
                "asset_id": r["asset_id"],
                "path": r["asset_path"],
                "source": r["source"],
                "verdict": verdict["verdict"] if verdict else "pending",
                "reason": verdict["reason"] if verdict else "",
                "decided_at": verdict["decided_at"] if verdict else None,
                "job_status": job["status"] if job else (
                    "uploaded" if r["source"] == "uploaded" else None
                ),
                "job_error": job["error"] if job else None,
            }
        )
    return out


def _latest_approved_image(conn, scene_id: int) -> dict | None:
    """The scene's newest approved image, or None. Approval is the
    only gate into a timeline — a rejected or pending image never
    qualifies, however new it is."""
    row = conn.execute(
        """
        SELECT si.asset_id, a.path AS asset_path
        FROM scene_images si
        JOIN assets a ON a.id = si.asset_id
        JOIN image_verdicts v ON v.asset_id = si.asset_id
        WHERE si.scene_id = ? AND v.verdict = 'approved'
        ORDER BY si.id DESC LIMIT 1
        """,
        (scene_id,),
    ).fetchone()
    return dict(row) if row else None


def _queue_one_image_job(
    conn, script: dict, scene: dict, now: str, force: bool = False,
    provider: str = "api", options: dict | None = None,
    batch_id: str | None = None,
) -> tuple[str, int | None]:
    """Queue one image-generate job for a scene. Returns
    (outcome, job_id). The daily quota is reserved at queue time and
    never silently crossed: past the limit, a failed job carries the
    plain limit message. force=True (regenerate) re-queues even a
    scene that already has a finished image, but still respects the
    quota and never runs two jobs for the same scene at once.
    provider is 'api' (Gemini API) or 'canvas' (Gemini Canvas web
    app, free via the user's Gemini Pro quota) — the API daily quota
    applies to API jobs only; Canvas jobs skip that reservation.
    options carries the AutoCut Character/Style Match toggles
    (character_match / style_match, both True by default) — stored
    on the job row for the worker. Slice 5: batch_id tags every job
    of one bulk run, so Queue History can list the batch and
    re-download it as a ZIP (None = a single regenerate, no batch)."""
    status = scene_generation_status(conn, scene["id"])["status"]
    if not force:
        if status == "done":
            return ("skipped_done", None)
        if status in ("queued", "running"):
            return ("skipped_queued", None)
    elif status in ("queued", "running"):
        return ("already_queued", None)
    if provider == "api":
        quota = _image_quota(conn)
        if quota["reserved_today"] >= quota["daily_limit"]:
            cur = conn.execute(
                "INSERT INTO jobs (project_id, kind, status, error,"
                " scene_id, provider, batch_id, created_at, updated_at)"
                " VALUES (?, 'image-generate', 'failed', ?, ?, 'api', ?, ?, ?)",
                (script["project_id"], GEMINI_LIMIT_MSG, scene["id"], batch_id, now, now),
            )
            return ("limit_blocked", cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO jobs (project_id, kind, status, scene_id, provider,"
        " options_json, batch_id, created_at, updated_at)"
        " VALUES (?, 'image-generate', 'queued', ?, ?, ?, ?, ?, ?)",
        (
            script["project_id"],
            scene["id"],
            provider,
            json.dumps(options or {}),
            batch_id,
            now,
            now,
        ),
    )
    return ("queued", cur.lastrowid)


def _strip_style_from_prompt(prompt: str) -> str:
    """Drop the leading "Style: ... ." bit from a template-built
    image prompt (the Style Match toggle, off). The prompt format is
    "Style: {name} — {desc}. Scene: {text}. ..." so the Style bit
    ends right before "Scene: " — the regex removes exactly that.
    A prompt with no Style bit (or no "Scene: ") comes back
    unchanged; the function never invents or reorders text."""
    stripped = re.sub(
        r"^Style: .*?\. (?=Scene: )", "", prompt, count=1
    )
    if stripped == prompt:
        parts = prompt.split(". ", 1)
        if len(parts) == 2 and parts[0].startswith("Style: "):
            stripped = parts[1]
    return stripped


def _strip_character_from_prompt(prompt: str) -> str:
    """Drop the "Main character: ... ." bit from a template-built
    image prompt (the Character Match toggle, off). The prompt format
    is "... Scene: {text}. Main character: {name} — same face, outfit
    and colours in every scene. No photorealism, ..." so the bit ends
    right before "No photorealism". A prompt with no Main character
    bit comes back unchanged."""
    stripped = re.sub(
        r"Main character: .*?\. (?=No photorealism)", "", prompt, count=1
    )
    if stripped == prompt:
        parts = prompt.split(". ")
        kept = [p for p in parts if not p.startswith("Main character: ")]
        stripped = ". ".join(kept)
    return stripped


def script_images_detail(conn, script_id: int) -> dict:
    """Verification list for one script: every scene with its
    candidate images and their verdicts."""
    script = conn.execute(
        "SELECT * FROM scripts WHERE id = ?", (script_id,)
    ).fetchone()
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    scenes = conn.execute(
        "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
        (script_id,),
    ).fetchall()
    return {
        "script_id": script["id"],
        "topic": script["topic"],
        "project_id": script["project_id"],
        "scenes": [
            {
                "scene_id": s["id"],
                "position": s["position"],
                "text": s["text"],
                "images": _scene_images_detail(conn, s["id"]),
            }
            for s in scenes
        ],
    }


def _save_generated_image(
    conn, project_id: int, scene_id: int, job_id: int,
    image_bytes: bytes, mime: str,
) -> str:
    """Save generated image bytes — API or Canvas, same pipeline — as
    a project asset linked to its scene, and mark the job done.
    Returns the asset's relative path. The verification flow
    (approve / reject / use-approved) reads exactly these rows, so a
    Canvas image enters the same pipeline as an API image."""
    ext = (
        ".png"
        if mime == "image/png"
        else ".webp"
        if mime == "image/webp"
        else ".jpg"
    )
    folder = PROJECTS_DIR / str(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"gen_{int(time.time())}_scene{scene_id}{ext}"
    (folder / name).write_bytes(image_bytes)
    rel = f"projects/{project_id}/{name}"
    cur = conn.execute(
        "INSERT INTO assets (project_id, kind, path, created_at)"
        " VALUES (?, 'image', ?, ?)",
        (project_id, rel, utcnow()),
    )
    # Phase 4 slice 3: link the generated image to its scene, so the
    # verification view can show it for approve / reject without a
    # separate lookup.
    conn.execute(
        "INSERT OR IGNORE INTO scene_images"
        " (scene_id, asset_id, source, created_at)"
        " VALUES (?, ?, 'generated', ?)",
        (scene_id, cur.lastrowid, utcnow()),
    )
    conn.execute(
        "UPDATE jobs SET status = ?, output_path = ?, error = NULL,"
        " updated_at = ? WHERE id = ?",
        ("done", rel, utcnow(), job_id),
    )
    return rel


# --- Slice 3 PATCH: Retry Ladder + Fallback ------------------------------
# Fail image ka professional tareeqa — kabhi skip nahi, kabhi gap nahi,
# sab automatic (Ali ka standing rule: user se kuch manual nahi).
# Attempt 1 "same" (pre-check ke baad) -> attempt 2 "reword" (policy
# lafz hatao) -> attempt 3 "simplify" (close-up, simple scene) ->
# fallback (pichli / agli shot ki image, alag crop/zoom, "fallback
# used" mark). Fail shots main batch ko nahi rokti — wo retry queue
# me jati hain jo main batch ke BAAD chalti hai. Slice 4 ka auto-QC
# (tooti/khaali image ek dafa dobara) alag rehta hai — ye ladder us
# ko dobara nahi likhta, us ke saath wire hota hai (QC ladder ke
# baad chalta hai, sirf 'done' jobs par).
# ----------------------------------------------------------------------


def _update_job_options(job_id: int, updates: dict) -> None:
    """Merge keys into one job's options_json (retry history,
    pre-check, fallback marks). Missing/bad JSON starts fresh."""
    with db() as conn:
        row = conn.execute(
            "SELECT options_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return
        try:
            opts = json.loads(row["options_json"] or "{}")
        except (TypeError, ValueError):
            opts = {}
        opts.update(updates)
        conn.execute(
            "UPDATE jobs SET options_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(opts), utcnow(), job_id),
        )


async def _attempt_generation(
    job_id: int, provider: str, prompt: str, ref_path: str | None,
    ref_bytes: bytes | None, ref_mime: str | None,
    char_name: str | None, keys: list[str],
    profile_dir: str | None = None, backoff_base_s: float = 2.0,
) -> dict:
    """ONE generation attempt through the job's provider, with
    Slice 5 backoff: a rate-limit error (429 / quota) waits an
    exponential backoff and retries the SAME attempt, up to 2 extra
    times — never a retry storm, and the wait is real sleeping, not
    a tight loop. profile_dir picks the Flow account's browser
    profile (rotation); None = the shared profile. All other
    behaviour is _attempt_generation_once's (below)."""
    result = await _attempt_generation_once(
        job_id, provider, prompt, ref_path, ref_bytes, ref_mime,
        char_name, keys, profile_dir=profile_dir,
    )
    tries = 0
    while (
        not result["ok"]
        and result.get("status") == "failed"
        and _flow_hardening.is_rate_limit_error(result.get("error"))
        and tries < 2
    ):
        delay = _flow_hardening.backoff_delay_s(
            tries, base_s=backoff_base_s
        )
        await asyncio.sleep(delay)
        tries += 1
        result = await _attempt_generation_once(
            job_id, provider, prompt, ref_path, ref_bytes, ref_mime,
            char_name, keys, profile_dir=profile_dir,
        )
    if tries:
        result = dict(result)
        result["backoff_retries"] = tries
    return result


async def _attempt_generation_once(
    job_id: int, provider: str, prompt: str, ref_path: str | None,
    ref_bytes: bytes | None, ref_mime: str | None,
    char_name: str | None, keys: list[str],
    profile_dir: str | None = None,
) -> dict:
    """ONE generation attempt through the job's provider. Returns
    {ok, image_bytes, mime, provider, status, error}.
    - Flow: try Flow, fall back to Canvas ONCE on page/runtime
      errors (login problems BLOCK instead — Canvas shares the
      login, so a fallback would only hide the real cause).
      Slice 5: 'Unusual Activity' ALSO blocks (no silent Canvas
      fallback — the account needs the guided recovery first).
    - Canvas: direct (Playwright runs in a thread).
    - API: key rotation via _gemini_try_keys (keys passed in).
    Never raises for a generation failure — the caller decides
    (retry ladder / failed / blocked). The job row is only touched
    to record a real provider change (Flow -> Canvas fallback)."""
    if provider == "flow":
        try:
            image_bytes, mime = await asyncio.to_thread(
                _flow_provider.generate_image, prompt, ref_path=ref_path,
                profile_dir=profile_dir,
            )
            return {
                "ok": True, "image_bytes": image_bytes, "mime": mime,
                "provider": "flow", "status": "done", "error": None,
            }
        except _flow_provider.FlowNotLoggedIn as exc:
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "flow", "status": "blocked",
                "error": str(exc)[:300],
            }
        except _flow_provider.FlowUnavailable as exc:
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "flow", "status": "blocked",
                "error": str(exc)[:300],
            }
        except _flow_provider.FlowUnusualActivity as exc:
            # The block is Flow's own — Canvas on the same account
            # must not silently take over (it would hide the block
            # and risk tripping Canvas too). 'blocked' + the
            # recovery message; the worker marks the account
            # 'unusual' and rotation tries another account.
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "flow", "status": "blocked",
                "error": str(exc)[:300],
            }
        except (_flow_provider.FlowPageChanged, RuntimeError) as exc:
            flow_err = str(exc)[:200]
            try:
                image_bytes, mime = await asyncio.to_thread(
                    _canvas_provider.generate_image, prompt,
                    ref_path=ref_path, profile_dir=profile_dir,
                )
            except _canvas_provider.CanvasNotLoggedIn as cexc:
                return {
                    "ok": False, "image_bytes": None, "mime": None,
                    "provider": "flow", "status": "blocked",
                    "error": str(cexc)[:300],
                }
            except _canvas_provider.CanvasUnavailable as cexc:
                return {
                    "ok": False, "image_bytes": None, "mime": None,
                    "provider": "flow", "status": "blocked",
                    "error": str(cexc)[:300],
                }
            except Exception as cexc:  # noqa: BLE001 - both routes failed
                return {
                    "ok": False, "image_bytes": None, "mime": None,
                    "provider": "flow", "status": "failed",
                    "error": (
                        f"Flow fail ({flow_err}) — Canvas fallback"
                        f" bhi fail: {str(cexc)[:200]}"
                    ),
                }
            # Fallback worked: record the real provider.
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET provider = 'canvas',"
                    " updated_at = ? WHERE id = ?",
                    (utcnow(), job_id),
                )
            return {
                "ok": True, "image_bytes": image_bytes, "mime": mime,
                "provider": "canvas", "status": "done", "error": None,
            }
    if provider == "canvas":
        try:
            image_bytes, mime = await asyncio.to_thread(
                _canvas_provider.generate_image, prompt, ref_path=ref_path,
                profile_dir=profile_dir,
            )
            return {
                "ok": True, "image_bytes": image_bytes, "mime": mime,
                "provider": "canvas", "status": "done", "error": None,
            }
        except _canvas_provider.CanvasNotLoggedIn as exc:
            # The login lapsed between the gate check and this
            # job: 'blocked', not failed — it can run after the
            # user signs in.
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "canvas", "status": "blocked",
                "error": str(exc)[:300],
            }
        except _canvas_provider.CanvasUnavailable as exc:
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "canvas", "status": "blocked",
                "error": str(exc)[:300],
            }
        except (_canvas_provider.CanvasPageChanged, RuntimeError) as exc:
            return {
                "ok": False, "image_bytes": None, "mime": None,
                "provider": "canvas", "status": "failed",
                "error": str(exc)[:300],
            }
    try:
        (image_bytes, mime), _attempts = _gemini_try_keys(
            keys,
            lambda k: gemini_generate_image(
                k, prompt, ref_bytes, ref_mime, char_name,
            ),
        )
        return {
            "ok": True, "image_bytes": image_bytes, "mime": mime,
            "provider": "api", "status": "done", "error": None,
        }
    except RuntimeError as exc:
        return {
            "ok": False, "image_bytes": None, "mime": None,
            "provider": "api", "status": "failed",
            "error": str(exc)[:300],
        }


def _save_fallback_image(
    conn, project_id: int, scene_id: int, job_id: int,
    image_bytes: bytes,
) -> str:
    """Save a fallback crop (padosi shot ki image, alag crop/zoom)
    as a project asset linked to its scene, and mark the job done.
    Same shape as _save_generated_image, but the file is named
    fallback_* and the scene link source is 'fallback', so the UI
    + verification view can show the truth ("fallback used")."""
    folder = PROJECTS_DIR / str(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"fallback_{job_id}_scene{scene_id}.png"
    (folder / name).write_bytes(image_bytes)
    rel = f"projects/{project_id}/{name}"
    cur = conn.execute(
        "INSERT INTO assets (project_id, kind, path, created_at)"
        " VALUES (?, 'image', ?, ?)",
        (project_id, rel, utcnow()),
    )
    conn.execute(
        "INSERT OR IGNORE INTO scene_images"
        " (scene_id, asset_id, source, created_at)"
        " VALUES (?, ?, 'fallback', ?)",
        (scene_id, cur.lastrowid, utcnow()),
    )
    conn.execute(
        "UPDATE jobs SET status = ?, output_path = ?, error = NULL,"
        " updated_at = ? WHERE id = ?",
        ("done", rel, utcnow(), job_id),
    )
    return rel


def _apply_fallback(project_id: int, entry: dict) -> dict | None:
    """Fallback: pichli shot ki DONE image lo (warna agli), us ka
    alag crop/zoom banao, job ko 'done' karo. Returns
    {source_asset_id, path} ya None (koi padosi image nahi — tab
    timeline ka placeholder card hi gap bharta hai, jo pehle se
    maujood behaviour hai)."""
    with db() as conn:
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (entry["scene_id"],)
        ).fetchone()
        if scene is None:
            return None
        pos = scene["position"]
        row = conn.execute(
            "SELECT j.output_path FROM jobs j JOIN scenes s"
            " ON s.id = j.scene_id WHERE j.kind = 'image-generate'"
            " AND j.status = 'done' AND j.output_path IS NOT NULL"
            " AND s.script_id = ? AND s.position < ? AND s.id != ?"
            " ORDER BY s.position DESC LIMIT 1",
            (entry["script_id"], pos, entry["scene_id"]),
        ).fetchone()
        from_prev = row is not None
        if row is None:
            row = conn.execute(
                "SELECT j.output_path FROM jobs j JOIN scenes s"
                " ON s.id = j.scene_id WHERE j.kind = 'image-generate'"
                " AND j.status = 'done' AND j.output_path IS NOT NULL"
                " AND s.script_id = ? AND s.position > ? AND s.id != ?"
                " ORDER BY s.position ASC LIMIT 1",
                (entry["script_id"], pos, entry["scene_id"]),
            ).fetchone()
        if row is None:
            return None
        src_path = media_path(row["output_path"])
        if src_path is None or not src_path.is_file():
            return None
        src_bytes = src_path.read_bytes()
        src_asset = conn.execute(
            "SELECT id FROM assets WHERE path = ?", (row["output_path"],)
        ).fetchone()
    # Pichli shot -> centre zoom-in (variant 0); agli shot -> left
    # crop (variant 1): do fallback shots kabhi ek jaisi na lagen.
    fb_bytes = _retry_ladder.fallback_variant(
        src_bytes, 0 if from_prev else 1
    )
    if fb_bytes is None:
        return None
    with db() as conn:
        rel = _save_fallback_image(
            conn, project_id, entry["scene_id"], entry["job_id"], fb_bytes
        )
    return {
        "source_asset_id": src_asset["id"] if src_asset else None,
        "path": rel,
    }


async def _retry_attempt(entry: dict, prompt: str) -> tuple[str, str | None]:
    """One retry-queue attempt. API jobs re-check quota + keys
    first (limit/key fail fast, bina provider call). Success saves
    the image and the job is 'done'. Returns
    ("done"|"failed"|"blocked", error_or_None)."""
    provider = entry["provider"]
    keys: list[str] = []
    if provider == "api":
        with db() as conn:
            quota = _image_quota(conn)
            if quota["used_today"] + quota["running_today"] > quota["daily_limit"]:
                return ("failed", GEMINI_LIMIT_MSG)
            keys = _gemini_keys(conn)
            if not keys:
                return ("failed", GEMINI_KEY_MISSING_MSG)
    result = await _attempt_generation(
        entry["job_id"], provider, prompt, entry["ref_path"],
        entry["ref_bytes"], entry["ref_mime"], entry["char_name"], keys,
        profile_dir=entry.get("profile_dir"),
    )
    if result["ok"]:
        with db() as conn:
            _save_generated_image(
                conn, entry["project_id"], entry["scene_id"],
                entry["job_id"], result["image_bytes"], result["mime"],
            )
        return ("done", None)
    return (result["status"], result["error"])


async def _process_retry_queue(
    script_id: int, retry_queue: list[dict], project_id: int,
) -> list[dict]:
    """Retry queue: main batch ke BAAD chalti hai, taake ek fail se
    baaki 49 images na ruken. Har job: attempt 2 (reword) -> attempt
    3 (simplify) -> fallback (padosi shot, alag crop). Returns the
    retry log: [{scene_id, scene_position, job_id, error, fixed_by}]
    — fixed_by None = aakhir me bhi fail (summary me saaf likha
    jata hai). Limit ek dafa hit ho to baaki retries bekaar attempt
    nahi karti — seedha limit error."""
    log: list[dict] = []
    limit_hit = False
    for entry in retry_queue:
        job_id = entry["job_id"]
        history = list(entry["history"])
        fixed_by: str | None = None
        blocked_error: str | None = None
        limit_failed = False
        current_prompt = entry["prompt"]
        current_error = entry["error"]
        if limit_hit:
            limit_failed = True
            history.append({
                "step": "reword", "skipped": True,
                "reason": "limit khatam — retry nahi hua",
            })
            with db() as conn:
                _set_job(conn, job_id, "failed", GEMINI_LIMIT_MSG)
        else:
            # Attempt 2 — reword (policy-trigger lafz hatao).
            rw = _retry_ladder.reword_prompt(current_prompt, current_error)
            if not rw["changed"]:
                history.append({
                    "step": "reword", "skipped": True,
                    "reason": "koi trigger lafz nahi mila",
                })
            else:
                current_prompt = rw["prompt"]
                status, err = await _retry_attempt(entry, current_prompt)
                if status == "done":
                    fixed_by = "reword"
                    history.append({"step": "reword", "fixed": True})
                elif status == "blocked":
                    # Login lapse mid-retry: dobara chalane ka koi
                    # faida nahi — job 'blocked' rehti hai, 'failed'
                    # nahi banti (sign-in ke baad dobara chal sakti
                    # hai).
                    blocked_error = err or current_error
                    history.append({"step": "reword", "blocked": True})
                else:
                    current_error = err or current_error
                    history.append({"step": "reword", "error": current_error})
                    if err == GEMINI_LIMIT_MSG:
                        limit_hit = True
            if fixed_by is None and blocked_error is None and not limit_hit:
                # Attempt 3 — simplify (wahi timecode, close-up).
                current_prompt = _retry_ladder.simplify_prompt(current_prompt)
                status, err = await _retry_attempt(entry, current_prompt)
                if status == "done":
                    fixed_by = "simplify"
                    history.append({"step": "simplify", "fixed": True})
                elif status == "blocked":
                    blocked_error = err or current_error
                    history.append({"step": "simplify", "blocked": True})
                else:
                    current_error = err or current_error
                    history.append({"step": "simplify", "error": current_error})
                    if err == GEMINI_LIMIT_MSG:
                        limit_hit = True
            if fixed_by is None and blocked_error is None and not limit_hit:
                # Fallback — padosi shot, alag crop/zoom.
                fb = _apply_fallback(project_id, entry)
                if fb is not None:
                    fixed_by = "fallback"
                    history.append({
                        "step": "fallback", "fixed": True,
                        "source_asset_id": fb["source_asset_id"],
                    })
                else:
                    history.append({
                        "step": "fallback", "fixed": False,
                        "reason": "koi padosi image nahi",
                    })
            if fixed_by is None and blocked_error is not None:
                with db() as conn:
                    _set_job(conn, job_id, "blocked", blocked_error)
            elif fixed_by is None and not limit_failed:
                with db() as conn:
                    _set_job(
                        conn, job_id, "failed",
                        current_error
                        if current_error == GEMINI_LIMIT_MSG
                        else f"{current_error} — retry ladder bhi fail",
                    )
        _update_job_options(job_id, {
            "retry_stage": "done" if fixed_by else "failed",
            "retry_fixed_by": fixed_by,
            "retry_history": history,
        })
        log.append({
            "scene_id": entry["scene_id"],
            "scene_position": entry.get("scene_position"),
            "job_id": job_id,
            "error": entry["error"],
            "fixed_by": fixed_by,
        })
    return log


def _with_retry_fields(
    summary: dict, retry_log: list[dict], precheck_reworded: int,
) -> dict:
    """Batch summary me Retry Ladder ke counts + log jodo."""
    summary["retried"] = len(retry_log)
    summary["retry_fixed"] = sum(
        1 for e in retry_log if e["fixed_by"] in ("reword", "simplify")
    )
    summary["fallback_used"] = sum(
        1 for e in retry_log if e["fixed_by"] == "fallback"
    )
    summary["precheck_reworded"] = precheck_reworded
    summary["retry_log"] = retry_log
    return summary


# --- Slice 5: Flow provider hardening — accounts, queue, batches -------
# Flow accounts (up to 3, one browser profile each), the persistent
# pause flag, and the Fast-mode setting. No password/token is ever
# stored here: an account is a name + a profile directory; the login
# lives only in that directory's cookies.


def _minutes_from_now_iso(minutes: int) -> str:
    """UTC ISO timestamp N minutes from now (same shape as utcnow,
    so lexicographic comparison works for cooldown checks)."""
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(
        timespec="seconds"
    )


def _flow_accounts() -> list[dict]:
    """All Flow accounts, oldest first (account 1 = the shared
    profile, seeded in init_db)."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM flow_accounts ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def _flow_account_by_id(account_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM flow_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def _flow_set_account_status(
    account_id: int, status: str, limited_until: str | None = None
) -> None:
    """Set an account's status ('active' | 'limited' | 'unusual' |
    'not_logged_in'). A limit always carries its cooldown end; any
    other status clears it."""
    with db() as conn:
        conn.execute(
            "UPDATE flow_accounts SET status = ?, limited_until = ?,"
            " updated_at = ? WHERE id = ?",
            (status, limited_until, utcnow(), account_id),
        )


def _flow_mark_account_limited(account_id: int) -> None:
    """A rate-limited account rests for the cooldown (15 min) —
    rotation skips it until then, then it is usable again."""
    _flow_set_account_status(
        account_id,
        "limited",
        _minutes_from_now_iso(
            _flow_hardening.ACCOUNT_LIMIT_COOLDOWN_MIN
        ),
    )


def _flow_mark_account_unusual(account_id: int) -> None:
    """Flow's 'Unusual Activity' block: the account needs the
    guided recovery (site data clear) — no timer auto-recovers it."""
    _flow_set_account_status(account_id, "unusual")


def _flow_fast_concurrency() -> int:
    """Fast-mode setting (1–4, default 1 = sequential). A missing
    or bad value is 1 — never a crash, never a storm."""
    try:
        with db() as conn:
            row = conn.execute(
                "SELECT value FROM settings"
                " WHERE key = 'flow_fast_concurrency'"
            ).fetchone()
        if row is None:
            return 1
        return _flow_hardening.clamp_concurrency(row["value"])
    except Exception:
        return 1


def _flow_queue_paused(script_id: int) -> bool:
    """Is this script's image queue paused (persistent — survives
    a restart)?"""
    with db() as conn:
        row = conn.execute(
            "SELECT paused FROM flow_queue_state WHERE script_id = ?",
            (script_id,),
        ).fetchone()
    return bool(row and row["paused"])


def _flow_set_queue_paused(script_id: int, paused: bool) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO flow_queue_state (script_id, paused, updated_at)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(script_id) DO UPDATE SET paused = excluded.paused,"
            " updated_at = excluded.updated_at",
            (script_id, 1 if paused else 0, utcnow()),
        )


def _pick_flow_account(ctx: dict) -> dict | None:
    """Round-robin over the batch's usable Flow accounts. Returns
    the account row or None when none is usable anymore (all
    limited / unusual mid-batch) — the job is then 'blocked', never
    run on the shared profile by surprise."""
    usable = ctx.get("flow_accounts") or []
    if not usable:
        return None
    idx = ctx.get("account_rr", 0) % len(usable)
    ctx["account_rr"] = idx + 1
    return usable[idx]


def _flow_remove_usable_account(ctx: dict, account_id: int) -> None:
    """Drop an account from this batch's usable list (it just hit a
    limit or an Unusual Activity block) — later jobs in the same
    batch rotate past it."""
    ctx["flow_accounts"] = [
        a for a in (ctx.get("flow_accounts") or [])
        if a["id"] != account_id
    ]


async def process_image_jobs(script_id: int) -> dict:
    """Background worker: run one script's queued image-generate jobs
    one by one. Each job re-checks the quota and the key before calling
    Gemini; a failed job never blocks the rest, and a hit limit stops
    the remaining queued jobs with the same plain limit message.
    Canvas jobs dispatch to the Gemini Canvas provider instead: the
    login gate is checked ONCE before the loop, so a missing login
    marks every queued Canvas job 'blocked' with the exact login
    message instead of launching a browser per job. Flow jobs work
    the same way, with one extra step: a Flow failure on a scene
    retries that scene once on Canvas, on the same job.
    Slice 4 (Character Vault): after the main loop an auto-QC pass
    checks every Vault-pinned job that finished, and re-runs the
    gross failures once. Slice 3 PATCH (Retry Ladder): before the
    main loop every prompt is pre-checked for policy-trigger words
    (auto-reworded upfront); a retryable failure does NOT fail the
    job — it joins the retry queue, which runs AFTER the main loop
    (reword -> simplify -> neighbour-image fallback), so one fail
    never blocks the rest of the batch. Returns the batch summary
    {done, failed, blocked, qc_checked, qc_regenerated, retried,
    retry_fixed, fallback_used, precheck_reworded, retry_log} — the
    Magic Mode images stage reads the retry/qc fields for its
    summary."""
    async with _IMAGE_GEN_LOCK:
        return await _process_image_jobs_locked(script_id)


async def _run_one_image_job(job: dict, ctx: dict) -> str:
    """Run ONE queued image-generate job: prep (prompt,
    pre-check, #/@ chaining, account pick) -> one attempt
    (+backoff) -> save / blocked / failed / retry-queue.
    Returns "ok" (the job finished its turn, whatever the
    outcome), "limit_hit" (the API daily limit was hit — the
    caller fails the rest of the queue the same way and returns
    early) or "paused" (never returned here — pause is checked
    by the dispatcher between jobs/waves). Shared batch state
    lives in ctx (retry_queue, precheck count, vault sheet
    cache, usable Flow accounts, round-robin counter). Slice 5
    extracted this from _process_image_jobs_locked so Fast mode
    can run several Flow jobs side by side in waves; the
    sequential path calls it the same way, one job at a time."""
    with db() as conn:
        cur = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job["id"],)
        ).fetchone()
        if cur is None or cur["status"] != "queued":
            return "ok"
        job = dict(cur)
        _set_job(conn, job["id"], "running")
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (job["scene_id"],)
        ).fetchone()
        if scene is None:
            _set_job(conn, job["id"], "failed", "scene not found")
            return "ok"
        prompt = scene["image_prompt"] or scene["text"]
        provider = job.get("provider") or "api"
        # Cross-check slice: Character/Style Match toggles
        # from the job's stored options (both True by default).
        # character_match=False = no character reference image
        # attached; style_match=False = the "Style: ..." bit
        # is stripped from the prompt before the call.
        try:
            job_opts = json.loads(job.get("options_json") or "{}")
        except (TypeError, ValueError):
            job_opts = {}
        character_match = job_opts.get("character_match", True) is not False
        style_match = job_opts.get("style_match", True) is not False
        job_ref_bytes = ctx["ref_bytes"] if character_match else None
        job_ref_mime = ctx["ref_mime"] if character_match else None
        # Slice 3 auto-consistency: the character sheet
        # image rides along as a reference for Canvas/Flow
        # too (best-effort attach in the provider);
        # prompt-only when no character is set.
        job_ref_path = (
            str(DATA_DIR / ctx["char"]["image_path"])
            if (ctx["char"] and character_match and ctx["ref_bytes"] is not None)
            else None
        )
        # Slice 4 (Character Vault): the pinned cast's sheet
        # image replaces the project character reference for
        # this job — API, Canvas and Flow all take it through
        # the same ref slots. A missing sheet file falls back
        # to the project character reference, never a crash.
        vault = job_opts.get("vault") or {}
        sheet_rel = vault.get("sheet_path") or ""
        if sheet_rel and character_match:
            sheet_file = DATA_DIR / sheet_rel
            if sheet_file.is_file():
                job_ref_path = str(sheet_file)
                if sheet_rel not in ctx["vault_sheet_cache"]:
                    ctx["vault_sheet_cache"][sheet_rel] = (
                        sheet_file.read_bytes(),
                        _REF_MIME_BY_EXT.get(
                            sheet_file.suffix.lower(),
                            "image/jpeg",
                        ),
                    )
                job_ref_bytes, job_ref_mime = (
                    ctx["vault_sheet_cache"][sheet_rel]
                )
        # character_match=False also drops the "Main character"
        # bit from the prompt text AND the reference sentence
        # build_gemini_image_request adds — otherwise the name
        # would still lock the character by words alone.
        job_char_name = (
            ctx["char"]["name"] if (ctx["char"] and character_match) else None
        )
        if not character_match:
            prompt = _strip_character_from_prompt(prompt)
        if not style_match:
            prompt = _strip_style_from_prompt(prompt)
        # Slice 3 PATCH (Retry Ladder) pre-check: generate
        # karne se pehle policy-trigger lafz scan karo aur pehle
        # hi auto-reword karo — retry se behtar hai rokna.
        pre = _retry_ladder.precheck_prompt(prompt)
        if pre["changed"]:
            prompt = pre["prompt"]
            job_opts["precheck"] = {
                "triggers": pre["triggers"],
                "reworded": True,
            }
            ctx["precheck_reworded"] += 1
            conn.execute(
                "UPDATE jobs SET options_json = ?, updated_at = ?"
                " WHERE id = ?",
                (json.dumps(job_opts), utcnow(), job["id"]),
            )
        # Slice 5 (#/@ chaining): Vault ke locked characters ke
        # naam #Name / @Name se prompt me resolve hon — dono
        # locked description ban jate hain, taake har scene me
        # wahi chehra rahe. Unknown naam prompt me waisa hi
        # rehta hai aur job options me darj hota hai.
        chain_chars = (job_opts.get("vault") or {}).get("characters") or []
        if chain_chars:
            chain = _flow_hardening.resolve_chain_syntax(prompt, chain_chars)
            if chain["resolved"] or chain["unknown"]:
                prompt = chain["prompt"]
                job_opts["chain_resolved"] = [r["name"] for r in chain["resolved"]]
                job_opts["chain_unknown"] = chain["unknown"]
                conn.execute(
                    "UPDATE jobs SET options_json = ?, updated_at = ?"
                    " WHERE id = ?",
                    (json.dumps(job_opts), utcnow(), job["id"]),
                )
        if provider in ("canvas", "flow"):
            # Canvas/Flow jobs use the user's Gemini Pro quota,
            # not the API key and not the API daily limit — the
            # login gate was already checked once before the
            # loop, so there is nothing to check here.
            keys: list[str] = []
        else:
            if not ctx["sample_written"]:
                # Prove the request shape once per bulk run: the
                # exact body (prompt + character reference) is
                # saved locally BEFORE the key/quota checks, so it
                # exists even when no key is set — the key is never
                # in this file.
                sample = build_gemini_image_request(
                    prompt, job_ref_bytes, job_ref_mime,
                    job_char_name,
                )
                IMAGE_REQUEST_SAMPLE_PATH.write_text(
                    json.dumps(sample, indent=2), encoding="utf-8"
                )
                ctx["sample_written"] = True
            quota = _image_quota(conn)
            if quota["used_today"] + quota["running_today"] > quota["daily_limit"]:
                _set_job(conn, job["id"], "failed", GEMINI_LIMIT_MSG)
                # The limit is hit: fail the rest of this queue too,
                # so nothing is promised for today.
                rest = conn.execute(
                    "SELECT id FROM jobs WHERE kind = 'image-generate'"
                    " AND scene_id IN (SELECT id FROM scenes"
                    " WHERE script_id = ?) AND status = 'queued'",
                    (ctx["script_id"],),
                ).fetchall()
                for r in rest:
                    _set_job(conn, r["id"], "failed", GEMINI_LIMIT_MSG)
                # Limit hit: no QC second pass — a re-queue
                # would only fail with the same limit message.
                # Retry queue me jo jobs pehle se hain, wo bhi
                # limit error se fail hote hain (dobara chalane
                # ka koi faida nahi). Same conn se update (naya
                # connection yahan lock kar sakta hai).
                for rq in ctx["retry_queue"]:
                    _set_job(conn, rq["job_id"], "failed", GEMINI_LIMIT_MSG)
                    try:
                        opts = json.loads(
                            conn.execute(
                                "SELECT options_json FROM jobs WHERE id = ?",
                                (rq["job_id"],),
                            ).fetchone()["options_json"] or "{}"
                        )
                    except (TypeError, ValueError):
                        opts = {}
                    opts["retry_stage"] = "failed"
                    conn.execute(
                        "UPDATE jobs SET options_json = ?, updated_at = ?"
                        " WHERE id = ?",
                        (json.dumps(opts), utcnow(), rq["job_id"]),
                    )
                ctx["limit_retry_log"] = [
                    {
                        "scene_id": rq["scene_id"],
                        "scene_position": rq.get("scene_position"),
                        "job_id": rq["job_id"],
                        "error": rq["error"],
                        "fixed_by": None,
                    }
                    for rq in ctx["retry_queue"]
                ]
                return "limit_hit"
            keys = _gemini_keys(conn)
            if not keys:
                _set_job(conn, job["id"], "failed", GEMINI_KEY_MISSING_MSG)
                return "ok"
    # Slice 3 PATCH (Retry Ladder): one attempt through the
    # provider (Flow -> Canvas fallback is inside the helper).
    # Slice 5 (rotation): Flow jobs run on the batch's next
    # usable account (round-robin); koi usable account na bache
    # to job 'blocked' — shared profile par kabhi nahi chalaya
    # jata, rotation ka matlab hi ye hai ke har account apni
    # profile par chale.
    flow_account = None
    flow_profile_dir = None
    if provider == "flow":
        flow_account = _pick_flow_account(ctx)
        if flow_account is None:
            _msg = (
                _flow_hardening.RECOVERY_MSG
                if ctx.get("any_unusual")
                else "Flow ke saare accounts abhi limit par hain — "
                "15 minute baad dobara try karein"
            )
            with db() as conn:
                _set_job(conn, job["id"], "blocked", _msg)
            return "ok"
        flow_profile_dir = flow_account["profile_dir"]
    result = await _attempt_generation(
        job["id"], provider, prompt, job_ref_path,
        job_ref_bytes, job_ref_mime, job_char_name, keys,
        profile_dir=flow_profile_dir,
    )
    # Slice 5: is attempt se account ki sehat — rate limit par
    # account rest karega (rotation agle account par jayegi),
    # Unusual Activity par account 'unusual' (guided recovery).
    if flow_account is not None and not result["ok"]:
        _err = result.get("error") or ""
        if _flow_hardening.detect_unusual_activity(_err):
            ctx["any_unusual"] = True
            _flow_mark_account_unusual(flow_account["id"])
            _flow_remove_usable_account(ctx, flow_account["id"])
        elif _flow_hardening.is_rate_limit_error(_err):
            _flow_mark_account_limited(flow_account["id"])
            _flow_remove_usable_account(ctx, flow_account["id"])
    if result["ok"]:
        with db() as conn:
            _save_generated_image(
                conn, ctx["project_id"], job["scene_id"], job["id"],
                result["image_bytes"], result["mime"],
            )
        return "ok"
    elif result["status"] == "blocked":
        with db() as conn:
            _set_job(conn, job["id"], "blocked", result["error"])
        return "ok"
    elif not _retry_ladder.is_retryable_error(result["error"]):
        # Key nahi / limit khatam: dobara chalane ka koi faida
        # nahi — seedha failed (ladder me nahi jata).
        with db() as conn:
            _set_job(conn, job["id"], "failed", result["error"])
        return "ok"
    else:
        # Retryable fail: main batch ko roke baghair retry
        # queue me — dobara banega main batch ke BAAD (reword,
        # simplify, phir fallback). Baaki jobs pehle chalti
        # hain, is liye ek fail se 49 images nahi rukti.
        history = [{"step": "same", "error": result["error"]}]
        ctx["retry_queue"].append({
            "job_id": job["id"],
            "scene_id": job["scene_id"],
            "scene_position": scene["position"],
            "script_id": ctx["script_id"],
            "project_id": ctx["project_id"],
            "provider": provider,
            "profile_dir": flow_profile_dir,
            "account_id": flow_account["id"] if flow_account else None,
            "prompt": prompt,
            "ref_path": job_ref_path,
            "ref_bytes": job_ref_bytes,
            "ref_mime": job_ref_mime,
            "char_name": job_char_name,
            "error": result["error"],
            "history": history,
        })
        _update_job_options(job["id"], {
            "retry_stage": "queued",
            "retry_history": history,
        })
        with db() as conn:
            _set_job(
                conn, job["id"], "queued",
                "Retry queue me — main batch ke baad dobara banega",
            )
        return "ok"


async def _process_image_jobs_locked(script_id: int) -> dict:
    """The worker body (lock already held by process_image_jobs).
    Split out so the Slice 4 auto-QC pass can re-run it for its
    second pass without re-acquiring the lock."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            return _image_batch_summary(conn, [])
        project_id = script["project_id"]
        char = get_character(conn, project_id)
        ref_bytes: bytes | None = None
        ref_mime: str | None = None
        if char:
            ref_path = DATA_DIR / char["image_path"]
            if ref_path.is_file():
                ref_bytes = ref_path.read_bytes()
                ref_mime = _REF_MIME_BY_EXT.get(
                    ref_path.suffix.lower(), "image/jpeg"
                )
        queued = conn.execute(
            "SELECT * FROM jobs WHERE kind = 'image-generate'"
            " AND scene_id IN (SELECT id FROM scenes WHERE script_id = ?)"
            " AND status = 'queued' ORDER BY id",
            (script_id,),
        ).fetchall()
        queued = [dict(j) for j in queued]
    # Canvas login gate, once per bulk run: no Google session means
    # every Canvas job is 'blocked' (not failed — it can run later,
    # once the user signs in) with the exact message the UI shows.
    canvas_queued = [
        j for j in queued if (j.get("provider") or "api") == "canvas"
    ]
    if canvas_queued:
        block_msg: str | None = None
        try:
            login = await asyncio.to_thread(
                _canvas_provider.check_login
            )
            if not login["logged_in"]:
                block_msg = _canvas_provider.CANVAS_LOGIN_MSG
        except _canvas_provider.CanvasUnavailable as exc:
            block_msg = str(exc)
        except RuntimeError as exc:
            block_msg = str(exc)[:300]
        except Exception as exc:
            # A provider bug must never wedge jobs in 'running':
            # block them with a plain message instead.
            block_msg = (
                "Canvas check fail — dobara try karein"
                f" ({exc.__class__.__name__})"
            )
        if block_msg is not None:
            with db() as conn:
                for j in canvas_queued:
                    _set_job(conn, j["id"], "blocked", block_msg)
            queued = [
                j for j in queued
                if (j.get("provider") or "api") != "canvas"
            ]
    # Slice 5 (Flow hardening): the gate probes EVERY Flow account,
    # not just the shared profile — each account is its own browser
    # profile, so Flow can show its own consent screen on one
    # account while another is signed in. Usable = signed in + no
    # 'Unusual Activity' block. Unusual accounts are marked
    # 'unusual' (guided recovery, never auto-retried);
    # not-logged-in accounts are marked 'not_logged_in'; a
    # rate-limited account still inside its cooldown is skipped
    # without wasting a browser launch. No usable account -> every
    # Flow job is 'blocked' with the login message (or the recovery
    # message when the block is what stopped them).
    flow_accounts_usable: list[dict] = []
    flow_queued = [
        j for j in queued if (j.get("provider") or "api") == "flow"
    ]
    if flow_queued:
        _flow_block_msg: str | None = None
        _flow_any_unusual = False
        for _acct in _flow_accounts():
            _profile = _acct["profile_dir"]
            if _acct.get("status") == "limited" and _acct.get(
                "limited_until"
            ):
                if _acct["limited_until"] > utcnow():
                    continue
            try:
                _login = await asyncio.to_thread(
                    _flow_provider.check_login, profile_dir=_profile
                )
            except _flow_provider.FlowUnavailable as exc:
                # Playwright / Chromium missing — the whole provider
                # is down, not just this account.
                _flow_block_msg = str(exc)
                break
            except Exception:
                # This account's probe failed (network / browser) —
                # skip the account, never wedge the batch on it.
                _flow_set_account_status(_acct["id"], "not_logged_in")
                continue
            if _login.get("unusual_activity"):
                _flow_any_unusual = True
                _flow_set_account_status(_acct["id"], "unusual")
                continue
            if not _login.get("logged_in"):
                _flow_set_account_status(_acct["id"], "not_logged_in")
                continue
            _flow_set_account_status(_acct["id"], "active")
            flow_accounts_usable.append(_acct)
        if _flow_block_msg is not None:
            with db() as conn:
                for j in flow_queued:
                    _set_job(conn, j["id"], "blocked", _flow_block_msg)
            queued = [
                j for j in queued
                if (j.get("provider") or "api") != "flow"
            ]
        elif not flow_accounts_usable:
            _msg = (
                _flow_hardening.RECOVERY_MSG
                if _flow_any_unusual
                else _flow_provider.FLOW_LOGIN_MSG
            )
            with db() as conn:
                for j in flow_queued:
                    _set_job(conn, j["id"], "blocked", _msg)
            queued = [
                j for j in queued
                if (j.get("provider") or "api") != "flow"
            ]
    sample_written = False
    # Slice 4: the sheet bytes are read once per sheet path and
    # reused across the batch (a cast-sheet is ~1 MB).
    _vault_sheet_cache: dict = {}
    batch_ids = [j["id"] for j in queued]
    # Slice 3 PATCH (Retry Ladder): fail shots main batch ko nahi
    # rokti — wo retry_queue me jati hain jo main loop ke BAAD
    # chalti hai. precheck_reworded = pre-check ne kitne prompts
    # pehle hi reword kiye.
    retry_queue: list[dict] = []
    precheck_reworded = 0
    # Slice 5 (Fast mode): the per-job body lives in
    # _run_one_image_job; the loop below only dispatches it —
    # sequentially by default, or in waves of N for Flow-only
    # batches when Fast mode + 2+ usable accounts allow it.
    # (Canvas stays sequential: it shares one profile, and two
    # contexts on the same profile fight over the profile lock.)
    _fast_requested = _flow_fast_concurrency()
    _flow_only = bool(queued) and all(
        (j.get("provider") or "api") == "flow" for j in queued
    )
    _fast_n = (
        _flow_hardening.effective_concurrency(
            _fast_requested, len(flow_accounts_usable)
        )
        if (_flow_only and len(queued) >= 2)
        else 1
    )
    ctx: dict = {
        "script_id": script_id,
        "project_id": project_id,
        "char": char,
        "ref_bytes": ref_bytes,
        "ref_mime": ref_mime,
        "vault_sheet_cache": _vault_sheet_cache,
        "batch_ids": batch_ids,
        "retry_queue": retry_queue,
        "precheck_reworded": precheck_reworded,
        "sample_written": False,
        "paused": False,
        "any_unusual": False,
        "limit_retry_log": [],
        "flow_accounts": flow_accounts_usable,
        "account_rr": 0,
    }
    _limit_hit = False
    if _fast_n > 1:
        for _w in range(0, len(queued), _fast_n):
            if _flow_queue_paused(script_id):
                ctx["paused"] = True
                break
            _wave = queued[_w:_w + _fast_n]
            _outcomes = await asyncio.gather(
                *[_run_one_image_job(dict(j), ctx) for j in _wave]
            )
            if "limit_hit" in _outcomes:
                _limit_hit = True
                break
            if ctx.get("paused"):
                break
    else:
        for _job in queued:
            if _flow_queue_paused(script_id):
                ctx["paused"] = True
                break
            _outcome = await _run_one_image_job(_job, ctx)
            if _outcome == "limit_hit":
                _limit_hit = True
                break
            if _outcome == "paused":
                break
    retry_queue = ctx["retry_queue"]
    precheck_reworded = ctx["precheck_reworded"]
    if _limit_hit:
        with db() as conn:
            return _with_retry_fields(
                _image_batch_summary(conn, batch_ids),
                ctx["limit_retry_log"], precheck_reworded,
            )
    if ctx["paused"]:
        with db() as conn:
            _paused_summary = _image_batch_summary(conn, batch_ids)
        _paused_summary["paused"] = True
        return _with_retry_fields(
            _paused_summary, [], precheck_reworded,
        )
    # Slice 3 PATCH (Retry Ladder): retry queue main batch ke BAAD
    # chalti hai — reword -> simplify -> fallback. Is ke baad jo
    # jobs 'done' hain wo QC pass me bhi check hoti hain (fallback
    # crops bhi, kyunke wo bhi generated images hain).
    retry_log = await _process_retry_queue(script_id, retry_queue, project_id)
    # Slice 4 (Character Vault) auto-QC, second pass: every
    # Vault-pinned job that finished in this batch is checked
    # against its pinned sheet. Only gross failure (broken /
    # blank) is re-queued once; the second result stands.
    qc = await _vault_qc_pass(script_id, batch_ids)
    with db() as conn:
        summary = _image_batch_summary(conn, batch_ids)
    summary["qc_checked"] = qc["checked"]
    summary["qc_regenerated"] = qc["regenerated"]
    summary["qc_requeued"] = qc["requeued"]
    _with_retry_fields(summary, retry_log, precheck_reworded)
    return summary


def _image_batch_summary(conn, batch_ids: list[int]) -> dict:
    """done / failed / blocked counts for THIS batch only (the
    job ids the worker just ran), not the script's whole history.
    qc_* start at 0 and are filled in by the caller after the
    auto-QC pass."""
    counts = {
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "queued": 0,
        "running": 0,
        "paused": False,
        "qc_checked": 0,
        "qc_regenerated": 0,
        "qc_requeued": 0,
        "retried": 0,
        "retry_fixed": 0,
        "fallback_used": 0,
        "precheck_reworded": 0,
        "retry_log": [],
    }
    if not batch_ids:
        return counts
    placeholders = ",".join("?" * len(batch_ids))
    rows = conn.execute(
        f"SELECT status, COUNT(*) AS n FROM jobs WHERE id IN"
        f" ({placeholders}) GROUP BY status",
        tuple(batch_ids),
    ).fetchall()
    for r in rows:
        if r["status"] in counts:
            counts[r["status"]] = r["n"]
    return counts


async def _vault_qc_pass(script_id: int, batch_ids: list[int]) -> dict:
    """Slice 4 auto-QC second pass. For every job that finished
    in this batch with a Vault pin: read the saved image, check
    it against the pinned sheet with vault_qc.qc_check, and
    re-queue it ONCE when it is broken or blank. The similarity
    score is recorded in the job options for the record only —
    it never triggers a regenerate (calibration proved it
    cannot tell drift from a good image; see vault_qc.py).
    Jobs without a Vault pin, and jobs already QC'd once
    (qc_attempted), are skipped, so the second pass can never
    loop. Returns {checked, requeued, regenerated}."""
    if not batch_ids:
        return {"checked": 0, "requeued": 0, "regenerated": 0}
    placeholders = ",".join("?" * len(batch_ids))
    with db() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE id IN ({placeholders})"
            " AND status = 'done'",
            tuple(batch_ids),
        ).fetchall()
    to_requeue: list[tuple[int, str]] = []
    checked = 0
    for row in rows:
        try:
            opts = json.loads(row["options_json"] or "{}")
        except (TypeError, ValueError):
            opts = {}
        vault = opts.get("vault") or {}
        if not vault.get("sheet_path") or opts.get("qc_attempted"):
            continue
        out = row["output_path"]
        if not out:
            continue
        img_file = media_path(out)
        sheet_file = media_path(vault["sheet_path"])
        if not img_file.is_file():
            continue
        checked += 1
        sheet_bytes = sheet_file.read_bytes() if sheet_file.is_file() else None
        result = _vault_qc.qc_check(img_file.read_bytes(), sheet_bytes)
        opts["qc_score"] = result["score"]
        opts["qc_reason"] = result["reason"]
        opts["qc_attempted"] = True
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET options_json = ?, updated_at = ?"
                " WHERE id = ?",
                (json.dumps(opts), utcnow(), row["id"]),
            )
        if result["needs_regen"]:
            to_requeue.append((row["id"], result["reason"]))
    if not to_requeue:
        return {"checked": checked, "requeued": 0, "regenerated": 0}
    with db() as conn:
        for job_id, reason in to_requeue:
            conn.execute(
                "UPDATE jobs SET status = 'queued',"
                " error = ?, output_path = NULL, updated_at = ?"
                " WHERE id = ?",
                (
                    f"Auto-QC: {reason} — dobara ban raha hai",
                    utcnow(),
                    job_id,
                ),
            )
    # Second pass through the same worker (lock already held —
    # this is the _locked variant, so no deadlock). Only the
    # re-queued jobs are 'queued', so only they run; their
    # qc_attempted flag keeps this pass from looping.
    await _process_image_jobs_locked(script_id)
    with db() as conn:
        regenerated = conn.execute(
            f"SELECT COUNT(*) AS n FROM jobs WHERE id IN"
            f" ({','.join('?' * len(to_requeue))}) AND status = 'done'",
            tuple(job_id for job_id, _ in to_requeue),
        ).fetchone()["n"]
    return {
        "checked": checked,
        "requeued": len(to_requeue),
        "regenerated": regenerated,
    }


def script_detail(conn, script_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM scripts WHERE id = ?", (script_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="script not found")
    scenes = conn.execute(
        "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
        (script_id,),
    ).fetchall()
    detail = dict(row)
    detail["scenes"] = [dict(s) for s in scenes]
    return detail


def timeline_detail(conn, timeline_id: int) -> dict:
    tl = conn.execute(
        "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
    ).fetchone()
    if tl is None:
        raise HTTPException(status_code=404, detail="timeline not found")
    clips = conn.execute(
        """
        SELECT c.*, a.path AS asset_path, a.kind AS asset_kind,
               COALESCE(a.placeholder, 0) AS asset_placeholder,
               CASE WHEN v.verdict = 'approved' THEN 1 ELSE 0 END
                   AS asset_approved
        FROM clips c JOIN assets a ON a.id = c.asset_id
        LEFT JOIN image_verdicts v ON v.asset_id = c.asset_id
        WHERE c.timeline_id = ? ORDER BY c.position, c.id
        """,
        (timeline_id,),
    ).fetchall()
    detail = dict(tl)
    detail["clips"] = [dict(c) for c in clips]
    # Honest reuse flag: a clip reuses an image when the same asset
    # already appeared in an earlier clip of this timeline (image
    # cycling — the same picture never looks the same twice, because
    # every clip has a different effect). Clips stored before effects
    # existed get the positional effect, so old timelines render and
    # display with varied movement too.
    seen_assets: set[int] = set()
    for clip in detail["clips"]:
        clip["asset_reused"] = 1 if clip["asset_id"] in seen_assets else 0
        seen_assets.add(clip["asset_id"])
        clip["effect"] = clip_effect(clip)
    # Phase 2 slice 2: image prompts reference the character by name.
    char = get_character(conn, tl["project_id"])
    detail["character_name"] = char["name"] if char else None
    detail["character_image_path"] = char["image_path"] if char else None
    return detail


def latest_timeline_for_project(conn, project_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id FROM timelines WHERE project_id = ? ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    return timeline_detail(conn, row["id"])


def srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(clips: list) -> str:
    blocks = []
    n = 0
    for clip in clips:
        text = (clip.get("caption_text") or "").strip()
        if not text:
            continue
        n += 1
        blocks.append(
            f"{n}\n"
            f"{srt_timestamp(clip['start_s'])} --> {srt_timestamp(clip['end_s'])}\n"
            f"{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


MIN_CLIP_S = 2.0


def beat_durations(word_counts: list[int], total_s: float) -> list[float]:
    """Apportion a voiceover duration across clips by scene word count.

    words/total-words x VO duration, rounded to milliseconds, with the
    last clip taking the remainder so the sum is exactly total_s.
    Every clip gets at least MIN_CLIP_S (a one-line sentence still
    needs time to read and see); the extra time comes off the clips
    above the floor, proportionally, so the total stays exact. Falls
    back to equal splits when no clip has any words, or when the
    voiceover is too short for the floor on every clip.
    """
    n = len(word_counts)
    if n == 0:
        return []
    total_words = sum(max(0, w) for w in word_counts)
    if total_words <= 0 or total_s <= 0 or total_s <= n * MIN_CLIP_S:
        per = round(total_s / n, 3) if n else 0.0
        return [per] * n
    raw = [total_s * max(0, w) / total_words for w in word_counts]
    # Floor: short clips up to MIN_CLIP_S, the deficit taken from the
    # above-floor clips in proportion to how far above the floor they
    # are (no donor ever drops below the floor).
    durations = [max(MIN_CLIP_S, d) for d in raw]
    deficit = sum(durations) - total_s
    if deficit > 0:
        slack = [max(0.0, d - MIN_CLIP_S) for d in durations]
        slack_total = sum(slack)
        if slack_total > 0:
            durations = [
                d - deficit * s / slack_total for d, s in zip(durations, slack)
            ]
    # Round to milliseconds; the last clip takes the remainder so the
    # sum is exactly total_s.
    out: list[float] = []
    used = 0.0
    for i, d in enumerate(durations):
        if i == n - 1:
            out.append(round(total_s - used, 3))
        else:
            d = round(max(0.1, d), 3)
            out.append(d)
            used += d
    return out


def escape_drawtext(text: str) -> str:
    """Escape text for ffmpeg drawtext text= (inside single quotes).

    NOTE: kept for reference only — renders now use textfile= instead,
    because the filter parser mangles \\n and \\' in text= (see
    wrap_caption). Do not use this for captions.
    """
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def wrap_caption(
    text: str,
    fontsize: int = 44,
    uppercase: bool = True,
    max_lines: int = 4,
    frame_width: int = 1920,
) -> str:
    """Word-wrap a caption for drawtext, lines joined with REAL newlines.

    Captions are rendered via drawtext textfile= (a small text file per
    clip), NOT via the text= option: the filter-graph parser mangles
    backslash escapes (``\\n`` renders as a literal "n", ``\\'`` drops
    the apostrophe and can break the whole filter graph). A text file
    carries the exact characters, including apostrophes, and real
    newlines become real line breaks. UPPERCASE only when the style
    says so. Wrap width follows the font size (bold caps are wide)
    and the frame width — a 1080-wide vertical clip fits fewer
    characters per line than a 1920-wide landscape render.
    """
    shown = text.upper() if uppercase else text
    # 1600 px of usable text width on a 1920 frame (margins left over);
    # a narrower frame (1080 vertical) scales the same proportion.
    usable = 1600.0 * frame_width / 1920.0
    width = max(20, int(usable / max(1, fontsize * 0.72)))
    words = shown.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines[:max_lines])


# Seconds of crossfade between clips. The render keeps the video exactly
# VO-length: every clip except the last is rendered 0.5 s longer, and the
# Sentence-level visuals: every clip moves differently from its
# neighbours (zoom-in / zoom-out / pan-left / pan-right, rotating by
# position), so the video never sits still on one look — har sentence
# ke saath visual change.
# Phase 7 slice 2: four more named presets, each a visibly different
# zoompan — slow zooms (half the travel of the fast ones), drift (a
# slow diagonal pan) and pulse (the zoom breathes in and out twice).
CLIP_EFFECTS = [
    "zoom-in",
    "zoom-out",
    "pan-left",
    "pan-right",
    "slow-zoom-in",
    "slow-zoom-out",
    "drift",
    "pulse",
]

EFFECT_LABELS = {
    "zoom-in": "Zoom in",
    "zoom-out": "Zoom out",
    "pan-left": "Pan left",
    "pan-right": "Pan right",
    "slow-zoom-in": "Slow zoom in",
    "slow-zoom-out": "Slow zoom out",
    "drift": "Drift (diagonal pan)",
    "pulse": "Pulse (breathe in/out)",
}

# Render quality: output size per choice. The zoompan source is
# 4/3 of the output (e.g. 2560x1440 for 1080p), so the movement has
# headroom to crop. 4K from 1080p sources is an upscale — no new
# detail is invented, and the UI says so. 4K renders in TWO passes:
# pass 1 is the proven 1080p pipeline to a temp file, pass 2
# upscales that file to 3840x2160 (lanczos). The real sources are
# 2048 px wide at most, and a single graph with a 4K scale at the
# end OOM-killed this VM twice (jobs 92/93 native 4K, job 94
# 1080p-pipeline + in-graph upscale: ffmpeg SIGKILLed at frame
# ~281–284/1371, peak RSS 5.5–5.7 GB — the graph holds ~20 MB per
# 4K frame), while the 1080p render and a 45 s static 4K encode
# each complete on their own.
RENDER_QUALITIES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4K": (3840, 2160),
}
RENDER_SOURCES = {
    "720p": (1706, 960),
    "1080p": (2560, 1440),
    "4K": (2560, 1440),
}

# Atmosphere looks applied once, after captions, on the whole video —
# real ffmpeg filters only: vignette darkens the corners, noise adds
# film grain, colorbalance warms the grade.
ATMOSPHERE_FILTERS = ("vignette", "grain", "warm")


def effect_for_position(position: int) -> str:
    """The effect a clip at this position gets — rotating, so two
    neighbouring clips never share one."""
    return CLIP_EFFECTS[position % len(CLIP_EFFECTS)]


def clip_effect(clip: dict) -> str:
    """A clip's stored effect when it is a real one, else the
    positional fallback (old clips, stored before effects existed)."""
    stored = (clip.get("effect") or "").strip()
    if stored in CLIP_EFFECTS:
        return stored
    return effect_for_position(int(clip.get("position") or 0))


# xfade overlaps eat exactly that extra time.
XFADE_S = 0.5


def _render_cause(proc, timeline_id: int) -> str:
    """What the queue shows when a render fails. A killed ffmpeg
    (OOM: returncode -9) prints no error at all — stderr just ends
    mid-progress — so a bare "last line" is a useless frame counter
    or a stream header. Report the signal + where it stopped
    instead; a real ffmpeg error still surfaces as its own last
    message. The full log is saved next to the renders either way."""
    lines = (proc.stderr or "").strip().splitlines()
    progress = [
        ln.strip() for ln in lines
        if ln.lstrip().startswith("frame=")
    ]
    stopped = progress[-1] if progress else ""
    if proc.returncode and proc.returncode < 0:
        return (
            f"ffmpeg killed by signal {-proc.returncode}"
            f" (likely out of memory) at {stopped}"
            " — full log: "
            f"timeline_{timeline_id}_error.log"
        )
    # ffmpeg exits 255 (not -15) when it receives SIGTERM — e.g. the
    # backend was stopped mid-render. That is a killed render, not a
    # codec error; say so plainly instead of quoting ffmpeg's jargon
    # ("Exiting normally, received signal 15.").
    if proc.returncode == 255 and "received signal" in (proc.stderr or ""):
        sig = "?"
        for ln in lines:
            if "received signal" in ln:
                sig = ln.rsplit("signal", 1)[-1].strip().rstrip(".")
                break
        return (
            f"ffmpeg signal {sig} se band hua (render beech me ruka — "
            f"backend band hua ya render roka gaya) at {stopped}"
            " — full log: "
            f"timeline_{timeline_id}_error.log"
        )
    return next(
        (ln.strip() for ln in reversed(lines)
         if ln.strip()
         and not ln.lstrip().startswith("frame=")
         and "encoder" not in ln
         and not ln.lstrip().startswith("Stream #")),
        stopped or "ffmpeg failed",
    )


# --- Cross-check slice: named atmosphere presets -----------------------
# AutoCut Studio PRO shows ~28 atmosphere presets; Kreafy had the
# same idea as three bools (vignette / grain / warm). A preset is a
# list of real ffmpeg filter strings, applied in order after the
# captions, on the whole video. Letterbox 2.5:1 is a crop (1920x1080
# -> 1920x768) — the caption y-position is adjusted for it in
# run_render so the captions stay inside the visible band.
ATMOSPHERE_PRESETS: dict[str, list[str]] = {
    "Vintage Sepia": [
        "colorbalance=rs=0.10:gs=0.02:bs=-0.12",
        "eq=saturation=0.8:contrast=1.05",
    ],
    "Noir (Black & White)": ["eq=saturation=0"],
    "VHS Noise": [
        "noise=alls=20:allf=t",
        "eq=contrast=0.95:saturation=0.9",
    ],
    "Golden Hour": [
        "colorbalance=rs=0.12:gs=0.06:bs=-0.10",
        "eq=saturation=1.15",
    ],
    "Cool Winter": [
        "colorbalance=rs=-0.08:gs=0.0:bs=0.10",
        "eq=saturation=0.95",
    ],
    "Warm Sunset": [
        "colorbalance=rs=0.15:gs=0.03:bs=-0.12",
        "eq=saturation=1.2:contrast=1.05",
    ],
    "Dreamy Pastel": ["eq=saturation=0.75:brightness=0.03:contrast=0.9"],
    "Moody Dark": [
        "eq=brightness=-0.06:contrast=1.12:saturation=0.85",
        "vignette=0.7",
    ],
    "Letterbox 2.5:1": ["crop=iw:iw/2.5"],
}

# --- Cross-check slice: cancel ("Stop run") ---------------------------
# Renders run ffmpeg via _run_ffmpeg (Popen, not subprocess.run) so a
# cancel request can kill the live process. The registry maps
# job_id -> live Popen; _CANCELLED_JOBS is the set of job ids whose
# worker must report 'cancelled' instead of 'failed'.
_RUNNING_PROCS: dict[int, subprocess.Popen] = {}
_RUNNING_PROCS_LOCK = threading.Lock()
_CANCELLED_JOBS: set[int] = set()


def _run_ffmpeg(cmd: list[str], job_id: int, timeout: int = 900):
    """Run ffmpeg so a cancel can kill it. Returns a
    subprocess.CompletedProcess (returncode + stderr) so _render_cause
    works unchanged. A timeout kills the process and raises
    RuntimeError; a kill from cancel_job raises RuntimeError too —
    the caller checks _CANCELLED_JOBS first and marks 'cancelled'."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    with _RUNNING_PROCS_LOCK:
        _RUNNING_PROCS[job_id] = proc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise RuntimeError(
            "ffmpeg timed out after 15 minutes — render beech me ruk gaya"
        )
    finally:
        with _RUNNING_PROCS_LOCK:
            _RUNNING_PROCS.pop(job_id, None)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def run_render(job_id: int, timeline_id: int) -> None:
    """Background render: Ken Burns zoom + crossfades + burned-in
    captions + VO audio -> MP4, 30 fps.

    Quality + atmosphere come from the job's stored options_json
    (queued by /render or /rerender; the one-click run leaves them
    empty, which means 1080p with no atmosphere). Quality picks the
    output size — 720p, 1080p (default) or 4K, which upscales the
    1080p sources without inventing detail. Atmosphere is applied
    once, after the captions, on the whole video: vignette, film
    grain, warm grade — real ffmpeg filters only.

    Per clip: movement from its stored effect — zoom-in, zoom-out,
    pan-left, pan-right, slow-zoom-in, slow-zoom-out, drift, pulse —
    rotating by position so no two neighbours move the same way, via
    zoompan on a still image. Caption burned in with drawtext (Bold
    White: white text, black outline, bottom-centre, UPPERCASE).
    Clips are joined with 0.5 s xfade crossfades at the script-beat
    boundaries, so the finished video is exactly as long as the
    voiceover.
    """
    with db() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return
        # Cancelled while queued: the cancel endpoint already set the
        # status — the worker must not start the render at all.
        if job["status"] == "cancelled":
            return
        detail = timeline_detail(conn, timeline_id)
        # Release Packaging: the finished video is named after the
        # project, date-wise: <slug>_YYYY-MM-DD_HHMM.mp4 in
        # output/YYYY-MM-DD/.
        project_slug = _project_slug(conn, detail.get("project_id") or job["project_id"])
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("running", utcnow(), job_id),
        )
    # The queue stored the render options on the job row; an old job
    # (or the one-click run, which queues without options) has none,
    # which honestly means the defaults.
    options = {}
    try:
        options = json.loads(job["options_json"] or "{}")
    except (TypeError, ValueError, KeyError):
        options = {}
    quality = options.get("quality") or "1080p"
    if quality not in RENDER_QUALITIES:
        quality = "1080p"
    # Slice 3 (Magic Mode): aspect comes from the job's options (the
    # one-click run stores it there from the run row). 16:9 is exactly
    # today's dims, so every existing render is unchanged. A bad
    # aspect in an old job is ignored, never a silent crash.
    try:
        aspect = magic_validate_aspect(options.get("aspect") or "16:9")
    except ValueError:
        aspect = "16:9"
    out_w, out_h, pipe_w, pipe_h, src_w, src_h = magic_aspect_dims(
        aspect, quality
    )
    # Cross-check slice: atmosphere = the three bools (kept) + one
    # named preset (validated at the endpoint; an unknown preset
    # here is ignored, never a silent crash). Caption size % scales
    # the style's font; position moves the burned captions;
    # captions=False burns none at all (ClipNova "Captions: None").
    preset_name = options.get("atmosphere_preset") or ""
    preset_filters = ATMOSPHERE_PRESETS.get(preset_name, [])
    size_pct = options.get("caption_size_pct") or 100
    try:
        size_pct = int(size_pct)
    except (TypeError, ValueError):
        size_pct = 100
    size_pct = max(50, min(150, size_pct))
    cap_position = options.get("caption_position") or "bottom"
    if cap_position not in ("bottom", "center", "top"):
        cap_position = "bottom"
    captions_on = options.get("captions", True) is not False
    atmosphere = [
        name for name in ATMOSPHERE_FILTERS if options.get(name) is True
    ]
    try:
        clips = detail["clips"]
        if not clips:
            raise RuntimeError("timeline has no clips to render")
        vo_path = None
        if detail.get("vo_asset_id"):
            with db() as conn:
                vo = conn.execute(
                    "SELECT path FROM assets WHERE id = ?",
                    (detail["vo_asset_id"],),
                ).fetchone()
            if vo:
                vo_path = DATA_DIR / vo["path"]
                if not vo_path.exists():
                    vo_path = None
        out_name = _dated_name(project_slug, "mp4")
        out_path = output_dir_for_today() / out_name

        # Caption style actually applied to this timeline (Bold White
        # when none is chosen). Only styles in CAPTION_RENDER_SPECS can
        # be burned in — the spec is what the render really draws.
        spec = dict(CAPTION_RENDER_SPECS["Bold White"])
        style_name = "Bold White"
        if detail.get("caption_style_id"):
            with db() as conn:
                row = conn.execute(
                    "SELECT name FROM caption_styles WHERE id = ?",
                    (detail["caption_style_id"],),
                ).fetchone()
            if row and row["name"] in CAPTION_RENDER_SPECS:
                style_name = row["name"]
                spec = dict(CAPTION_RENDER_SPECS[style_name])
        fontfile = spec.get("fontfile") or FONT_PATH

        # Burned-in captions go through drawtext textfile= files (one per
        # clip, under studio/data/tmp/). See wrap_caption: the text=
        # option mangles apostrophes and newlines through the filter
        # parser, a file carries the exact characters.
        cap_dir = TMP_DIR / f"timeline_{timeline_id}_captions"
        cap_dir.mkdir(parents=True, exist_ok=True)
        cap_files: dict[int, Path] = {}
        # Cross-check slice: captions off = no caption files at all;
        # size % scales the font the style would use (wrap + draw
        # both use the scaled size so wrapping matches the drawing).
        draw_fs = max(16, round(spec["fontsize"] * size_pct / 100))
        if captions_on:
            for ci, clip in enumerate(clips):
                caption = (clip.get("caption_text") or "").strip()
                if not caption:
                    continue
                wrapped = wrap_caption(
                    caption,
                    fontsize=draw_fs,
                    uppercase=spec["uppercase"],
                    frame_width=pipe_w,
                )
                p = cap_dir / f"clip_{ci}.txt"
                p.write_text(wrapped, encoding="utf-8")
                cap_files[ci] = p

        # Beat durations from the stored clip timings (script-beat sync
        # already apportioned them; equal-split timelines still work).
        beat = [max(0.1, round(c["end_s"] - c["start_s"], 3)) for c in clips]
        n = len(clips)
        # Segment fed to xfade: +0.5 s for every clip except the last, so
        # the overlaps cancel out and total video == sum(beat) == VO.
        seg = [round(d + XFADE_S, 3) if i < n - 1 else d for i, d in enumerate(beat)]

        cmd = [shutil.which("ffmpeg") or "ffmpeg", "-y"]
        for clip in clips:
            img = DATA_DIR / clip["asset_path"]
            cmd += ["-i", str(img)]
        if vo_path:
            cmd += ["-i", str(vo_path)]

        filters: list[str] = []
        for i, clip in enumerate(clips):
            frames = max(1, int(round(seg[i] * 30)))
            # Every clip moves differently from its neighbours: the
            # stored effect rotates by position. Pans hold a fixed
            # 1.15x zoom and slide the window across the frame; zooms
            # stay centred. Slow zooms travel half as far as the fast
            # ones; drift slides diagonally; pulse breathes in and out
            # twice over the clip (sin, two full cycles).
            effect = clip_effect(clip)
            if effect == "zoom-out":
                zoom = f"1.15-0.15*on/{frames}"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif effect == "pan-left":
                zoom = "1.15"
                x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
                y_expr = "ih/2-(ih/zoom/2)"
            elif effect == "pan-right":
                zoom = "1.15"
                x_expr = f"(iw-iw/zoom)*on/{frames}"
                y_expr = "ih/2-(ih/zoom/2)"
            elif effect == "slow-zoom-in":
                zoom = f"1+0.08*on/{frames}"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif effect == "slow-zoom-out":
                zoom = f"1.08-0.08*on/{frames}"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif effect == "drift":
                zoom = "1.15"
                x_expr = f"(iw-iw/zoom)*on/{frames}"
                y_expr = f"(ih-ih/zoom)*on/{frames}"
            elif effect == "pulse":
                zoom = f"1+0.05*sin(12.566*on/{frames})"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            else:  # zoom-in (default)
                zoom = f"1+0.15*on/{frames}"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            chain = (
                f"[{i}:v]scale={src_w}:{src_h}:force_original_aspect_ratio=increase,"
                f"crop={src_w}:{src_h},"
                f"zoompan=z='{zoom}':x='{x_expr}':y='{y_expr}'"
                f":d={frames}:s={pipe_w}x{pipe_h}:fps=30,"
                f"settb=AVTB,format=yuv420p"
            )
            filters.append(f"{chain}[v{i}]")
        # Chain the 0.5 s crossfades at the beat boundaries.
        if n == 1:
            filters.append("[v0]format=yuv420p[vout]")
        else:
            cur = "v0"
            offset = 0.0
            for i in range(1, n):
                offset += beat[i - 1]
                nxt = f"x{i}" if i < n - 1 else "vout"
                filters.append(
                    f"[{cur}][v{i}]xfade=transition=fade"
                    f":duration={XFADE_S}:offset={offset:.3f}[{nxt}]"
                )
                cur = nxt
        # Burned-in captions AFTER the crossfades, timed to the VO beats
        # (enable between clip start/end). Drawing them per-clip before
        # the xfade made two captions overlap unreadably for 0.5 s at
        # every cut; timed captions switch crisply at the beat instead.
        cap_in = "vout"
        cap_indices = [
            i
            for i, clip in enumerate(clips)
            if captions_on
            and (clip.get("caption_text") or "").strip()
            and fontfile
            and i in cap_files
        ]
        # Cross-check slice: caption position. Bottom is the old
        # y=h-text_h-70; center and top use the frame height. With
        # the Letterbox preset the visible band is the middle
        # pipe_w/2.5 pixels, so the bottom caption sits inside that
        # band instead of under the crop.
        if preset_name == "Letterbox 2.5:1":
            _crop_h = pipe_w / 2.5
            _crop_top = (pipe_h - _crop_h) / 2
            cap_y = f"{int(_crop_top + _crop_h - 20)}-text_h"
        elif cap_position == "center":
            cap_y = "(h-text_h)/2"
        elif cap_position == "top":
            cap_y = "70"
        else:
            cap_y = "h-text_h-70"
        for j, i in enumerate(cap_indices):
            clip = clips[i]
            last = j == len(cap_indices) - 1
            cap_out = "vfinal" if last else f"vc{j}"
            dt = (
                f"[{cap_in}]drawtext=fontfile={fontfile}"
                f":textfile='{cap_files[i]}'"
                f":fontsize={draw_fs}"
                f":fontcolor={spec['fontcolor']}"
                f":borderw={spec['borderw']}:bordercolor=black"
            )
            if spec["shadow"]:
                dt += ":shadowcolor=black:shadowx=2:shadowy=2"
            if spec["box"]:
                dt += ":box=1:boxcolor=black@0.55:boxborderw=12"
            dt += (
                f":x=(w-text_w)/2:y={cap_y}"
                f":enable='between(t\\,{clip['start_s']:.3f}\\,{clip['end_s']:.3f})'"
                f"[{cap_out}]"
            )
            filters.append(dt)
            cap_in = cap_out
        final_label = "vfinal" if cap_indices else "vout"
        # Atmosphere looks, once, on the whole finished video (after
        # captions): vignette darkens the corners, noise adds film
        # grain, colorbalance warms the grade, and a named preset adds
        # its own filter chain (e.g. Noir desaturates, VHS adds
        # noise). Each is a real ffmpeg filter; nothing here is a
        # label-only effect.
        atm_in = final_label
        atm_filters: list[str] = []
        for name in atmosphere:
            if name == "vignette":
                atm_filters.append("vignette=0.628")
            elif name == "grain":
                atm_filters.append("noise=alls=12:allf=t")
            elif name == "warm":
                atm_filters.append(
                    "colorbalance=rs=0.08:gs=0.02:bs=-0.08"
                )
        atm_filters.extend(preset_filters)
        for k, filt in enumerate(atm_filters):
            atm_out = f"atm{k}"
            filters.append(f"[{atm_in}]{filt}[{atm_out}]")
            atm_in = atm_out
        final_label = atm_in
        cmd += ["-filter_complex", ";".join(filters)]
        cmd += ["-map", f"[{final_label}]"]
        if vo_path:
            cmd += ["-map", f"{n}:a", "-c:a", "aac"]
        else:
            cmd += ["-an"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-movflags", "+faststart", "-shortest"]
        # 4K is TWO passes (see RENDER_SOURCES note): pass 1 renders
        # the proven 1080p pipeline to a temp file; pass 2 upscales
        # that file to 3840x2160. A single graph with a 4K scale at
        # the end OOM-killed this VM (job 94 / probe 2: SIGKILL at
        # frame 284, peak RSS 5.7 GB) while the 1080p render and a
        # 45 s static 4K encode each complete on their own.
        pass1_path = out_path
        if quality == "4K":
            pass1_path = TMP_DIR / f"timeline_{timeline_id}_{int(time.time())}_1080p.mp4"
        proc = _run_ffmpeg(cmd + [str(pass1_path)], job_id)
        if proc.returncode != 0:
            # Keep the full ffmpeg log next to the renders so a failed
            # render can be diagnosed on the PC (the job only stores
            # the last line). Never fails the job update itself.
            try:
                (TMP_DIR / f"timeline_{timeline_id}_error.log").write_text(
                    "CMD: " + " ".join(cmd + [str(pass1_path)]) + "\n\n" + (proc.stderr or ""),
                    encoding="utf-8",
                )
            except OSError:
                pass
            raise RuntimeError(_render_cause(proc, timeline_id))
        if quality == "4K":
            # Pass 2: upscale the finished 1080p file. Single input,
            # no zoompan/xfade graph — the step that OOMs is avoided.
            cmd2 = [
                shutil.which("ffmpeg") or "ffmpeg", "-y",
                "-i", str(pass1_path),
                "-vf", f"scale={out_w}:{out_h}:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-movflags", "+faststart",
                "-c:a", "copy",
                str(out_path),
            ]
            proc2 = _run_ffmpeg(cmd2, job_id)
            try:
                pass1_path.unlink()
            except OSError:
                pass
            if proc2.returncode != 0:
                try:
                    (TMP_DIR / f"timeline_{timeline_id}_error.log").write_text(
                        "CMD: " + " ".join(cmd2) + "\n\n" + (proc2.stderr or ""),
                        encoding="utf-8",
                    )
                except OSError:
                    pass
                raise RuntimeError(
                    "4K upscale pass failed: " + _render_cause(proc2, timeline_id)
                )
        rel = f"output/{_today_str()}/{out_name}"
        # Cancelled in the last moment (ffmpeg finished just as the
        # user pressed cancel): the file is discarded and the job is
        # 'cancelled', never 'done'.
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "render roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, output_path = ?, updated_at = ?"
                " WHERE id = ?",
                ("done", rel, utcnow(), job_id),
            )
    except Exception as exc:  # noqa: BLE001 - record the failure on the job
        # Cross-check slice: a cancelled render is 'cancelled', not
        # 'failed' — the user stopped it on purpose. The cancel
        # endpoint puts the job id in _CANCELLED_JOBS before killing
        # ffmpeg, so this branch knows the difference.
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            # A killed ffmpeg leaves a partial output file (no moov
            # atom — unplayable). Delete it so a cancelled render
            # never looks like a video on disk.
            for _p in (locals().get("out_path"), locals().get("pass1_path")):
                try:
                    if _p is not None:
                        Path(_p).unlink(missing_ok=True)
                except OSError:
                    pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "render roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                " WHERE id = ?",
                ("failed", str(exc)[:500], utcnow(), job_id),
            )


# --- Phase 3 slice 2: one-click run ---------------------------------------

# The six pipeline steps, in order. Each step is a jobs row (kind below)
# linked to the run by run_id, so the Jobs list and the run-progress
# view show the same honest per-step state.
# Slice 3 (Magic Mode — One-Click Autopilot v2): the six stages
# Ali sees in the progress bar. Script and Images run in the Magic
# worker; Voice is produced there too; Timeline / Captions / Render
# are the existing one-click run's steps, mirrored into these
# stages so the bar never shows a step the app did not really do.
MAGIC_STAGES = ["script", "images", "voice", "timeline", "captions", "render"]
MAGIC_STAGE_LABELS = {
    "script": "Script",
    "images": "Images",
    "voice": "Voice",
    "timeline": "Timeline",
    "captions": "Captions",
    "render": "Render",
}
MAGIC_ASPECTS = ("16:9", "9:16", "1:1")
MAGIC_LANGUAGES = ("en", "ur")


def magic_validate_aspect(aspect: str) -> str:
    """'16:9' / '9:16' / '1:1' — anything else is a plain error,
    never a silent fallback to 16:9."""
    aspect = (aspect or "").strip() or "16:9"
    if aspect not in MAGIC_ASPECTS:
        raise ValueError("aspect '16:9', '9:16' ya '1:1' hona chahiye")
    return aspect


def magic_validate_language(language: str) -> str:
    """'en' (English) / 'ur' (Roman Urdu) — anything else is a
    plain error, never a silent fallback to English."""
    language = (language or "").strip().lower() or "en"
    if language not in MAGIC_LANGUAGES:
        raise ValueError("language 'en' (English) ya 'ur' (Roman Urdu)"
                         " hona chahiye")
    return language


def magic_aspect_dims(aspect: str, quality: str) -> tuple[int, int, int, int, int, int]:
    """(out_w, out_h, pipe_w, pipe_h, src_w, src_h) for a render at
    this aspect + quality. 16:9 is exactly today's dims (the old
    RENDER_QUALITIES / RENDER_SOURCES values, unchanged). 9:16 swaps
    the frame; 1:1 squares it. Sources stay 4/3 of the pipe size
    (the zoompan headroom the 16:9 pipeline already uses), rounded
    to even numbers for yuv420p. 4K pipes through the 1080p-sized
    graph and upscales once at the end, as before."""
    aspect = magic_validate_aspect(aspect)
    if quality not in RENDER_QUALITIES:
        quality = "1080p"
    base_w, base_h = RENDER_QUALITIES[quality]
    if aspect == "16:9":
        out_w, out_h = base_w, base_h
    elif aspect == "9:16":
        out_w, out_h = base_h, base_w
    else:  # 1:1
        out_w, out_h = base_h, base_h
    if quality == "4K":
        if aspect == "16:9":
            pipe_w, pipe_h = 1920, 1080
        elif aspect == "9:16":
            pipe_w, pipe_h = 1080, 1920
        else:
            pipe_w, pipe_h = 1080, 1080
    else:
        pipe_w, pipe_h = out_w, out_h
    if aspect == "16:9":
        src_w, src_h = RENDER_SOURCES[quality]
    else:
        src_w = (pipe_w * 4 // 3) // 2 * 2
        src_h = (pipe_h * 4 // 3) // 2 * 2
    return (out_w, out_h, pipe_w, pipe_h, src_w, src_h)


def estimate_video_duration_s(words: int) -> float:
    """Video length from the script alone (Ali's rule, Slice 3):
    words / ~150 words per minute. 1,500 words is ~10 minutes.
    The real video length is still the voiceover's, once it exists
    — this is the estimate Magic shows before the voice is made."""
    return round(max(0.0, int(words) / WORDS_PER_MINUTE * 60), 1)


def _split_tts_chunks(text: str, max_chars: int = 4500) -> list[str]:
    """Split narration into <= max_chars chunks for TTS (Edge-TTS
    and HeyGen both take ~5,000 characters per call). Splits happen
    on sentence boundaries; one over-long sentence is split on word
    boundaries. Empty input -> []. Pure function — white-box tested."""
    text = (text or "").strip()
    if not text:
        return []
    sentences: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if para.strip():
            sentences.extend(_sentences(para))
    if not sentences:
        sentences = [text]
    chunks: list[str] = []
    cur = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(cur) + (1 if cur else 0) + len(sent) <= max_chars:
            cur = f"{cur} {sent}" if cur else sent
            continue
        if cur:
            chunks.append(cur)
        cur = ""
        words = sent.split()
        part = ""
        for word in words:
            if len(part) + (1 if part else 0) + len(word) > max_chars:
                if part:
                    chunks.append(part)
                part = word
            else:
                part = f"{part} {word}" if part else word
        cur = part
    if cur.strip():
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def _concat_audio_parts(
    project_id: int, parts: list[Path], tag: str
) -> tuple[str, Path]:
    """Join TTS chunk MP3s into one voiceover file (ffmpeg concat
    demuxer + libmp3lame re-encode, so chunk boundaries never
    glitch). Returns (relative path, disk path). Raises RuntimeError
    with a plain message on failure — the caller turns it into a
    failed voice stage."""
    if not parts:
        raise RuntimeError("koi audio chunk nahi mila — voiceover nahi bana")
    folder = PROJECTS_DIR / str(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    name = f"voice_magic_{tag}_{stamp}.mp3"
    disk = folder / name
    lst = folder / f".magic_{tag}_{stamp}_concat.txt"
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    try:
        lst.write_text(
            "".join(f"file '{p.resolve()}'\n" for p in parts),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                ffmpeg, "-y", "-f", "concat", "-safe", "0",
                "-i", str(lst), "-c:a", "libmp3lame", "-q:a", "3",
                str(disk),
            ],
            capture_output=True, text=True, timeout=900,
        )
        if proc.returncode != 0:
            lines = (proc.stderr or "").strip().splitlines()
            raise RuntimeError(
                "voiceover chunks jorne me fail: "
                + (lines[-1] if lines else "ffmpeg failed")
            )
    finally:
        try:
            lst.unlink()
        except OSError:
            pass
    if not disk.exists() or disk.stat().st_size == 0:
        raise RuntimeError("voiceover chunks jorne se khaali file bani")
    return f"projects/{project_id}/{name}", disk


RUN_STEP_KINDS = [
    "run_script",
    "run_voice",
    "run_images",
    "run_timeline",
    "run_captions",
    "render",
]

RUN_STEP_LABELS = {
    "run_script": "Script",
    "run_voice": "Voice",
    "run_images": "Images",
    "run_timeline": "Timeline",
    "run_captions": "Captions",
    "render": "Render",
}


def _set_job(conn, job_id: int, status: str, error: str | None = None) -> None:
    """Update one step job's status/error. output_path is owned by the
    render step itself (run_render) and is never touched here."""
    conn.execute(
        "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
        (status, error, utcnow(), job_id),
    )


def _set_run(conn, run_id: int, status: str, **fields) -> None:
    """Update a run's status plus any of the allowed fields."""
    allowed = {"error", "output_path", "srt_path", "timeline_id", "vo_asset_id"}
    sets = ["status = ?", "updated_at = ?"]
    values: list = [status, utcnow()]
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(value)
    values.append(run_id)
    conn.execute(
        f"UPDATE runs SET {', '.join(sets)} WHERE id = ?",
        values,
    )


def run_detail(conn, run_id: int) -> dict:
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    detail = dict(row)
    steps = conn.execute(
        "SELECT * FROM jobs WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    detail["steps"] = [dict(s) for s in steps]
    return detail


async def _tts_save(project_id: int, text: str, voice: str) -> tuple[str, Path]:
    """Generate free Edge-TTS audio into the project folder.

    Returns (relative path, disk path). Raises RuntimeError with a plain
    message when Edge-TTS is missing, blocked, or produces no audio —
    the caller turns that into a 503 (TTS endpoint) or a failed voice
    step (one-click run). Shared by both, so the wording stays the same.
    """
    try:
        import edge_tts  # noqa: PLC0415 - optional dependency, lazy import
    except ImportError:
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    folder = PROJECTS_DIR / str(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"voice_tts_{int(time.time())}.mp3"
    disk = folder / name
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(disk))
    except Exception:  # noqa: BLE001 - any TTS failure is "unavailable"
        if disk.exists():
            disk.unlink()
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    if not disk.exists() or disk.stat().st_size == 0:
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    return f"projects/{project_id}/{name}", disk


def make_placeholder_image(
    project_id: int,
    run_id: int,
    scene_index: int,
    scene_text: str,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """A real title-card PNG for a scene with no uploaded image: dark
    background, scene number, first words, and a "Placeholder - real
    image needed" line. Built with ffmpeg drawtext textfile= (the same
    mechanism as burned-in captions), so apostrophes are safe. The
    asset is flagged placeholder=1 so the UI marks it clearly instead
    of showing it as an ordinary upload. Phase 4 (VisualForge) is
    what replaces these with generated images. Slice 3 (Magic Mode):
    width/height follow the run's aspect (9:16 cards are tall)."""
    folder = PROJECTS_DIR / str(project_id) / "placeholders"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"placeholder_run{run_id}_scene{scene_index + 1}.png"
    disk = folder / name
    first_words = " ".join(scene_text.split()[:12])
    num_file = folder / f".ph_{run_id}_{scene_index}_num.txt"
    words_file = folder / f".ph_{run_id}_{scene_index}_words.txt"
    foot_file = folder / f".ph_{run_id}_{scene_index}_foot.txt"
    try:
        num_file.write_text(f"SCENE {scene_index + 1}", encoding="utf-8")
        words_file.write_text(
            wrap_caption(first_words, fontsize=48, uppercase=False, max_lines=3),
            encoding="utf-8",
        )
        foot_file.write_text("Placeholder - real image needed", encoding="utf-8")
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        # Text rows scale with the card height (16:9 is the old
        # 340/520/100); the colour source uses the card size.
        y_num = int(340 * height / 1080)
        y_words = int(520 * height / 1080)
        y_foot = int(100 * height / 1080)
        colour = f"color=c=0x0f0f0f:s={width}x{height}:d=1"
        if FONT_PATH:
            filters = (
                f"drawtext=fontfile={FONT_PATH}:textfile='{num_file}'"
                f":fontsize=110:fontcolor=#C8A96B:x=(w-text_w)/2:y={y_num},"
                f"drawtext=fontfile={FONT_PATH}:textfile='{words_file}'"
                f":fontsize=48:fontcolor=white:x=(w-text_w)/2:y={y_words},"
                f"drawtext=fontfile={FONT_PATH}:textfile='{foot_file}'"
                f":fontsize=32:fontcolor=#aaaaaa:x=(w-text_w)/2:y={y_foot}"
            )
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                colour,
                "-vf",
                filters,
                "-frames:v",
                "1",
                str(disk),
            ]
        else:
            # No font on this PC: a plain dark card is still a valid
            # placeholder (the UI badge says what it is).
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                colour,
                "-frames:v",
                "1",
                str(disk),
            ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            lines = (proc.stderr or "").strip().splitlines()
            raise RuntimeError(lines[-1] if lines else "ffmpeg placeholder failed")
    finally:
        for p in (num_file, words_file, foot_file):
            try:
                p.unlink()
            except OSError:
                pass
    return f"projects/{project_id}/placeholders/{name}"


async def run_pipeline(run_id: int) -> None:
    """Background one-click run: script -> voice -> images -> timeline
    -> captions -> render. Each step is a jobs row; a failed step stops
    the run and is never marked done. Nothing is invented: a missing
    voice is a failed voice step; images cycle across the sentence
    scenes, and a placeholder title card appears only when the
    project has no images at all."""

    with db() as conn:
        run = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if run is None:
            return
        steps = conn.execute(
            "SELECT * FROM jobs WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    step_id = {s["kind"]: s["id"] for s in steps}
    project_id = run["project_id"]
    # Slice 3 (Magic Mode): the run may carry an aspect + an
    # explicit Style DNA preset. Old runs (created before the
    # migration) have neither — 16:9 + last-used style, as before.
    run_aspect = "16:9"
    run_style_id = None
    try:
        if "aspect" in run.keys() and run["aspect"]:
            run_aspect = magic_validate_aspect(run["aspect"])
        if "style_dna_id" in run.keys():
            run_style_id = run["style_dna_id"]
    except ValueError:
        run_aspect = "16:9"

    def fail_run(message: str, failed_kind: str | None = None) -> None:
        with db() as conn:
            if failed_kind and failed_kind in step_id:
                _set_job(conn, step_id[failed_kind], "failed", error=message[:500])
            _set_run(conn, run_id, "failed", error=message[:500])

    def step_status(kind: str, status: str) -> None:
        with db() as conn:
            _set_job(conn, step_id[kind], status)

    if set(step_id) != set(RUN_STEP_KINDS):
        fail_run("Run steps missing — run dobara shuru karein", None)
        return
    with db() as conn:
        _set_run(conn, run_id, "running")

    # Preflight: a run with no voice source at all fails on the voice
    # step before anything is marked done.
    voice_text = (run["voice_text"] or "").strip()
    if run["vo_asset_id"] is None and not voice_text:
        fail_run(
            "Voiceover upload karein ya voice text dein — ek to chahiye",
            "run_voice",
        )
        return

    # Step 1 — Script: load the script's scenes.
    try:
        step_status("run_script", "running")
        with db() as conn:
            scene_rows = conn.execute(
                "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
                (run["script_id"],),
            ).fetchall()
            scenes = [dict(s) for s in scene_rows]
        if not scenes:
            fail_run(
                "Script me koi scene nahi hai — script dobara save karein",
                "run_script",
            )
            return
        step_status("run_script", "done")
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Script step failed: {exc}", "run_script")
        return

    # Step 2 — Voice: uploaded VO, or free Edge-TTS from the text.
    vo_asset_id = run["vo_asset_id"]
    vo_duration = 0.0
    try:
        step_status("run_voice", "running")
        if vo_asset_id is not None:
            with db() as conn:
                vo = conn.execute(
                    "SELECT * FROM assets WHERE id = ? AND project_id = ?",
                    (vo_asset_id, project_id),
                ).fetchone()
            if vo is None or vo["kind"] != "voice":
                fail_run(
                    "Voiceover asset nahi mila — dobara upload karein",
                    "run_voice",
                )
                return
            vo_path = DATA_DIR / vo["path"]
            if not vo_path.exists():
                fail_run(
                    "Voiceover file nahi mili — dobara upload karein",
                    "run_voice",
                )
                return
            vo_duration = probe_duration(vo_path)
            if vo_duration <= 0:
                fail_run(
                    "Voiceover file ki duration nahi mili — file dobara"
                    " upload karein",
                    "run_voice",
                )
                return
        else:
            try:
                rel, disk = await _tts_save(project_id, voice_text, run["voice"])
            except RuntimeError as exc:
                fail_run(str(exc), "run_voice")
                return
            vo_duration = probe_duration(disk)
            if vo_duration <= 0:
                fail_run(
                    "Edge-TTS ne khaali audio banayi — voiceover upload karein",
                    "run_voice",
                )
                return
            with db() as conn:
                cur = conn.execute(
                    "INSERT INTO assets (project_id, kind, path, created_at)"
                    " VALUES (?, 'voice', ?, ?)",
                    (project_id, rel, utcnow()),
                )
                vo_asset_id = cur.lastrowid
            with db() as conn:
                _set_run(conn, run_id, "running", vo_asset_id=vo_asset_id)
        step_status("run_voice", "done")
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Voice step failed: {exc}", "run_voice")
        return

    # Step 3 — Images: uploaded images cycle across the sentence
    # scenes (image i mod n), each occurrence with a different
    # effect, so the same picture never looks the same twice in a
    # row. A placeholder title card appears ONLY when the project
    # has zero images at all — never just because images are fewer
    # than sentences.
    clip_assets: list[dict] = []
    try:
        step_status("run_images", "running")
        with db() as conn:
            real_rows = conn.execute(
                "SELECT * FROM assets WHERE project_id = ? AND kind = 'image'"
                " AND COALESCE(placeholder, 0) = 0 ORDER BY id",
                (project_id,),
            ).fetchall()
            real_images = [dict(a) for a in real_rows]
        for i, scene in enumerate(scenes):
            if real_images:
                clip_assets.append(
                    {
                        "asset_id": real_images[i % len(real_images)]["id"],
                        "placeholder": 0,
                    }
                )
            else:
                # Slice 3: placeholders follow the run's aspect
                # (a 9:16 run gets tall title cards, not cropped ones).
                _, _, ph_w, ph_h, _, _ = magic_aspect_dims(
                    run_aspect, "1080p"
                )
                rel = make_placeholder_image(
                    project_id, run_id, i, scene["text"], ph_w, ph_h
                )
                with db() as conn:
                    cur = conn.execute(
                        "INSERT INTO assets (project_id, kind, path,"
                        " placeholder, created_at) VALUES (?, 'image', ?, 1, ?)",
                        (project_id, rel, utcnow()),
                    )
                    ph_id = cur.lastrowid
                clip_assets.append({"asset_id": ph_id, "placeholder": 1})
        step_status("run_images", "done")
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Images step failed: {exc}", "run_images")
        return

    # Step 4 — Timeline: scenes become clips, durations follow the
    # script beats (word counts x VO duration), captions are scene text.
    # The project's Style DNA / caption style carry over unless the run
    # overrode the caption style.
    timeline_id: int | None = None
    try:
        step_status("run_timeline", "running")
        with db() as conn:
            prev = conn.execute(
                "SELECT style_dna_id, caption_style_id FROM timelines"
                " WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            # Slice 3 (Magic Mode): an explicit Style DNA preset on
            # the run wins over the last timeline's style.
            style_id = run_style_id or (
                prev["style_dna_id"] if prev else None
            )
            caption_id = run["caption_style_id"] or (
                prev["caption_style_id"] if prev else None
            )
            durations = beat_durations(
                [len(s["text"].split()) for s in scenes], vo_duration
            )
            old_all = conn.execute(
                "SELECT id FROM timelines WHERE project_id = ?", (project_id,)
            ).fetchall()
            # Runs keep a timeline_id FK to their timeline: clear it for
            # the timelines about to be replaced, or the DELETE below
            # fails the foreign key (the run keeps its MP4/SRT paths,
            # only the link to the replaced timeline goes).
            conn.execute(
                "UPDATE runs SET timeline_id = NULL WHERE timeline_id IN"
                " (SELECT id FROM timelines WHERE project_id = ?)",
                (project_id,),
            )
            for row in old_all:
                conn.execute(
                    "DELETE FROM clips WHERE timeline_id = ?", (row["id"],)
                )
                conn.execute("DELETE FROM timelines WHERE id = ?", (row["id"],))
            now = utcnow()
            cur = conn.execute(
                "INSERT INTO timelines (project_id, style_dna_id,"
                " caption_style_id, vo_duration_s, vo_asset_id, created_at,"
                " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    style_id,
                    caption_id,
                    round(sum(durations), 3),
                    vo_asset_id,
                    now,
                    now,
                ),
            )
            timeline_id = cur.lastrowid
            start = 0.0
            for i, scene in enumerate(scenes):
                end = round(start + durations[i], 3)
                conn.execute(
                    "INSERT INTO clips (timeline_id, asset_id, position,"
                    " start_s, end_s, caption_text, effect)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        timeline_id,
                        clip_assets[i]["asset_id"],
                        i,
                        round(start, 3),
                        end,
                        scene["text"],
                        effect_for_position(i),
                    ),
                )
                start = end
            _set_run(conn, run_id, "running", timeline_id=timeline_id)
        step_status("run_timeline", "done")
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Timeline step failed: {exc}", "run_timeline")
        return

    # Step 5 — Captions: the SRT file for this run (burned-in captions
    # are drawn by the render from the same clip texts).
    try:
        step_status("run_captions", "running")
        with db() as conn:
            detail = timeline_detail(conn, timeline_id)
        srt = build_srt(detail["clips"])
        if not srt.strip():
            fail_run(
                "Captions khaali hain — scene texts check karein",
                "run_captions",
            )
            return
        srt_rel = f"output/{_today_str()}/run_{run_id}.srt"
        (output_dir_for_today() / f"run_{run_id}.srt").write_text(srt, encoding="utf-8")
        with db() as conn:
            _set_run(conn, run_id, "running", srt_path=srt_rel)
        step_status("run_captions", "done")
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Captions step failed: {exc}", "run_captions")
        return

    # Step 6 — Render: the render step job IS the render job, so the
    # Jobs list and the run show the same MP4 and the same error.
    try:
        step_status("render", "running")
        # Slice 3: the render job carries the run's aspect in its
        # options so run_render frames the video for it (16:9 jobs
        # get the same dims as before — no behaviour change).
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET options_json = ? WHERE id = ?",
                (
                    json.dumps({"aspect": run_aspect}),
                    step_id["render"],
                ),
            )
        run_render(step_id["render"], timeline_id)
        with db() as conn:
            job = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (step_id["render"],)
            ).fetchone()
        if job is None or job["status"] != "done":
            err = (job["error"] if job else None) or "render failed"
            # The render step already carries its own error (run_render
            # wrote it); only the run still needs marking failed.
            fail_run(f"Render failed: {err}", None)
            return
        with db() as conn:
            _set_run(conn, run_id, "done", output_path=job["output_path"])
    except Exception as exc:  # noqa: BLE001 - any failure stops the run
        fail_run(f"Render step failed: {exc}", "render")
        return


@app.post("/api/projects/{project_id}/run", status_code=202)
def start_run(
    project_id: int, body: RunIn, background_tasks: BackgroundTasks
) -> dict:
    """Start a one-click Documentary Director run: script -> voice ->
    images -> timeline -> captions -> render, each step a jobs row.
    Validation failures (bad script / voiceover asset / caption style)
    are plain 400/404s before anything is queued; a missing voice
    source is NOT validated here — it fails honestly on the voice step
    so the run shows a clear failed job instead of a silent nothing."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ? AND project_id = ?",
            (body.script_id, project_id),
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        scenes = conn.execute(
            "SELECT id FROM scenes WHERE script_id = ?", (body.script_id,)
        ).fetchall()
        if not scenes:
            raise HTTPException(
                status_code=400, detail="script me koi scene nahi hai"
            )
        if body.voiceover_asset_id is not None:
            vo = conn.execute(
                "SELECT * FROM assets WHERE id = ? AND project_id = ?",
                (body.voiceover_asset_id, project_id),
            ).fetchone()
            if vo is None or vo["kind"] != "voice":
                raise HTTPException(
                    status_code=400, detail="voiceover asset not found"
                )
        if body.caption_style_id is not None:
            cs = conn.execute(
                "SELECT id FROM caption_styles WHERE id = ?",
                (body.caption_style_id,),
            ).fetchone()
            if cs is None:
                raise HTTPException(
                    status_code=404, detail="caption style not found"
                )
        # Slice 3 (Magic Mode): aspect + Style DNA preset ride on
        # the run. Bad values are plain 400/404s, never silent
        # fallbacks; empty means 16:9 + last-used style, as before.
        try:
            run_aspect = magic_validate_aspect(body.aspect)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        run_style_id = None
        if body.style_dna_id is not None:
            srow = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.style_dna_id,),
            ).fetchone()
            if srow is None:
                raise HTTPException(
                    status_code=404, detail="style preset not found"
                )
            run_style_id = body.style_dna_id
        now = utcnow()
        # No voice given = the saved default voice (VoiceForge favourite).
        run_voice = body.voice.strip() or _default_tts_voice()
        cur = conn.execute(
            "INSERT INTO runs (project_id, script_id, vo_asset_id,"
            " caption_style_id, voice_text, voice, style_dna_id, aspect,"
            " status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)",
            (
                project_id,
                body.script_id,
                body.voiceover_asset_id,
                body.caption_style_id,
                (body.voice_text or "").strip(),
                run_voice,
                run_style_id,
                run_aspect,
                now,
                now,
            ),
        )
        run_id = cur.lastrowid
        for kind in RUN_STEP_KINDS:
            conn.execute(
                "INSERT INTO jobs (project_id, kind, status, run_id,"
                " created_at, updated_at) VALUES (?, ?, 'queued', ?, ?, ?)",
                (project_id, kind, run_id, now, now),
            )
        detail = run_detail(conn, run_id)
    background_tasks.add_task(run_pipeline, run_id)
    return detail


@app.get("/api/runs/{run_id}")
def get_run(run_id: int) -> dict:
    with db() as conn:
        return run_detail(conn, run_id)


@app.get("/api/projects/{project_id}/runs")
def list_runs(project_id: int) -> list:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            "SELECT * FROM runs WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Slice 3: Magic Mode (One-Click Autopilot v2) -------------------------
# Ali's spec: topic + script in, voice character picked, everything
# else automatic - beats + timecode prompts, bulk images, voiceover,
# auto-sync, captions, render, MP4 + thumbnail, one progress bar.
# Magic is an ORCHESTRATOR, not a parallel pipeline: script + images
# + voice run here, then the existing one-click run_pipeline does
# timeline / captions / render, and its steps are mirrored into the
# Magic stages. Nothing is invented: a blocked image login is
# 'blocked', a failed voice fails the run, placeholders are counted.


class MagicIn(BaseModel):
    """Magic Mode input: the ONLY six things the user picks. Every
    field has a smart default, so an empty body still runs. Topic is
    required (a video needs a topic); empty script_text means
    "research it and write it yourself" (Slice 2 Deep Research).
    voice_kind 'upload' needs vo_asset_id; 'edge' needs a library
    voice; 'heygen' uses the saved clone voice. caption_style_id
    empty = Bold White; style_dna_id empty = last used preset;
    aspect empty = 16:9; language empty = English."""

    topic: str = Field(default="", max_length=300)
    script_text: str = Field(default="", max_length=50000)
    voice_kind: str = Field(default="upload", max_length=20)
    voice_id: str = Field(default="", max_length=100)
    vo_asset_id: int | None = None
    caption_style_id: int | None = None
    style_dna_id: int | None = None
    aspect: str = Field(default="16:9", max_length=10)
    language: str = Field(default="en", max_length=10)
    # Slice 4 (Character Vault): niche_id pins the run to that
    # niche's locked cast — the guard blocks the run at start
    # when the niche's mains are not locked yet. scene_characters
    # is an optional per-scene override {scene_id: character
    # name}; default is fully automatic (mains rotate).
    niche_id: int | None = None
    scene_characters: dict | None = None


def _magic_stages_default() -> dict:
    return {
        stage: {"status": "queued", "detail": ""}
        for stage in MAGIC_STAGES
    }


def _magic_detail(conn, magic_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM magic_runs WHERE id = ?", (magic_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="magic run not found")
    detail = dict(row)
    try:
        detail["stages"] = json.loads(row["stages_json"] or "{}")
    except (ValueError, TypeError):
        detail["stages"] = _magic_stages_default()
    try:
        detail["summary"] = json.loads(row["summary_json"] or "{}")
    except (ValueError, TypeError):
        detail["summary"] = {}
    try:
        detail["scene_characters"] = json.loads(
            row["scene_characters_json"] or "{}"
        )
    except (ValueError, TypeError):
        detail["scene_characters"] = {}
    return detail


def _set_magic_stage(
    conn, magic_id: int, stage: str, status: str, detail: str = ""
) -> None:
    row = conn.execute(
        "SELECT stages_json FROM magic_runs WHERE id = ?", (magic_id,)
    ).fetchone()
    try:
        stages = json.loads(row["stages_json"] or "{}") if row else {}
    except (ValueError, TypeError):
        stages = {}
    if not stages:
        stages = _magic_stages_default()
    stages[stage] = {"status": status, "detail": (detail or "")[:500]}
    conn.execute(
        "UPDATE magic_runs SET stages_json = ?, updated_at = ?"
        " WHERE id = ?",
        (json.dumps(stages), utcnow(), magic_id),
    )


def _set_magic(
    conn, magic_id: int, status: str, error: str | None = None, **fields
) -> None:
    allowed = {"script_id", "run_id", "vo_asset_id", "summary_json"}
    sets = ["status = ?", "updated_at = ?"]
    values: list = [status, utcnow()]
    if error is not None:
        sets.append("error = ?")
        values.append(error[:500])
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(value)
    values.append(magic_id)
    conn.execute(
        f"UPDATE magic_runs SET {', '.join(sets)} WHERE id = ?", values
    )


async def _magic_voice_edge(
    project_id: int, text: str, voice_id: str
) -> tuple[int, float, int]:
    """Edge-TTS voiceover in <=4500-char chunks, joined into one VO
    asset. Returns (asset_id, duration_s, chunk_count). A chunk
    failure raises RuntimeError with the plain Edge-TTS wording."""
    chunks = _split_tts_chunks(text, 4500)
    if not chunks:
        raise RuntimeError("voiceover ke liye script text khaali hai")
    parts: list[Path] = []
    try:
        for chunk in chunks:
            _rel, disk = await _tts_save(project_id, chunk, voice_id)
            parts.append(disk)
        rel, disk = _concat_audio_parts(project_id, parts, "edge")
    finally:
        for part in parts:
            try:
                part.unlink()
            except OSError:
                pass
    duration = probe_duration(disk)
    if duration <= 0:
        raise RuntimeError(
            "Edge-TTS ne khaali audio banayi - voiceover upload karein"
        )
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'voice', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
    return asset_id, round(duration, 3), len(chunks)


async def _magic_voice_heygen(
    project_id: int, text: str, voice_id: str, hey_language: str
) -> tuple[int, float, int]:
    """HeyGen clone voiceover in <=5000-char chunks (the per-call
    limit), joined into one VO asset. Returns (asset_id, duration_s,
    chunk_count). No key -> the job fails with the plain key
    message; a dead quota fails with the provider error. Nothing is
    ever faked: a failed chunk fails the whole voice stage."""
    chunks = _split_tts_chunks(text, 5000)
    if not chunks:
        raise RuntimeError("voiceover ke liye script text khaali hai")
    parts: list[Path] = []
    now = utcnow()
    for chunk in chunks:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO jobs (project_id, kind, status, created_at,"
                " updated_at) VALUES (?, 'heygen-voice', 'queued', ?, ?)",
                (project_id, now, now),
            )
            job_id = cur.lastrowid
        await _run_heygen_speak(
            job_id, project_id, chunk, hey_language, voice_id
        )
        with db() as conn:
            job = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if job is None or job["status"] != "done":
            err = (job["error"] if job else None) or "HeyGen voice failed"
            raise RuntimeError(err)
        parts.append(media_path(job["output_path"]))
    rel, disk = _concat_audio_parts(project_id, parts, "heygen")
    duration = probe_duration(disk)
    if duration <= 0:
        raise RuntimeError(
            "HeyGen ne khaali audio banayi - voiceover upload karein"
        )
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'voice', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
    return asset_id, round(duration, 3), len(chunks)


async def process_magic_run(magic_id: int) -> None:
    """Background Magic run: script -> images -> voice -> (one-click
    run: timeline -> captions -> render) -> thumbnail -> summary.
    Voice is a hard dependency (fails the run honestly). Images are
    not: a blocked or failed image becomes a placeholder card in the
    timeline and the summary says exactly how many. The run never
    ends 'done' with a silent failure."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM magic_runs WHERE id = ?", (magic_id,)
        ).fetchone()
        if row is None:
            return
        magic = dict(row)
    project_id = magic["project_id"]
    aspect = magic["aspect"] or "16:9"
    language = magic["language"] or "en"
    summary: dict = {
        "words": 0,
        "est_duration_s": 0.0,
        "scenes": 0,
        "images_generated": 0,
        "images_skipped_done": 0,
        "images_failed": 0,
        "images_retried": 0,
        "images_retry_fixed": 0,
        "images_fallback_used": 0,
        "images_precheck_reworded": 0,
        "images_retry_log": [],
        "images_blocked": 0,
        "images_fallback_flow": 0,
        "images_qc_checked": 0,
        "images_qc_regenerated": 0,
        "vault_niche": None,
        "uploaded_images": 0,
        "placeholders_used": 0,
        "voice_chars": 0,
        "voice_chunks": 0,
        "voice_kind": magic["voice_kind"],
        "duration_s": 0.0,
        "output_path": None,
        "thumbnail_path": None,
        "warnings": [],
    }

    def fail(message: str, stage: str | None = None) -> None:
        with db() as conn:
            if stage:
                _set_magic_stage(conn, magic_id, stage, "failed", message)
            _set_magic(
                conn,
                magic_id,
                "failed",
                error=message,
                summary_json=json.dumps(summary),
            )

    # ---- Stage 1: script (pasted, or Deep Research -> script) --------
    script_id = magic["script_id"]
    try:
        with db() as conn:
            _set_magic(
                conn, magic_id, "running", summary_json=json.dumps(summary)
            )
            _set_magic_stage(conn, magic_id, "script", "running")
        script_text = (magic["script_text"] or "").strip()
        topic = (magic["topic"] or "").strip()
        style_obj = None
        if magic["style_dna_id"]:
            with db() as conn:
                srow = conn.execute(
                    "SELECT * FROM style_dna WHERE id = ?",
                    (magic["style_dna_id"],),
                ).fetchone()
                style_obj = dict(srow) if srow else None
        if script_text:
            full_text = script_text
            with db() as conn:
                detail = _insert_script(
                    conn,
                    project_id,
                    topic,
                    script_text,
                    "pasted",
                    style=style_obj,
                    aspect=aspect,
                )
            script_id = detail["id"]
        else:
            # Empty script: Slice 2 Deep Research, then a script
            # from the facts - the same route as the StoryCraft UI.
            with db() as conn:
                keys = _gemini_keys(conn)
            if not keys:
                raise RuntimeError(
                    "script text likhein ya Gemini key Settings me"
                    " lagayen - bina key ke research nahi ho sakti"
                )
            try:
                (res_text, facts), _a = _gemini_try_keys(
                    keys,
                    lambda k: gemini_deep_research(
                        k, topic, language=language
                    ),
                )
            except RuntimeError as exc:
                raise RuntimeError(str(exc))
            if facts:
                content = "\n\n".join(
                    "Fact: " + f["fact"] + "\nSource: "
                    + (f.get("source") or "-")
                    for f in facts
                )
            else:
                content = res_text
            with db() as conn:
                now = utcnow()
                conn.execute(
                    "INSERT INTO research_notes (project_id, title,"
                    " content, kind, facts_json, created_at, updated_at)"
                    " VALUES (?, ?, ?, 'deep-research', ?, ?, ?)",
                    (
                        project_id,
                        topic,
                        content,
                        json.dumps(facts),
                        now,
                        now,
                    ),
                )
            if facts:
                facts_text = "\n".join(
                    "- " + f.get("fact", "") + " (Source: "
                    + (f.get("source") or "-") + ")"
                    for f in facts
                    if f.get("fact")
                )
                prompt_topic = (
                    topic
                    + "\n\nResearched key facts (use only these facts"
                    " in the script):\n" + facts_text
                )
            else:
                prompt_topic = topic + "\n\nResearch notes:\n" + content
            try:
                full_text, _a = _gemini_try_keys(
                    keys,
                    lambda k: gemini_generate_script(
                        k,
                        prompt_topic,
                        thinking_level="medium",
                        model="fast",
                        language=language,
                    ),
                )
            except RuntimeError as exc:
                raise RuntimeError(str(exc))
            with db() as conn:
                detail = _insert_script(
                    conn,
                    project_id,
                    topic,
                    full_text,
                    "gemini",
                    style=style_obj,
                    aspect=aspect,
                )
            script_id = detail["id"]
        words = len(full_text.split())
        summary["words"] = words
        summary["est_duration_s"] = estimate_video_duration_s(words)
        with db() as conn:
            scenes = conn.execute(
                "SELECT * FROM scenes WHERE script_id = ?"
                " ORDER BY position, id",
                (script_id,),
            ).fetchall()
            summary["scenes"] = len(scenes)
            _set_magic(
                conn,
                magic_id,
                "running",
                script_id=script_id,
                summary_json=json.dumps(summary),
            )
            _set_magic_stage(
                conn,
                magic_id,
                "script",
                "done",
                f"{len(scenes)} scenes - {words} lafz -"
                f" ~{summary['est_duration_s'] / 60:.1f} min",
            )
    except HTTPException as exc:
        fail(str(exc.detail), "script")
        return
    except Exception as exc:  # noqa: BLE001 - plain Roman Urdu error
        fail(f"Script step failed: {exc}", "script")
        return

    # ---- Stage 2: bulk images (Canvas default, Retry Ladder) ----------
    try:
        with db() as conn:
            _set_magic_stage(conn, magic_id, "images", "running")
            script_row = conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (script_id,)
            ).fetchone()
            script = dict(script_row)
            scenes = [
                dict(s)
                for s in conn.execute(
                    "SELECT * FROM scenes WHERE script_id = ?"
                    " ORDER BY position, id",
                    (script_id,),
                ).fetchall()
            ]
            uploaded = conn.execute(
                "SELECT COUNT(*) AS n FROM assets WHERE project_id = ?"
                " AND kind = 'image' AND COALESCE(placeholder, 0) = 0",
                (project_id,),
            ).fetchone()["n"]
            summary["uploaded_images"] = uploaded
        now = utcnow()
        wait_scenes: list[dict] = []
        queued: list[int] = []
        img_options: dict = {
            "character_match": True,
            "style_match": True,
        }
        # Slice 4 (Character Vault): the run's niche pins its
        # locked cast — guard again here (a sheet could have been
        # unlocked between start and this stage), apply the cast
        # to the scene prompts, and pin it into every job's
        # options, so the worker + auto-QC use exactly this cast.
        niche_id = magic.get("niche_id")
        with db() as conn:
            main_char = _vault_main(conn)
            if niche_id is not None:
                resolved = _vault_guard(conn, niche_id)
                vault_pin = _vault_pin(resolved, main_char)
                img_options["vault"] = vault_pin
                summary["vault_niche"] = resolved["niche_name"]
                if vault_pin.get("main_character"):
                    summary["main_character"] = vault_pin["main_character"]["name"]
                try:
                    scene_overrides = json.loads(
                        magic.get("scene_characters_json") or "{}"
                    )
                except (ValueError, TypeError):
                    scene_overrides = {}
                _vault_apply_to_scenes(
                    conn, script_id, vault_pin, style_obj, aspect,
                    scene_overrides,
                )
            elif main_char is not None:
                # No niche chosen, but the user HAS a locked main
                # character — the main IS the cast for this run.
                niche_row = conn.execute(
                    "SELECT name FROM niches WHERE id = ?",
                    (main_char["niche_id"],),
                ).fetchone()
                vault_pin = _vault_pin_for_main(
                    main_char, niche_row["name"] if niche_row else ""
                )
                img_options["vault"] = vault_pin
                summary["vault_niche"] = vault_pin["niche_name"]
                summary["main_character"] = main_char["name"]
                _vault_apply_to_scenes(
                    conn, script_id, vault_pin, style_obj, aspect, {},
                )
        with db() as conn:
            for scene in scenes:
                st = scene_generation_status(conn, scene["id"])["status"]
                if st == "done":
                    summary["images_skipped_done"] += 1
                    continue
                wait_scenes.append(scene)
                _outcome, job_id = _queue_one_image_job(
                    conn,
                    script,
                    scene,
                    now,
                    provider="canvas",
                    options=img_options,
                )
                if job_id is not None:
                    queued.append(job_id)
        if queued:
            img_summary = await process_image_jobs(script_id)
            summary["images_qc_checked"] += img_summary["qc_checked"]
            summary["images_qc_regenerated"] += (
                img_summary["qc_regenerated"]
            )
            # Slice 3 PATCH (Retry Ladder): the worker already ran
            # reword -> simplify -> fallback INSIDE the batch — the
            # old second Flow-only retry is gone (it re-ran the
            # same prompt and never reworded). Ladder counts + log
            # ride the summary so the UI can show them.
            summary["images_retried"] += img_summary.get("retried", 0)
            summary["images_retry_fixed"] += img_summary.get("retry_fixed", 0)
            summary["images_fallback_used"] += img_summary.get(
                "fallback_used", 0
            )
            summary["images_precheck_reworded"] += img_summary.get(
                "precheck_reworded", 0
            )
            summary["images_retry_log"].extend(
                img_summary.get("retry_log", [])
            )

        def read_outcomes(
            scenes_now: list[dict],
        ) -> tuple[list[dict], list[dict]]:
            """Returns (generated, failed) for the given scenes."""
            gen: list[dict] = []
            fail_list: list[dict] = []
            with db() as conn:
                for scene in scenes_now:
                    st = scene_generation_status(conn, scene["id"])
                    if st["status"] == "done":
                        gen.append(scene)
                        prow = None
                        if st.get("job_id") is not None:
                            prow = conn.execute(
                                "SELECT provider FROM jobs WHERE id = ?",
                                (st["job_id"],),
                            ).fetchone()
                        if prow and (prow["provider"] or "api") == "flow":
                            summary["images_fallback_flow"] += 1
                    elif st["status"] == "blocked":
                        summary["images_blocked"] += 1
                    else:
                        fail_list.append(scene)
            return gen, fail_list

        generated, failed_scenes = read_outcomes(wait_scenes)
        summary["images_generated"] += len(generated)
        # No second Flow-only retry any more: the worker's Retry
        # Ladder (reword -> simplify -> fallback) already ran
        # inside process_image_jobs for every failed scene, and
        # read_outcomes above already counts what it fixed.
        summary["images_failed"] += len(failed_scenes)
        usable = (
            summary["images_generated"]
            + summary["images_skipped_done"]
            + summary["uploaded_images"]
        )
        detail = (
            f"{summary['images_generated']} bani -"
            f" {summary['images_skipped_done']} pehle se -"
            f" {summary['images_blocked']} blocked -"
            f" {summary['images_failed']} fail"
        )
        if summary["images_retried"]:
            detail += f" - {summary['images_retried']} retry"
        if summary["images_retry_fixed"]:
            detail += (
                f" - retry se {summary['images_retry_fixed']} bani"
            )
        if summary["images_fallback_used"]:
            detail += (
                f" - {summary['images_fallback_used']} fallback"
            )
        if summary["images_qc_checked"]:
            detail += (
                f" - QC: {summary['images_qc_checked']} check,"
                f" {summary['images_qc_regenerated']} dobara bani"
            )
        if usable == 0 and summary["images_blocked"] > 0:
            stage_status = "blocked"
            detail += " - Google login nahi hai, placeholder cards"
            detail += " se video banegi"
        elif summary["images_failed"] > 0 and usable == 0:
            stage_status = "blocked"
            detail += " - koi image nahi bani, placeholder cards"
            detail += " se video banegi"
        else:
            stage_status = "done"
        # A blocked image is always worth a warning, even when
        # uploaded images saved the video - the user should know
        # the Canvas/Flow route did not run.
        if summary["images_blocked"] > 0:
            if usable == 0:
                summary["warnings"].append(
                    "Images: Google login nahi hai - Connect Google se"
                    " sign-in karein, warna video placeholder cards se"
                    " banegi."
                )
            else:
                summary["warnings"].append(
                    f"Images: {summary['images_blocked']} blocked"
                    " (Google login nahi hai) - upload ki hui"
                    " tasveerein use hui hain."
                )
        elif summary["images_failed"] > 0 and usable == 0:
            summary["warnings"].append(
                "Images: koi image nahi bani - video placeholder"
                " cards se banegi."
            )
        with db() as conn:
            _set_magic_stage(conn, magic_id, "images", stage_status, detail)
            _set_magic(
                conn, magic_id, "running", summary_json=json.dumps(summary)
            )
    except Exception as exc:  # noqa: BLE001 - images never fail a run
        summary["warnings"].append(f"Images step me masla: {exc}")
        with db() as conn:
            _set_magic_stage(
                conn, magic_id, "images", "blocked", str(exc)[:200]
            )
            _set_magic(
                conn, magic_id, "running", summary_json=json.dumps(summary)
            )

    # ---- Stage 3: voiceover (hard dependency) --------------------------
    vo_asset_id = magic["vo_asset_id"]
    try:
        with db() as conn:
            _set_magic_stage(conn, magic_id, "voice", "running")
            script_row = conn.execute(
                "SELECT full_text FROM scripts WHERE id = ?",
                (script_id,),
            ).fetchone()
        full_text = script_row["full_text"]
        summary["voice_chars"] = len(full_text)
        voice_kind = magic["voice_kind"]
        chunks = 0
        if voice_kind == "upload":
            if vo_asset_id is None:
                raise RuntimeError(
                    "voiceover asset nahi mila - upload karein ya"
                    " Edge-TTS chunein"
                )
            with db() as conn:
                vo = conn.execute(
                    "SELECT * FROM assets WHERE id = ? AND project_id = ?",
                    (vo_asset_id, project_id),
                ).fetchone()
            if vo is None or vo["kind"] != "voice":
                raise RuntimeError(
                    "Voiceover asset nahi mila - dobara upload karein"
                )
            vo_path = DATA_DIR / vo["path"]
            if not vo_path.exists():
                raise RuntimeError(
                    "Voiceover file nahi mili - dobara upload karein"
                )
            vo_duration = probe_duration(vo_path)
            if vo_duration <= 0:
                raise RuntimeError(
                    "Voiceover file ki duration nahi mili - file"
                    " dobara upload karein"
                )
            voice_detail = f"{vo_duration:.1f} s - uploaded"
        elif voice_kind == "edge":
            voice_id = magic["voice_id"] or _default_tts_voice()
            vo_asset_id, vo_duration, chunks = await _magic_voice_edge(
                project_id, full_text, voice_id
            )
            summary["voice_chunks"] = chunks
            voice_detail = f"{vo_duration:.1f} s - {chunks} chunk"
        elif voice_kind == "heygen":
            with db() as conn:
                hey_voice = magic["voice_id"] or _heygen_voice_id(conn)
            hey_language = "hi" if language == "ur" else "en"
            vo_asset_id, vo_duration, chunks = await _magic_voice_heygen(
                project_id, full_text, hey_voice, hey_language
            )
            summary["voice_chunks"] = chunks
            voice_detail = f"{vo_duration:.1f} s - {chunks} chunk"
        else:
            raise RuntimeError("voice kind samajh nahi aaya")
        with db() as conn:
            _set_magic(
                conn,
                magic_id,
                "running",
                vo_asset_id=vo_asset_id,
                summary_json=json.dumps(summary),
            )
            _set_magic_stage(conn, magic_id, "voice", "done", voice_detail)
    except RuntimeError as exc:
        fail(str(exc), "voice")
        return
    except Exception as exc:  # noqa: BLE001 - plain Roman Urdu error
        fail(f"Voice step failed: {exc}", "voice")
        return

    # ---- Stages 4-6: the existing one-click pipeline ------------------
    run_id = None
    try:
        with db() as conn:
            now = utcnow()
            run_voice = (
                magic["voice_id"]
                if magic["voice_kind"] == "edge"
                else _default_tts_voice()
            )
            cur = conn.execute(
                "INSERT INTO runs (project_id, script_id, vo_asset_id,"
                " caption_style_id, voice_text, voice, style_dna_id,"
                " aspect, status, created_at, updated_at) VALUES"
                " (?, ?, ?, ?, '', ?, ?, ?, 'queued', ?, ?)",
                (
                    project_id,
                    script_id,
                    vo_asset_id,
                    magic["caption_style_id"],
                    run_voice,
                    magic["style_dna_id"],
                    aspect,
                    now,
                    now,
                ),
            )
            run_id = cur.lastrowid
            for kind in RUN_STEP_KINDS:
                conn.execute(
                    "INSERT INTO jobs (project_id, kind, status, run_id,"
                    " created_at, updated_at) VALUES (?, ?, 'queued',"
                    " ?, ?, ?)",
                    (project_id, kind, run_id, now, now),
                )
            _set_magic(
                conn,
                magic_id,
                "running",
                run_id=run_id,
                summary_json=json.dumps(summary),
            )
            _set_magic_stage(conn, magic_id, "timeline", "running")
        await run_pipeline(run_id)
        with db() as conn:
            run = conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            steps = {
                s["kind"]: dict(s)
                for s in conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ? ORDER BY id",
                    (run_id,),
                ).fetchall()
            }
        run_error = (run["error"] if run else None) or ""
        with db() as conn:
            for stage, kind in (
                ("timeline", "run_timeline"),
                ("captions", "run_captions"),
                ("render", "render"),
            ):
                step = steps.get(kind, {})
                status = step.get("status", "failed")
                detail = step.get("error") or ""
                if status == "queued" and run_error:
                    # The run stopped before this step: say so,
                    # instead of leaving it 'queued' forever.
                    status = "failed"
                    detail = "run is step se pehle ruk gaya"
                _set_magic_stage(conn, magic_id, stage, status, detail)
        if run is None or run["status"] != "done":
            err = run_error or "one-click run failed"
            fail(f"Render pipeline failed: {err}")
            return
        summary["output_path"] = run["output_path"]
        with db() as conn:
            tl_row = conn.execute(
                "SELECT id FROM timelines WHERE project_id = ?"
                " ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if tl_row:
                ph = conn.execute(
                    "SELECT COUNT(*) AS n FROM clips c JOIN assets a"
                    " ON a.id = c.asset_id WHERE c.timeline_id = ?"
                    " AND COALESCE(a.placeholder, 0) = 1",
                    (tl_row["id"],),
                ).fetchone()["n"]
                summary["placeholders_used"] = ph
        out_disk = media_path(run["output_path"])
        if out_disk is not None and out_disk.exists():
            summary["duration_s"] = round(probe_duration(out_disk), 3)
    except Exception as exc:  # noqa: BLE001 - plain Roman Urdu error
        fail(f"Pipeline step failed: {exc}")
        return

    # ---- Thumbnail (aspect size) - a failure is a warning, not a
    # failed run: the video is already done.
    try:
        tw, th = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1": (720, 720),
        }[aspect]
        thumb = create_thumbnail(
            project_id, ThumbnailIn(timestamp_s=None, width=tw, height=th)
        )
        summary["thumbnail_path"] = thumb["path"]
    except HTTPException as exc:
        summary["warnings"].append(f"Thumbnail nahi bana: {exc.detail}")
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append(f"Thumbnail nahi bana: {exc}")
    with db() as conn:
        _set_magic(
            conn, magic_id, "done", summary_json=json.dumps(summary)
        )


@app.get("/api/projects/{project_id}/magic/options")
async def magic_options(project_id: int, language: str = "en") -> dict:
    """Everything the Magic Mode form needs: caption styles, aspect
    ratios, Style DNA presets, languages, and the REAL voice
    choices - uploaded voiceovers, Edge-TTS library voices (the
    live list when it loads, the curated list otherwise), and the
    HeyGen clone (only when a key is saved). No fake option: a
    voice with no key or no quota is listed as unavailable."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        caption_rows = conn.execute(
            "SELECT id, name, description, language FROM caption_styles"
            " ORDER BY id"
        ).fetchall()
        style_rows = conn.execute(
            "SELECT id, name, description, master_prompt FROM style_dna"
            " ORDER BY id"
        ).fetchall()
        uploaded_rows = conn.execute(
            "SELECT id, path, created_at FROM assets WHERE project_id = ?"
            " AND kind = 'voice' ORDER BY id DESC",
            (project_id,),
        ).fetchall()
        last_style = resolve_script_style(conn, project_id)
        bold = conn.execute(
            "SELECT id FROM caption_styles WHERE name = 'Bold White'"
            " LIMIT 1"
        ).fetchone()
    lang = magic_validate_language(language)
    prefix = "ur-" if lang == "ur" else "en-"
    # The live Edge-TTS list does a network call that can hang for
    # ~40 s where Edge-TTS is blocked: cap it at 6 s and fall back
    # to the curated list (real Microsoft voice IDs, labelled as
    # such) instead of making the form wait.
    try:
        live = await asyncio.wait_for(_live_tts_voices(), timeout=6)
    except asyncio.TimeoutError:
        live = None
    source = "live" if live is not None else "curated"
    voices_all = live if live is not None else CURATED_TTS_VOICES
    voices = [v for v in voices_all if v["locale"].startswith(prefix)]
    note = ""
    if not voices:
        voices = list(voices_all)
        note = (
            "Roman Urdu voices nahi mile - English voices dikha raha"
            " hoon"
            if lang == "ur"
            else "English voices nahi mile - saari voices dikha raha"
            " hoon"
        )
    uploaded = []
    for row in uploaded_rows:
        dur = 0.0
        try:
            disk = media_path(row["path"])
            if disk is not None and disk.exists():
                dur = round(probe_duration(disk), 3)
        except Exception:  # noqa: BLE001 - unknown duration, not fatal
            dur = 0.0
        uploaded.append(
            {
                "id": row["id"],
                "path": row["path"],
                "duration_s": dur,
                "created_at": row["created_at"],
            }
        )
    with db() as conn:
        hey_key = _heygen_key(conn)
        hey_voice = _heygen_voice_id(conn)
        # Slice 4 (Character Vault): the 7 niches with their Vault
        # status — locked cast count + whether the guard passes
        # (all mains locked). The UI disables a niche whose guard
        # fails and says why, instead of letting the run fail.
        niche_rows = conn.execute(
            "SELECT * FROM niches ORDER BY id"
        ).fetchall()
        niches = []
        for nrow in niche_rows:
            resolved = _vault_resolve(conn, nrow["id"])
            expected = _niche_main_names(nrow["main_characters"])
            missing = [
                n for n in expected
                if n not in {c["name"] for c in resolved["mains"]}
            ]
            niches.append(
                {
                    "id": nrow["id"],
                    "name": nrow["name"],
                    "main_characters": resolved["main_characters"],
                    "character_count": resolved["character_count"],
                    "sheet_url": resolved["sheet_url"],
                    "sheet_exists": resolved["sheet_exists"],
                    "guard_ok": not missing,
                    "missing_mains": missing,
                }
            )
    return {
        "caption_styles": [dict(r) for r in caption_rows],
        "niches": niches,
        "aspects": [
            {
                "value": a,
                "label": {
                    "16:9": "16:9 (YouTube)",
                    "9:16": "9:16 (Shorts/Reels)",
                    "1:1": "1:1 (Square)",
                }[a],
            }
            for a in MAGIC_ASPECTS
        ],
        "languages": [
            {"value": "en", "label": "English"},
            {"value": "ur", "label": "Roman Urdu"},
        ],
        "style_dna": [dict(r) for r in style_rows],
        "last_used_style_dna_id": last_style.get("id") if last_style else None,
        "voices": {
            "uploaded": uploaded,
            "edge": {
                "available": live is not None,
                "source": source,
                "note": note,
                "list": [
                    {
                        "id": v["voice_id"],
                        "label": v["name"],
                        "locale": v["locale"],
                        "language": v.get("language", ""),
                        "gender": v.get("gender", ""),
                    }
                    for v in voices
                ],
            },
            "heygen": {
                "available": bool(hey_key) and bool(hey_voice),
                "key_configured": bool(hey_key),
                "voice_id": hey_voice,
                "voice_name": "HeyGen clone voice" if hey_voice else "",
                "model": HEYGEN_VOICE_MODEL,
                "note": (
                    "HeyGen free quota khatam hai - voice banane se"
                    " pehle quota check karein"
                    if not hey_key
                    else ""
                ),
            },
        },
        "defaults": {
            "voice_kind": "upload" if uploaded else "edge",
            "vo_asset_id": uploaded[0]["id"] if uploaded else None,
            "voice_id": _default_tts_voice(),
            "caption_style_id": bold["id"] if bold else (
                caption_rows[0]["id"] if caption_rows else None
            ),
            "style_dna_id": last_style.get("id") if last_style else None,
            "aspect": "16:9",
            "language": "en",
        },
    }


@app.post("/api/projects/{project_id}/magic", status_code=202)
def start_magic(
    project_id: int, body: MagicIn, background_tasks: BackgroundTasks
) -> dict:
    """Start a Magic Mode run. Only the six inputs are taken; every
    empty select gets its smart default. One running Magic per
    project - a second start while one runs is a plain 409."""
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(
            status_code=400,
            detail="topic likhein - Magic Mode ko topic chahiye",
        )
    try:
        aspect = magic_validate_aspect(body.aspect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        language = magic_validate_language(body.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if body.voice_kind not in ("upload", "edge", "heygen"):
        raise HTTPException(
            status_code=400,
            detail="voice kind upload, edge ya heygen hona chahiye",
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        busy = conn.execute(
            "SELECT id FROM magic_runs WHERE project_id = ?"
            " AND status IN ('queued', 'running')",
            (project_id,),
        ).fetchone()
        if busy is not None:
            raise HTTPException(
                status_code=409,
                detail="pehle wala Magic run chal raha hai - us ke"
                " khatam hone ka intezar karein",
            )
        if body.caption_style_id is not None:
            cs = conn.execute(
                "SELECT id FROM caption_styles WHERE id = ?",
                (body.caption_style_id,),
            ).fetchone()
            if cs is None:
                raise HTTPException(
                    status_code=404, detail="caption style not found"
                )
            caption_id = body.caption_style_id
        else:
            bold = conn.execute(
                "SELECT id FROM caption_styles WHERE name = 'Bold White'"
                " LIMIT 1"
            ).fetchone()
            caption_id = bold["id"] if bold else None
        if body.style_dna_id is not None:
            srow = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.style_dna_id,),
            ).fetchone()
            if srow is None:
                raise HTTPException(
                    status_code=404, detail="style preset not found"
                )
            style_id = body.style_dna_id
        else:
            last = resolve_script_style(conn, project_id)
            style_id = last.get("id") if last else None
        voice_id = body.voice_id.strip()
        vo_asset_id = body.vo_asset_id
        if body.voice_kind == "upload":
            if vo_asset_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="voiceover upload karein ya Edge-TTS"
                    " chunein - bina voice ke video nahi ban sakti",
                )
            vo = conn.execute(
                "SELECT id, kind FROM assets WHERE id = ?"
                " AND project_id = ?",
                (vo_asset_id, project_id),
            ).fetchone()
            if vo is None or vo["kind"] != "voice":
                raise HTTPException(
                    status_code=400,
                    detail="voiceover asset nahi mila",
                )
        elif body.voice_kind == "edge":
            if not voice_id:
                voice_id = _default_tts_voice()
            elif not any(
                v["voice_id"] == voice_id for v in CURATED_TTS_VOICES
            ):
                raise HTTPException(
                    status_code=400, detail="Edge-TTS voice nahi mila"
                )
        else:  # heygen
            if not voice_id:
                voice_id = _heygen_voice_id(conn) or ""
        # Slice 4 (Character Vault): a niche given here is
        # guarded NOW, so the user gets the plain 400 at once
        # instead of a failed run later. No locked cast, no run.
        if body.niche_id is not None:
            _vault_guard(conn, body.niche_id)
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO magic_runs (project_id, topic, script_text,"
            " voice_kind, voice_id, vo_asset_id, caption_style_id,"
            " style_dna_id, aspect, language, niche_id,"
            " scene_characters_json, status, stages_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?, 'queued', ?, ?, ?)",
            (
                project_id,
                topic,
                body.script_text.strip(),
                body.voice_kind,
                voice_id,
                vo_asset_id,
                caption_id,
                style_id,
                aspect,
                language,
                body.niche_id,
                json.dumps(body.scene_characters or {}),
                json.dumps(_magic_stages_default()),
                now,
                now,
            ),
        )
        magic_id = cur.lastrowid
    background_tasks.add_task(process_magic_run, magic_id)
    with db() as conn:
        return _magic_detail(conn, magic_id)


@app.get("/api/projects/{project_id}/magic")
def list_magic(project_id: int) -> list:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            "SELECT id FROM magic_runs WHERE project_id = ?"
            " ORDER BY id DESC",
            (project_id,),
        ).fetchall()
        return [_magic_detail(conn, r["id"]) for r in rows]


@app.get("/api/magic/{magic_id}")
def get_magic(magic_id: int) -> dict:
    with db() as conn:
        return _magic_detail(conn, magic_id)


# --- Phase 2 endpoints ----------------------------------------------------

@app.post("/api/projects/{project_id}/upload-voice", status_code=201)
async def upload_voice(project_id: int, file: UploadFile = File(...)) -> dict:
    """Upload a voiceover file (mp3/wav/m4a). The default VO source."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in VOICE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "ye file voiceover nahi hai — "
                f"{', '.join(sorted(VOICE_EXTS))} me se ek upload karein"
            ),
        )
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="voiceover 200 MB se bara hai — chhoti file upload karein",
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(
                status_code=404,
                detail="project not found — Projects page se dobara kholein",
            )
        folder = PROJECTS_DIR / str(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        name = f"voice_{int(time.time())}_{safe_filename(file.filename)}"
        disk = folder / name
        disk.write_bytes(data)
        rel = f"projects/{project_id}/{name}"
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'voice', ?, ?)",
            (project_id, rel, utcnow()),
        )
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    result = dict(row)
    result["duration_s"] = round(probe_duration(disk), 3)
    return result


@app.post("/api/projects/{project_id}/upload-images", status_code=201)
async def upload_images(
    project_id: int, files: list[UploadFile] = File(...)
) -> list:
    """Upload one or more images (png/jpg/webp)."""
    saved = []
    skipped: list[str] = []
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(
                status_code=404,
                detail="project not found — Projects page se dobara kholein",
            )
        folder = PROJECTS_DIR / str(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        for f in files:
            fname = f.filename or "unnamed"
            ext = Path(fname).suffix.lower()
            if ext not in IMAGE_EXTS:
                skipped.append(
                    f"{fname}: tasveer nahi hai — png, jpg ya webp dein"
                )
                continue
            data = await f.read()
            if len(data) > 50 * 1024 * 1024:
                skipped.append(f"{fname}: 50 MB se bara hai — chhoti file dein")
                continue
            name = f"img_{int(time.time())}_{safe_filename(f.filename)}"
            (folder / name).write_bytes(data)
            rel = f"projects/{project_id}/{name}"
            cur = conn.execute(
                "INSERT INTO assets (project_id, kind, path, created_at)"
                " VALUES (?, 'image', ?, ?)",
                (project_id, rel, utcnow()),
            )
            row = conn.execute(
                "SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            saved.append(dict(row))
    if not saved:
        # Phase 7 slice 3: skipped files used to vanish silently —
        # now the error names each file and why it was skipped.
        detail = (
            "koi tasveer save nahi hui — " + "; ".join(skipped)
            if skipped
            else "koi tasveer save nahi hui — png, jpg ya webp file dein"
        )
        raise HTTPException(status_code=400, detail=detail)
    return saved


@app.post("/api/projects/{project_id}/character", status_code=201)
async def set_character(
    project_id: int,
    name: str = Form(""),
    description: str = Form(""),
    file: UploadFile = File(...),
) -> dict:
    """Set the project's main character: a name + one reference image
    (png/jpg/webp) + an optional one-line locked description (look,
    outfit, beard, props). Stored under
    studio/data/projects/{id}/character/ and recorded in SQLite
    (project_characters). Re-uploading replaces the character. Image
    prompts reference the character by name and description
    automatically - the user never writes a prompt."""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="character name is required")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="character name too long")
    description = (description or "").strip()
    if len(description) > 500:
        raise HTTPException(
            status_code=400,
            detail="character description too long (max 500)",
        )
    ext = Path(file.filename or "").suffix.lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"character image must be one of: {', '.join(sorted(IMAGE_EXTS))}",
        )
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="image too large (max 50 MB)")
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        folder = PROJECTS_DIR / str(project_id) / "character"
        folder.mkdir(parents=True, exist_ok=True)
        for old_file in folder.iterdir():
            if old_file.is_file():
                old_file.unlink()
        fname = f"character_{int(time.time())}_{safe_filename(file.filename)}"
        (folder / fname).write_bytes(data)
        rel = f"projects/{project_id}/character/{fname}"
        now = utcnow()
        conn.execute(
            "INSERT INTO project_characters (project_id, name, description,"
            " image_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(project_id) DO UPDATE SET name = excluded.name,"
            " description = excluded.description,"
            " image_path = excluded.image_path, updated_at = excluded.updated_at",
            (project_id, name, description, rel, now, now),
        )
        row = conn.execute(
            "SELECT * FROM project_characters WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}/character")
def get_project_character(project_id: int) -> dict | None:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        char = get_character(conn, project_id)
    # No character set yet is normal empty state — return null with
    # 200 so the UI does not log a 404 for every project card.
    return char


def _insert_script(
    conn,
    project_id: int,
    topic: str,
    text: str,
    source: str,
    style: dict | None = None,
    aspect: str | None = None,
) -> dict:
    """Save a script's text and split it into scenes with image prompts.
    Shared by pasted/Gemini scripts and by transcription-as-script.
    Slice 3 (Magic Mode): a given style overrides the project's
    resolved style, and aspect is baked into the image prompts."""
    scenes = split_script(text)
    if not scenes:
        raise HTTPException(
            status_code=400, detail="script text khaali hai — kuch likhein"
        )
    if style is None:
        style = resolve_script_style(conn, project_id)
    char = get_character(conn, project_id)
    char_name = char["name"] if char else None
    # Slice 3 auto-consistency: the locked description (set once
    # at character upload, optional) is injected into every
    # prompt - the user never writes one.
    char_desc = None
    if char:
        char_desc = (char.get("description") or "").strip() or None
    now = utcnow()
    cur = conn.execute(
        "INSERT INTO scripts (project_id, topic, full_text, source,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, topic, text, source, now, now),
    )
    script_id = cur.lastrowid
    for i, scene_text in enumerate(scenes):
        conn.execute(
            "INSERT INTO scenes (script_id, position, text,"
            " image_prompt, duration_s) VALUES (?, ?, ?, ?, ?)",
            (
                script_id,
                i,
                scene_text,
                build_image_prompt(
                    scene_text, style, char_name, aspect, char_desc
                ),
                estimate_duration_s(scene_text),
            ),
        )
    return script_detail(conn, script_id)


# --- Phase 3: scripts + scene breakdown ---------------------------------

@app.post("/api/projects/{project_id}/scripts", status_code=201)
def create_script(project_id: int, body: ScriptIn) -> dict:
    """Save a script for a project and split it into scenes.

    Paste/type full_text (always works, no key, no paid call), or give
    only a topic: then the optional Gemini free-tier key from Settings
    generates the text. Topic-only with no key is a plain 400 — the
    endpoint never invents a key and never fails silently.
    """
    topic = (body.topic or "").strip()
    full_text = (body.full_text or "").strip()
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(
                status_code=404,
                detail="project not found — Projects page se dobara kholein",
            )
        if full_text:
            text, source = full_text, "pasted"
        elif topic:
            # Slice 2: Thinking Level + model picker — a bad value is
            # a plain 400, never a silent fallback to the defaults.
            try:
                level = _validate_thinking_level(body.thinking_level)
                model = _validate_script_model(body.model)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            # Phase 7 slice 3: key rotation — every configured key is
            # tried in order; a dead key moves to the next one, and
            # only when all keys are dead does the request fail.
            try:
                text, source = _generate_script_text(
                    conn, topic, thinking_level=level, model=model
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc))
        else:
            raise HTTPException(
                status_code=400,
                detail="topic ya script text dein — ek to likhna parega",
            )
        return _insert_script(conn, project_id, topic, text, source)


@app.get("/api/projects/{project_id}/scripts")
def list_scripts(project_id: int) -> list:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            """
            SELECT s.*, COUNT(sc.id) AS scene_count FROM scripts s
            LEFT JOIN scenes sc ON sc.script_id = s.id
            WHERE s.project_id = ? GROUP BY s.id ORDER BY s.id DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/scripts/{script_id}/scenes")
def list_scenes(script_id: int) -> list:
    with db() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        rows = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def prompts_detail(conn, script_id: int) -> dict:
    """VisualForge prompt list (Phase 4 slice 1): every scene's image
    prompt with the Style DNA + main character it was built from, and
    the honest Gemini quota. Status is real per-scene state from slice
    2's image-generate jobs — 'pending' until a job exists, then the
    job's own status. Nothing is faked."""
    script = conn.execute(
        "SELECT * FROM scripts WHERE id = ?", (script_id,)
    ).fetchone()
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    scenes = conn.execute(
        "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
        (script_id,),
    ).fetchall()
    style = resolve_script_style(conn, script["project_id"])
    char = get_character(conn, script["project_id"])
    quota = _image_quota(conn)
    key_set = bool(_gemini_key(conn))
    return {
        "script_id": script["id"],
        "topic": script["topic"],
        "style_dna_name": style["name"] if style else None,
        "character_name": char["name"] if char else None,
        "prompts": [
            {
                "scene_id": s["id"],
                "position": s["position"],
                "text": s["text"],
                "image_prompt": s["image_prompt"],
                "duration_s": s["duration_s"],
                "status": scene_generation_status(conn, s["id"])["status"],
            }
            for s in scenes
        ],
        "quota": {
            "daily_limit": quota["daily_limit"],
            "used_today": quota["used_today"],
            "remaining": quota["remaining"],
            "generation_available": key_set,
            "note": (
                "Image generation live — Gemini, "
                f"{quota['remaining']} left today."
                if key_set
                else "Gemini key Settings me lagayen — bina key ke image"
                " nahi ban sakti (prompts list + upload wala rasta kaam"
                " karta hai)."
            ),
        },
        "providers": {
            "api": {
                "available": key_set,
                "note": (
                    "Gemini API — reliable, billing lagti hai"
                    if key_set
                    else "Gemini key Settings me lagayen"
                ),
            },
            "canvas": {
                # Cheap check only (Playwright + Chromium present?) —
                # the Google login state comes from /api/canvas/status.
                "available": _canvas_provider.canvas_available()[0],
                "note": (
                    "Gemini Canvas — free, aapki Gemini Pro quota se"
                    " (Google login chahiye)"
                ),
            },
            "flow": {
                # Cheap check only — the Google login state comes
                # from /api/google/status. Flow is the second free
                # bulk route; Canvas stays the default.
                "available": _flow_provider.flow_available()[0],
                "note": (
                    "Google Flow — free images, aapki Gemini Pro quota se"
                    " (Google login chahiye; fail ho to Canvas fallback)"
                ),
            },
        },
    }


@app.get("/api/scripts/{script_id}/prompts")
def list_script_prompts(script_id: int) -> dict:
    with db() as conn:
        return prompts_detail(conn, script_id)


@app.get("/api/projects/{project_id}/prompts")
def list_project_prompts(project_id: int) -> dict:
    """Prompt list for the project's latest script."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        script = conn.execute(
            "SELECT id FROM scripts WHERE project_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if script is None:
            raise HTTPException(
                status_code=404,
                detail="pehle script save karein — prompts script se bante hain",
            )
        return prompts_detail(conn, script["id"])


# --- Phase 4 slice 2: bulk image generation -------------------------------


@app.post("/api/scripts/{script_id}/generate-images")
def generate_images(
    script_id: int,
    background_tasks: BackgroundTasks,
    body: GenerateImagesIn | None = None,
) -> dict:
    """Queue one image-generate job per scene of a script. Scenes that
    already have a finished image are skipped; scenes already queued
    or generating are skipped. The daily quota is reserved at queue
    time: once today's done + running + queued jobs reach the limit,
    further scenes are created as failed jobs with the plain limit
    message — the limit is never silently crossed. A missing Gemini key
    is NOT rejected here: the jobs fail honestly on their turn, so the
    status view shows the exact reason instead of a silent nothing.
    provider='canvas' queues the same jobs on the Canvas provider
    instead (free via the user's Gemini Pro quota; the API daily limit
    does not apply to them, and a missing Google login marks them
    'blocked' with the exact login message on their turn).
    provider='flow' queues them on the Google Flow provider instead
    (same free quota, same Google login); a Flow failure on a scene
    retries that scene once on Canvas, on the same job."""
    provider = (body.provider if body else "api") or "api"
    if provider not in ("api", "canvas", "flow"):
        raise HTTPException(
            status_code=400,
            detail="provider 'api', 'canvas' ya 'flow' hona chahiye",
        )
    # Cross-check slice: Character/Style Match toggles (AutoCut
    # Gemini Bulk parity) — both default True (the locked look).
    options = {
        "character_match": bool(body.character_match) if body else True,
        "style_match": bool(body.style_match) if body else True,
    }
    # Slice 4 (Character Vault): niche given -> guard first
    # (locked mains required), then the locked cast is applied
    # to the scene prompts and pinned into every job's options,
    # so the worker + auto-QC use exactly this cast.
    vault_pin: dict | None = None
    vault_mapping: dict[int, dict] = {}
    niche_id = body.niche_id if body else None
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        script = dict(script)
        if niche_id is not None:
            resolved = _vault_guard(conn, niche_id)
            vault_pin = _vault_pin(resolved, _vault_main(conn))
            options["vault"] = vault_pin
            style_row = conn.execute(
                "SELECT * FROM style_dna WHERE id = ?",
                (script.get("style_dna_id"),),
            ).fetchone()
            style = dict(style_row) if style_row else None
            first_prompt = conn.execute(
                "SELECT image_prompt FROM scenes WHERE script_id = ?"
                " ORDER BY position, id LIMIT 1",
                (script_id,),
            ).fetchone()
            aspect = _vault_prompt_aspect(
                first_prompt["image_prompt"] if first_prompt else ""
            )
            vault_mapping = _vault_apply_to_scenes(
                conn, script_id, vault_pin, style, aspect,
                body.scene_characters if body else None,
            )
        else:
            # No niche chosen, but the user HAS a locked main
            # character — the main IS the cast for this run.
            main_char = _vault_main(conn)
            if main_char is not None:
                niche_row = conn.execute(
                    "SELECT name FROM niches WHERE id = ?",
                    (main_char["niche_id"],),
                ).fetchone()
                vault_pin = _vault_pin_for_main(
                    main_char, niche_row["name"] if niche_row else ""
                )
                options["vault"] = vault_pin
                style_row = conn.execute(
                    "SELECT * FROM style_dna WHERE id = ?",
                    (script.get("style_dna_id"),),
                ).fetchone()
                style = dict(style_row) if style_row else None
                first_prompt = conn.execute(
                    "SELECT image_prompt FROM scenes WHERE script_id = ?"
                    " ORDER BY position, id LIMIT 1",
                    (script_id,),
                ).fetchone()
                aspect = _vault_prompt_aspect(
                    first_prompt["image_prompt"] if first_prompt else ""
                )
                vault_mapping = _vault_apply_to_scenes(
                    conn, script_id, vault_pin, style, aspect,
                    body.scene_characters if body else None,
                )
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
        if not scenes:
            raise HTTPException(
                status_code=400, detail="script me koi scene nahi hai"
            )
        now = utcnow()
        # Slice 5: one batch id for the whole bulk run — Queue
        # History groups by it, and the batch ZIP re-downloads it.
        import uuid

        batch_id = uuid.uuid4().hex[:12]
        queued: list[int] = []
        skipped_done: list[int] = []
        skipped_queued: list[int] = []
        limit_blocked: list[int] = []
        for scene in scenes:
            outcome, job_id = _queue_one_image_job(
                conn, script, dict(scene), now, provider=provider,
                options=options, batch_id=batch_id,
            )
            if outcome == "queued" and job_id is not None:
                queued.append(job_id)
            elif outcome == "skipped_done":
                skipped_done.append(scene["id"])
            elif outcome == "skipped_queued":
                skipped_queued.append(scene["id"])
            elif outcome == "limit_blocked" and job_id is not None:
                limit_blocked.append(job_id)
        quota = _image_quota(conn)
    if queued:
        background_tasks.add_task(process_image_jobs, script_id)
    return {
        "script_id": script_id,
        "provider": provider,
        "batch_id": batch_id,
        "character_match": options["character_match"],
        "style_match": options["style_match"],
        "queued_job_ids": queued,
        "skipped_done_scene_ids": skipped_done,
        "skipped_queued_scene_ids": skipped_queued,
        "limit_blocked_job_ids": limit_blocked,
        "quota": quota,
        "niche_id": niche_id,
        "vault": (
            {
                "niche_name": vault_pin["niche_name"],
                "character_count": len(vault_pin["characters"]),
                "sheet_path": vault_pin["sheet_path"],
                "main_character": (
                    vault_pin["main_character"]["name"]
                    if vault_pin.get("main_character")
                    else None
                ),
                "scene_characters": {
                    str(sid): info["character"]
                    for sid, info in vault_mapping.items()
                },
            }
            if vault_pin
            else None
        ),
    }


@app.get("/api/scripts/{script_id}/generation-status")
def get_generation_status(script_id: int) -> dict:
    """Per-scene generation status + quota for one script."""
    with db() as conn:
        return generation_status_detail(conn, script_id)


# --- Gemini Canvas provider (free image route) ----------------------------

_CANVAS_STATUS_CACHE: dict = {"at": 0.0, "data": None}
_CANVAS_STATUS_TTL_S = 60


def _canvas_status_data() -> dict:
    """Canvas readiness: Playwright + Chromium present? Google logged
    in? The login probe launches a headless browser (~10-20 s), so
    the result is cached for 60 s — the UI polls, the browser does
    not relaunch every time."""
    now = time.monotonic()
    if (
        _CANVAS_STATUS_CACHE["data"] is not None
        and now - _CANVAS_STATUS_CACHE["at"] < _CANVAS_STATUS_TTL_S
    ):
        return _CANVAS_STATUS_CACHE["data"]
    available, reason = _canvas_provider.canvas_available()
    profile_exists = CANVAS_PROFILE_DIR.is_dir() and any(
        CANVAS_PROFILE_DIR.iterdir()
    )
    data: dict = {
        "provider": "canvas",
        "available": available,
        "logged_in": False,
        "needs_login": True,
        "profile_exists": profile_exists,
        "message": reason or "",
        "detail": "",
        "setup_steps": [
            "1. 'Canvas login kholein' dabayein — browser khulega.",
            "2. Apne Google account se sign-in karein (Gemini Pro wala).",
            "3. Browser band kar dein — login save ho jata hai.",
            "4. 'Generate all images' dabayein — images aapki Gemini"
            " Pro quota se free banengi.",
        ],
    }
    if available:
        try:
            login = _canvas_provider.check_login()
            data["logged_in"] = bool(login["logged_in"])
            data["needs_login"] = not login["logged_in"]
            data["detail"] = login.get("detail", "")
            data["message"] = (
                "Canvas ready — free images, aapki Gemini Pro quota se"
                if login["logged_in"]
                else _canvas_provider.CANVAS_LOGIN_MSG
            )
        except _canvas_provider.CanvasUnavailable as exc:
            data["message"] = str(exc)
        except Exception as exc:
            data["message"] = str(exc)[:300]
    _CANVAS_STATUS_CACHE["at"] = now
    _CANVAS_STATUS_CACHE["data"] = data
    return data


@app.get("/api/canvas/status")
def canvas_status() -> dict:
    """Canvas provider readiness (Playwright + Chromium + Google
    login). Cheap for the UI to poll — the browser probe is cached
    for 60 s."""
    return _canvas_status_data()


@app.post("/api/canvas/open-login", status_code=202)
def canvas_open_login() -> dict:
    """Open the one-time Google login window (a VISIBLE browser on
    the Canvas profile). The user signs into Google once and closes
    the window; the profile keeps the login after that. The window
    must actually open — if it does not (e.g. a headless server with
    no display), the endpoint fails plainly with a 503 instead of
    pretending the browser opened."""
    if _canvas_provider.login_window_open():
        raise HTTPException(
            status_code=409,
            detail="Canvas login browser pehle se khula hai",
        )
    available, reason = _canvas_provider.canvas_available()
    if not available:
        raise HTTPException(status_code=503, detail=reason)

    import threading

    def _run() -> None:
        try:
            _canvas_provider.open_login_window()
        except Exception:
            pass
        finally:
            # Login state may have changed — re-probe next time.
            _CANVAS_STATUS_CACHE["at"] = 0.0

    threading.Thread(target=_run, daemon=True).start()
    # Wait for the window to REALLY open (page loaded), not just for
    # the launch to start — a failed launch clears the flag again, so
    # a clear flag here means it failed and the answer is a plain 503.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _canvas_provider.login_window_opened():
            return {
                "message": (
                    "Canvas login browser khul gaya — Google sign-in"
                    " karein, phir browser band kar dein. Phir dobara"
                    " generate karein."
                )
            }
        if not _canvas_provider.login_window_open():
            break
        time.sleep(0.5)
    raise HTTPException(
        status_code=503,
        detail=(
            "Canvas login browser nahi khul saka — is PC par display"
            " nahi hai ya Chromium headed mode me nahi chal sakta"
        ),
    )


# --- Connect Google (one sign-in for Canvas + Flow) ----------------------

_GOOGLE_STATUS_CACHE: dict = {"at": 0.0, "data": None}
_GOOGLE_STATUS_TTL_S = 60


def _google_status_data() -> dict:
    """One Google sign-in for Canvas + Flow: Playwright + Chromium
    present? Google logged in? Per-service readiness for Canvas and
    Flow. Each login probe launches a headless browser (~10-20 s),
    so the result is cached for 60 s — the UI polls, the browser
    does not relaunch every time. The overall logged_in is True
    when EITHER service sees a Google session: the account is one
    session in the shared profile, and a service that does not see
    it yet reports its own detail in its block."""
    now = time.monotonic()
    if (
        _GOOGLE_STATUS_CACHE["data"] is not None
        and now - _GOOGLE_STATUS_CACHE["at"] < _GOOGLE_STATUS_TTL_S
    ):
        return _GOOGLE_STATUS_CACHE["data"]
    available, reason = _google_browser.browser_available()
    profile_exists = CANVAS_PROFILE_DIR.is_dir() and any(
        CANVAS_PROFILE_DIR.iterdir()
    )
    data: dict = {
        "provider": "google",
        "available": available,
        "logged_in": False,
        "needs_login": True,
        "profile_exists": profile_exists,
        "message": reason or "",
        "detail": "",
        "canvas": {"logged_in": False, "message": ""},
        "flow": {"logged_in": False, "message": ""},
        "setup_steps": [
            "1. 'Connect Google' dabayein — browser khulega.",
            "2. Apne Google account se sign-in karein (Gemini Pro wala).",
            "3. Browser band kar dein — login save ho jata hai.",
            "4. VisualForge me Canvas ya Flow chunein — images aapki"
            " Gemini Pro quota se free banengi.",
        ],
    }
    if available:
        try:
            login = _canvas_provider.check_login()
            data["canvas"] = {
                "logged_in": bool(login["logged_in"]),
                "message": login.get("detail", ""),
            }
        except Exception as exc:
            data["canvas"] = {"logged_in": False, "message": str(exc)[:200]}
        try:
            login = _flow_provider.check_login()
            data["flow"] = {
                "logged_in": bool(login["logged_in"]),
                "message": login.get("detail", ""),
            }
        except Exception as exc:
            data["flow"] = {"logged_in": False, "message": str(exc)[:200]}
        data["logged_in"] = bool(
            data["canvas"]["logged_in"] or data["flow"]["logged_in"]
        )
        data["needs_login"] = not data["logged_in"]
        data["message"] = (
            "Google connected — Canvas aur Flow dono ke liye login hai"
            if data["logged_in"]
            else "Google login nahi hai — 'Connect Google' se ek dafa"
            " sign-in karein"
        )
    _GOOGLE_STATUS_CACHE["at"] = now
    _GOOGLE_STATUS_CACHE["data"] = data
    return data


@app.get("/api/google/status")
def google_status() -> dict:
    """Connect Google readiness (Playwright + Chromium + Google
    login + per-service Canvas/Flow readiness). Cheap for the UI to
    poll — the browser probes are cached for 60 s."""
    return _google_status_data()


@app.post("/api/google/open-login", status_code=202)
def google_open_login() -> dict:
    """Open the one-time Google sign-in window (a VISIBLE browser on
    the shared Google profile, at myaccount.google.com). The user
    signs into Google once and closes the window; the profile keeps
    the login after that, and Canvas + Flow both pick it up — no
    second sign-in. The window must actually open — if it does not
    (e.g. a headless server with no display), the endpoint fails
    plainly with a 503 instead of pretending the browser opened.
    The login-window lock is shared with the Canvas login button:
    one of them open means the other gets a 409."""
    if _google_browser.login_window_open():
        raise HTTPException(
            status_code=409,
            detail="Google login browser pehle se khula hai",
        )
    available, reason = _google_browser.browser_available()
    if not available:
        raise HTTPException(status_code=503, detail=reason)

    import threading

    def _run() -> None:
        try:
            _google_browser.open_login_window(
                _google_browser.GOOGLE_ACCOUNT_URL
            )
        except Exception:
            pass
        finally:
            # Login state may have changed — re-probe next time.
            _GOOGLE_STATUS_CACHE["at"] = 0.0
            _CANVAS_STATUS_CACHE["at"] = 0.0

    threading.Thread(target=_run, daemon=True).start()
    # Wait for the window to REALLY open (page loaded), not just for
    # the launch to start — a failed launch clears the flag again, so
    # a clear flag here means it failed and the answer is a plain 503.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _google_browser.login_window_opened():
            return {
                "message": (
                    "Google login browser khul gaya — Google sign-in"
                    " karein, phir browser band kar dein. Canvas aur"
                    " Flow dono ke liye yahi ek login kaafi hai."
                )
            }
        if not _google_browser.login_window_open():
            break
        time.sleep(0.5)
    raise HTTPException(
        status_code=503,
        detail=(
            "Google login browser nahi khul saka — is PC par display"
            " nahi hai ya Chromium headed mode me nahi chal sakta"
        ),
    )


@app.post("/api/google/disconnect")
def google_disconnect() -> dict:
    """Sign out of Google in the shared browser profile: delete the
    profile's contents (cookies + login state) so Canvas and Flow
    both go back to 'not connected'. Explicit user action only —
    nothing else is deleted, and the profile folder itself stays.
    Refuses with 409 while a login window is open. NOTE: disconnect
    while a generation is running will fail that run (its browser
    loses the profile mid-flight) — the UI only offers it when
    nothing is generating."""
    if _google_browser.login_window_open():
        raise HTTPException(
            status_code=409,
            detail=(
                "Google login browser khula hai — pehle band karein,"
                " phir disconnect karein"
            ),
        )
    import shutil

    removed = 0
    if CANVAS_PROFILE_DIR.is_dir():
        for child in CANVAS_PROFILE_DIR.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except FileNotFoundError:
                    pass
            removed += 1
    _GOOGLE_STATUS_CACHE["at"] = 0.0
    _CANVAS_STATUS_CACHE["at"] = 0.0
    return {"disconnected": True, "removed_entries": removed}


# --- Slice 5: Flow provider hardening ------------------------------------
# Ready indicator (green + project fragment), multi-account rotation
# (up to 3 Flow accounts, one browser profile each), Fast mode
# (parallel generations), Unusual-Activity guided recovery, queue
# history + ZIP re-download, persistent pause/resume, #/@ chaining.
# Free only: no new provider, no credential store — accounts are
# names + profile directories; the login lives only in the profile.

_FLOW_STATUS_CACHE: dict = {"at": 0.0, "data": None}
_FLOW_STATUS_TTL_S = 60


class FlowSettingsIn(BaseModel):
    fast_concurrency: int = 1


class ChainResolveIn(BaseModel):
    prompt: str = ""
    niche_id: int | None = None


def _flow_status_data() -> dict:
    """Flow readiness per account: Playwright + Chromium present?
    Which accounts are signed in, which project is open (first 4
    chars of the project ID, like Flow Automator's green Ready),
    which account is blocked by 'Unusual Activity'. Each login
    probe launches a headless browser (~10-20 s per account), so
    the result is cached for 60 s — the UI polls, the browser does
    not relaunch every time. Limited (cooldown) and unusual
    accounts are NOT re-probed here — their last-known state is
    reported, and the recover endpoint re-probes after clearing
    site data."""
    now = time.monotonic()
    if (
        _FLOW_STATUS_CACHE["data"] is not None
        and now - _FLOW_STATUS_CACHE["at"] < _FLOW_STATUS_TTL_S
    ):
        return _FLOW_STATUS_CACHE["data"]
    available, reason = _google_browser.browser_available()
    fast_requested = _flow_fast_concurrency()
    accounts: list[dict] = []
    any_ready = False
    any_unusual = False
    for acct in _flow_accounts():
        row = {
            "id": acct["id"],
            "name": acct["name"],
            "status": acct["status"],
            "logged_in": False,
            "ready": False,
            "project_id_fragment": None,
            "detail": "",
            "unusual_activity": False,
            "last_used_at": acct.get("last_used_at"),
            "limited_until": acct.get("limited_until"),
        }
        if not available:
            row["detail"] = reason
            accounts.append(row)
            continue
        if acct["status"] == "unusual":
            any_unusual = True
            row["unusual_activity"] = True
            row["detail"] = _flow_hardening.RECOVERY_MSG
            accounts.append(row)
            continue
        if acct["status"] == "limited" and acct.get("limited_until"):
            if acct["limited_until"] > utcnow():
                row["detail"] = (
                    "Rate limit — account rest kar raha hai"
                    f" ({acct['limited_until']} tak)"
                )
                accounts.append(row)
                continue
        try:
            login = _flow_provider.check_login(
                profile_dir=acct["profile_dir"]
            )
        except Exception as exc:
            row["detail"] = str(exc)[:200]
            accounts.append(row)
            continue
        row["logged_in"] = bool(login.get("logged_in"))
        row["project_id_fragment"] = login.get("project_id_fragment")
        row["unusual_activity"] = bool(login.get("unusual_activity"))
        row["detail"] = login.get("detail", "")
        if row["unusual_activity"]:
            any_unusual = True
            row["status"] = "unusual"
            _flow_set_account_status(acct["id"], "unusual")
        elif row["logged_in"]:
            row["ready"] = True
            row["status"] = "active"
            any_ready = True
        accounts.append(row)
    usable = sum(1 for a in accounts if a["ready"])
    effective = _flow_hardening.effective_concurrency(
        fast_requested, usable
    )
    data: dict = {
        "provider": "flow",
        "available": available,
        "ready": any_ready,
        "fast_concurrency": fast_requested,
        "effective_concurrency": effective,
        "accounts": accounts,
        "message": reason
        if not available
        else (
            "Flow ready — green"
            if any_ready
            else (
                "Flow 'Unusual Activity' — recovery steps follow karein"
                if any_unusual
                else "Flow login nahi hai — account connect karein"
            )
        ),
        "recovery_steps": (
            _flow_hardening.RECOVERY_STEPS if any_unusual else []
        ),
        "recovery_tip": (
            _flow_hardening.RECOVERY_TIP if any_unusual else ""
        ),
    }
    _FLOW_STATUS_CACHE["at"] = now
    _FLOW_STATUS_CACHE["data"] = data
    return data


@app.get("/api/flow/status")
def flow_status() -> dict:
    """Flow readiness: per-account login + project fragment + Fast
    mode + recovery steps when an account is blocked. Cheap for the
    UI to poll — the browser probes are cached for 60 s."""
    return _flow_status_data()


@app.get("/api/flow/accounts")
def flow_accounts_list() -> dict:
    """Flow accounts (no browser probe — just the stored rows)."""
    return {"accounts": _flow_accounts()}


@app.post("/api/flow/accounts", status_code=201)
def flow_account_add() -> dict:
    """Add a Flow account (max 3 — Flow Automator's own limit).
    Account 1 is the shared profile and always exists; this creates
    account 2 or 3 on its own profile directory. The user signs in
    next, via open-login on the new account — no password or token
    is ever stored."""
    existing = _flow_accounts()
    if len(existing) >= _flow_hardening.FLOW_MAX_ACCOUNTS:
        raise HTTPException(
            status_code=400,
            detail="3 Flow accounts hi ho sakte hain — pehle ek remove karein",
        )
    used = {a["name"] for a in existing}
    n = next(
        i for i in (2, 3) if f"Account {i}" not in used
    )
    profile_dir = FLOW_PROFILES_DIR / f"account-{n}"
    profile_dir.mkdir(parents=True, exist_ok=True)
    now = utcnow()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO flow_accounts"
            " (name, profile_dir, status, created_at, updated_at)"
            " VALUES (?, ?, 'not_logged_in', ?, ?)",
            (f"Account {n}", str(profile_dir), now, now),
        )
        row = conn.execute(
            "SELECT * FROM flow_accounts WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    _FLOW_STATUS_CACHE["at"] = 0.0
    return {"account": dict(row)}


@app.delete("/api/flow/accounts/{account_id}")
def flow_account_delete(account_id: int) -> dict:
    """Remove a Flow account (row + its profile directory, so the
    login goes with it). Account 1 cannot be removed — it IS the
    shared Google profile Canvas + Connect Google use."""
    acct = _flow_account_by_id(account_id)
    if acct is None:
        raise HTTPException(status_code=404, detail="account not found")
    if acct["profile_dir"] == str(CANVAS_PROFILE_DIR):
        raise HTTPException(
            status_code=400,
            detail="Account 1 (pehla) delete nahi ho sakta — ye Canvas"
            " aur Connect Google ke saath shared profile hai",
        )
    if _google_browser.login_window_open():
        raise HTTPException(
            status_code=409,
            detail="Google login browser khula hai — pehle band karein",
        )
    import shutil

    shutil.rmtree(acct["profile_dir"], ignore_errors=True)
    with db() as conn:
        conn.execute(
            "DELETE FROM flow_accounts WHERE id = ?", (account_id,)
        )
    _FLOW_STATUS_CACHE["at"] = 0.0
    return {"deleted": True, "account_id": account_id}


@app.post("/api/flow/accounts/{account_id}/open-login", status_code=202)
def flow_account_open_login(account_id: int) -> dict:
    """Open the one-time Google login window on THIS account's
    profile (a VISIBLE browser). The user signs in with that
    account's Google login and closes the window; the profile keeps
    the session. Same 20-second 'really opened' check as Connect
    Google — a failed launch is a plain 503, never a pretend."""
    acct = _flow_account_by_id(account_id)
    if acct is None:
        raise HTTPException(status_code=404, detail="account not found")
    if _google_browser.login_window_open():
        raise HTTPException(
            status_code=409,
            detail="Google login browser pehle se khula hai",
        )
    available, reason = _google_browser.browser_available()
    if not available:
        raise HTTPException(status_code=503, detail=reason)

    import threading

    def _run() -> None:
        try:
            _google_browser.open_login_window(
                _google_browser.GOOGLE_ACCOUNT_URL,
                profile_dir=acct["profile_dir"],
            )
        except Exception:
            pass
        finally:
            _FLOW_STATUS_CACHE["at"] = 0.0
            _GOOGLE_STATUS_CACHE["at"] = 0.0

    threading.Thread(target=_run, daemon=True).start()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _google_browser.login_window_opened():
            return {
                "message": (
                    f"{acct['name']} login browser khul gaya — is"
                    " account ke Google se sign-in karein, phir"
                    " browser band kar dein."
                )
            }
        if not _google_browser.login_window_open():
            break
        time.sleep(0.5)
    raise HTTPException(
        status_code=503,
        detail=(
            "Login browser nahi khul saka — is PC par display nahi hai"
            " ya Chromium headed mode me nahi chal sakta"
        ),
    )


@app.post("/api/flow/accounts/{account_id}/recover")
def flow_account_recover(account_id: int) -> dict:
    """Guided 1-minute 'Unusual Activity' recovery for one account:
    clear Flow's on-device site data in that account's profile
    (site-scoped — the Google sign-in stays), then re-probe the
    login. Recovered -> the account is 'active' again and the queue
    can resume on it. Not recovered -> the manual browser steps
    are returned (site-info icon -> Cookies and site data ->
    Manage on-device site data -> Flow entries delete -> reload).
    Refuses while a generation is running (the profile is in use)
    or a login window is open."""
    acct = _flow_account_by_id(account_id)
    if acct is None:
        raise HTTPException(status_code=404, detail="account not found")
    if _google_browser.login_window_open():
        raise HTTPException(
            status_code=409,
            detail="Google login browser khula hai — pehle band karein",
        )
    if _IMAGE_GEN_LOCK.locked():
        raise HTTPException(
            status_code=409,
            detail="Generation chal rahi hai — khatam hone par recover karein",
        )
    try:
        cleared = _flow_provider.clear_site_data(
            profile_dir=acct["profile_dir"]
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:300])
    _FLOW_STATUS_CACHE["at"] = 0.0
    try:
        login = _flow_provider.check_login(
            profile_dir=acct["profile_dir"]
        )
    except Exception as exc:
        return {
            "recovered": False,
            "cleared": cleared,
            "detail": str(exc)[:300],
            "manual_steps": _flow_hardening.RECOVERY_STEPS,
        }
    recovered = bool(
        login.get("logged_in") and not login.get("unusual_activity")
    )
    if recovered:
        _flow_set_account_status(account_id, "active")
    return {
        "recovered": recovered,
        "cleared": cleared,
        "logged_in": bool(login.get("logged_in")),
        "unusual_activity": bool(login.get("unusual_activity")),
        "detail": login.get("detail", ""),
        "manual_steps": (
            [] if recovered else _flow_hardening.RECOVERY_STEPS
        ),
        "tip": "" if recovered else _flow_hardening.RECOVERY_TIP,
    }


@app.post("/api/flow/settings")
def flow_settings(body: FlowSettingsIn) -> dict:
    """Fast-mode concurrency (1–4). 1 = sequential (aaj tak ka
    behaviour); 2–4 = parallel — lekin asal parallel sirf utne
    accounts jitne connected hain (max 3)."""
    n = body.fast_concurrency
    if n < _flow_hardening.FLOW_FAST_MIN_CONCURRENCY or (
        n > _flow_hardening.FLOW_FAST_MAX_CONCURRENCY
    ):
        raise HTTPException(
            status_code=400,
            detail="fast_concurrency 1 se 4 ke beech hona chahiye",
        )
    with db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, note) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (
                "flow_fast_concurrency",
                str(n),
                "Flow Fast mode: kitni generations ek saath chalein.",
            ),
        )
    return {"fast_concurrency": n}


@app.get("/api/flow/queues")
def flow_queue_history() -> dict:
    """Queue History: past bulk runs (newest first), each with its
    provider, per-status counts and created time. A batch is the
    jobs that share one batch_id (Slice 5); single regenerates
    (batch_id NULL) are not a queue and do not appear."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT j.batch_id, MIN(j.created_at) AS created_at,
                   MAX(j.provider) AS provider,
                   s.id AS script_id, s.topic AS topic,
                   SUM(CASE WHEN j.status = 'done' THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN j.status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN j.status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
                   SUM(CASE WHEN j.status IN ('queued', 'running') THEN 1 ELSE 0 END) AS pending,
                   COUNT(*) AS total
            FROM jobs j LEFT JOIN scenes sc ON sc.id = j.scene_id
            LEFT JOIN scripts s ON s.id = sc.script_id
            WHERE j.kind = 'image-generate' AND j.batch_id IS NOT NULL
            GROUP BY j.batch_id ORDER BY created_at DESC LIMIT 20
            """
        ).fetchall()
    return {
        "queues": [
            {
                "batch_id": r["batch_id"],
                "created_at": r["created_at"],
                "provider": r["provider"],
                "script_id": r["script_id"],
                "topic": r["topic"],
                "done": r["done"],
                "failed": r["failed"],
                "blocked": r["blocked"],
                "pending": r["pending"],
                "total": r["total"],
            }
            for r in rows
        ]
    }


@app.get("/api/flow/queues/{batch_id}/images.zip")
def flow_queue_zip(batch_id: str):
    """Re-download one past queue's finished images as a ZIP
    (scene order, scene-01… — same naming as the approved-images
    ZIP). 404 for an unknown batch, 400 when the batch has no
    finished image yet."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT j.output_path, sc.position AS position
            FROM jobs j JOIN scenes sc ON sc.id = j.scene_id
            WHERE j.kind = 'image-generate' AND j.batch_id = ?
              AND j.status = 'done' AND j.output_path IS NOT NULL
            ORDER BY sc.position, j.id
            """,
            (batch_id,),
        ).fetchall()
        any_job = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["n"]
    if not any_job:
        raise HTTPException(status_code=404, detail="queue not found")
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="is queue ki koi image abhi ready nahi hai",
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, r in enumerate(rows, start=1):
            path = media_path(r["output_path"])
            if path is None or not path.is_file():
                continue
            ext = path.suffix or ".png"
            zf.writestr(f"scene-{i:02d}{ext}", path.read_bytes())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="flow-queue-{batch_id}.zip"'
            )
        },
    )


@app.post("/api/scripts/{script_id}/queue/pause")
def flow_queue_pause(script_id: int) -> dict:
    """Pause this script's image queue (persistent — a restart
    does not lose the pause). The job already generating finishes;
    the rest stay queued for resume."""
    with db() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
    _flow_set_queue_paused(script_id, True)
    return {"script_id": script_id, "paused": True}


@app.post("/api/scripts/{script_id}/queue/resume")
def flow_queue_resume(
    script_id: int, background_tasks: BackgroundTasks
) -> dict:
    """Resume a paused queue: the flag clears and the worker
    re-runs the script's queued jobs (same jobs, same batch)."""
    with db() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        queued = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE kind = 'image-generate'"
            " AND scene_id IN (SELECT id FROM scenes WHERE script_id = ?)"
            " AND status = 'queued'",
            (script_id,),
        ).fetchone()["n"]
    _flow_set_queue_paused(script_id, False)
    if queued:
        background_tasks.add_task(process_image_jobs, script_id)
    return {
        "script_id": script_id,
        "paused": False,
        "resumed": bool(queued),
        "queued_jobs": queued,
    }


@app.get("/api/scripts/{script_id}/queue-state")
def flow_queue_state(script_id: int) -> dict:
    """Is this script's image queue paused?"""
    with db() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
    return {"script_id": script_id, "paused": _flow_queue_paused(script_id)}


@app.post("/api/flow/resolve-chain")
def flow_resolve_chain(body: ChainResolveIn) -> dict:
    """Preview #name / @name chaining for one prompt against a
    niche's locked Vault characters: which markers resolve (and to
    what), which names the Vault does not have. No generation
    happens here — the worker resolves the same way at run time."""
    characters: list[dict] = []
    niche_name: str | None = None
    if body.niche_id is not None:
        with db() as conn:
            resolved = _vault_resolve(conn, body.niche_id)
        niche_name = resolved["niche_name"]
        characters = resolved["mains"] + resolved["secondaries"]
    result = _flow_hardening.resolve_chain_syntax(
        body.prompt, characters
    )
    return {
        "prompt": result["prompt"],
        "resolved": result["resolved"],
        "unknown": result["unknown"],
        "niche_id": body.niche_id,
        "niche_name": niche_name,
    }


# --- Phase 4 slice 3: image verification + use ---------------------------


@app.post("/api/scenes/{scene_id}/attach-image", status_code=201)
def attach_image_to_scene(scene_id: int, body: AttachImageIn) -> dict:
    """Attach an uploaded image to a scene, so it enters the same
    approve / reject flow as a generated image (the upload path works
    with no Gemini key at all)."""
    with db() as conn:
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if scene is None:
            raise HTTPException(status_code=404, detail="scene not found")
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (scene["script_id"],)
        ).fetchone()
        asset = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (body.asset_id,)
        ).fetchone()
        if asset is None or asset["kind"] != "image":
            raise HTTPException(
                status_code=404, detail="image asset not found"
            )
        if asset["project_id"] != script["project_id"]:
            raise HTTPException(
                status_code=400,
                detail="ye image is project ki nahi hai",
            )
        if asset["placeholder"]:
            raise HTTPException(
                status_code=400,
                detail="placeholder title card attach nahi ho sakta",
            )
        conn.execute(
            "INSERT OR IGNORE INTO scene_images"
            " (scene_id, asset_id, source, created_at)"
            " VALUES (?, ?, 'uploaded', ?)",
            (scene_id, body.asset_id, utcnow()),
        )
        return {
            "scene_id": scene_id,
            "asset_id": body.asset_id,
            "path": asset["path"],
            "source": "uploaded",
            "verdict": (
                _verdict_for_asset(conn, body.asset_id) or {}
            ).get("verdict", "pending"),
        }


@app.get("/api/scripts/{script_id}/images")
def list_script_images(script_id: int) -> dict:
    """Verification list: every scene with its candidate images and
    their verdicts (approved / rejected / pending)."""
    with db() as conn:
        return script_images_detail(conn, script_id)


def _set_verdict(conn, asset_id: int, verdict: str, reason: str) -> dict:
    """Record Ale's verdict for one image (one verdict per image;
    deciding again replaces the old one). Returns the verdict row."""
    link = conn.execute(
        "SELECT * FROM scene_images WHERE asset_id = ? ORDER BY id DESC"
        " LIMIT 1",
        (asset_id,),
    ).fetchone()
    if link is None:
        raise HTTPException(
            status_code=400,
            detail="is image ka koi scene nahi — pehle scene se jodein",
        )
    now = utcnow()
    conn.execute(
        "INSERT INTO image_verdicts"
        " (asset_id, scene_id, verdict, reason, decided_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(asset_id) DO UPDATE SET scene_id = excluded.scene_id,"
        " verdict = excluded.verdict, reason = excluded.reason,"
        " decided_at = excluded.decided_at",
        (asset_id, link["scene_id"], verdict, reason, now),
    )
    return {
        "asset_id": asset_id,
        "scene_id": link["scene_id"],
        "verdict": verdict,
        "reason": reason,
        "decided_at": now,
    }


@app.post("/api/images/{asset_id}/approve")
def approve_image(asset_id: int) -> dict:
    """Approve one image: only approved images may enter a timeline
    via use-approved. Approving again is a no-op (same verdict)."""
    with db() as conn:
        asset = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None or asset["kind"] != "image":
            raise HTTPException(
                status_code=404, detail="image asset not found"
            )
        return _set_verdict(conn, asset_id, "approved", "")


@app.post("/api/images/{asset_id}/reject")
def reject_image(asset_id: int, body: RejectImageIn) -> dict:
    """Reject one image, with an optional short reason for the record.
    A rejected image never enters a timeline; it can be regenerated."""
    with db() as conn:
        asset = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None or asset["kind"] != "image":
            raise HTTPException(
                status_code=404, detail="image asset not found"
            )
        return _set_verdict(
            conn, asset_id, "rejected", (body.reason or "").strip()
        )


@app.post("/api/images/{asset_id}/regenerate", status_code=202)
def regenerate_image(asset_id: int, background_tasks: BackgroundTasks) -> dict:
    """Re-queue generation for the rejected image's scene. The daily
    quota is respected exactly like a bulk generate (limit → a failed
    job with the plain limit message), and a scene that is already
    queued/running is not queued twice. No key → the job fails
    honestly with the key message on its turn."""
    with db() as conn:
        asset = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None or asset["kind"] != "image":
            raise HTTPException(
                status_code=404, detail="image asset not found"
            )
        link = conn.execute(
            "SELECT * FROM scene_images WHERE asset_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (asset_id,),
        ).fetchone()
        if link is None:
            raise HTTPException(
                status_code=400,
                detail="is image ka koi scene nahi — pehle scene se jodein",
            )
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (link["scene_id"],)
        ).fetchone()
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (scene["script_id"],)
        ).fetchone()
        # Regenerate on the SAME provider that made the rejected image
        # (Canvas images re-run on Canvas, API images on the API).
        prev = conn.execute(
            "SELECT provider FROM jobs WHERE kind = 'image-generate'"
            " AND scene_id = ? ORDER BY id DESC LIMIT 1",
            (link["scene_id"],),
        ).fetchone()
        provider = (prev["provider"] if prev else None) or "api"
        outcome, job_id = _queue_one_image_job(
            conn, dict(script), dict(scene), utcnow(), force=True,
            provider=provider,
        )
        if outcome == "already_queued":
            raise HTTPException(
                status_code=409,
                detail="is scene ki image pehle se queue me hai",
            )
        script_id = script["id"]
    if outcome == "queued":
        background_tasks.add_task(process_image_jobs, script_id)
    return {
        "asset_id": asset_id,
        "scene_id": link["scene_id"],
        "script_id": script_id,
        "job_id": job_id,
        "provider": provider,
        "outcome": outcome,
        "message": (
            GEMINI_LIMIT_MSG
            if outcome == "limit_blocked"
            else GEMINI_REGENERATE_MSG
        ),
    }


@app.post("/api/scripts/{script_id}/use-approved")
def use_approved_images(script_id: int) -> dict:
    """Build (or rebuild) the project's CineCut timeline from the
    script's APPROVED images, in scene order. Scenes with no approved
    image keep the old timeline's clip at that position, or get a
    clearly-marked placeholder title card when there is none. The
    response says plainly which scenes were filled and which were
    not. At least one approved image is required — an all-placeholder
    timeline is not built here (auto-sync / one-click run already do
    that, and say so)."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        script = dict(script)
        project_id = script["project_id"]
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
        scenes = [dict(s) for s in scenes]
        if not scenes:
            raise HTTPException(
                status_code=400, detail="script me koi scene nahi hai"
            )
        approved = [
            _latest_approved_image(conn, s["id"]) for s in scenes
        ]
        if not any(approved):
            raise HTTPException(
                status_code=400,
                detail="koi approved image nahi — pehle kisi image ko"
                " approve karein",
            )
        # Voiceover duration drives the beat split; without one, 3 s
        # per clip (same rule as auto-sync).
        vo = conn.execute(
            "SELECT * FROM assets WHERE project_id = ? AND kind = 'voice'"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        vo_duration = 0.0
        vo_asset_id = None
        if vo is not None:
            vo_asset_id = vo["id"]
            vo_duration = probe_duration(DATA_DIR / vo["path"])
        if vo_duration > 0:
            durations = beat_durations(
                [len(s["text"].split()) for s in scenes], vo_duration
            )
        else:
            durations = [DEFAULT_CLIP_S] * len(scenes)
        # Old timeline's clips (by position) survive for scenes with
        # no approved image — the timeline is rebuilt, not emptied.
        old_clips: list[dict] = []
        old = conn.execute(
            "SELECT id FROM timelines WHERE project_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if old is not None:
            old_clips = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM clips WHERE timeline_id = ?"
                    " ORDER BY position, id",
                    (old["id"],),
                ).fetchall()
            ]
        prev = old
        style_id = None
        caption_id = None
        if prev is not None:
            row = conn.execute(
                "SELECT style_dna_id, caption_style_id FROM timelines"
                " WHERE id = ?",
                (prev["id"],),
            ).fetchone()
            if row is not None:
                style_id = row["style_dna_id"]
                caption_id = row["caption_style_id"]
        clip_assets: list[dict] = []
        filled: list[int] = []
        unfilled: list[int] = []
        stamp = int(time.time())
        for i, scene in enumerate(scenes):
            if approved[i] is not None:
                clip_assets.append(
                    {"asset_id": approved[i]["asset_id"], "placeholder": 0}
                )
                filled.append(i + 1)
            elif i < len(old_clips):
                clip_assets.append(
                    {"asset_id": old_clips[i]["asset_id"], "placeholder": 0}
                )
                unfilled.append(i + 1)
            else:
                rel = make_placeholder_image(
                    project_id, stamp, i, scene["text"]
                )
                cur = conn.execute(
                    "INSERT INTO assets (project_id, kind, path,"
                    " placeholder, created_at) VALUES (?, 'image', ?, 1, ?)",
                    (project_id, rel, utcnow()),
                )
                clip_assets.append(
                    {"asset_id": cur.lastrowid, "placeholder": 1}
                )
                unfilled.append(i + 1)
        # Replace the project's timelines (same FK-safe pattern as
        # auto-sync: clear runs' timeline links first).
        conn.execute(
            "UPDATE runs SET timeline_id = NULL WHERE timeline_id IN"
            " (SELECT id FROM timelines WHERE project_id = ?)",
            (project_id,),
        )
        old_all = conn.execute(
            "SELECT id FROM timelines WHERE project_id = ?", (project_id,)
        ).fetchall()
        for row in old_all:
            conn.execute("DELETE FROM clips WHERE timeline_id = ?", (row["id"],))
            conn.execute("DELETE FROM timelines WHERE id = ?", (row["id"],))
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO timelines (project_id, style_dna_id,"
            " caption_style_id, vo_duration_s, vo_asset_id, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                style_id,
                caption_id,
                round(sum(durations), 3),
                vo_asset_id,
                now,
                now,
            ),
        )
        timeline_id = cur.lastrowid
        start = 0.0
        for i, scene in enumerate(scenes):
            end = round(start + durations[i], 3)
            conn.execute(
                "INSERT INTO clips (timeline_id, asset_id, position,"
                " start_s, end_s, caption_text, effect)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    timeline_id,
                    clip_assets[i]["asset_id"],
                    i,
                    round(start, 3),
                    end,
                    scene["text"],
                    effect_for_position(i),
                ),
            )
            start = end
        detail = timeline_detail(conn, timeline_id)
        total = len(scenes)
        summary = (
            f"{len(filled)} of {total} scenes filled"
            + (
                f" — scenes {', '.join(str(n) for n in unfilled)}"
                " still need an image"
                if unfilled
                else " — all scenes have an approved image"
            )
        )
        return {
            "script_id": script_id,
            "timeline": detail,
            "filled_scene_positions": filled,
            "unfilled_scene_positions": unfilled,
            "summary": summary,
        }


@app.get("/api/scripts/{script_id}/images.zip")
def download_approved_images_zip(script_id: int) -> StreamingResponse:
    """ZIP of the script's APPROVED images only (latest approved per
    scene), named by timecode + scene number (AutoCut Gemini Bulk
    parity: filenames auto-match the timecodes). The timecode is the
    scene's cumulative start in the script's estimated timeline
    (scene duration_s values, the same estimates script-beat sync
    uses). 400 when nothing is approved yet — an empty ZIP would be
    a fake deliverable."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
        files: list[tuple[str, Path]] = []
        start = 0.0
        for scene in scenes:
            approved = _latest_approved_image(conn, scene["id"])
            if approved is not None:
                disk = DATA_DIR / approved["asset_path"]
                if disk.is_file():
                    ext = disk.suffix.lower() or ".png"
                    mm = int(start // 60)
                    ss = int(start % 60)
                    files.append(
                        (
                            f"{mm:02d}:{ss:02d}-scene-"
                            f"{scene['position'] + 1:02d}{ext}",
                            disk,
                        )
                    )
            start += float(scene["duration_s"] or 0)
        if not files:
            raise HTTPException(
                status_code=400,
                detail="koi approved image nahi — pehle kisi image ko"
                " approve karein",
            )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, disk in files:
            zf.write(disk, arcname=name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=visualforge-approved-script-"
                f"{script_id}.zip"
            )
        },
    )


@app.put("/api/scenes/{scene_id}")
def update_scene(scene_id: int, body: SceneUpdate) -> dict:
    with db() as conn:
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if scene is None:
            raise HTTPException(status_code=404, detail="scene not found")
        text = body.text.strip() if body.text is not None else scene["text"]
        if not text:
            raise HTTPException(status_code=400, detail="scene text khaali nahi ho sakta")
        duration = body.duration_s
        if duration is None and body.text is not None:
            # Text changed: re-estimate the scene length from word count.
            duration = estimate_duration_s(text)
        if duration is not None and duration <= 0:
            raise HTTPException(
                status_code=400, detail="duration 0 se zyada honi chahiye"
            )
        image_prompt = body.image_prompt
        if image_prompt is None and body.text is not None:
            # Text changed: rebuild the prompt from the new text.
            script = conn.execute(
                "SELECT project_id FROM scripts WHERE id = ?",
                (scene["script_id"],),
            ).fetchone()
            style = (
                resolve_script_style(conn, script["project_id"])
                if script
                else None
            )
            char = (
                get_character(conn, script["project_id"]) if script else None
            )
            image_prompt = build_image_prompt(
                text, style, char["name"] if char else None
            )
        conn.execute(
            "UPDATE scenes SET text = ?, image_prompt = ?, duration_s = ?"
            " WHERE id = ?",
            (
                text,
                image_prompt if image_prompt is not None else scene["image_prompt"],
                duration if duration is not None else scene["duration_s"],
                scene_id,
            ),
        )
        conn.execute(
            "UPDATE scripts SET updated_at = ? WHERE id = ?",
            (utcnow(), scene["script_id"]),
        )
        row = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
    return dict(row)


@app.post("/api/scenes/{scene_id}/regenerate-prompt")
def regenerate_scene_prompt(scene_id: int) -> dict:
    """Rebuild one scene's image prompt from its current text (template
    only — no AI call): style + main character are re-applied."""
    with db() as conn:
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if scene is None:
            raise HTTPException(status_code=404, detail="scene not found")
        script = conn.execute(
            "SELECT project_id FROM scripts WHERE id = ?",
            (scene["script_id"],),
        ).fetchone()
        style = resolve_script_style(conn, script["project_id"])
        char = get_character(conn, script["project_id"])
        prompt = build_image_prompt(
            scene["text"], style, char["name"] if char else None
        )
        conn.execute(
            "UPDATE scenes SET image_prompt = ? WHERE id = ?",
            (prompt, scene_id),
        )
        row = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
    return dict(row)


@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int) -> dict:
    with db() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        # Runs reference their script (FK): deleting a script with runs
        # would fail the key. A deleted script's runs are meaningless,
        # so remove them with their step jobs first (their MP4 files
        # stay on disk under studio/data/renders/).
        run_rows = conn.execute(
            "SELECT id FROM runs WHERE script_id = ?", (script_id,)
        ).fetchall()
        for r in run_rows:
            conn.execute("DELETE FROM jobs WHERE run_id = ?", (r["id"],))
            conn.execute("DELETE FROM runs WHERE id = ?", (r["id"],))
        conn.execute("DELETE FROM scenes WHERE script_id = ?", (script_id,))
        conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
    return {"deleted": True, "id": script_id}


@app.post("/api/scripts/{script_id}/resplit-sentences")
def resplit_script_sentences(script_id: int) -> dict:
    """Re-split an existing script's scenes into one scene per
    sentence (the sentence-level split — har sentence ke saath visual
    change). Old scenes are replaced; their VisualForge candidate
    links (scene_images) go with them, and verdicts keep their asset
    but lose the dead scene link. Image-generate jobs are history and
    are left alone. The script text itself never changes."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        script = dict(script)
        scenes = split_script(script["full_text"])
        if not scenes:
            raise HTTPException(
                status_code=400, detail="script text khaali hai — kuch likhein"
            )
        style = resolve_script_style(conn, script["project_id"])
        char = get_character(conn, script["project_id"])
        char_name = char["name"] if char else None
        old_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM scenes WHERE script_id = ?", (script_id,)
            ).fetchall()
        ]
        if old_ids:
            q = ",".join("?" * len(old_ids))
            conn.execute(
                f"DELETE FROM scene_images WHERE scene_id IN ({q})", old_ids
            )
            conn.execute(
                f"UPDATE image_verdicts SET scene_id = NULL"
                f" WHERE scene_id IN ({q})",
                old_ids,
            )
        conn.execute("DELETE FROM scenes WHERE script_id = ?", (script_id,))
        now = utcnow()
        for i, scene_text in enumerate(scenes):
            conn.execute(
                "INSERT INTO scenes (script_id, position, text,"
                " image_prompt, duration_s) VALUES (?, ?, ?, ?, ?)",
                (
                    script_id,
                    i,
                    scene_text,
                    build_image_prompt(scene_text, style, char_name),
                    estimate_duration_s(scene_text),
                ),
            )
        conn.execute(
            "UPDATE scripts SET updated_at = ? WHERE id = ?", (now, script_id)
        )
        return script_detail(conn, script_id)


# Phase 5 slice 1 (VoiceForge): the free Microsoft Edge-TTS voice
# library. These are REAL Microsoft Neural voice IDs from the Edge-TTS
# catalogue (en-US / en-GB / hi-IN / ur-PK) — no invented names. The
# live list is tried first whenever Edge-TTS is reachable; on a PC
# where it is blocked (like this build VM) the curated list below is
# returned instead, honestly marked unverified here.
CURATED_TTS_VOICES: list[dict] = [
    {"voice_id": "en-US-AriaNeural", "name": "Aria", "locale": "en-US", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-US-GuyNeural", "name": "Guy", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-US-JennyNeural", "name": "Jenny", "locale": "en-US", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-US-DavisNeural", "name": "Davis", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-US-ChristopherNeural", "name": "Christopher", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-US-EmmaNeural", "name": "Emma", "locale": "en-US", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-US-EricNeural", "name": "Eric", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-US-MichelleNeural", "name": "Michelle", "locale": "en-US", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-US-RogerNeural", "name": "Roger", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-US-SteffanNeural", "name": "Steffan", "locale": "en-US", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-GB-SoniaNeural", "name": "Sonia", "locale": "en-GB", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-GB-RyanNeural", "name": "Ryan", "locale": "en-GB", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-GB-LibbyNeural", "name": "Libby", "locale": "en-GB", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-GB-MaisieNeural", "name": "Maisie", "locale": "en-GB", "language": "English", "gender": "Female", "verified_here": False},
    {"voice_id": "en-GB-ThomasNeural", "name": "Thomas", "locale": "en-GB", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "en-GB-OliverNeural", "name": "Oliver", "locale": "en-GB", "language": "English", "gender": "Male", "verified_here": False},
    {"voice_id": "hi-IN-MadhurNeural", "name": "Madhur", "locale": "hi-IN", "language": "Hindi", "gender": "Male", "verified_here": False},
    {"voice_id": "hi-IN-SwaraNeural", "name": "Swara", "locale": "hi-IN", "language": "Hindi", "gender": "Female", "verified_here": False},
    {"voice_id": "ur-PK-AsadNeural", "name": "Asad", "locale": "ur-PK", "language": "Urdu", "gender": "Male", "verified_here": False},
    {"voice_id": "ur-PK-UzmaNeural", "name": "Uzma", "locale": "ur-PK", "language": "Urdu", "gender": "Female", "verified_here": False},
]

# Short sample line per language for voice previews.
PREVIEW_TEXTS = {
    "English": "Hello, this is a sample of my voice.",
    "Hindi": "Namaste, yeh meri awaaz ka namuna hai.",
    "Urdu": "Assalam-o-Alaikum, ye meri awaz ka sample hai.",
}


def _language_of(locale: str) -> str:
    """Display language for an Edge-TTS locale (en-US -> English)."""
    lang = (locale or "").split("-")[0].lower()
    return {"en": "English", "hi": "Hindi", "ur": "Urdu"}.get(lang, locale or "Other")


def _default_tts_voice() -> str:
    """The saved default free TTS voice (VoiceForge favourite)."""
    try:
        with db() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'default_tts_voice'"
            ).fetchone()
        if row and (row["value"] or "").strip():
            return row["value"].strip()
    except Exception:  # noqa: BLE001 - a missing setting is not fatal
        pass
    return "en-US-AriaNeural"


async def _live_tts_voices() -> list[dict] | None:
    """The real Edge-TTS voice list, or None when it is not reachable
    here (not installed, or the network blocks it)."""
    try:
        import edge_tts  # noqa: PLC0415 - optional dependency, lazy import
    except ImportError:
        return None
    try:
        voices = await edge_tts.list_voices()
    except Exception:  # noqa: BLE001 - any failure means "not available here"
        return None
    out: list[dict] = []
    for v in voices:
        short = v.get("ShortName", "")
        if not short:
            continue
        locale = v.get("Locale", "")
        name = short
        if locale and short.startswith(locale + "-"):
            name = short[len(locale) + 1 :]
        if name.endswith("Neural"):
            name = name[: -len("Neural")]
        out.append(
            {
                "voice_id": short,
                "name": name,
                "locale": locale,
                "language": _language_of(locale),
                "gender": v.get("Gender", ""),
                "verified_here": True,
            }
        )
    return out


# v0.14.1 fix round 2 — Edge-TTS: ONE availability verdict, shared by
# the list, the Generate button and the voice preview.
# Root cause of the mismatch Ali saw: the voice LIST is a plain HTTPS
# GET (edge_tts.list_voices) while voice GENERATION is a WebSocket
# synthesis (edge_tts.Communicate().save()) — two different network
# paths. The list can succeed while synthesis fails, so the UI said
# "reachable — 318 voices" and Generate answered 503 at the same time.
# Now the list endpoint runs the list AND a tiny real synthesis probe;
# `available` is True ONLY when synthesis actually worked here. The
# probe result is cached 10 minutes so the endpoint stays fast.
EDGE_TTS_UNAVAILABLE_MSG = (
    "Edge-TTS yahan nahi chal raha — pehle Setup me Install Requirements"
    " chalao aur launcher restart karo; phir bhi na chale to voiceover"
    " file upload karein (wohi reliable rasta hai)."
)
_EDGE_TTS_STATUS_CACHE: dict = {"at": 0.0, "status": None}


async def _edge_tts_probe(voice_id: str) -> bool:
    """Tiny real synthesis ("Hi") with a live-list voice — True only
    when Edge-TTS can actually make audio here. Capped at 20 s; any
    failure means unavailable. No asset is created (scratch file)."""
    try:
        import edge_tts  # noqa: PLC0415 - optional dependency, lazy import
    except ImportError:
        return False
    probe_dir = DATA_DIR / "tmp"
    probe_dir.mkdir(parents=True, exist_ok=True)
    disk = probe_dir / "_edge_tts_probe.mp3"
    try:
        communicate = edge_tts.Communicate("Hi", voice_id)
        await asyncio.wait_for(communicate.save(str(disk)), timeout=20)
    except Exception:  # noqa: BLE001 - any failure is "unavailable"
        return False
    ok = disk.exists() and disk.stat().st_size > 0
    try:
        disk.unlink()
    except OSError:
        pass
    return ok


async def _edge_tts_status() -> dict:
    """The single Edge-TTS verdict: {available, synthesis_ok,
    list_source, reason, voices}. `available` is True ONLY when the
    synthesis probe worked here — the list and Generate can never
    disagree again."""
    now = time.time()
    cached = _EDGE_TTS_STATUS_CACHE["status"]
    if cached is not None and now - _EDGE_TTS_STATUS_CACHE["at"] < 600:
        return cached
    live = await _live_tts_voices()
    if not live:
        status = {
            "available": False,
            "synthesis_ok": False,
            "list_source": "curated",
            "reason": EDGE_TTS_UNAVAILABLE_MSG,
            "voices": [dict(v) for v in CURATED_TTS_VOICES],
        }
    else:
        ok = await _edge_tts_probe(live[0]["voice_id"])
        status = {
            "available": ok,
            "synthesis_ok": ok,
            "list_source": "live",
            "reason": "" if ok else EDGE_TTS_UNAVAILABLE_MSG,
            "voices": live,
        }
    _EDGE_TTS_STATUS_CACHE["at"] = now
    _EDGE_TTS_STATUS_CACHE["status"] = status
    return status


@app.get("/api/tts-voices")
async def list_tts_voices() -> dict:
    """Free Microsoft Edge-TTS voice library — ONE verdict (v0.14.1 fix
    round 2). `available` is True only when a real synthesis probe
    worked here, so the list and the Generate button can never disagree.
    The live list is tried first; when Edge-TTS is blocked on this PC
    (or not installed), the curated list of real Microsoft voice IDs is
    returned instead, honestly marked unverified here. The saved
    default voice rides along so the UI can show the favourite.
    """
    status = await _edge_tts_status()
    default_voice = _default_tts_voice()
    with db() as conn:
        providers = _voice_providers_list(conn)
    return {
        "available": status["available"],
        "synthesis_ok": status["synthesis_ok"],
        "list_source": status["list_source"],
        "reason": status["reason"],
        "curated": status["list_source"] == "curated",
        "default_voice": default_voice,
        "voices": status["voices"],
        "providers": providers,
    }


async def _tts_preview_save(voice_id: str, text: str) -> Path:
    """Generate one short voice sample and cache it under studio/data/
    tts-previews/ (one file per voice, gitignored) so a preview is
    generated once and replayed free. Raises RuntimeError with the
    same plain wording as _tts_save when Edge-TTS cannot run."""
    try:
        import edge_tts  # noqa: PLC0415 - optional dependency, lazy import
    except ImportError:
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    folder = DATA_DIR / "tts-previews"
    folder.mkdir(parents=True, exist_ok=True)
    disk = folder / f"{safe_filename(voice_id)}.mp3"
    if disk.exists() and disk.stat().st_size > 0:
        return disk
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(disk))
    except Exception:  # noqa: BLE001 - any TTS failure is "unavailable"
        if disk.exists():
            disk.unlink()
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    if not disk.exists() or disk.stat().st_size == 0:
        raise RuntimeError(EDGE_TTS_UNAVAILABLE_MSG)
    return disk


@app.post("/api/tts-voices/{voice_id}/preview", status_code=201)
async def preview_tts_voice(voice_id: str) -> dict:
    """A short sample of one library voice, cached for replay. The
    voice must be in the library (curated list, or the live list when
    it is reachable). Where Edge-TTS is blocked this returns HTTP 503
    with the same plain message as the TTS endpoint — no fake audio."""
    known = {v["voice_id"]: v for v in CURATED_TTS_VOICES}
    live = await _live_tts_voices()
    if live:
        for v in live:
            known.setdefault(v["voice_id"], v)
    voice = known.get(voice_id)
    if voice is None:
        raise HTTPException(status_code=404, detail="voice not in the library")
    text = PREVIEW_TEXTS.get(voice["language"], PREVIEW_TEXTS["English"])
    cache = DATA_DIR / "tts-previews" / f"{safe_filename(voice_id)}.mp3"
    cached = cache.exists() and cache.stat().st_size > 0
    try:
        disk = await _tts_preview_save(voice_id, text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    rel = f"tts-previews/{disk.name}"
    return {
        "voice_id": voice_id,
        "path": rel,
        "url": media_url(rel),
        "cached": cached,
    }


def _audio_reader_ok() -> bool:
    """Can this PC really transcribe? Probe the exact path the worker
    uses: ffmpeg decode + tiny model on 0.2 s of silence. Result is
    cached for the life of the process (a model load takes ~1 s). The
    old probe called faster-whisper's decode_audio, which is broken
    against PyAV 19.0.2 — the worker never uses it any more."""
    if _TRANSCRIBE_PROBE["ok"] is not None:
        return bool(_TRANSCRIBE_PROBE["ok"])
    import os
    import struct
    import tempfile
    import wave

    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(struct.pack("<3200h", *([0] * 3200)))
        _transcribe_audio(path, "tiny")
        _TRANSCRIBE_PROBE.update({"ok": True, "error": None})
        return True
    except Exception as exc:  # noqa: BLE001 - probe result, not a crash
        _TRANSCRIBE_PROBE.update({"ok": False, "error": str(exc)})
        return False
    finally:
        if path:
            try:
                Path(path).unlink()
            except OSError:
                pass


# Phase 5 slice 2: the PyAV bug is fixed by NOT using faster-whisper's
# decode_audio at all. faster-whisper 1.2.1 passes a metadata_errors
# kwarg to av.open that PyAV 19.0.2 rejects, so every transcription
# failed even though the engine and models were present. ffmpeg (already
# a dependency) decodes to 16 kHz mono float32 samples instead, and the
# numpy array goes straight into WhisperModel.transcribe. Verified live
# on the 45.71 s Eiffel VO: 143 words, timestamps real.
_TRANSCRIBE_PROBE: dict = {"ok": None, "error": None}


def _cached_whisper_models() -> list[str]:
    """Whisper models already cached on this PC — nothing is ever
    downloaded. Scans the Hugging Face hub cache (Systran faster-whisper
    + large-v3-turbo) and the legacy openai-whisper cache."""
    models: list[str] = []
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    if cache.is_dir():
        for d in sorted(cache.iterdir()):
            if d.name.startswith("models--Systran--faster-whisper-"):
                models.append(d.name[len("models--Systran--faster-whisper-"):])
            elif d.name.startswith("models--mobiuslabsgmbh--faster-whisper-"):
                models.append(d.name[len("models--mobiuslabsgmbh--faster-whisper-"):])
    legacy = Path.home() / ".cache" / "whisper"
    if legacy.is_dir():
        models += sorted(
            p.stem for p in legacy.glob("*.pt") if p.stem not in models
        )
    return models


def _decode_audio_ffmpeg(path) -> object:
    """Decode any audio/video file to 16 kHz mono float32 samples via
    ffmpeg. Raises RuntimeError with a plain message when ffmpeg fails
    or the file has no audio."""
    import numpy as np  # noqa: PLC0415 - lazy, optional dep

    cmd = [
        "ffmpeg", "-nostdin", "-threads", "0", "-i", str(path),
        "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
        "-ar", "16000", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"ffmpeg audio decode nahi chala: {exc}")
    if proc.returncode != 0:
        raise RuntimeError(
            "is file me audio nahi mila ya format samajh nahi aaya —"
            " mp3/wav/m4a/ogg/flac/mp4 dein"
        )
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size == 0:
        raise RuntimeError("is file me audio nahi mila — khaali file hai")
    return audio


def _transcribe_audio(path, model: str) -> tuple[list[dict], str, float]:
    """Run local faster-whisper on one file. Returns
    (segments, language, duration_s); segments carry word timestamps.

    local_files_only=True — the model must already be cached; a missing
    model is a plain error, never a download.
    """
    audio = _decode_audio_ffmpeg(path)
    duration_s = round(len(audio) / 16000, 3)
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError:
        raise RuntimeError(
            "faster-whisper app me installed nahi hai —"
            " pip install faster-whisper"
        )
    try:
        model_obj = WhisperModel(
            model, device="cpu", compute_type="int8", local_files_only=True
        )
        segments, info = model_obj.transcribe(audio, word_timestamps=True)
        out: list[dict] = []
        for seg in segments:
            out.append(
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text,
                    "words": [
                        {
                            "word": w.word,
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                        }
                        for w in (seg.words or [])
                    ],
                }
            )
        return out, (info.language or ""), duration_s
    except Exception as exc:  # noqa: BLE001 - surfaced as a plain job error
        raise RuntimeError(f"Whisper transcription fail ho gayi: {exc}")


# Same probe as a string, for the system-python3 case (the app venv may
# not have faster-whisper even when system python3 does). Tests the
# exact path the worker uses: ffmpeg decode + tiny model on 0.2 s of
# silence. No download, no fake success.
_AUDIO_PROBE_CODE = """
import struct, subprocess, sys, tempfile, wave
import numpy as np
fd, p = tempfile.mkstemp(suffix='.wav')
import os; os.close(fd)
w = wave.open(p, 'wb'); w.setnchannels(1); w.setsampwidth(2)
w.setframerate(16000); w.writeframes(struct.pack('<3200h', *([0]*3200))); w.close()
out = subprocess.run(['ffmpeg','-nostdin','-i',p,'-f','s16le','-ac','1',
    '-acodec','pcm_s16le','-ar','16000','-'], capture_output=True, check=True).stdout
audio = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0
from faster_whisper import WhisperModel
m = WhisperModel('tiny', device='cpu', compute_type='int8', local_files_only=True)
segs, info = m.transcribe(audio, word_timestamps=True)
list(segs); print('audio-ok')
"""


@app.get("/api/whisper-status")
def whisper_status() -> dict:
    """Local Whisper availability — check only, never downloads anything.

    Reports whether faster-whisper / openai-whisper is importable, whether
    a whisper CLI binary exists, and which models are already cached on
    this PC (e.g. tiny / small / large-v3-turbo under the Hugging Face
    cache. Transcription runs locally via POST /api/transcribe; this only answers
    "can this PC transcribe offline for free?".
    """
    engines: list[str] = []
    version = None
    try:
        import faster_whisper  # noqa: PLC0415 - check only, no model load

        engines.append("faster-whisper")
        version = getattr(faster_whisper, "__version__", None)
    except ImportError:
        # The app runs in its own venv; faster-whisper may still be
        # installed in the system Python. Check that too (no install,
        # just a probe) so Settings tells the truth about the PC.
        try:
            probe = subprocess.run(
                [
                    shutil.which("python3") or "python3",
                    "-c",
                    "import faster_whisper;"
                    " print(getattr(faster_whisper, '__version__', ''))",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if probe.returncode == 0:
                engines.append("faster-whisper (system python3)")
                version = (probe.stdout or "").strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        import whisper  # noqa: PLC0415,F401 - check only

        engines.append("openai-whisper")
    except ImportError:
        pass
    models = _cached_whisper_models()
    binary = shutil.which("whisper") or shutil.which("faster-whisper")
    system_only = any("system python3" in e for e in engines)
    # Presence is not readiness: probe the audio reader (see
    # _audio_reader_ok). Importable + cached models can still fail a
    # real transcription when PyAV and faster-whisper disagree.
    audio_ok: bool | None = None
    if any("faster-whisper" in e for e in engines):
        if "faster-whisper" in engines:
            audio_ok = _audio_reader_ok()
        else:
            try:
                probe = subprocess.run(
                    [shutil.which("python3") or "python3", "-c", _AUDIO_PROBE_CODE],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                audio_ok = probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                audio_ok = False
    transcribe_ready = bool(engines) and bool(models) and audio_ok is True
    if transcribe_ready:
        note = (
            "Local Whisper is installed with cached models — offline "
            "transcription can run free on this PC."
        )
    elif engines and models and audio_ok is False:
        note = (
            "Whisper engine + models are present, but a real transcription "
            "probe failed here — see probe_error. No model download is "
            "needed; the environment needs a fix first."
        )
    elif engines and models:
        note = (
            "Local Whisper is installed with cached models — offline "
            "transcription can run free on this PC."
        )
    elif engines:
        note = (
            "A Whisper engine is installed but no model is cached yet — "
            "a model download (with your permission) is needed before "
            "offline transcription works."
        )
    elif models:
        note = (
            "Whisper models are already cached on this PC, but no Whisper "
            "engine is installed in the app — install faster-whisper "
            "before offline transcription works (no model download needed)."
        )
    else:
        note = "No local Whisper engine is installed on this PC."
    if system_only:
        note += (
            " Note: the engine lives in system python3, not the app's own "
            "environment — transcription code must run where it is installed."
        )
    return {
        "available": bool(engines),
        "transcribe_ready": transcribe_ready,
        "audio_reader_ok": audio_ok,
        "probe_error": _TRANSCRIBE_PROBE.get("error"),
        "engines": engines,
        "version": version,
        "models_cached": models,
        "cli_binary": binary,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Phase 5 slice 2: local Whisper transcription (VoiceForge). Free,
# offline, no key, no download — only models already cached on this PC.
# ---------------------------------------------------------------------------

TRANSCRIBE_EXTS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".webm",
}
TRANSCRIBE_DIR = DATA_DIR / "transcribe"
TRANSCRIBE_DIR.mkdir(parents=True, exist_ok=True)


def _transcription_row(row, include_words: bool = True) -> dict:
    detail = dict(row)
    if include_words:
        detail["words"] = json.loads(row["words_json"] or "[]")
        detail["segments"] = json.loads(row["segments_json"] or "[]")
    else:
        detail["word_count"] = len(json.loads(row["words_json"] or "[]"))
    del detail["words_json"]
    del detail["segments_json"]
    return detail


def _fmt_srt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(
            f"{_fmt_srt_timestamp(seg['start'])} -->"
            f" {_fmt_srt_timestamp(seg['end'])}"
        )
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def _segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = _fmt_srt_timestamp(seg["start"]).replace(",", ".")
        end = _fmt_srt_timestamp(seg["end"]).replace(",", ".")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


async def _run_transcription(
    job_id: int, transcription_id: int, src_path: Path, model: str
) -> None:
    """Background worker: decode + transcribe + save. A failure is a
    plain job error, never a fake transcript. A job cancelled while
    queued never starts; a cancel mid-transcription lands as
    'cancelled', not 'failed'."""
    with db() as conn:
        _row = conn.execute(
            "SELECT status FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if _row is None or _row["status"] == "cancelled":
            return
    try:
        segments, language, duration_s = await asyncio.to_thread(
            _transcribe_audio, src_path, model
        )
    except RuntimeError as exc:
        with db() as conn:
            if job_id in _CANCELLED_JOBS:
                _CANCELLED_JOBS.discard(job_id)
                _set_job(conn, job_id, "cancelled", "transcription roki gayi (cancel)")
            else:
                _set_job(conn, job_id, "failed", str(exc))
        return
    words = [w for seg in segments for w in seg["words"]]
    full_text = " ".join(seg["text"].strip() for seg in segments).strip()
    with db() as conn:
        conn.execute(
            "UPDATE transcriptions SET language = ?, duration_s = ?,"
            " full_text = ?, words_json = ?, segments_json = ? WHERE id = ?",
            (
                language,
                duration_s,
                full_text,
                json.dumps(words),
                json.dumps(segments),
                transcription_id,
            ),
        )
        _set_job(conn, job_id, "done")
        conn.execute(
            "UPDATE jobs SET transcription_id = ? WHERE id = ?",
            (transcription_id, job_id),
        )


@app.post("/api/transcribe", status_code=202)
async def transcribe_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model: str = Form("tiny"),
    project_id: int = Form(...),
) -> dict:
    """Transcribe an audio/video file with local Whisper (free, offline).

    Only models already cached on this PC are offered — a model that is
    not cached is a plain 400, never a download. Returns the queued job;
    poll GET /api/projects/{id}/transcriptions for the result.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in TRANSCRIBE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "transcribe ke liye audio/video file dein:"
                f" {', '.join(sorted(TRANSCRIBE_EXTS))}"
            ),
        )
    cached = _cached_whisper_models()
    if model not in cached:
        raise HTTPException(
            status_code=400,
            detail=(
                f"model '{model}' is PC par cached nahi hai"
                + (
                    f" — cached models: {', '.join(cached)}"
                    if cached
                    else " — koi model cached nahi hai"
                )
            ),
        )
    data = await file.read()
    if len(data) > 500 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="file 500 MB se bari hai — chhoti file dein (max 500 MB)",
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        name = f"tr_{int(time.time())}_{safe_filename(file.filename)}"
        disk = TRANSCRIBE_DIR / name
        disk.write_bytes(data)
        rel = f"transcribe/{name}"
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at,"
            " updated_at) VALUES (?, 'transcribe', 'queued', ?, ?)",
            (project_id, utcnow(), utcnow()),
        )
        job_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO transcriptions (project_id, job_id, model, language,"
            " source_filename, source_path, created_at)"
            " VALUES (?, ?, ?, '', ?, ?, ?)",
            (project_id, job_id, model, file.filename or name, rel, utcnow()),
        )
        transcription_id = cur.lastrowid
    background_tasks.add_task(
        _run_transcription, job_id, transcription_id, disk, model
    )
    return {
        "job_id": job_id,
        "transcription_id": transcription_id,
        "status": "queued",
        "model": model,
    }


@app.get("/api/projects/{project_id}/transcriptions")
def list_transcriptions(project_id: int) -> list:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            "SELECT t.*, j.status AS job_status, j.error AS job_error"
            " FROM transcriptions t LEFT JOIN jobs j ON j.id = t.job_id"
            " WHERE t.project_id = ? ORDER BY t.id DESC",
            (project_id,),
        ).fetchall()
        out = []
        for row in rows:
            d = _transcription_row(row, include_words=False)
            d["job_status"] = row["job_status"]
            d["job_error"] = row["job_error"]
            out.append(d)
        return out


@app.get("/api/transcriptions/{transcription_id}")
def get_transcription(transcription_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT t.*, j.status AS job_status, j.error AS job_error"
            " FROM transcriptions t LEFT JOIN jobs j ON j.id = t.job_id"
            " WHERE t.id = ?",
            (transcription_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="transcription not found")
        d = _transcription_row(row)
        d["job_status"] = row["job_status"]
        d["job_error"] = row["job_error"]
        return d


def _transcription_segments(conn, transcription_id: int) -> tuple[dict, list[dict]]:
    row = conn.execute(
        "SELECT t.*, j.status AS job_status FROM transcriptions t"
        " LEFT JOIN jobs j ON j.id = t.job_id WHERE t.id = ?",
        (transcription_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="transcription not found")
    if row["job_status"] != "done":
        raise HTTPException(
            status_code=409,
            detail="transcription abhi tayyar nahi — pehle job complete hone dein",
        )
    return dict(row), json.loads(row["segments_json"] or "[]")


@app.get("/api/transcriptions/{transcription_id}/srt")
def get_transcription_srt(transcription_id: int) -> PlainTextResponse:
    with db() as conn:
        row, segments = _transcription_segments(conn, transcription_id)
        return PlainTextResponse(
            _segments_to_srt(segments),
            headers={
                "Content-Disposition": (
                    f"attachment; filename=transcription-{transcription_id}.srt"
                )
            },
        )


@app.get("/api/transcriptions/{transcription_id}/vtt")
def get_transcription_vtt(transcription_id: int) -> PlainTextResponse:
    with db() as conn:
        row, segments = _transcription_segments(conn, transcription_id)
        return PlainTextResponse(
            _segments_to_vtt(segments),
            headers={
                "Content-Disposition": (
                    f"attachment; filename=transcription-{transcription_id}.vtt"
                )
            },
        )


@app.get("/api/transcriptions/{transcription_id}/txt")
def get_transcription_txt(transcription_id: int) -> PlainTextResponse:
    """Plain-text transcript download (AutoCut transcriber parity:
    SRT / VTT / TXT). Same done-gate as SRT/VTT."""
    with db() as conn:
        row, segments = _transcription_segments(conn, transcription_id)
        return PlainTextResponse(
            (row["full_text"] or "").strip() + "\n",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=transcription-{transcription_id}.txt"
                )
            },
        )


@app.put("/api/transcriptions/{transcription_id}")
def update_transcription(
    transcription_id: int, body: TranscriptionUpdateIn
) -> dict:
    """Edit the transcript's full text (ClipNova 'Edit transcript'
    parity). Only full_text changes — the Whisper words and segments
    stay as transcribed, so SRT/VTT (and any reframe/final render)
    still use the original segments and timings. The UI says this
    on save."""
    text = (body.full_text or "").strip()
    if not text:
        raise HTTPException(
            status_code=400, detail="transcript khaali nahi ho sakta"
        )
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="transcription not found"
            )
        conn.execute(
            "UPDATE transcriptions SET full_text = ? WHERE id = ?",
            (text, transcription_id),
        )
        row = conn.execute(
            "SELECT t.*, j.status AS job_status, j.error AS job_error"
            " FROM transcriptions t LEFT JOIN jobs j ON j.id = t.job_id"
            " WHERE t.id = ?",
            (transcription_id,),
        ).fetchone()
        d = _transcription_row(row)
        d["job_status"] = row["job_status"]
        d["job_error"] = row["job_error"]
        return d


@app.post(
    "/api/transcriptions/{transcription_id}/use-as-script", status_code=201
)
def use_transcription_as_script(
    transcription_id: int, body: dict | None = None
) -> dict:
    """Turn a finished transcript into a project script (same split +
    scene image prompts as a pasted script)."""
    topic = ((body or {}).get("topic") or "").strip()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM transcriptions WHERE id = ?", (transcription_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="transcription not found")
        text = (row["full_text"] or "").strip()
        if not text:
            raise HTTPException(
                status_code=409,
                detail="transcription abhi tayyar nahi ya khaali hai",
            )
        if not topic:
            topic = " ".join(text.split()[:8])
        return _insert_script(conn, row["project_id"], topic, text, "transcription")


# ---------------------------------------------------------------------------
# Phase 6 slice 1: ClipForge — long video upload + transcription.
# A long video is uploaded once, its audio is transcribed locally by
# Whisper (cached models only, no download), and the word timestamps
# become the raw material for moment detection (slice 2). Free, offline,
# no key, no watermark — the video file itself is never altered.
# ---------------------------------------------------------------------------

SOURCE_VIDEO_EXTS = {".mp4", ".mov", ".webm"}
SOURCE_VIDEO_DIR = DATA_DIR / "source-videos"
SOURCE_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_VIDEO_MAX_BYTES = 2 * 1024 * 1024 * 1024

_SOURCE_VIDEO_SELECT = (
    "SELECT sv.*, a.path AS asset_path, t.source_filename,"
    " t.model AS tr_model, t.language AS tr_language, t.full_text AS tr_full_text,"
    " t.words_json AS tr_words_json, t.segments_json AS tr_segments_json,"
    " t.duration_s AS tr_duration_s, j.status AS job_status,"
    " j.error AS job_error FROM source_videos sv"
    " LEFT JOIN assets a ON a.id = sv.asset_id"
    " LEFT JOIN transcriptions t ON t.id = sv.transcription_id"
    " LEFT JOIN jobs j ON j.id = sv.job_id"
)


def _source_video_row(row, include_words: bool = False) -> dict:
    d = {
        "id": row["id"],
        "project_id": row["project_id"],
        "asset_id": row["asset_id"],
        "job_id": row["job_id"],
        "transcription_id": row["transcription_id"],
        "duration_s": row["duration_s"],
        "created_at": row["created_at"],
        "source_filename": row["source_filename"],
        "asset_path": row["asset_path"],
        "video_url": media_url(row["asset_path"]) if row["asset_path"] else None,
        "job_status": row["job_status"],
        "job_error": row["job_error"],
        "model": row["tr_model"] or "",
        "language": row["tr_language"] or "",
        "word_count": len(json.loads(row["tr_words_json"] or "[]")),
    }
    if include_words:
        d["full_text"] = row["tr_full_text"] or ""
        d["words"] = json.loads(row["tr_words_json"] or "[]")
        d["segments"] = json.loads(row["tr_segments_json"] or "[]")
        d["transcription_duration_s"] = row["tr_duration_s"] or 0
    return d


@app.post("/api/projects/{project_id}/source-videos", status_code=202)
async def upload_source_video(
    background_tasks: BackgroundTasks,
    project_id: int,
    file: UploadFile = File(...),
    model: str = Form("tiny"),
) -> dict:
    """Upload a long video and transcribe it with local Whisper.

    The video is streamed to disk in 1 MB chunks (up to 2 GB) — never
    held fully in memory. Its audio is transcribed by the same local
    faster-whisper worker as POST /api/transcribe (cached models only,
    no download). Returns the queued job; poll
    GET /api/projects/{id}/source-videos for the result.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SOURCE_VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "ClipForge ke liye video file dein:"
                f" {', '.join(sorted(SOURCE_VIDEO_EXTS))}"
            ),
        )
    cached = _cached_whisper_models()
    if model not in cached:
        raise HTTPException(
            status_code=400,
            detail=(
                f"model '{model}' is PC par cached nahi hai"
                + (
                    f" — cached models: {', '.join(cached)}"
                    if cached
                    else " — koi model cached nahi hai"
                )
            ),
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
    name = f"sv_{int(time.time())}_{safe_filename(file.filename)}"
    disk = SOURCE_VIDEO_DIR / name
    written = 0
    try:
        with disk.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > SOURCE_VIDEO_MAX_BYTES:
                    raise HTTPException(
                        status_code=400, detail="video too large (max 2 GB)"
                    )
                out.write(chunk)
    except HTTPException:
        disk.unlink(missing_ok=True)
        raise
    except OSError as exc:
        disk.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500, detail=f"video save nahi ho saki: {exc}"
        )
    if written == 0:
        disk.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="khaali file hai")
    duration_s = round(probe_duration(disk), 3)
    rel = f"source-videos/{name}"
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'source-video', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at,"
            " updated_at) VALUES (?, 'source-video', 'queued', ?, ?)",
            (project_id, utcnow(), utcnow()),
        )
        job_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO transcriptions (project_id, job_id, model, language,"
            " source_filename, source_path, created_at)"
            " VALUES (?, ?, ?, '', ?, ?, ?)",
            (project_id, job_id, model, file.filename or name, rel, utcnow()),
        )
        transcription_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO source_videos (project_id, asset_id, job_id,"
            " transcription_id, duration_s, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                asset_id,
                job_id,
                transcription_id,
                duration_s,
                utcnow(),
            ),
        )
        source_video_id = cur.lastrowid
    background_tasks.add_task(
        _run_transcription, job_id, transcription_id, disk, model
    )
    return {
        "job_id": job_id,
        "source_video_id": source_video_id,
        "transcription_id": transcription_id,
        "status": "queued",
        "model": model,
        "duration_s": duration_s,
    }


@app.get("/api/projects/{project_id}/source-videos")
def list_source_videos(project_id: int) -> list:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.project_id = ? ORDER BY sv.id DESC",
            (project_id,),
        ).fetchall()
        return [_source_video_row(r) for r in rows]


@app.get("/api/source-videos/{source_video_id}")
def get_source_video(source_video_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
            (source_video_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="source video not found")
        return _source_video_row(row, include_words=True)


# --- Phase 6 slice 2: ClipForge moment detection -----------------------
# A moment is a 15–60 s window of the source video that would make a
# good short clip. Candidates are built from the Whisper segments
# (consecutive segments grouped until the window is long enough), then
# scored from the REAL word timestamps only — nothing is invented:
#   density  — words per second in the window (busy speech scores
#              higher); 3.0 words/s is the reference pace.
#   keywords — hook-word hits in the window's text: question words,
#              numbers, and emotion/hook words (English + Roman Urdu).
#   silence  — the real pauses around the window (gap before the first
#              word + gap after the last word); a clean pause at both
#              ends means the clip cuts cleanly.
#   length   — 1.0 for 20–45 s (ideal short-clip length), tapering to
#              0.5 at the 15 s / 60 s edges.
# Audio energy is deliberately NOT part of the score: it is not
# measured here, so inventing an energy number would be fake data.
# The best-scoring windows win, with overlapping windows removed
# (non-maximum suppression: two moments may not overlap by more than
# half of the shorter window). Re-running detection replaces the old
# moments for that source video.

MIN_MOMENT_S = 15.0
MAX_MOMENT_S = 60.0
IDEAL_MOMENT_MIN_S = 20.0
IDEAL_MOMENT_MAX_S = 45.0
MIN_MOMENT_WORDS = 20
MAX_MOMENTS = 5

# Hook words: a window that asks a question, names a number, or uses
# a strong/emotional word is more likely to hold a viewer. Matched
# against lowercased words with punctuation stripped. English first
# (the test videos are English), plus the Roman Urdu hooks Ale's
# audience would use.
HOOK_WORDS = {
    # question words
    "what", "why", "how", "when", "who", "where", "which", "whose",
    "imagine", "did", "kya", "kyun", "kaise", "kab", "kaun", "kahan",
    # numbers
    "billion", "million", "thousand", "percent", "crore", "lakh",
    "hazaar", "arab",
    # emotion / hook words
    "fraud", "arrested", "secret", "shocking", "strange", "warning",
    "warned", "handcuffs", "stopped", "problem", "truth", "never",
    "nobody", "hidden", "caught", "scam", "dhoka", "raaz", "sach",
    "giraftar", "chori", "jhooth",
}

_SCORE_WEIGHTS = {"density": 0.35, "keywords": 0.30, "silence": 0.20, "length": 0.15}


def _clean_word(word: str) -> str:
    return word.strip().lower().strip(".,!?;:'\"()[]—-")


def _score_window(
    words: list[dict],
    start_s: float,
    end_s: float,
    gap_before: float,
    gap_after: float,
    target_length_s: float | None = None,
) -> tuple[float, dict]:
    """Score one candidate window. `words` are the window's words
    (each with real start/end); the gaps are the real pauses around
    the window (previous word end → first word start, last word end
    → next word start, or the video edges). target_length_s moves
    the length-score peak to the chosen clip length (ClipNova parity:
    Auto/15/25/30/40/60/90 s) — None keeps the old 20–45 s ideal."""
    span = max(0.001, end_s - start_s)
    wps = len(words) / span
    density = min(1.0, wps / 3.0)
    hits = sum(1 for w in words if _clean_word(w["word"]) in HOOK_WORDS)
    hits += sum(1 for w in words if any(ch.isdigit() for ch in w["word"]))
    keywords = min(1.0, hits / 4.0)
    silence = min(1.0, max(0.0, gap_before + gap_after) / 1.0)
    if target_length_s is not None:
        # Peak 1.0 at the target, falling linearly to 0.5 at 15 s
        # and at 60 s (the window limits) — a target only re-weights,
        # it never invents a window outside the real timestamps.
        if span <= target_length_s:
            length = 0.5 + 0.5 * (span - MIN_MOMENT_S) / max(
                0.001, target_length_s - MIN_MOMENT_S
            )
        else:
            length = 1.0 - 0.5 * (span - target_length_s) / max(
                0.001, MAX_MOMENT_S - target_length_s
            )
    elif span < IDEAL_MOMENT_MIN_S:
        length = 0.5 + 0.5 * (span - MIN_MOMENT_S) / (
            IDEAL_MOMENT_MIN_S - MIN_MOMENT_S
        )
    elif span > IDEAL_MOMENT_MAX_S:
        length = 1.0 - 0.5 * (span - IDEAL_MOMENT_MAX_S) / (
            MAX_MOMENT_S - IDEAL_MOMENT_MAX_S
        )
    else:
        length = 1.0
    breakdown = {
        "density": round(density, 3),
        "keywords": round(keywords, 3),
        "silence": round(silence, 3),
        "length": round(max(0.0, min(1.0, length)), 3),
        "hook_hits": hits,
        "words_per_second": round(wps, 2),
        "gap_before_s": round(max(0.0, gap_before), 2),
        "gap_after_s": round(max(0.0, gap_after), 2),
    }
    total = sum(
        _SCORE_WEIGHTS[k] * breakdown[k]
        for k in ("density", "keywords", "silence", "length")
    )
    return round(total, 3), breakdown


def _detect_moments(
    words: list[dict],
    segments: list[dict],
    duration_s: float,
    max_moments: int = 5,
    target_length_s: float | None = None,
) -> list[dict]:
    """Find and score moments from the real word timestamps.

    Candidates are groups of consecutive Whisper segments whose span
    (first word start → last word end) is 15–60 s with at least 20
    words. Silence is measured from the real gaps: the pause between
    the previous word and the window's first word, and between the
    window's last word and the next word (or the video edges).
    Overlapping candidates are removed greedily by score, keeping at
    most max_moments, returned in time order. target_length_s moves
    the length-score peak to the chosen clip length (None = the old
    20–45 s ideal)."""
    if not words or not segments or duration_s < MIN_MOMENT_S:
        return []
    # Assign every word to its segment (a word belongs to the first
    # segment whose end is not before the word's start — segments are
    # in time order, so one pass is enough).
    seg_of_word: list[int] = []
    seg_idx = 0
    for w in words:
        while (
            seg_idx < len(segments) - 1
            and w["start"] >= segments[seg_idx]["end"]
        ):
            seg_idx += 1
        seg_of_word.append(seg_idx)
    # Word-index range of each segment that actually holds words.
    seg_ranges: list[tuple[int, int]] = []
    for s in range(len(segments)):
        idxs = [k for k, v in enumerate(seg_of_word) if v == s]
        if idxs:
            seg_ranges.append((idxs[0], idxs[-1]))
    if not seg_ranges:
        return []
    candidates: list[dict] = []
    for i in range(len(seg_ranges)):
        for j in range(i, len(seg_ranges)):
            first = seg_ranges[i][0]
            last = seg_ranges[j][1]
            group = words[first : last + 1]
            start_s = group[0]["start"]
            end_s = group[-1]["end"]
            span = end_s - start_s
            if span > MAX_MOMENT_S:
                break
            if span < MIN_MOMENT_S or len(group) < MIN_MOMENT_WORDS:
                continue
            gap_before = start_s - (
                words[first - 1]["end"] if first > 0 else 0.0
            )
            gap_after = (
                words[last + 1]["start"]
                if last + 1 < len(words)
                else duration_s
            ) - end_s
            score, breakdown = _score_window(
                group, start_s, end_s, gap_before, gap_after, target_length_s
            )
            text = " ".join(
                w["word"].strip() for w in group if w["word"].strip()
            ).strip()
            # Whisper splits some punctuation into its own word
            # ("455" + ",000"); rejoin it so the excerpt reads
            # naturally. Words and timestamps are unchanged.
            text = re.sub(r"\s+([,.;:!?%])", r"\1", text)
            candidates.append(
                {
                    "start_s": round(start_s, 2),
                    "end_s": round(end_s, 2),
                    "score": score,
                    "score_breakdown": breakdown,
                    "title": _moment_title(text),
                    "excerpt": _moment_excerpt(text),
                    "word_count": len(group),
                }
            )
    # Non-maximum suppression: best first, drop anything overlapping
    # an accepted moment by more than half of the shorter window.
    candidates.sort(key=lambda c: (-c["score"], c["start_s"]))
    accepted: list[dict] = []
    for cand in candidates:
        overlap = False
        for acc in accepted:
            inter = max(
                0.0, min(cand["end_s"], acc["end_s"]) - max(cand["start_s"], acc["start_s"])
            )
            shorter = min(
                cand["end_s"] - cand["start_s"], acc["end_s"] - acc["start_s"]
            )
            if shorter > 0 and inter / shorter > 0.5:
                overlap = True
                break
        if not overlap:
            accepted.append(cand)
        if len(accepted) >= max(1, min(10, max_moments)):
            break
    accepted.sort(key=lambda c: c["start_s"])
    return accepted


def _moment_title(text: str) -> str:
    """Short title: the first sentence, or the first 8 words."""
    first = text.split(".")[0].strip()
    if len(first.split()) > 10:
        first = " ".join(first.split()[:8])
    title = first[:60].strip()
    return title or text[:60].strip()


def _moment_excerpt(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _moment_row(row) -> dict:
    d = dict(row)
    d["score_breakdown"] = json.loads(row["score_breakdown"] or "{}")
    return d


@app.post("/api/source-videos/{source_video_id}/detect-moments", status_code=201)
def detect_moments(source_video_id: int, body: DetectMomentsIn | None = None) -> dict:
    """Score moments for a source video from its real transcription.

    Synchronous and fast — pure computation on the stored word
    timestamps, no Whisper, no ffmpeg. Re-running replaces the old
    moments for this source video. A source video whose transcription
    is not done yet (or has no words) returns a plain 400 — no fake
    moments are ever invented. max_moments (1–10, default 5) and
    target_length_s (Auto/15/25/30/40/60/90) come from the body;
    an empty body keeps the old defaults.
    """
    with db() as conn:
        sv = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?", (source_video_id,)
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        words = json.loads(sv["tr_words_json"] or "[]")
        segments = json.loads(sv["tr_segments_json"] or "[]")
        duration_s = sv["duration_s"] or sv["tr_duration_s"] or 0
        if sv["job_status"] != "done" or not words:
            raise HTTPException(
                status_code=400,
                detail=(
                    "transcription abhi tayyar nahi — pehle video"
                    " transcribe hone dein, phir moments niklein ge"
                ),
            )
        moments = _detect_moments(
            words,
            segments,
            duration_s,
            max_moments=(body.max_moments if body else MAX_MOMENTS),
            target_length_s=(body.target_length_s if body else None),
        )
        # Slice 4: re-running detection replaces the moments — their
        # reframes + final clips (rows, asset rows, files) go first,
        # or the DELETE fails on the foreign keys (no ON DELETE
        # CASCADE). Job rows stay as honest history.
        old_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM moments WHERE source_video_id = ?",
                (source_video_id,),
            ).fetchall()
        ]
        for mid in old_ids:
            _delete_moment_artifacts(conn, mid)
        conn.execute(
            "DELETE FROM moments WHERE source_video_id = ?",
            (source_video_id,),
        )
        for m in moments:
            conn.execute(
                "INSERT INTO moments (source_video_id, start_s, end_s,"
                " score, score_breakdown, title, excerpt, word_count,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_video_id,
                    m["start_s"],
                    m["end_s"],
                    m["score"],
                    json.dumps(m["score_breakdown"]),
                    m["title"],
                    m["excerpt"],
                    m["word_count"],
                    utcnow(),
                ),
            )
        # Return the stored rows (with ids) — the computed moments
        # have no id, and the UI needs a stable key per card.
        stored = conn.execute(
            "SELECT * FROM moments WHERE source_video_id = ? ORDER BY start_s",
            (source_video_id,),
        ).fetchall()
        moments = [_moment_row(r) for r in stored]
    note = None
    if not moments:
        if duration_s < MIN_MOMENT_S:
            note = (
                f"video sirf {duration_s:.1f}s ki hai — 15s se chhote"
                " moments nahi bante"
            )
        else:
            note = (
                "koi 15–60s ka moment nahi bana — likhai bahut chhoti"
                " hai ya alfaz bahut kam hain"
            )
    return {
        "source_video_id": source_video_id,
        "moments": moments,
        "count": len(moments),
        "note": note,
    }


@app.get("/api/source-videos/{source_video_id}/moments")
def list_moments(source_video_id: int) -> list:
    with db() as conn:
        sv = conn.execute(
            "SELECT id FROM source_videos WHERE id = ?", (source_video_id,)
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        rows = conn.execute(
            "SELECT * FROM moments WHERE source_video_id = ? ORDER BY start_s",
            (source_video_id,),
        ).fetchall()
        return [_moment_row(r) for r in rows]


# --- Phase 6 slice 3: ClipForge 9:16 reframe + captions ----------------
# A moment becomes a vertical 9:16 preview: the moment's time range
# is cut from the source video, centre-cropped to 9:16 (face tracking
# comes later — this slice never claims it), scaled to 1080x1920, and
# the moment's real Whisper segments are burned in as timed captions
# in the chosen style (the same 8 CAPTION_RENDER_SPECS the CineCut
# render draws, fontsize scaled ~1.3x for the narrower frame). The
# output is a clip-preview asset under studio/data/ with its own job
# row, so progress and failure are visible. No approval gating and no
# final render here — that is slice 4.

REFRAME_DIR = DATA_DIR / "clip-previews"
REFRAME_DIR.mkdir(parents=True, exist_ok=True)
REFRAME_WIDTH = 1080
REFRAME_HEIGHT = 1920

_REFRAME_SELECT = (
    "SELECT rf.*, j.status AS job_status, j.error AS job_error,"
    " a.path AS asset_path FROM reframes rf"
    " LEFT JOIN jobs j ON j.id = rf.job_id"
    " LEFT JOIN assets a ON a.id = rf.asset_id"
)


def _reframe_row(row) -> dict:
    d = dict(row)
    d["video_url"] = media_url(row["asset_path"]) if row["asset_path"] else None
    return d


# Cross-check slice: ClipNova aspect parity (9:16 / 1:1 / 4:5 / 3:4)
# and the word-level "One Word Pop" caption style (FrameLoom /
# StickFilm parity). One Word Pop is NOT in CAPTION_RENDER_SPECS —
# it needs real Whisper word timestamps, so only the ClipForge
# renderers (which have them) can draw it. Its spec is fixed: big
# yellow words, one at a time, always centred.
VERTICAL_ASPECTS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "3:4": (1080, 1440),
}
ONE_WORD_POP_SPEC = {
    "fontcolor": "#FFD400", "fontsize": 64, "borderw": 4,
    "shadow": True, "box": False, "uppercase": True, "fontfile": None,
}


def _render_vertical_9x16(
    src: Path,
    start_s: float,
    end_s: float,
    caption_style: str,
    segments: list,
    out_dir: Path,
    stem: str,
    aspect: str = "9:16",
    words: list | None = None,
    caption_size_pct: int = 100,
    caption_position: str = "bottom",
    captions: bool = True,
    job_id: int | None = None,
    exact_name: str | None = None,
) -> Path:
    """Shared vertical render for the slice-3 preview (_run_reframe)
    and the slice-4 final clip (_run_final_clip): cut the time
    range, centre-crop to the chosen aspect (9:16 / 1:1 / 4:5 / 3:4),
    scale to the aspect's output size, burn the moment's real Whisper
    segments in as timed captions, keep the source audio. Output
    seeking (-ss after -i) cuts accurately, but ffmpeg keeps the
    SOURCE timestamps through the filter graph after such a seek — a
    drawtext %{pts} probe at output 1 s reads 00:00:05.467 for a
    4.46 s cut, and setpts=PTS-STARTPTS does NOT reset it. So the
    caption windows use the segments' ABSOLUTE source times, not
    times relative to the cut. caption_style "One Word Pop" burns one
    real Whisper word at a time (big, yellow, always centred) instead
    of segment lines — it needs `words`; without them it is a plain
    400 at the endpoint, never a silent fallback. caption_size_pct
    scales the font (50–150); caption_position is bottom / center /
    top; captions=False burns no captions. Returns the output MP4
    path; raises RuntimeError on failure (ffmpeg's last stderr line,
    with the full log written next to the output as {stem}_error.log)."""
    if not src.exists():
        raise RuntimeError(
            "source video file nahi mili — dobara upload karein;"
            " bina file ke preview nahi ban sakta"
        )
    dur = round(end_s - start_s, 3)
    if dur <= 0:
        raise RuntimeError("moment ki duration zero hai")
    sw, sh = probe_video_dims(src)
    if sw <= 0 or sh <= 0:
        raise RuntimeError("source video ki size nahi parh saki")
    # Centre crop to the chosen aspect (even dimensions — x264 needs
    # them). The source is wider than the target -> crop the width;
    # taller -> crop the height. 9:16 on a landscape source is the
    # old behaviour, unchanged.
    out_w, out_h = VERTICAL_ASPECTS.get(aspect) or (1080, 1920)
    ratio = out_w / out_h
    if sw / sh >= ratio:  # source wider than the target aspect
        crop_h = sh
        crop_w = int(sh * ratio) // 2 * 2
        crop_x = (sw - crop_w) // 2
        crop_y = 0
    else:  # source taller than the target aspect
        crop_w = sw
        crop_h = int(sw / ratio) // 2 * 2
        crop_x = 0
        crop_y = (sh - crop_h) // 2
    if caption_style == "One Word Pop":
        spec = dict(ONE_WORD_POP_SPEC)
    else:
        spec = dict(CAPTION_RENDER_SPECS[caption_style])
    fontfile = spec.get("fontfile") or FONT_PATH
    if not fontfile:
        raise RuntimeError("caption font nahi mila — drawtext nahi chal sakta")
    # Vertical frame is narrower: ~1.3x fontsize (capped), wrap
    # width scales with the frame (see wrap_caption). Size % scales
    # it further (50–150).
    fontsize_v = max(
        16, min(72, round(spec["fontsize"] * 1.3 * caption_size_pct / 100))
    )
    # Caption chunks are the moment's real Whisper segments,
    # clipped to the moment window. The windows stay in ABSOLUTE
    # source time (see the docstring): drawtext's clock reads the
    # source time after output seeking, so a relative window
    # would show every caption ~start_s early. A segment with no
    # words in the window is skipped — nothing is invented.
    # "One Word Pop" instead takes the real Whisper WORDS: one word
    # per chunk, each shown for its own real start/end (always
    # centred — the position option does not apply to this style).
    chunks: list[tuple[float, float, str]] = []
    if captions:
        if caption_style == "One Word Pop":
            for w in words or []:
                ws = max(start_s, float(w.get("start", 0)))
                we = min(end_s, float(w.get("end", 0)))
                if we - ws < 0.05:
                    continue
                text = (w.get("word") or "").strip()
                if not text:
                    continue
                chunks.append((ws, we, text))
        else:
            for seg in segments:
                rs = max(start_s, float(seg.get("start", 0)))
                re_ = min(end_s, float(seg.get("end", 0)))
                if re_ - rs < 0.2:
                    continue
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                chunks.append((rs, re_, text))
    cap_dir = TMP_DIR / f"{stem}_captions"
    cap_dir.mkdir(parents=True, exist_ok=True)
    cap_files: list[tuple[float, float, Path]] = []
    for i, (rs, re_, text) in enumerate(chunks):
        wrapped = wrap_caption(
            text,
            fontsize=fontsize_v,
            uppercase=spec["uppercase"],
            frame_width=REFRAME_WIDTH,
        )
        p = cap_dir / f"cap_{i}.txt"
        p.write_text(wrapped, encoding="utf-8")
        cap_files.append((rs, re_, p))
    # Release Packaging: final clips get the exact date-wise name
    # (<slug>_YYYY-MM-DD_HHMM.mp4); previews keep the old stem_ts name.
    out_name = exact_name or f"{stem}_{int(time.time())}.mp4"
    out_path = out_dir / out_name
    filters = [
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={out_w}:{out_h},setsar=1,fps=30,"
        f"format=yuv420p[v0]"
    ]
    # Cross-check slice: caption position. Bottom is the old
    # y=h-text_h-160; "One Word Pop" is always centred.
    if caption_style == "One Word Pop":
        cap_y = "(h-text_h)/2"
    elif caption_position == "center":
        cap_y = "(h-text_h)/2"
    elif caption_position == "top":
        cap_y = "160"
    else:
        cap_y = "h-text_h-160"
    cap_in = "v0"
    for j, (rs, re_, p) in enumerate(cap_files):
        last = j == len(cap_files) - 1
        cap_out = "vfinal" if last else f"vc{j}"
        dt = (
            f"[{cap_in}]drawtext=fontfile={fontfile}"
            f":textfile='{p}'"
            f":fontsize={fontsize_v}"
            f":fontcolor={spec['fontcolor']}"
            f":borderw={spec['borderw']}:bordercolor=black"
        )
        if spec["shadow"]:
            dt += ":shadowcolor=black:shadowx=2:shadowy=2"
        if spec["box"]:
            dt += ":box=1:boxcolor=black@0.55:boxborderw=12"
        dt += (
            f":x=(w-text_w)/2:y={cap_y}"
            f":enable='between(t\\,{rs:.3f}\\,{re_:.3f})'"
            f"[{cap_out}]"
        )
        filters.append(dt)
        cap_in = cap_out
    final_label = "vfinal" if cap_files else "v0"
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ss",
        f"{start_s:.3f}",
        "-t",
        f"{dur:.3f}",
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{final_label}]",
        "-map",
        "0:a",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    if job_id is not None:
        proc = _run_ffmpeg(cmd, job_id, timeout=600)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        try:
            (TMP_DIR / f"{stem}_error.log").write_text(
                "CMD: " + " ".join(cmd) + "\n\n" + (proc.stderr or ""),
                encoding="utf-8",
            )
        except OSError:
            pass
        lines = (proc.stderr or "").strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "ffmpeg failed")
    return out_path


def _run_reframe(job_id: int, reframe_id: int) -> None:
    """Background reframe: cut the moment's range, centre-crop to
    9:16, scale to 1080x1920, burn the moment's real segments in as
    timed captions, keep the source audio. Output seeking (-ss after
    -i) cuts accurately, but ffmpeg keeps the SOURCE timestamps
    through the filter graph after such a seek — a drawtext
    ``%{pts}`` probe at output 1 s reads 00:00:05.467 for a 4.46 s
    cut, and setpts=PTS-STARTPTS does NOT reset it (STARTPTS is the
    source stream's start time, 0). So the caption windows use the
    segments' ABSOLUTE source times, not times relative to the cut —
    the clock and the times are the same clock. (The first two
    renders used relative times and the captions ran 4.46 s early;
    both bad previews were deleted.)"""
    with db() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if job is None:
            return
        rf = conn.execute(
            _REFRAME_SELECT + " WHERE rf.id = ?", (reframe_id,)
        ).fetchone()
        if rf is None:
            return
        # Cancelled while queued — the worker must not start.
        if job["status"] == "cancelled":
            return
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("running", utcnow(), job_id),
        )
    try:
        with db() as conn:
            moment = conn.execute(
                "SELECT * FROM moments WHERE id = ?", (rf["moment_id"],)
            ).fetchone()
            if moment is None:
                raise RuntimeError("moment not found")
            sv = conn.execute(
                _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
                (moment["source_video_id"],),
            ).fetchone()
            if sv is None or not sv["asset_path"]:
                raise RuntimeError("source video not found")
            src = DATA_DIR / sv["asset_path"]
            project_id = sv["project_id"]
            segments = json.loads(sv["tr_segments_json"] or "[]")
            words = json.loads(sv["tr_words_json"] or "[]")
        if not src.exists():
            raise RuntimeError(
                "source video file nahi mili — dobara upload karein;"
                " bina file ke preview nahi ban sakta"
            )
        start_s = float(moment["start_s"])
        end_s = float(moment["end_s"])
        out_path = _render_vertical_9x16(
            src,
            start_s,
            end_s,
            rf["caption_style"],
            segments,
            REFRAME_DIR,
            f"reframe_{reframe_id}",
            aspect=rf["aspect"] or "9:16",
            words=words,
            caption_size_pct=rf["caption_size_pct"] or 100,
            caption_position=rf["caption_position"] or "bottom",
            captions=bool(rf["captions"]),
            job_id=job_id,
        )
        rel = f"clip-previews/{out_path.name}"
        # Cancelled in the last moment: discard the file, mark
        # 'cancelled' — never store an asset for a stopped preview.
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "reframe roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO assets (project_id, kind, path, created_at)"
                " VALUES (?, 'clip-preview', ?, ?)",
                (project_id, rel, utcnow()),
            )
            asset_id = cur.lastrowid
            conn.execute(
                "UPDATE reframes SET asset_id = ? WHERE id = ?",
                (asset_id, reframe_id),
            )
            conn.execute(
                "UPDATE jobs SET status = ?, output_path = ?, updated_at = ?"
                " WHERE id = ?",
                ("done", rel, utcnow(), job_id),
            )
    except Exception as exc:  # noqa: BLE001 - record the failure on the job
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            # A killed ffmpeg leaves a partial preview file — delete
            # it so a cancelled reframe never looks like a clip.
            for _p in REFRAME_DIR.glob(f"reframe_{reframe_id}_*.mp4"):
                try:
                    _p.unlink(missing_ok=True)
                except OSError:
                    pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "reframe roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                " WHERE id = ?",
                ("failed", str(exc)[:500], utcnow(), job_id),
            )


@app.post("/api/moments/{moment_id}/reframe", status_code=202)
def reframe_moment(
    moment_id: int, body: ReframeIn, background_tasks: BackgroundTasks
) -> dict:
    """Queue a vertical preview for one moment. The caption style
    must be one of the renderable styles, or "One Word Pop"
    (word-level — needs real Whisper word timestamps on the source
    video). aspect is 9:16 / 1:1 / 4:5 / 3:4. The source video file
    must exist on disk — a missing file is a plain 400 at queue
    time, never a fake clip. Returns the reframe row (job queued);
    poll GET /api/moments/{id}/reframes for the result."""
    style = (body.caption_style or "").strip()
    if style not in CAPTION_RENDER_SPECS and style != "One Word Pop":
        raise HTTPException(
            status_code=400,
            detail=(
                f"caption style '{style}' burn nahi ho sakta — in me"
                f" se chunein: {', '.join(CAPTION_RENDER_SPECS)},"
                " One Word Pop"
            ),
        )
    aspect = (body.aspect or "9:16").strip()
    if aspect not in VERTICAL_ASPECTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"aspect '{aspect}' nahi — in me se chunein:"
                f" {', '.join(VERTICAL_ASPECTS)}"
            ),
        )
    position = (body.caption_position or "bottom").strip()
    if position not in ("bottom", "center", "top"):
        raise HTTPException(
            status_code=400,
            detail="caption position bottom / center / top me se ho",
        )
    with db() as conn:
        m = conn.execute(
            "SELECT * FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if m is None:
            raise HTTPException(status_code=404, detail="moment not found")
        sv = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
            (m["source_video_id"],),
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        if style == "One Word Pop" and not json.loads(
            sv["tr_words_json"] or "[]"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "One Word Pop ke liye word timestamps chahiye —"
                    " transcription me words nahi mile"
                ),
            )
        if not sv["asset_path"] or not (DATA_DIR / sv["asset_path"]).exists():
            raise HTTPException(
                status_code=400,
                detail=(
                    "source video file nahi mili — dobara upload karein;"
                    " bina file ke preview nahi ban sakta"
                ),
            )
        project_id = sv["project_id"]
        dur = round(float(m["end_s"]) - float(m["start_s"]), 3)
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at,"
            " updated_at) VALUES (?, 'clip-reframe', 'queued', ?, ?)",
            (project_id, utcnow(), utcnow()),
        )
        job_id = cur.lastrowid
        out_w, out_h = VERTICAL_ASPECTS[aspect]
        cur = conn.execute(
            "INSERT INTO reframes (moment_id, job_id, caption_style,"
            " width, height, duration_s, aspect, caption_size_pct,"
            " caption_position, captions, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                moment_id,
                job_id,
                style,
                out_w,
                out_h,
                dur,
                aspect,
                body.caption_size_pct,
                position,
                1 if body.captions else 0,
                utcnow(),
            ),
        )
        reframe_id = cur.lastrowid
    background_tasks.add_task(_run_reframe, job_id, reframe_id)
    with db() as conn:
        row = conn.execute(
            _REFRAME_SELECT + " WHERE rf.id = ?", (reframe_id,)
        ).fetchone()
    return _reframe_row(row)


@app.get("/api/moments/{moment_id}/reframes")
def list_reframes(moment_id: int) -> list:
    with db() as conn:
        m = conn.execute(
            "SELECT id FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if m is None:
            raise HTTPException(status_code=404, detail="moment not found")
        rows = conn.execute(
            _REFRAME_SELECT + " WHERE rf.moment_id = ? ORDER BY rf.id DESC",
            (moment_id,),
        ).fetchall()
        return [_reframe_row(r) for r in rows]


@app.get("/api/reframes/{reframe_id}")
def get_reframe(reframe_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            _REFRAME_SELECT + " WHERE rf.id = ?", (reframe_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="reframe not found")
        return _reframe_row(row)


# --- Phase 6 slice 4: ClipForge approval gating + final render --------
# A moment only becomes a FINAL clip after approval. The moment's
# approval column ('pending' / 'approved' / 'rejected', slice-4
# migration) gates POST /api/moments/{id}/render — an unapproved
# moment is a plain 400, never a clip. The final render reuses the
# slice-3 pipeline (_render_vertical_9x16: same centre crop,
# 1080x1920, same burned captions, same caption style). One final
# clip per moment: a re-render reuses the row, and the old file is
# deleted only after the new render succeeds. Per final clip:
# Download (the MP4 via /files/), SRT (the moment's real Whisper
# segments, shifted to clip-relative times), rename, delete (file +
# row gone, the moment stays approved so it can render again).

FINAL_DIR = DATA_DIR / "clip-finals"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

_FINAL_SELECT = (
    "SELECT fc.*, j.status AS job_status, j.error AS job_error,"
    " a.path AS asset_path, m.title AS moment_title,"
    " m.source_video_id AS source_video_id FROM final_clips fc"
    " LEFT JOIN jobs j ON j.id = fc.job_id"
    " LEFT JOIN assets a ON a.id = fc.asset_id"
    " LEFT JOIN moments m ON m.id = fc.moment_id"
)


def _final_clip_row(row) -> dict:
    d = dict(row)
    d["video_url"] = media_url(row["asset_path"]) if row["asset_path"] else None
    return d


def _delete_asset_file(conn, asset_id: int | None) -> None:
    """Delete one asset row + its file under DATA_DIR. Only used for
    clip-preview / clip-final assets, which nothing else references
    (their only record is the reframe / final-clip row). Job rows are
    kept as history."""
    if not asset_id:
        return
    row = conn.execute(
        "SELECT path FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if row is None:
        return
    try:
        _p = media_path(row["path"])
        if _p is not None:
            _p.unlink(missing_ok=True)
    except OSError:
        pass
    conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))


def _delete_moment_artifacts(conn, moment_id: int) -> None:
    """Delete a moment's reframes + final clips (rows, asset rows and
    files on disk) — used when detect-moments re-runs and replaces
    the moments: without this, the DELETE FROM moments fails on the
    foreign keys (reframes.moment_id / final_clips.moment_id have no
    ON DELETE CASCADE). Job rows are kept as honest history."""
    for fc in conn.execute(
        "SELECT id, asset_id FROM final_clips WHERE moment_id = ?",
        (moment_id,),
    ).fetchall():
        # Row first, then its asset: the row still references the
        # asset, so deleting the asset first fails the foreign key.
        conn.execute("DELETE FROM final_clips WHERE id = ?", (fc["id"],))
        _delete_asset_file(conn, fc["asset_id"])
        try:
            shutil.rmtree(
                TMP_DIR / f"final_{fc['id']}_captions", ignore_errors=True
            )
        except OSError:
            pass
        try:
            (TMP_DIR / f"final_{fc['id']}_error.log").unlink(missing_ok=True)
        except OSError:
            pass
    for rf in conn.execute(
        "SELECT id, asset_id FROM reframes WHERE moment_id = ?", (moment_id,)
    ).fetchall():
        conn.execute("DELETE FROM reframes WHERE id = ?", (rf["id"],))
        _delete_asset_file(conn, rf["asset_id"])
        try:
            shutil.rmtree(
                TMP_DIR / f"reframe_{rf['id']}_captions", ignore_errors=True
            )
        except OSError:
            pass
        try:
            (TMP_DIR / f"reframe_{rf['id']}_error.log").unlink(
                missing_ok=True
            )
        except OSError:
            pass


def _run_final_clip(job_id: int, final_id: int) -> None:
    """Background final render: the same pipeline as the preview
    (_render_vertical_9x16), written as a clip-final asset. The old
    file (on a re-render) is deleted only after the new render
    succeeds — until then the old clip keeps playing. On failure the
    job fails with the error and the old clip is untouched."""
    with db() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if job is None:
            return
        fc = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
        if fc is None:
            return
        # Cancelled while queued — the worker must not start.
        if job["status"] == "cancelled":
            return
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("running", utcnow(), job_id),
        )
    try:
        with db() as conn:
            moment = conn.execute(
                "SELECT * FROM moments WHERE id = ?", (fc["moment_id"],)
            ).fetchone()
            if moment is None:
                raise RuntimeError("moment not found")
            sv = conn.execute(
                _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
                (moment["source_video_id"],),
            ).fetchone()
            if sv is None or not sv["asset_path"]:
                raise RuntimeError("source video not found")
            src = DATA_DIR / sv["asset_path"]
            project_id = sv["project_id"]
            segments = json.loads(sv["tr_segments_json"] or "[]")
            words = json.loads(sv["tr_words_json"] or "[]")
            # Release Packaging: final clip ka naam date-wise hota hai.
            final_name = _dated_name(_project_slug(conn, project_id), "mp4")
        start_s = float(moment["start_s"])
        end_s = float(moment["end_s"])
        out_path = _render_vertical_9x16(
            src,
            start_s,
            end_s,
            fc["caption_style"],
            segments,
            output_dir_for_today(),
            f"final_{final_id}",
            aspect=fc["aspect"] or "9:16",
            words=words,
            caption_size_pct=fc["caption_size_pct"] or 100,
            caption_position=fc["caption_position"] or "bottom",
            captions=bool(fc["captions"]),
            job_id=job_id,
            exact_name=final_name,
        )
        rel = f"output/{_today_str()}/{out_path.name}"
        # Cancelled in the last moment: discard the file, mark
        # 'cancelled' — the old clip (on a re-render) stays untouched.
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "final clip roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            old_asset_id = fc["asset_id"]
            cur = conn.execute(
                "INSERT INTO assets (project_id, kind, path, created_at)"
                " VALUES (?, 'clip-final', ?, ?)",
                (project_id, rel, utcnow()),
            )
            asset_id = cur.lastrowid
            conn.execute(
                "UPDATE final_clips SET asset_id = ? WHERE id = ?",
                (asset_id, final_id),
            )
            conn.execute(
                "UPDATE jobs SET status = ?, output_path = ?, updated_at = ?"
                " WHERE id = ?",
                ("done", rel, utcnow(), job_id),
            )
            # The old file goes only now that the new one is stored.
            _delete_asset_file(conn, old_asset_id)
    except Exception as exc:  # noqa: BLE001 - record the failure on the job
        if job_id in _CANCELLED_JOBS:
            _CANCELLED_JOBS.discard(job_id)
            # A killed ffmpeg leaves a partial final file — delete it
            # so a cancelled render never looks like a clip (the old
            # clip, on a re-render, stays untouched).
            _partial = output_dir_for_today() / locals().get("final_name", "")
            try:
                _partial.unlink(missing_ok=True)
            except OSError:
                pass
            for _p in FINAL_DIR.glob(f"final_{final_id}_*.mp4"):
                try:
                    _p.unlink(missing_ok=True)
                except OSError:
                    pass
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                    " WHERE id = ?",
                    ("cancelled", "final clip roka gaya (cancel)", utcnow(), job_id),
                )
            return
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                " WHERE id = ?",
                ("failed", str(exc)[:500], utcnow(), job_id),
            )


def _set_moment_approval(moment_id: int, approval: str) -> dict:
    with db() as conn:
        m = conn.execute(
            "SELECT * FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if m is None:
            raise HTTPException(status_code=404, detail="moment not found")
        conn.execute(
            "UPDATE moments SET approval = ? WHERE id = ?",
            (approval, moment_id),
        )
        row = conn.execute(
            "SELECT * FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
    return _moment_row(row)


@app.post("/api/moments/{moment_id}/approve")
def approve_moment(moment_id: int) -> dict:
    """Approve a moment — only approved moments render as final
    clips. Approval is the user's call, never automatic."""
    return _set_moment_approval(moment_id, "approved")


@app.post("/api/moments/{moment_id}/reject")
def reject_moment(moment_id: int) -> dict:
    """Reject a moment — it never renders as a final clip. A
    rejected moment can be approved later (approval is a state,
    not a deletion)."""
    return _set_moment_approval(moment_id, "rejected")


@app.get("/api/source-videos/{source_video_id}/approved-moments")
def list_approved_moments(source_video_id: int) -> list:
    with db() as conn:
        sv = conn.execute(
            "SELECT id FROM source_videos WHERE id = ?", (source_video_id,)
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        rows = conn.execute(
            "SELECT * FROM moments WHERE source_video_id = ?"
            " AND approval = 'approved' ORDER BY start_s",
            (source_video_id,),
        ).fetchall()
        return [_moment_row(r) for r in rows]


@app.post("/api/moments/{moment_id}/render", status_code=202)
def render_final_clip(
    moment_id: int, body: RenderFinalIn, background_tasks: BackgroundTasks
) -> dict:
    """Queue the FINAL vertical clip for one moment. Gated on approval:
    a moment that is not approved is a plain 400 — no clip is ever
    produced without approval. The caption style / aspect / size /
    position / captions default to the latest done reframe's values
    (the preview the user already saw), or the values in the body.
    One final clip per moment: a re-render reuses the row, and the old
    file is deleted only after the new render succeeds. Returns the
    final-clip row (job queued); poll GET /api/moments/{id}/final-clips
    for the result."""
    with db() as conn:
        m = conn.execute(
            "SELECT * FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if m is None:
            raise HTTPException(status_code=404, detail="moment not found")
        if (m["approval"] or "pending") != "approved":
            raise HTTPException(
                status_code=400,
                detail=(
                    "pehle approve karein — bina approval ke final clip"
                    " nahi banta"
                ),
            )
        sv = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
            (m["source_video_id"],),
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        if not sv["asset_path"] or not (DATA_DIR / sv["asset_path"]).exists():
            raise HTTPException(
                status_code=400,
                detail=(
                    "source video file nahi mili — dobara upload karein;"
                    " bina file ke final clip nahi ban sakta"
                ),
            )
        # Cross-check slice: empty fields inherit the latest DONE
        # reframe (the preview the user already saw) — style, aspect,
        # caption size/position, captions on/off. A body value always
        # wins over the inherited one.
        latest = conn.execute(
            "SELECT * FROM reframes WHERE moment_id = ?"
            " AND asset_id IS NOT NULL ORDER BY id DESC LIMIT 1",
            (moment_id,),
        ).fetchone()
        style = (body.caption_style or "").strip()
        if not style:
            style = latest["caption_style"] if latest else "Bold White"
        if style not in CAPTION_RENDER_SPECS and style != "One Word Pop":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"caption style '{style}' burn nahi ho sakta — in me"
                    f" se chunein: {', '.join(CAPTION_RENDER_SPECS)},"
                    " One Word Pop"
                ),
            )
        if style == "One Word Pop" and not json.loads(
            sv["tr_words_json"] or "[]"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "One Word Pop ke liye word timestamps chahiye —"
                    " transcription me words nahi mile"
                ),
            )
        aspect = (body.aspect or "").strip()
        if not aspect:
            aspect = latest["aspect"] if latest else "9:16"
        if aspect not in VERTICAL_ASPECTS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"aspect '{aspect}' nahi — in me se chunein:"
                    f" {', '.join(VERTICAL_ASPECTS)}"
                ),
            )
        size_pct = body.caption_size_pct
        if size_pct is None:
            size_pct = latest["caption_size_pct"] if latest else 100
        position = (body.caption_position or "").strip()
        if not position:
            position = latest["caption_position"] if latest else "bottom"
        if position not in ("bottom", "center", "top"):
            raise HTTPException(
                status_code=400,
                detail="caption position bottom / center / top me se ho",
            )
        captions_on = body.captions
        if captions_on is None:
            captions_on = bool(latest["captions"]) if latest else True
        rf = conn.execute(
            "SELECT id FROM reframes WHERE moment_id = ?"
            " AND caption_style = ? AND asset_id IS NOT NULL"
            " ORDER BY id DESC LIMIT 1",
            (moment_id, style),
        ).fetchone()
        reframe_id = rf["id"] if rf else None
        project_id = sv["project_id"]
        dur = round(float(m["end_s"]) - float(m["start_s"]), 3)
        out_w, out_h = VERTICAL_ASPECTS[aspect]
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at,"
            " updated_at) VALUES (?, 'clip-final-render', 'queued', ?, ?)",
            (project_id, utcnow(), utcnow()),
        )
        job_id = cur.lastrowid
        existing = conn.execute(
            "SELECT id FROM final_clips WHERE moment_id = ?", (moment_id,)
        ).fetchone()
        if existing:
            final_id = existing["id"]
            conn.execute(
                "UPDATE final_clips SET job_id = ?, reframe_id = ?,"
                " caption_style = ?, duration_s = ?, aspect = ?,"
                " caption_size_pct = ?, caption_position = ?,"
                " captions = ?, width = ?, height = ? WHERE id = ?",
                (
                    job_id, reframe_id, style, dur, aspect, size_pct,
                    position, 1 if captions_on else 0, out_w, out_h,
                    final_id,
                ),
            )
        else:
            cur = conn.execute(
                "INSERT INTO final_clips (moment_id, reframe_id, job_id,"
                " title, caption_style, width, height, duration_s,"
                " aspect, caption_size_pct, caption_position, captions,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    moment_id,
                    reframe_id,
                    job_id,
                    m["title"],
                    style,
                    out_w,
                    out_h,
                    dur,
                    aspect,
                    size_pct,
                    position,
                    1 if captions_on else 0,
                    utcnow(),
                ),
            )
            final_id = cur.lastrowid
    background_tasks.add_task(_run_final_clip, job_id, final_id)
    with db() as conn:
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
    return _final_clip_row(row)


@app.get("/api/moments/{moment_id}/final-clips")
def list_final_clips_for_moment(moment_id: int) -> list:
    with db() as conn:
        m = conn.execute(
            "SELECT id FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if m is None:
            raise HTTPException(status_code=404, detail="moment not found")
        rows = conn.execute(
            _FINAL_SELECT + " WHERE fc.moment_id = ? ORDER BY fc.id DESC",
            (moment_id,),
        ).fetchall()
        return [_final_clip_row(r) for r in rows]


@app.get("/api/source-videos/{source_video_id}/final-clips")
def list_final_clips_for_source_video(source_video_id: int) -> list:
    with db() as conn:
        sv = conn.execute(
            "SELECT id FROM source_videos WHERE id = ?", (source_video_id,)
        ).fetchone()
        if sv is None:
            raise HTTPException(status_code=404, detail="source video not found")
        rows = conn.execute(
            _FINAL_SELECT
            + " WHERE m.source_video_id = ? ORDER BY fc.id DESC",
            (source_video_id,),
        ).fetchall()
        return [_final_clip_row(r) for r in rows]


@app.get("/api/final-clips/{final_id}")
def get_final_clip(final_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="final clip not found")
        return _final_clip_row(row)


@app.get("/api/final-clips/{final_id}/srt", response_class=PlainTextResponse)
def get_final_clip_srt(final_id: int) -> PlainTextResponse:
    """SRT for a final clip: the moment's real Whisper segments,
    clipped to the moment window and shifted so the clip starts at
    0:00:00. Times are clip-relative here (unlike the burned-in
    captions, which use absolute source times because of ffmpeg's
    clock — see _render_vertical_9x16)."""
    with db() as conn:
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="final clip not found")
        moment = conn.execute(
            "SELECT * FROM moments WHERE id = ?", (row["moment_id"],)
        ).fetchone()
        sv = conn.execute(
            _SOURCE_VIDEO_SELECT + " WHERE sv.id = ?",
            (moment["source_video_id"],),
        ).fetchone()
        segments = json.loads(sv["tr_segments_json"] or "[]")
    start_s = float(moment["start_s"])
    end_s = float(moment["end_s"])
    shifted: list[dict] = []
    for seg in segments:
        rs = max(start_s, float(seg.get("start", 0))) - start_s
        re_ = min(end_s, float(seg.get("end", 0))) - start_s
        if re_ - rs < 0.2:
            continue
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        shifted.append({"start": rs, "end": re_, "text": text})
    return PlainTextResponse(
        _segments_to_srt(shifted),
        headers={
            "Content-Disposition": f"attachment; filename=clip-{final_id}.srt"
        },
    )


@app.patch("/api/final-clips/{final_id}")
def rename_final_clip(final_id: int, body: RenameFinalIn) -> dict:
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=400, detail="title khali nahi ho sakta"
        )
    with db() as conn:
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="final clip not found")
        conn.execute(
            "UPDATE final_clips SET title = ? WHERE id = ?",
            (title, final_id),
        )
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
    return _final_clip_row(row)


@app.delete("/api/final-clips/{final_id}")
def delete_final_clip(final_id: int) -> dict:
    """Delete a final clip: file + asset row + clip row go; the
    moment stays approved, so it can be rendered again."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM final_clips WHERE id = ?", (final_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="final clip not found")
        moment_id = row["moment_id"]
        asset_id = row["asset_id"]
        # Row first, then its asset: the row still references the
        # asset, so deleting the asset first fails the foreign key.
        conn.execute("DELETE FROM final_clips WHERE id = ?", (final_id,))
        _delete_asset_file(conn, asset_id)
        try:
            shutil.rmtree(
                FINAL_DIR / f"final_{final_id}_captions", ignore_errors=True
            )
        except OSError:
            pass
    return {"deleted": True, "final_clip_id": final_id, "moment_id": moment_id}


@app.post("/api/final-clips/{final_id}/reuse", status_code=201)
def reuse_final_clip(final_id: int, body: ReuseFinalClipIn) -> dict:
    """Reuse a final clip in another project (ClipNova Library
    'Reuse' parity): the clip file is COPIED into the target
    project's folder as a real asset (kind 'clip-final'), never
    shared by path — so a delete in one project never breaks the
    other. A clip with no rendered file yet is a plain 400."""
    with db() as conn:
        row = conn.execute(
            _FINAL_SELECT + " WHERE fc.id = ?", (final_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="final clip not found")
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (body.project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        if not row["asset_path"]:
            raise HTTPException(
                status_code=400,
                detail="is clip ki file abhi tayyar nahi — pehle render hone dein",
            )
        src = DATA_DIR / row["asset_path"]
        if not src.exists():
            raise HTTPException(
                status_code=400,
                detail="clip ki file nahi mili — dobara render karein",
            )
        folder = PROJECTS_DIR / str(body.project_id)
        folder.mkdir(parents=True, exist_ok=True)
        name = f"reused_clip_{final_id}_{int(time.time())}.mp4"
        disk = folder / name
        shutil.copyfile(src, disk)
        rel = f"projects/{body.project_id}/{name}"
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'clip-final', ?, ?)",
            (body.project_id, rel, utcnow()),
        )
        asset = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    result = dict(asset)
    result["duration_s"] = round(probe_duration(disk), 3)
    result["source_final_clip_id"] = final_id
    return result


@app.post("/api/projects/{project_id}/tts", status_code=201)
async def text_to_speech(project_id: int, body: TtsIn) -> dict:
    """Best-effort free TTS via Edge-TTS (Microsoft voices, no key).

    Edge-TTS is blocked on some networks (it was blocked in the build VM).
    When it cannot run, this returns HTTP 503 with a plain message and
    nothing breaks — uploading a voiceover file is the reliable path.
    """
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
    try:
        # No voice given = the saved default voice (VoiceForge favourite).
        voice = body.voice.strip() or _default_tts_voice()
        rel, disk = await _tts_save(project_id, body.text, voice)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'voice', ?, ?)",
            (project_id, rel, utcnow()),
        )
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    result = dict(row)
    result["duration_s"] = round(probe_duration(disk), 3)
    return result


# --- HeyGen clone voice (Phase 5 slice 3) --------------------------------
# The user's OWN cloned voice as a narration source. HeyGen is the ONE
# paid/credit service in this app: it needs the user's own API key
# (Settings, masked) + their own clone voice_id, and every generation
# is charged to THEIR account, never anyone else's. No live HeyGen call
# was made in the build VM — the worker below is written from HeyGen's
# own docs + the verified MCP usage in this workspace, and the first
# real run with a key will prove it.


def _heygen_key(conn) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'heygen_api_key'"
    ).fetchone()
    return (row["value"].strip() if row else "")


def _heygen_voice_id(conn) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'heygen_voice_id'"
    ).fetchone()
    return (row["value"].strip() if row else "")


def build_heygen_speech_request(
    voice_id: str, text: str, language: str
) -> dict:
    """The exact HeyGen speech request body. Model heygen-voice-1-turbo
    (the server rejects heygen-voice-1-turbo-free on this path — that
    was the Eiffel Tower VO lesson); expressivenessBoost 1.0 is the
    locked value from the Urdu VO recipe. The API key is NOT in this
    body — it rides as the X-Api-Key header, so this payload is safe
    to log for audit."""
    return {
        "model": HEYGEN_VOICE_MODEL,
        "voice_id": voice_id,
        "text": text,
        "language": language,
        "expressivenessBoost": 1.0,
    }


_RUBBERBAND_CACHE: bool | None = None


def _rubberband_available() -> bool:
    """True when this ffmpeg build has the rubberband filter (pitch
    shift with tempo untouched). Cached per process."""
    global _RUBBERBAND_CACHE
    if _RUBBERBAND_CACHE is None:
        try:
            out = subprocess.run(
                [shutil.which("ffmpeg") or "ffmpeg", "-filters"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            _RUBBERBAND_CACHE = " rubberband " in out.stdout
        except (OSError, subprocess.SubprocessError):
            _RUBBERBAND_CACHE = False
    return bool(_RUBBERBAND_CACHE)


def _apply_106hz_pitch(src: Path, dst: Path) -> None:
    """106 Hz lock for Urdu/Hindi: pitch x1.0495, tempo exactly 1.0.
    ffmpeg rubberband does pitch-only shifting; the output duration
    stays the same as the input. Raises RuntimeError on failure."""
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-af",
        f"rubberband=pitch={HEYGEN_PITCH_FACTOR}:tempo=1.0",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError(
            "pitch shift (rubberband) fail ho gaya: "
            + (proc.stderr or "").strip()[-200:]
        )


def heygen_speak(api_key: str, payload: dict) -> tuple[bytes, str]:
    """One HeyGen speech call. Returns (audio bytes, mime type). The
    endpoint returns a JSON with an audio URL (44.1 kHz WAV by
    default); the audio is then downloaded. If the endpoint ever
    returns raw audio instead, that is used directly. Any provider
    failure is a plain RuntimeError — the caller turns it into a
    failed job, never a fake voice file."""
    import urllib.error
    import urllib.parse
    import urllib.request

    req = urllib.request.Request(
        HEYGEN_TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            content_type = resp.headers.get_content_type()
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HeyGen API error ({exc.code}): {detail}")
    except OSError as exc:
        raise RuntimeError(f"HeyGen request failed: {exc}")
    if content_type.startswith("audio/"):
        return body, content_type
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("HeyGen returned an unreadable response")
    audio_url = None
    if isinstance(data, dict):
        inner = data.get("data") or {}
        if isinstance(inner, dict):
            audio_url = inner.get("audio_url") or inner.get("url")
        audio_url = audio_url or data.get("audio_url") or data.get("url")
    if not audio_url:
        raise RuntimeError(
            "HeyGen returned no audio URL: " + json.dumps(data)[:200]
        )
    try:
        with urllib.request.urlopen(audio_url, timeout=180) as audio_resp:
            audio = audio_resp.read()
            mime = audio_resp.headers.get_content_type() or "audio/wav"
    except OSError as exc:
        raise RuntimeError(f"HeyGen audio download failed: {exc}")
    if not audio:
        raise RuntimeError("HeyGen returned an empty audio file")
    return audio, mime


async def _run_heygen_speak(
    job_id: int, project_id: int, text: str, language: str, voice_id: str
) -> None:
    """Background worker: HeyGen call -> download -> 106 Hz pitch lock
    (hi only) -> VO asset. A failure is a plain job error, never a
    fake voice file. No live call happens without a key."""
    payload = build_heygen_speech_request(voice_id, text, language)
    # Audit sample: the exact request that WOULD be sent (no key in
    # it — the key is a header). Written before the key check, so it
    # exists even when the job fails for a missing key.
    try:
        (DATA_DIR / "heygen-speech-request-sample.json").write_text(
            json.dumps(
                {
                    "endpoint": HEYGEN_TTS_URL,
                    "headers": [
                        "Content-Type: application/json",
                        "X-Api-Key: <from Settings, never stored here>",
                    ],
                    "body": payload,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    with db() as conn:
        api_key = _heygen_key(conn)
    if not api_key:
        with db() as conn:
            _set_job(conn, job_id, "failed", HEYGEN_KEY_MISSING_MSG)
        return
    if not voice_id:
        with db() as conn:
            _set_job(conn, job_id, "failed", HEYGEN_VOICE_MISSING_MSG)
        return
    with db() as conn:
        _set_job(conn, job_id, "running")
    try:
        audio_bytes, mime = await asyncio.to_thread(
            heygen_speak, api_key, payload
        )
    except RuntimeError as exc:
        with db() as conn:
            _set_job(conn, job_id, "failed", str(exc))
        return
    stamp = int(time.time())
    folder = PROJECTS_DIR / str(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    ext = ".wav" if "wav" in mime else ".mp3"
    raw_name = f"voice_heygen_{stamp}_raw{ext}"
    raw_disk = folder / raw_name
    raw_disk.write_bytes(audio_bytes)
    final_disk = raw_disk
    final_name = raw_name
    pitch_applied = 0
    if language == "hi" and _rubberband_available():
        # 106 Hz lock: pitch x1.0495, tempo untouched. The raw file
        # stays on disk next to it for audit; the pitched file is the
        # VO asset.
        pitched_name = f"voice_heygen_{stamp}.mp3"
        pitched_disk = folder / pitched_name
        try:
            await asyncio.to_thread(
                _apply_106hz_pitch, raw_disk, pitched_disk
            )
        except RuntimeError as exc:
            with db() as conn:
                _set_job(conn, job_id, "failed", str(exc))
            return
        final_disk = pitched_disk
        final_name = pitched_name
        pitch_applied = 1
    # When language is hi but rubberband is missing on this PC, the raw
    # audio is still saved (a paid generation is never thrown away) and
    # pitch_applied stays 0 — the UI says so plainly.
    rel = f"projects/{project_id}/{final_name}"
    duration_s = round(probe_duration(final_disk), 3)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'voice', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
        conn.execute(
            "INSERT INTO heygen_voices (project_id, job_id, asset_id,"
            " voice_id, language, pitch_applied, pitch_factor,"
            " duration_s, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                job_id,
                asset_id,
                voice_id,
                language,
                pitch_applied,
                HEYGEN_PITCH_FACTOR if pitch_applied else 1.0,
                duration_s,
                utcnow(),
            ),
        )
        _set_job(conn, job_id, "done")
        conn.execute(
            "UPDATE jobs SET output_path = ? WHERE id = ?",
            (rel, job_id),
        )


@app.post("/api/projects/{project_id}/heygen/speak", status_code=202)
def heygen_speak_endpoint(
    project_id: int, body: HeyGenSpeakIn, background_tasks: BackgroundTasks
) -> dict:
    """Generate a voiceover in the user's OWN HeyGen clone voice. The
    job fails honestly when no key (or no voice_id) is set — nothing is
    ever faked. The live call only happens inside the background worker,
    with the key from Settings. voice_id must be a 32-hex-char HeyGen
    voice id when given; empty means the saved clone voice."""
    language = body.language.strip().lower()
    if language not in {"en", "hi"}:
        raise HTTPException(
            status_code=400,
            detail="language sirf 'en' (English) ya 'hi' (Urdu/Hindi) ho sakti hai",
        )
    voice_id = body.voice_id.strip()
    if voice_id and not re.fullmatch(r"[0-9a-f]{32}", voice_id):
        raise HTTPException(
            status_code=400,
            detail="voice_id HeyGen voice id jaisa nahi hai (32 hex characters)",
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        if not voice_id:
            voice_id = _heygen_voice_id(conn)
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at,"
            " updated_at) VALUES (?, 'heygen-voice', 'queued', ?, ?)",
            (project_id, now, now),
        )
        job_id = cur.lastrowid
    background_tasks.add_task(
        _run_heygen_speak, job_id, project_id, body.text, language, voice_id
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "language": language,
        "voice_id": voice_id,
        "model": HEYGEN_VOICE_MODEL,
    }


@app.get("/api/projects/{project_id}/heygen-voices")
def list_heygen_voices(project_id: int) -> list:
    """Finished HeyGen clone voiceovers for a project, with their job
    status, pitch-lock state and VO asset path. The audio plays from
    /files/ like any uploaded voiceover."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            "SELECT hv.*, a.path AS asset_path, j.status AS job_status,"
            " j.error AS job_error FROM heygen_voices hv"
            " LEFT JOIN assets a ON a.id = hv.asset_id"
            " LEFT JOIN jobs j ON j.id = hv.job_id"
            " WHERE hv.project_id = ? ORDER BY hv.id DESC",
            (project_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["pitch_applied"] = bool(d["pitch_applied"])
        out.append(d)
    return out


@app.get("/api/heygen/status")
def heygen_status() -> dict:
    """HeyGen integration state for the UI. key_configured is a bool
    only — the key itself is never returned. The free note is the
    plain truth: HeyGen is NOT a free-tier default."""
    with db() as conn:
        api_key = _heygen_key(conn)
        voice_id = _heygen_voice_id(conn)
    return {
        "key_configured": bool(api_key),
        "voice_id": voice_id,
        "voice_name": "HeyGen clone voice" if voice_id else "",
        "model": HEYGEN_VOICE_MODEL,
        "pitch_factor": HEYGEN_PITCH_FACTOR,
        "pitch_languages": ["hi"],
        "rubberband_available": _rubberband_available(),
        "free_note": (
            "HeyGen free-tier default NAHI hai — Turbo paid hai"
            " ($4/1M characters); Turbo Free 30 Nov 2026 tak free hai."
            " Apni key aur apni clone voice_id Settings me lagayen."
        ),
    }


@app.post("/api/projects/{project_id}/timeline/auto-sync", status_code=201)
def auto_sync(project_id: int, body: AutoSyncIn | None = None) -> dict:
    """Build (or rebuild) the project's timeline.

    Script-beat mode (default): clip durations follow the SCRIPT — each
    clip gets words/total-words x VO duration, so the visuals change on
    the dialogue beats instead of on equal slices. Falls back to the
    equal split only when a clip has no caption text. mode="equal"
    forces the old equal split. With no voiceover, 3 s per image.
    When the project has a script, its sentence scenes drive the
    clips — one clip per sentence, images cycling across them (so the
    visual changes on every sentence). Without a script, one clip per
    image (the old behaviour). Scene texts passed here also become
    the clip captions. When no captions are passed, captions from the
    previous timeline are kept (by position) so a re-sync does not
    wipe edited captions.
    """
    body = body or AutoSyncIn()
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        images = conn.execute(
            "SELECT * FROM assets WHERE project_id = ? AND kind = 'image'"
            " AND COALESCE(placeholder, 0) = 0 ORDER BY id",
            (project_id,),
        ).fetchall()
        if not images:
            raise HTTPException(
                status_code=400, detail="upload images first, then auto-sync"
            )
        vo = conn.execute(
            "SELECT * FROM assets WHERE project_id = ? AND kind = 'voice'"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        vo_duration = 0.0
        vo_asset_id = None
        if vo is not None:
            vo_asset_id = vo["id"]
            vo_duration = probe_duration(DATA_DIR / vo["path"])
        # Sentence scenes drive the clips when the project has a
        # script: one clip per sentence, images cycling across them
        # (image i mod n), captions are the sentence texts. Without
        # a script, the old behaviour stands — one clip per image.
        script_row = conn.execute(
            "SELECT id FROM scripts WHERE project_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        script_scenes: list[dict] = []
        if script_row is not None:
            script_scenes = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM scenes WHERE script_id = ?"
                    " ORDER BY position, id",
                    (script_row["id"],),
                ).fetchall()
            ]
        if script_scenes:
            n_clips = len(script_scenes)
            if body.captions is not None:
                captions = [
                    (body.captions[i] if i < len(body.captions) else "")
                    for i in range(n_clips)
                ]
            else:
                captions = [s["text"] for s in script_scenes]
            clip_images = [images[i % len(images)] for i in range(n_clips)]
        else:
            # Captions: explicit scene texts win; otherwise keep the
            # previous timeline's captions (by position); otherwise
            # empty.
            old_captions: list[str] = []
            old = conn.execute(
                "SELECT id FROM timelines WHERE project_id = ? ORDER BY id DESC"
                " LIMIT 1",
                (project_id,),
            ).fetchone()
            if old is not None:
                rows = conn.execute(
                    "SELECT caption_text FROM clips WHERE timeline_id = ?"
                    " ORDER BY position, id",
                    (old["id"],),
                ).fetchall()
                old_captions = [r["caption_text"] for r in rows]
            if body.captions is not None:
                captions = [
                    (body.captions[i] if i < len(body.captions) else "")
                    for i in range(len(images))
                ]
            else:
                captions = [
                    (old_captions[i] if i < len(old_captions) else "")
                    for i in range(len(images))
                ]
            clip_images = list(images)
        n_clips = len(clip_images)
        if body.mode == "equal" or vo_duration <= 0:
            per_clip = (
                vo_duration / n_clips if vo_duration > 0 else DEFAULT_CLIP_S
            )
            durations = [round(per_clip, 3)] * n_clips
            # Last clip takes the rounding remainder so the total is exact.
            durations[-1] = round(
                (vo_duration if vo_duration > 0 else per_clip * n_clips)
                - sum(durations[:-1]),
                3,
            )
        else:
            durations = beat_durations(
                [len(c.split()) for c in captions], vo_duration
            )
        total = round(sum(durations), 3)
        # Replace any previous timeline for this project.
        # Runs keep a timeline_id FK to their timeline: clear it for
        # the timelines about to be replaced, or the DELETE below
        # fails the foreign key (the run keeps its MP4/SRT paths).
        conn.execute(
            "UPDATE runs SET timeline_id = NULL WHERE timeline_id IN"
            " (SELECT id FROM timelines WHERE project_id = ?)",
            (project_id,),
        )
        old_all = conn.execute(
            "SELECT id FROM timelines WHERE project_id = ?", (project_id,)
        ).fetchall()
        for row in old_all:
            conn.execute("DELETE FROM clips WHERE timeline_id = ?", (row["id"],))
            conn.execute("DELETE FROM timelines WHERE id = ?", (row["id"],))
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO timelines (project_id, vo_duration_s, vo_asset_id,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, total, vo_asset_id, now, now),
        )
        timeline_id = cur.lastrowid
        start = 0.0
        for i, img in enumerate(clip_images):
            end = round(start + durations[i], 3)
            conn.execute(
                "INSERT INTO clips (timeline_id, asset_id, position, start_s,"
                " end_s, caption_text, effect) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    timeline_id,
                    img["id"],
                    i,
                    round(start, 3),
                    end,
                    captions[i],
                    effect_for_position(i),
                ),
            )
            start = end
        return timeline_detail(conn, timeline_id)


@app.get("/api/projects/{project_id}/timeline")
def get_project_timeline(project_id: int) -> dict | None:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        detail = latest_timeline_for_project(conn, project_id)
    # No timeline yet is normal empty state (new project), not an
    # error — return null with 200 so the UI does not log a 404 for
    # every project card on every page load.
    return detail


@app.get("/api/timelines/{timeline_id}")
def get_timeline(timeline_id: int) -> dict:
    with db() as conn:
        return timeline_detail(conn, timeline_id)


@app.put("/api/timelines/{timeline_id}/clips/{clip_id}")
def update_clip(timeline_id: int, clip_id: int, body: ClipUpdate) -> dict:
    with db() as conn:
        clip = conn.execute(
            "SELECT * FROM clips WHERE id = ? AND timeline_id = ?",
            (clip_id, timeline_id),
        ).fetchone()
        if clip is None:
            raise HTTPException(status_code=404, detail="clip not found")
        start = body.start_s if body.start_s is not None else clip["start_s"]
        end = body.end_s if body.end_s is not None else clip["end_s"]
        if start < 0 or end <= start:
            raise HTTPException(
                status_code=400, detail="clip needs start >= 0 and end > start"
            )
        caption = (
            body.caption_text if body.caption_text is not None
            else clip["caption_text"]
        )
        position = (
            body.position if body.position is not None else clip["position"]
        )
        effect = clip["effect"]
        if body.effect is not None:
            # Empty string clears the stored effect back to "auto"
            # (decided by position); any other value must be a real
            # preset, or the request is a plain 400.
            stripped = body.effect.strip()
            if stripped == "":
                effect = ""
            elif stripped in CLIP_EFFECTS:
                effect = stripped
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "effect must be one of: " + ", ".join(CLIP_EFFECTS)
                    ),
                )
        conn.execute(
            "UPDATE clips SET start_s = ?, end_s = ?, caption_text = ?,"
            " position = ?, effect = ? WHERE id = ?",
            (round(start, 3), round(end, 3), caption, position, effect, clip_id),
        )
        if body.position is not None and body.position != clip["position"]:
            # Reorder fix (slice 1 bug): swapping positions alone left
            # the clips' start/end times in the old order, so the
            # timeline played out of order — and a lone position PUT left
            # two clips sharing one position. A position change is a real
            # swap: the clip sitting at the target position takes this
            # clip's old position, then all clips are re-laid end to end
            # by position, keeping each clip's own duration.
            other = conn.execute(
                "SELECT id FROM clips WHERE timeline_id = ? AND position = ?"
                " AND id != ?",
                (timeline_id, body.position, clip_id),
            ).fetchone()
            if other is not None:
                conn.execute(
                    "UPDATE clips SET position = ? WHERE id = ?",
                    (clip["position"], other["id"]),
                )
            rows = conn.execute(
                "SELECT id, end_s - start_s AS dur FROM clips"
                " WHERE timeline_id = ? ORDER BY position, id",
                (timeline_id,),
            ).fetchall()
            t = 0.0
            for r in rows:
                dur = round(r["dur"], 3)
                conn.execute(
                    "UPDATE clips SET start_s = ?, end_s = ? WHERE id = ?",
                    (round(t, 3), round(t + dur, 3), r["id"]),
                )
                t += dur
        conn.execute(
            "UPDATE timelines SET updated_at = ? WHERE id = ?",
            (utcnow(), timeline_id),
        )
        return timeline_detail(conn, timeline_id)


@app.post("/api/timelines/{timeline_id}/apply-style")
def apply_style(timeline_id: int, body: ApplyStyleIn) -> dict:
    if body.style_dna_id is None and body.caption_style_id is None:
        raise HTTPException(
            status_code=400, detail="pass style_dna_id and/or caption_style_id"
        )
    with db() as conn:
        tl = conn.execute(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        ).fetchone()
        if tl is None:
            raise HTTPException(status_code=404, detail="timeline not found")
        if body.style_dna_id is not None:
            row = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?", (body.style_dna_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="style DNA not found")
        if body.caption_style_id is not None:
            row = conn.execute(
                "SELECT id FROM caption_styles WHERE id = ?",
                (body.caption_style_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=404, detail="caption style not found"
                )
        conn.execute(
            "UPDATE timelines SET style_dna_id = COALESCE(?, style_dna_id),"
            " caption_style_id = COALESCE(?, caption_style_id),"
            " updated_at = ? WHERE id = ?",
            (body.style_dna_id, body.caption_style_id, utcnow(), timeline_id),
        )
        return timeline_detail(conn, timeline_id)


@app.get("/api/timelines/{timeline_id}/srt", response_class=PlainTextResponse)
def get_srt(timeline_id: int) -> str:
    with db() as conn:
        detail = timeline_detail(conn, timeline_id)
    return build_srt(detail["clips"])


# --- Phase 3 slice 3: per-scene regenerate + deliverables ---------------

def _queue_render(
    conn, timeline: dict, background_tasks: BackgroundTasks,
    options: dict | None = None,
) -> dict:
    """Create a render job and queue run_render for it. Shared by the
    first render and by re-render: a re-render never touches the old
    MP4 — run_render writes a new timestamped file, so the previous
    video stays playable until the new one succeeds. The chosen
    options (quality + atmosphere) are stored on the job row, so the
    render queue can say what each job actually produced."""
    now = utcnow()
    # The timeline id rides in the options so a later resume knows
    # which timeline this job renders — the jobs table has no column
    # for it (Phase 7 slice 3).
    stored_options = dict(options or {})
    stored_options["timeline_id"] = timeline["id"]
    cur = conn.execute(
        "INSERT INTO jobs (project_id, kind, status, created_at, updated_at,"
        " options_json) VALUES (?, 'render', 'queued', ?, ?, ?)",
        (timeline["project_id"], now, now, json.dumps(stored_options)),
    )
    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    background_tasks.add_task(run_render, job["id"], timeline["id"])
    return dict(job)


def render_options(body) -> dict:
    """Validated render options from a request body (or the honest
    defaults when the caller sent none). Cross-check slice: the
    named atmosphere preset, caption size % / position, and the
    captions on/off toggle are validated here too — an unknown
    preset or position is a plain 400, never a silent fallback."""
    if body is None:
        return {}
    quality = (body.quality or "1080p").strip()
    if quality not in RENDER_QUALITIES:
        raise HTTPException(
            status_code=400,
            detail=(
                "quality must be one of: "
                + ", ".join(sorted(RENDER_QUALITIES))
            ),
        )
    preset = (body.atmosphere_preset or "").strip()
    if preset and preset not in ATMOSPHERE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"atmosphere preset '{preset}' nahi — in me se chunein:"
                f" {', '.join(ATMOSPHERE_PRESETS)}"
            ),
        )
    position = (body.caption_position or "bottom").strip()
    if position not in ("bottom", "center", "top"):
        raise HTTPException(
            status_code=400,
            detail="caption position bottom / center / top me se ho",
        )
    return {
        "quality": quality,
        "vignette": bool(body.vignette),
        "grain": bool(body.grain),
        "warm": bool(body.warm),
        "atmosphere_preset": preset,
        "caption_size_pct": int(body.caption_size_pct or 100),
        "caption_position": position,
        "captions": bool(body.captions),
    }


def latest_done_render_job(conn, project_id: int) -> dict | None:
    """The project's current video: the newest render job that finished
    with a real output file. Failed/queued renders are never current."""
    row = conn.execute(
        "SELECT * FROM jobs WHERE project_id = ? AND kind = 'render'"
        " AND status = 'done' AND output_path IS NOT NULL"
        " ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def current_video(conn, project_id: int) -> dict | None:
    """{job_id, output_path, duration_s} for the current video, or None
    when the project has no finished render yet. A video still in the
    old data/renders/ folder is MIGRATED to output/YYYY-MM-DD/ on
    first access here (name unchanged) and the stored path updated —
    old videos keep opening, they just live in the new place after."""
    job = latest_done_render_job(conn, project_id)
    if job is None:
        return None
    rel = migrate_media(conn, job["output_path"])
    disk = media_path(rel)
    if disk is None or not disk.exists():
        return None
    return {
        "job_id": job["id"],
        "output_path": rel,
        "duration_s": round(probe_duration(disk), 3),
    }


def probe_image_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of an image file via ffprobe, or None."""
    try:
        proc = subprocess.run(
            [
                shutil.which("ffprobe") or "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        w, h = (proc.stdout or "").strip().split(",")
        return int(w), int(h)
    except Exception:  # noqa: BLE001 - any probe failure means unknown size
        return None


# Words too common to be useful as YouTube tags.
TAG_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "nor", "on", "at", "to",
    "from", "by", "of", "in", "into", "with", "without", "over", "under",
    "after", "before", "while", "when", "where", "which", "who", "whom",
    "whose", "why", "how", "what", "that", "this", "these", "those",
    "there", "here", "then", "than", "also", "just", "even", "still",
    "more", "most", "some", "any", "all", "each", "every", "both",
    "have", "has", "had", "was", "were", "are", "been", "being",
    "will", "would", "can", "could", "should", "may", "might",
    "they", "them", "their", "he", "she", "his", "her", "him",
    "you", "your", "we", "our", "us", "it", "its", "not", "no",
    "one", "two", "first", "said", "says", "like", "get", "got",
    "back", "down", "out", "off", "about", "between", "through",
}


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return parts[0].strip()


def _keywords(text: str, limit: int = 12) -> list[str]:
    """Content words from the script, in first-seen order: words of 4+
    letters that are not stopwords. Template-only — no AI, no key."""
    seen: list[str] = []
    for word in re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text or ""):
        w = word.lower().strip("-'")
        if len(w) < 4 or w in TAG_STOPWORDS or w in seen:
            continue
        seen.append(w)
        if len(seen) >= limit:
            break
    return seen


def build_youtube_metadata(topic: str, scenes: list) -> dict:
    """Draft YouTube title / description / tags from the real script.
    Title is the topic (or the first scene's first sentence); the
    description is the hook + a scene list + a subscribe CTA; tags are
    the script's own keywords plus honest generic ones. Nothing is
    invented beyond the script text."""
    title = (topic or "").strip()
    if not title and scenes:
        title = _first_sentence(scenes[0].get("text", ""))
    title = title[:100]
    hook = scenes[0].get("text", "").strip() if scenes else ""
    lines = [hook, "", "Is video mein:"]
    for scene in scenes[:6]:
        first = _first_sentence(scene.get("text", ""))
        if first:
            lines.append(f"- {first}")
    lines += [
        "",
        "Aisi aur kahaniyan dekhne ke liye subscribe karein.",
    ]
    description = "\n".join(lines).strip()[:5000]
    joined = " ".join([topic] + [s.get("text", "") for s in scenes])
    tags = _keywords(joined) + ["documentary", "history", "true story"]
    return {
        "title": title,
        "description": description,
        "tags": ", ".join(tags[:15]),
    }


@app.post(
    "/api/timelines/{timeline_id}/clips/{clip_id}/replace-image",
    status_code=201,
)
async def replace_clip_image(
    timeline_id: int, clip_id: int, file: UploadFile = File(...)
) -> dict:
    """Per-scene regenerate: swap one clip's image for a newly uploaded
    one. Everything else — VO, other clips, durations, captions — is
    untouched. The clip is flagged image_replaced so the UI says so.
    The old asset stays in the asset list (honest history); a
    placeholder it replaced is simply no longer used by this clip."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"image must be one of: {', '.join(sorted(IMAGE_EXTS))}",
        )
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="image too large (max 50 MB)")
    with db() as conn:
        tl = conn.execute(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        ).fetchone()
        if tl is None:
            raise HTTPException(status_code=404, detail="timeline not found")
        clip = conn.execute(
            "SELECT * FROM clips WHERE id = ? AND timeline_id = ?",
            (clip_id, timeline_id),
        ).fetchone()
        if clip is None:
            raise HTTPException(status_code=404, detail="clip not found")
        project_id = tl["project_id"]
        folder = PROJECTS_DIR / str(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        name = (
            f"img_{int(time.time())}_replaced_{safe_filename(file.filename)}"
        )
        (folder / name).write_bytes(data)
        rel = f"projects/{project_id}/{name}"
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'image', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
        conn.execute(
            "UPDATE clips SET asset_id = ?, image_replaced = 1 WHERE id = ?",
            (asset_id, clip_id),
        )
        conn.execute(
            "UPDATE timelines SET updated_at = ? WHERE id = ?",
            (utcnow(), timeline_id),
        )
        return timeline_detail(conn, timeline_id)


@app.post("/api/timelines/{timeline_id}/rerender", status_code=202)
def rerender_timeline(
    timeline_id: int, background_tasks: BackgroundTasks,
    body: RenderIn | None = None,
) -> dict:
    """Re-render the same timeline after a per-scene image swap (or a
    caption/style edit). The old MP4 is never deleted or overwritten:
    run_render writes a new timestamped file, so the project keeps a
    working video until the new render succeeds."""
    with db() as conn:
        tl = conn.execute(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        ).fetchone()
        if tl is None:
            raise HTTPException(status_code=404, detail="timeline not found")
        clips = conn.execute(
            "SELECT id FROM clips WHERE timeline_id = ?", (timeline_id,)
        ).fetchall()
        if not clips:
            raise HTTPException(
                status_code=400, detail="timeline has no clips to render"
            )
        return _queue_render(
            conn, dict(tl), background_tasks, render_options(body)
        )


@app.get("/api/projects/{project_id}/deliverables")
def get_deliverables(project_id: int) -> dict:
    """Everything ready to publish: the current MP4, the latest
    thumbnail (a real frame from that MP4), and the saved YouTube
    metadata. Any part may be null — nothing is faked when it is
    missing."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        video = current_video(conn, project_id)
        thumb = conn.execute(
            "SELECT * FROM thumbnails WHERE project_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        meta = conn.execute(
            "SELECT * FROM project_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return {
        "project_id": project_id,
        "video": video,
        "thumbnail": dict(thumb) if thumb else None,
        "metadata": dict(meta) if meta else None,
    }


@app.post("/api/projects/{project_id}/thumbnail", status_code=201)
def create_thumbnail(project_id: int, body: ThumbnailIn) -> dict:
    """Pull one real frame out of the current rendered MP4 as a
    JPG thumbnail (default 1280x720; Magic Mode passes the video's
    aspect size). Default time is the middle of the first clip (the
    video's opening image); pass timestamp_s for any other moment.
    No video yet -> plain 400, never a stock picture."""
    with db() as conn:
        project = conn.execute(
            "SELECT id, name FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        video = current_video(conn, project_id)
        if video is None:
            raise HTTPException(
                status_code=400,
                detail="pehle video render karein — thumbnail ke liye MP4 chahiye",
            )
        video_path = media_path(video["output_path"])
        if video_path is None or not video_path.exists():
            raise HTTPException(
                status_code=400, detail="rendered video file nahi mili"
            )
        duration = video["duration_s"]
        ts = body.timestamp_s
        if ts is None:
            tl = latest_timeline_for_project(conn, project_id)
            if tl and tl["clips"]:
                first = tl["clips"][0]
                ts = (first["start_s"] + first["end_s"]) / 2
            elif duration > 0:
                ts = duration / 2
            else:
                ts = 0.0
        if duration > 0:
            ts = max(0.0, min(float(ts), max(0.0, duration - 0.1)))
        else:
            ts = 0.0
        source_job_id = video["job_id"]
    # Release Packaging: thumbnails bhi final deliverables hain — aaj
    # ke output/ folder me, project ke naam se.
    folder = output_dir_for_today()
    name = _dated_name(_slugify(project["name"], f"project-{project_id}") + "_thumb", "jpg")
    disk = folder / name
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg", "-y",
        "-ss", f"{ts:.3f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-vf", f"scale={body.width}:{body.height}:force_original_aspect_ratio=decrease,"
               f"pad={body.width}:{body.height}:(ow-iw)/2:(oh-ih)/2",
        "-q:v", "3",
        str(disk),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not disk.exists() or disk.stat().st_size == 0:
        lines = (proc.stderr or "").strip().splitlines()
        raise HTTPException(
            status_code=500,
            detail="thumbnail failed: "
            + (lines[-1] if lines else "ffmpeg failed"),
        )
    size = probe_image_size(disk)
    if size != (body.width, body.height):
        raise HTTPException(
            status_code=500,
            detail=f"thumbnail wrong size: {size}",
        )
    rel = f"output/{_today_str()}/{name}"
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO thumbnails (project_id, path, timestamp_s,"
            " source_job_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, rel, round(ts, 3), source_job_id, utcnow()),
        )
        row = conn.execute(
            "SELECT * FROM thumbnails WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}/metadata")
def get_metadata(project_id: int) -> dict:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        meta = conn.execute(
            "SELECT * FROM project_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    if meta is None:
        return {
            "project_id": project_id,
            "title": "",
            "description": "",
            "tags": "",
            "updated_at": None,
        }
    return dict(meta)


@app.put("/api/projects/{project_id}/metadata")
def put_metadata(project_id: int, body: MetadataIn) -> dict:
    """Save hand-edited YouTube title / description / tags."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        conn.execute(
            "INSERT INTO project_metadata"
            " (project_id, title, description, tags, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(project_id) DO UPDATE SET"
            " title = excluded.title,"
            " description = excluded.description,"
            " tags = excluded.tags,"
            " updated_at = excluded.updated_at",
            (
                project_id,
                body.title.strip(),
                body.description.strip(),
                body.tags.strip(),
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM project_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return dict(row)


@app.post("/api/projects/{project_id}/metadata/generate", status_code=201)
def generate_metadata(project_id: int) -> dict:
    """Draft the YouTube pack from the project's latest script —
    template only, no AI call, no key. Overwrites any saved draft;
    edit it afterwards with PUT /metadata."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        script = conn.execute(
            "SELECT * FROM scripts WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if script is None:
            raise HTTPException(
                status_code=400,
                detail="pehle script save karein — metadata script se banta hai",
            )
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script["id"],),
        ).fetchall()
        draft = build_youtube_metadata(
            script["topic"], [dict(s) for s in scenes]
        )
        conn.execute(
            "INSERT INTO project_metadata"
            " (project_id, title, description, tags, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(project_id) DO UPDATE SET"
            " title = excluded.title,"
            " description = excluded.description,"
            " tags = excluded.tags,"
            " updated_at = excluded.updated_at",
            (
                project_id,
                draft["title"],
                draft["description"],
                draft["tags"],
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM project_metadata WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return dict(row)


@app.post("/api/timelines/{timeline_id}/render", status_code=202)
def render_timeline(
    timeline_id: int, background_tasks: BackgroundTasks,
    body: RenderIn | None = None,
) -> dict:
    with db() as conn:
        tl = conn.execute(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        ).fetchone()
        if tl is None:
            raise HTTPException(status_code=404, detail="timeline not found")
        clips = conn.execute(
            "SELECT id FROM clips WHERE timeline_id = ?", (timeline_id,)
        ).fetchall()
        if not clips:
            raise HTTPException(
                status_code=400, detail="timeline has no clips to render"
            )
        return _queue_render(
            conn, dict(tl), background_tasks, render_options(body)
        )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return dict(row)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int) -> dict:
    """Cancel a job (StickFilm 'Stop run' parity). A queued job is
    marked 'cancelled' at once and its worker never starts (workers
    check the status first). A running render / reframe / final job
    has its live ffmpeg killed — the worker then marks it
    'cancelled', not 'failed'. A done / failed / cancelled job is a
    plain 400. A cancelled render can be re-queued with the normal
    render button (the existing Resume also works for interrupted
    jobs)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        if row["status"] not in ("queued", "running"):
            raise HTTPException(
                status_code=400,
                detail=f"job {row['status']} hai — cancel nahi ho sakta",
            )
        _CANCELLED_JOBS.add(job_id)
        with _RUNNING_PROCS_LOCK:
            proc = _RUNNING_PROCS.get(job_id)
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
            " WHERE id = ?",
            ("cancelled", "cancel kiya gaya", utcnow(), job_id),
        )
    return {"id": job_id, "status": "cancelled"}


# --- Phase 7 slice 1: StickMan + StoryCraft -------------------------------

MASTER_PROMPT_CATEGORIES = {"hook", "story", "style-dna", "viral-short"}

# Pose picker: keyword scan of the scene text first (the words say
# what the figure does), rotating fallback by scene position so two
# neighbouring scenes never get the same pose by accident.
_POSE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("walking", ["walk", "walking", "chala", "chalna", "journey", "travel", "safar"]),
    ("pointing", ["point", "pointing", "ishara", "show", "dikha", "reveal", "dekho"]),
    ("thinking", ["think", "thinking", "soch", "wonder", "plan", "figure out", "samajh"]),
    ("celebrating", ["celebrat", "win", "won", "jeet", "victory", "khush", "success", "rich", "ameer"]),
    ("falling", ["fall", "falling", "gir", "trip", "collapse", "fail", "haar"]),
    ("sitting", ["sit", "sitting", "baith", "rest", "aaram", "fire", "aag"]),
]

_EXPRESSION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("sad", ["sad", "sorry", "regret", "afsoos", "dukhi", "cry", "rona"]),
    ("happy", ["happy", "glad", "khush", "win", "won", "celebrat", "success"]),
    ("angry", ["angry", "furious", "gussa", "rage", "cheat", "fraud", "dhoka"]),
    ("worried", ["scared", "fear", "darr", "worried", "danger", "khatra", "arrest", "handcuff"]),
]

_PROP_KEYWORDS: list[tuple[str, list[str]]] = [
    ("coins and a money bag", ["money", "coin", "paisa", "dollar", "rupee", "cash", "bank"]),
    ("a tall tower", ["tower", "eiffel", "minar"]),
    ("a vintage car", ["car", "gaari", "drive", "safar"]),
    ("an open book", ["book", "kitab", "read", "padh"]),
    ("a spear and a torch", ["spear", "torch", "bhaala", "mashaal", "fire", "aag"]),
]

_BACKGROUND_KEYWORDS: list[tuple[str, list[str]]] = [
    ("1920s Paris street", ["paris", "france", "eiffel"]),
    ("rocky desert at sunset", ["desert", "sehra", "rocky", "sunset"]),
    ("dark cave with a dying fire", ["cave", "gufa", "prehistoric", "ancient"]),
    ("busy stock-market floor", ["stock", "market", "bazaar", "share", "fund"]),
    ("mountain village", ["mountain", "village", "gaon", "hill", "pahad"]),
]


def _keyword_pick(text: str, table: list[tuple[str, list[str]]]) -> str | None:
    low = text.lower()
    for value, words in table:
        if any(w in low for w in words):
            return value
    return None


def pick_stickman_pose(text: str, position: int) -> str:
    """Pose for a scene: keyword first, else rotate through the
    library by position so neighbours differ."""
    hit = _keyword_pick(text, _POSE_KEYWORDS)
    if hit:
        return hit
    names = [p["name"] for p in STICKMAN_POSES]
    return names[position % len(names)]


def build_stickman_prompt(
    scene_text: str, position: int, style_name: str | None, char_name: str | None
) -> dict:
    """Template-built stick-figure animation prompt for one scene.
    No AI call, no key — the prompt is assembled from the scene's
    own words plus the picked pose / expression / props /
    background. The first clause of the scene is the action."""
    pose = pick_stickman_pose(scene_text, position)
    expression = _keyword_pick(scene_text, _EXPRESSION_KEYWORDS) or "neutral"
    props = _keyword_pick(scene_text, _PROP_KEYWORDS) or "none"
    background = _keyword_pick(scene_text, _BACKGROUND_KEYWORDS) or "plain warm"
    action = " ".join(scene_text.split())[:140].rstrip(". ")
    style_line = (
        f"Style: {style_name}. " if style_name else ""
    ) + ("Character: " + char_name + ". " if char_name else "")
    prompt = (
        "Flat 2D stick-figure animation frame, monochrome black lines on a"
        f" {background} background. One stick figure, pose: {pose},"
        f" expression: {expression}, action: {action}. Props: {props}."
        " Thick uniform black outlines, simple geometric forms, no"
        " shading, no photorealism, no 3D, no text in the image. Style:"
        " 2D Stickman (Monochrome Flat Vector). " + style_line
    ).strip()
    return {
        "pose": pose,
        "action": action,
        "expression": expression,
        "props": props,
        "background": background,
        "prompt": prompt,
    }


def _rotate(points: list[tuple[float, float]], cx: float, cy: float, deg: float):
    """Rotate points around (cx, cy) by deg degrees (falling pose)."""
    import math

    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
    return out


def render_stickman_png(
    pose: str, expression: str, props: str, out_path: Path
) -> None:
    """Draw a REAL stick-figure PNG with Pillow: head circle +
    body/limb lines in the chosen pose, face for the expression, and
    a simple prop shape when one is named. 1920x1080 so the frame
    goes straight into the 16:9 timeline. Pillow is imported lazily:
    when it is missing the caller gets a plain RuntimeError instead
    of the whole app failing to start."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            "pillow nahi hai — stickman frame ke liye pip install pillow"
            " chalaien (requirements.txt me hai)"
        ) from exc
    W, H = 1920, 1080
    GROUND_Y = 880
    INK = (20, 20, 20)
    img = Image.new("RGB", (W, H), (251, 246, 236))
    d = ImageDraw.Draw(img)
    d.line([(120, GROUND_Y), (1800, GROUND_Y)], fill=(216, 205, 180), width=6)
    lw = 12
    cx = 960
    # Skeleton joints (standing reference). Each pose overrides them.
    head_c = (cx, 430)
    head_r = 75
    neck = (cx, 505)
    shoulder_l, shoulder_r = (cx - 10, 560), (cx + 10, 560)
    hip = (cx, 700)
    if pose == "walking":
        leg_l = [(cx, 700), (cx - 80, 790), (cx - 120, 878)]
        leg_r = [(cx, 700), (cx + 70, 790), (cx + 110, 878)]
        arm_l = [(cx - 10, 560), (cx - 60, 640), (cx - 90, 700)]
        arm_r = [(cx + 10, 560), (cx + 60, 640), (cx + 100, 690)]
        torso = [neck, hip]
    elif pose == "pointing":
        leg_l = [(cx, 700), (cx - 30, 878)]
        leg_r = [(cx, 700), (cx + 30, 878)]
        arm_l = [(cx - 10, 560), (cx - 80, 700)]
        arm_r = [(cx + 10, 560), (cx + 160, 560)]
        torso = [neck, hip]
    elif pose == "thinking":
        leg_l = [(cx, 700), (cx - 15, 878)]
        leg_r = [(cx, 700), (cx + 15, 878)]
        arm_l = [(cx - 10, 560), (cx - 60, 660), (cx, 700)]
        arm_r = [(cx + 10, 560), (cx + 50, 640), (cx + 30, 520)]
        torso = [neck, hip]
    elif pose == "celebrating":
        leg_l = [(cx, 700), (cx - 70, 858)]
        leg_r = [(cx, 700), (cx + 70, 858)]
        arm_l = [(cx - 10, 560), (cx - 120, 420)]
        arm_r = [(cx + 10, 560), (cx + 120, 420)]
        torso = [neck, hip]
    elif pose == "falling":
        pts = _rotate(
            [
                (cx, 430),  # head
                (cx, 505),  # neck
                (cx - 10, 560),
                (cx + 10, 560),  # shoulders
                (cx, 700),  # hip
                (cx - 30, 878),
                (cx + 30, 878),  # feet
                (cx - 120, 420),
                (cx + 120, 420),  # hands
            ],
            cx,
            700,
            -32,
        )
        head_c = (int(pts[0][0]), int(pts[0][1]))
        neck = pts[1]
        shoulder_l, shoulder_r = pts[2], pts[3]
        hip = pts[4]
        leg_l = [hip, pts[5]]
        leg_r = [hip, pts[6]]
        arm_l = [shoulder_l, pts[7]]
        arm_r = [shoulder_r, pts[8]]
        torso = [neck, hip]
    elif pose == "sitting":
        hip = (cx, 760)
        head_c = (cx, 525)
        neck = (cx, 600)
        shoulder_l, shoulder_r = (cx - 10, 655), (cx + 10, 655)
        leg_l = [(cx, 760), (cx - 110, 760), (cx - 110, 878)]
        leg_r = [(cx, 760), (cx + 110, 760), (cx + 110, 878)]
        arm_l = [shoulder_l, (cx - 80, 700), (cx - 110, 760)]
        arm_r = [shoulder_r, (cx + 80, 700), (cx + 110, 760)]
        torso = [neck, hip]
    else:  # standing (and any unknown pose falls back to standing)
        leg_l = [(cx, 700), (cx - 40, 878)]
        leg_r = [(cx, 700), (cx + 40, 878)]
        arm_l = [(cx - 10, 560), (cx - 80, 700)]
        arm_r = [(cx + 10, 560), (cx + 80, 700)]
        torso = [neck, hip]
    # Limbs + torso, then the head.
    for poly in (leg_l, leg_r, arm_l, arm_r, torso):
        d.line(poly, fill=INK, width=lw, joint="curve")
    d.ellipse(
        [
            head_c[0] - head_r,
            head_c[1] - head_r,
            head_c[0] + head_r,
            head_c[1] + head_r,
        ],
        outline=INK,
        width=10,
    )
    # Face: two eyes + a mouth for the expression.
    ex, ey = head_c[0] - 28, head_c[1] - 15
    for ox in (-28, 28):
        d.ellipse(
            [head_c[0] + ox - 10, ey - 10, head_c[0] + ox + 10, ey + 10],
            fill=INK,
        )
    mx, my = head_c[0], head_c[1] + 30
    if expression == "happy":
        d.arc([mx - 32, my - 18, mx + 32, my + 26], start=15, end=165, fill=INK, width=8)
    elif expression == "sad":
        d.arc([mx - 32, my - 8, mx + 32, my + 36], start=195, end=345, fill=INK, width=8)
    elif expression == "angry":
        d.line([(ex - 12, ey - 28), (ex + 22, ey - 14)], fill=INK, width=8)
        d.line([(head_c[0] + 40, ey - 14), (head_c[0] + 6, ey - 28)], fill=INK, width=8)
        d.line([(mx - 30, my + 8), (mx + 30, my + 8)], fill=INK, width=8)
    elif expression == "worried":
        d.ellipse([mx - 12, my - 12, mx + 12, my + 12], outline=INK, width=7)
    else:  # neutral
        d.line([(mx - 30, my + 8), (mx + 30, my + 8)], fill=INK, width=8)
    # Props: simple black shapes at the side, same line style.
    low_props = (props or "").lower()
    px = 1300
    if "coin" in low_props or "money bag" in low_props:
        for ox, r in ((0, 18), (42, 15), (-38, 12)):
            d.ellipse(
                [px + ox - r, GROUND_Y - 2 * r, px + ox + r, GROUND_Y],
                outline=INK,
                width=7,
            )
        d.polygon(
            [(px + 95, GROUND_Y - 10), (px + 105, GROUND_Y - 95),
             (px + 155, GROUND_Y - 95), (px + 165, GROUND_Y - 10)],
            outline=INK,
        )
        d.line([(px + 112, GROUND_Y - 92), (px + 148, GROUND_Y - 92)], fill=INK, width=7)
    elif "tower" in low_props:
        d.polygon(
            [(px - 60, GROUND_Y), (px + 60, GROUND_Y), (px, GROUND_Y - 340)],
            outline=INK,
        )
        d.line([(px, GROUND_Y - 340), (px, GROUND_Y - 400)], fill=INK, width=7)
        d.line([(px, GROUND_Y - 400), (px + 45, GROUND_Y - 385)], fill=INK, width=7)
    elif "car" in low_props:
        d.rounded_rectangle(
            [px - 30, GROUND_Y - 110, px + 230, GROUND_Y - 30],
            radius=24,
            outline=INK,
            width=8,
        )
        for wx in (px + 20, px + 170):
            d.ellipse([wx - 26, GROUND_Y - 52, wx + 26, GROUND_Y], outline=INK, width=8)
    elif "book" in low_props:
        d.polygon(
            [(px - 90, GROUND_Y - 260), (px, GROUND_Y - 230),
             (px, GROUND_Y - 160), (px - 90, GROUND_Y - 190)],
            outline=INK,
        )
        d.polygon(
            [(px + 90, GROUND_Y - 260), (px, GROUND_Y - 230),
             (px, GROUND_Y - 160), (px + 90, GROUND_Y - 190)],
            outline=INK,
        )
    elif "spear" in low_props or "torch" in low_props:
        d.line([(px + 60, GROUND_Y), (px + 160, GROUND_Y - 360)], fill=INK, width=9)
        d.polygon(
            [(px + 160, GROUND_Y - 360), (px + 140, GROUND_Y - 300),
             (px + 185, GROUND_Y - 315)],
            outline=INK,
        )
        d.ellipse(
            [px + 130, GROUND_Y - 420, px + 190, GROUND_Y - 340],
            outline=INK,
            width=8,
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def _master_prompt_detail(conn, row) -> dict:
    style_name = None
    if row["style_dna_id"] is not None:
        s = conn.execute(
            "SELECT name FROM style_dna WHERE id = ?", (row["style_dna_id"],)
        ).fetchone()
        style_name = s["name"] if s else None
    d = dict(row)
    d["style_dna_name"] = style_name
    return d


def _stickman_frame_for_scene(conn, scene_id: int) -> dict | None:
    """Latest stickman frame linked to a scene (if any), with its
    verdict — so the prompt list can show the frame thumbnail."""
    row = conn.execute(
        "SELECT si.asset_id, a.path FROM scene_images si"
        " JOIN assets a ON a.id = si.asset_id"
        " WHERE si.scene_id = ? AND si.source = 'stickman'"
        " ORDER BY si.id DESC LIMIT 1",
        (scene_id,),
    ).fetchone()
    if row is None:
        return None
    verdict = _verdict_for_asset(conn, row["asset_id"])
    return {
        "asset_id": row["asset_id"],
        "path": row["path"],
        "verdict": (verdict or {}).get("verdict", "pending"),
    }


# --- endpoints ------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "kreafy-creator-studio",
        "version": APP_VERSION,
        "phase": "watermark-cleaner",
        "database": "sqlite",
        "ffmpeg": ffmpeg_info(),
    }


# --- Phase 7 slice 1: StickMan poses --------------------------------------


@app.get("/api/stickman-poses")
def list_stickman_poses() -> list:
    """The pose library: 7 poses with editable descriptions."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM stickman_poses ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.put("/api/stickman-poses/{pose_id}")
def update_stickman_pose(pose_id: int, body: StickmanPoseUpdate) -> dict:
    """Edit a pose's description. The name never changes — it is
    the contract with the renderer."""
    description = (body.description or "").strip()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM stickman_poses WHERE id = ?", (pose_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="pose not found")
        if not description:
            raise HTTPException(
                status_code=400, detail="pose description khaali nahi ho sakti"
            )
        conn.execute(
            "UPDATE stickman_poses SET description = ? WHERE id = ?",
            (description, pose_id),
        )
        row = conn.execute(
            "SELECT * FROM stickman_poses WHERE id = ?", (pose_id,)
        ).fetchone()
    return dict(row)


# --- Phase 7 slice 1: StickMan prompts + frames ---------------------------


@app.post("/api/scripts/{script_id}/stickman-prompts", status_code=201)
def generate_stickman_prompts(script_id: int) -> dict:
    """Build (or rebuild) one stick-figure prompt per scene of a
    script. Template-built from the scene's own words — no AI call,
    no key. Re-running replaces the old prompts for these scenes;
    scene text never changes."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
        if not scenes:
            raise HTTPException(
                status_code=400, detail="script me koi scene nahi hai"
            )
        style = resolve_script_style(conn, script["project_id"])
        char = get_character(conn, script["project_id"])
        now = utcnow()
        made = []
        for scene in scenes:
            built = build_stickman_prompt(
                scene["text"],
                scene["position"],
                style["name"] if style else None,
                char["name"] if char else None,
            )
            conn.execute(
                "DELETE FROM stickman_prompts WHERE scene_id = ?",
                (scene["id"],),
            )
            cur = conn.execute(
                "INSERT INTO stickman_prompts (scene_id, pose, action,"
                " expression, props, background, prompt, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scene["id"],
                    built["pose"],
                    built["action"],
                    built["expression"],
                    built["props"],
                    built["background"],
                    built["prompt"],
                    now,
                ),
            )
            made.append(cur.lastrowid)
    return {"script_id": script_id, "prompt_ids": made, "count": len(made)}


@app.get("/api/scripts/{script_id}/stickman-prompts")
def list_stickman_prompts(script_id: int) -> dict:
    """Stickman prompts for a script's scenes, in scene order, each
    with its scene text and any rendered frame linked to the scene."""
    with db() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        scenes = conn.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY position, id",
            (script_id,),
        ).fetchall()
        prompts = []
        for scene in scenes:
            row = conn.execute(
                "SELECT * FROM stickman_prompts WHERE scene_id = ?",
                (scene["id"],),
            ).fetchone()
            prompts.append(
                {
                    "scene_id": scene["id"],
                    "position": scene["position"],
                    "text": scene["text"],
                    "prompt": dict(row) if row else None,
                    "frame": _stickman_frame_for_scene(conn, scene["id"]),
                }
            )
    return {"script_id": script_id, "prompts": prompts}


@app.put("/api/stickman-prompts/{prompt_id}")
def update_stickman_prompt(prompt_id: int, body: StickmanPromptUpdate) -> dict:
    """Edit a stickman prompt (pose must be in the pose library)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM stickman_prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="stickman prompt not found"
            )
        patch = dict(row)
        if body.pose is not None:
            pose = body.pose.strip()
            known = conn.execute(
                "SELECT id FROM stickman_poses WHERE name = ?", (pose,)
            ).fetchone()
            if known is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"pose '{pose}' pose library me nahi hai",
                )
            patch["pose"] = pose
        for field in ("action", "expression", "props", "background", "prompt"):
            value = getattr(body, field)
            if value is not None:
                patch[field] = value.strip()
        if not patch["prompt"]:
            raise HTTPException(
                status_code=400, detail="prompt khaali nahi ho sakta"
            )
        conn.execute(
            "UPDATE stickman_prompts SET pose = ?, action = ?,"
            " expression = ?, props = ?, background = ?, prompt = ?"
            " WHERE id = ?",
            (
                patch["pose"],
                patch["action"],
                patch["expression"],
                patch["props"],
                patch["background"],
                patch["prompt"],
                prompt_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM stickman_prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
    return dict(row)


@app.post("/api/scenes/{scene_id}/stickman-frame", status_code=201)
def render_scene_stickman_frame(scene_id: int, body: StickmanFrameIn) -> dict:
    """Render a REAL stick-figure PNG for one scene (1920x1080,
    Pillow) and save it as a project image asset, linked to the
    scene with source 'stickman'. The frame then enters the same
    approve / reject flow as any image: approve it in VisualForge
    and 'Use approved in timeline' puts it in the CineCut timeline.
    Pose empty = the scene's stickman prompt pose (or 'standing'
    when there is none). Pillow missing -> plain 503, never a fake
    image."""
    with db() as conn:
        scene = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if scene is None:
            raise HTTPException(status_code=404, detail="scene not found")
        script = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (scene["script_id"],)
        ).fetchone()
        project_id = script["project_id"]
        prompt_row = conn.execute(
            "SELECT * FROM stickman_prompts WHERE scene_id = ?",
            (scene_id,),
        ).fetchone()
        pose = (body.pose or "").strip()
        if pose:
            known = conn.execute(
                "SELECT id FROM stickman_poses WHERE name = ?", (pose,)
            ).fetchone()
            if known is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"pose '{pose}' pose library me nahi hai",
                )
        else:
            pose = prompt_row["pose"] if prompt_row else "standing"
        props = (body.props or "").strip() or (
            prompt_row["props"] if prompt_row else ""
        )
        expression = prompt_row["expression"] if prompt_row else "neutral"
        folder = PROJECTS_DIR / str(project_id) / "stickman"
        name = f"stickman_scene{scene['position'] + 1}_{pose}.png"
        disk = folder / name
        try:
            render_stickman_png(pose, expression, props, disk)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        rel = f"projects/{project_id}/stickman/{name}"
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, 'image', ?, ?)",
            (project_id, rel, utcnow()),
        )
        asset_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO scene_images"
            " (scene_id, asset_id, source, created_at)"
            " VALUES (?, ?, 'stickman', ?)",
            (scene_id, asset_id, utcnow()),
        )
    return {
        "scene_id": scene_id,
        "asset_id": asset_id,
        "pose": pose,
        "expression": expression,
        "props": props,
        "path": rel,
        "url": media_url(rel),
        "verdict": "pending",
    }


# --- Phase 7 slice 1: StoryCraft Master Prompt library --------------------


@app.get("/api/master-prompts")
def list_master_prompts() -> list:
    """The Master Prompt library, with each prompt's linked Style
    DNA name (None when the style has no Style DNA entry)."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM master_prompts ORDER BY id"
        ).fetchall()
        return [_master_prompt_detail(conn, r) for r in rows]


@app.post("/api/master-prompts", status_code=201)
def create_master_prompt(body: MasterPromptIn) -> dict:
    """Add a master prompt. Empty name or template is a plain 400;
    an unknown category or style_dna_id is a plain 400 too."""
    name = (body.name or "").strip()
    category = (body.category or "").strip()
    template = (body.template or "").strip()
    source = (body.source or "").strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="master prompt ka naam likhein"
        )
    if not template:
        raise HTTPException(
            status_code=400, detail="master prompt ka template likhein"
        )
    if category not in MASTER_PROMPT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="category hook / story / style-dna / viral-short me se"
            " honi chahiye",
        )
    with db() as conn:
        if body.style_dna_id is not None:
            style = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.style_dna_id,),
            ).fetchone()
            if style is None:
                raise HTTPException(
                    status_code=400, detail="style_dna_id galat hai"
                )
        try:
            cur = conn.execute(
                "INSERT INTO master_prompts (name, category, template,"
                " style_dna_id, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, category, template, body.style_dna_id, source, utcnow()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{name}' naam ka master prompt pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM master_prompts WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _master_prompt_detail(conn, row)


@app.put("/api/master-prompts/{prompt_id}")
def update_master_prompt(prompt_id: int, body: MasterPromptUpdate) -> dict:
    """Edit a master prompt (any field optional)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM master_prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="master prompt not found"
            )
        patch = dict(row)
        if body.name is not None:
            patch["name"] = body.name.strip()
        if body.category is not None:
            patch["category"] = body.category.strip()
        if body.template is not None:
            patch["template"] = body.template.strip()
        if body.source is not None:
            patch["source"] = body.source.strip()
        if body.style_dna_id is not None:
            style = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.style_dna_id,),
            ).fetchone()
            if style is None:
                raise HTTPException(
                    status_code=400, detail="style_dna_id galat hai"
                )
            patch["style_dna_id"] = body.style_dna_id
        if not patch["name"]:
            raise HTTPException(
                status_code=400, detail="master prompt ka naam khaali nahi"
            )
        if not patch["template"]:
            raise HTTPException(
                status_code=400, detail="master prompt ka template khaali nahi"
            )
        if patch["category"] not in MASTER_PROMPT_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail="category hook / story / style-dna / viral-short me"
                " se honi chahiye",
            )
        try:
            conn.execute(
                "UPDATE master_prompts SET name = ?, category = ?,"
                " template = ?, style_dna_id = ?, source = ? WHERE id = ?",
                (
                    patch["name"],
                    patch["category"],
                    patch["template"],
                    patch["style_dna_id"],
                    patch["source"],
                    prompt_id,
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{patch['name']}' naam ka master prompt pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM master_prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
    return _master_prompt_detail(conn, row)


@app.delete("/api/master-prompts/{prompt_id}")
def delete_master_prompt(prompt_id: int) -> dict:
    """Delete a master prompt (seeds included — it is the user's
    library)."""
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM master_prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="master prompt not found"
            )
        conn.execute(
            "DELETE FROM master_prompts WHERE id = ?", (prompt_id,)
        )
    return {"deleted": True, "id": prompt_id}


# --- Cross-check slice: master-prompt import + niches + style builder --
# AutoCut's Master Prompts Library imports .txt/.md files; the unnamed
# Video 7 tool and AutoCut Writer organise work by niche (with AI
# topic ideas); StickFilm's "New category" writes a style from a
# plain-language description. All three are small, honest endpoints
# on the same Gemini free-tier path as script creation (no key ->
# plain 400, never a fake result).


@app.post("/api/master-prompts/import", status_code=201)
async def import_master_prompt(
    file: UploadFile = File(...), category: str = Form("style-dna")
) -> dict:
    """Import a master prompt from a .txt / .md file. The name is the
    file's stem; the whole file is the template. Empty file, wrong
    extension, over 1 MB, non-UTF-8 text, or a duplicate name is a
    plain 400 — nothing is half-imported."""
    filename = file.filename or ""
    name = Path(filename).stem.strip()
    if not name:
        raise HTTPException(status_code=400, detail="file ka naam nahi mila")
    ext = Path(filename).suffix.lower()
    if ext not in (".txt", ".md"):
        raise HTTPException(
            status_code=400, detail="sirf .txt ya .md file chahiye"
        )
    raw = await file.read()
    if len(raw) > 1_000_000:
        raise HTTPException(status_code=400, detail="file 1 MB se badi hai")
    try:
        template = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="file UTF-8 text nahi hai"
        )
    if not template:
        raise HTTPException(status_code=400, detail="file khaali hai")
    category = (category or "style-dna").strip()
    if category not in MASTER_PROMPT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="category hook / story / style-dna / viral-short me se"
            " honi chahiye",
        )
    with db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO master_prompts (name, category, template,"
                " style_dna_id, source, created_at)"
                " VALUES (?, ?, ?, NULL, ?, ?)",
                (
                    name,
                    category,
                    template,
                    f"Imported file: {filename}",
                    utcnow(),
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{name}' naam ka master prompt pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM master_prompts WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _master_prompt_detail(conn, row)


def _niche_row(row) -> dict:
    d = dict(row)
    return d


@app.get("/api/niches")
def list_niches() -> list:
    """All niches, with each niche's default Style DNA name."""
    with db() as conn:
        rows = conn.execute(
            "SELECT n.*, s.name AS default_style_dna_name FROM niches n"
            " LEFT JOIN style_dna s ON s.id = n.default_style_dna_id"
            " ORDER BY n.id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/niches", status_code=201)
def create_niche(body: NicheIn) -> dict:
    """Add a niche. Empty name or an unknown default_style_dna_id
    is a plain 400; a duplicate name is a plain 400."""
    name = (body.name or "").strip()
    description = (body.description or "").strip()
    main_characters = (body.main_characters or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="niche ka naam likhein")
    with db() as conn:
        if body.default_style_dna_id is not None:
            style = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.default_style_dna_id,),
            ).fetchone()
            if style is None:
                raise HTTPException(
                    status_code=400, detail="default_style_dna_id galat hai"
                )
        try:
            cur = conn.execute(
                "INSERT INTO niches (name, description, main_characters,"
                " default_style_dna_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    name,
                    description,
                    main_characters,
                    body.default_style_dna_id,
                    utcnow(),
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400, detail=f"'{name}' naam ka niche pehle se hai"
            )
        row = conn.execute(
            "SELECT * FROM niches WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _niche_row(row)


@app.put("/api/niches/{niche_id}")
def update_niche(niche_id: int, body: NicheUpdate) -> dict:
    """Edit a niche (any field optional)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="niche not found")
        patch = dict(row)
        if body.name is not None:
            patch["name"] = body.name.strip()
        if body.description is not None:
            patch["description"] = body.description.strip()
        if body.main_characters is not None:
            patch["main_characters"] = body.main_characters.strip()
        if body.default_style_dna_id is not None:
            style = conn.execute(
                "SELECT id FROM style_dna WHERE id = ?",
                (body.default_style_dna_id,),
            ).fetchone()
            if style is None:
                raise HTTPException(
                    status_code=400, detail="default_style_dna_id galat hai"
                )
            patch["default_style_dna_id"] = body.default_style_dna_id
        if not patch["name"]:
            raise HTTPException(
                status_code=400, detail="niche ka naam khaali nahi"
            )
        try:
            conn.execute(
                "UPDATE niches SET name = ?, description = ?,"
                " main_characters = ?, default_style_dna_id = ?"
                " WHERE id = ?",
                (
                    patch["name"],
                    patch["description"],
                    patch.get("main_characters", ""),
                    patch["default_style_dna_id"],
                    niche_id,
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{patch['name']}' naam ka niche pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
    return _niche_row(row)


@app.delete("/api/niches/{niche_id}")
def delete_niche(niche_id: int) -> dict:
    """Delete a niche. Scripts and projects are untouched — a niche
    is only a topic family, never an owner of content. Its Vault
    characters go with it (a Vault cast without its niche is
    meaningless)."""
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="niche not found")
        conn.execute(
            "DELETE FROM vault_characters WHERE niche_id = ?",
            (niche_id,),
        )
        conn.execute("DELETE FROM niches WHERE id = ?", (niche_id,))
    return {"deleted": True, "id": niche_id}


@app.post("/api/niches/{niche_id}/suggest-topics")
def suggest_topics(niche_id: int) -> dict:
    """Ask Gemini for 10 fresh video topics in this niche (AutoCut
    Writer parity). No Gemini key -> the same plain 400 as script
    creation; a provider failure -> 502. Topics come from the model
    and are returned as a plain list — nothing is invented locally."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="niche not found")
        keys = _gemini_keys(conn)
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="topic ideas ke liye Gemini key Settings me lagayen",
            )
        prompt = (
            "Give 10 video topic ideas for a faceless YouTube channel"
            f" in the niche '{row['name']}'"
            f" ({row['description'] or 'general'}). One topic per line,"
            " no numbering, no extra text, no headings."
        )
        try:
            text, _attempts = _gemini_try_keys(
                keys, lambda k: gemini_generate_text(k, prompt, max_tokens=800)
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    topics = [
        ln.strip().lstrip("0123456789.-) ").strip()
        for ln in text.splitlines()
    ]
    topics = [t for t in topics if t][:10]
    return {"niche_id": niche_id, "topics": topics}


# --- Slice 4: Character Vault -------------------------------------------
# A niche's Vault is its approved characters, locked and versioned.
# Flow: sheet upload -> approve -> lock -> bulk. A locked version
# is never edited in place: an edit creates a new draft version,
# and locking it supersedes the old locked one. Bulk (VisualForge
# / Magic Mode) only ever reads the ACTIVE locked version, so one
# video never mixes v1/v2.
# ------------------------------------------------------------------------


def _vault_validate_poses(poses: list | None, name: str, prop: str) -> list:
    """Poses as stored: a list of {name, description}. None = the
    5 default poses. Anything else is a plain 400, never a silent
    empty list (a character with no poses cannot pick one)."""
    if poses is None:
        return _vault_default_poses(name, prop)
    if not isinstance(poses, list) or not poses:
        raise HTTPException(
            status_code=400, detail="poses ki list khaali nahi ho sakti"
        )
    clean = []
    for pose in poses:
        if not isinstance(pose, dict) or not str(pose.get("name", "")).strip():
            raise HTTPException(
                status_code=400,
                detail="har pose ka naam aur description chahiye",
            )
        clean.append(
            {
                "name": str(pose["name"]).strip(),
                "description": str(pose.get("description", "")).strip(),
            }
        )
    return clean


@app.get("/api/vault")
def list_vault() -> list:
    """All 7 niches with their Vault status: locked cast count,
    guard (all mains locked?), sheet present? Real data only."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM niches ORDER BY id").fetchall()
        out = []
        for nrow in rows:
            resolved = _vault_resolve(conn, nrow["id"])
            expected = _niche_main_names(nrow["main_characters"])
            missing = [
                n for n in expected
                if n not in {c["name"] for c in resolved["mains"]}
            ]
            out.append(
                {
                    "niche_id": nrow["id"],
                    "niche_name": nrow["name"],
                    "character_count": resolved["character_count"],
                    "mains_locked": len(resolved["mains"]),
                    "mains_expected": len(expected),
                    "missing_mains": missing,
                    "guard_ok": not missing,
                    "sheet_path": resolved["sheet_path"],
                    "sheet_url": resolved["sheet_url"],
                    "sheet_exists": resolved["sheet_exists"],
                    # v0.14.1 fix round 2: mains with thumbnails, so the
                    # niche card shows the characters at first glance.
                    "mains": [
                        {"name": c["name"], "thumb_url": c.get("thumb_url")}
                        for c in resolved["mains"]
                    ],
                }
            )
        return out


@app.get("/api/niches/{niche_id}/vault")
def get_vault(niche_id: int) -> dict:
    """One niche's full Vault: every character version (newest
    first per name), plus the resolved locked cast."""
    with db() as conn:
        niche = conn.execute(
            "SELECT * FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if niche is None:
            raise HTTPException(status_code=404, detail="niche not found")
        rows = conn.execute(
            "SELECT * FROM vault_characters WHERE niche_id = ?"
            " ORDER BY name, version DESC",
            (niche_id,),
        ).fetchall()
        return {
            "niche_id": niche["id"],
            "niche_name": niche["name"],
            "characters": [_vault_row(r) for r in rows],
            "locked": _vault_resolve(conn, niche_id),
        }


@app.get("/api/niches/{niche_id}/vault/resolve")
def resolve_vault(niche_id: int) -> dict:
    """The niche's ACTIVE locked cast: mains (auto-select order),
    secondaries, sheet. This is what bulk runs pin."""
    with db() as conn:
        return _vault_resolve(conn, niche_id)


@app.post("/api/niches/{niche_id}/vault/characters", status_code=201)
def create_vault_character(niche_id: int, body: VaultCharacterIn) -> dict:
    """Add a character to the Vault as a DRAFT (new version when
    the name already exists). Drafts cannot be used by bulk until
    approved + locked."""
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="character ka naam likhein"
        )
    role = (body.role or "secondary").strip().lower()
    if role not in ("main", "secondary"):
        raise HTTPException(
            status_code=400,
            detail="role 'main' ya 'secondary' hona chahiye",
        )
    description = body.description.strip()
    prop = body.signature_prop.strip()
    poses = _vault_validate_poses(body.poses, name, prop)
    sheet_path = body.sheet_path.strip()
    with db() as conn:
        niche = conn.execute(
            "SELECT id FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if niche is None:
            raise HTTPException(status_code=404, detail="niche not found")
        top = conn.execute(
            "SELECT MAX(version) AS v FROM vault_characters"
            " WHERE niche_id = ? AND name = ?",
            (niche_id, name),
        ).fetchone()
        version = (top["v"] or 0) + 1
        cur = conn.execute(
            "INSERT INTO vault_characters (niche_id, name, description,"
            " signature_prop, role, poses_json, sheet_path, version,"
            " status, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, ?, ?)",
            (
                niche_id,
                name,
                description,
                prop,
                role,
                json.dumps(poses),
                sheet_path,
                version,
                utcnow(),
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _vault_row(row)


@app.put("/api/niches/{niche_id}/vault/characters/{char_id}")
def update_vault_character(
    niche_id: int, char_id: int, body: VaultCharacterUpdate
) -> dict:
    """Edit a Vault character: creates a NEW DRAFT version (vN+1)
    from the given row — the locked version is never edited in
    place, so a video that used v1 always finds v1 again."""
    with db() as conn:
        src = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if src is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        role = src["role"]
        if body.role is not None:
            role = body.role.strip().lower()
            if role not in ("main", "secondary"):
                raise HTTPException(
                    status_code=400,
                    detail="role 'main' ya 'secondary' hona chahiye",
                )
        description = (
            body.description.strip()
            if body.description is not None
            else src["description"]
        )
        prop = (
            body.signature_prop.strip()
            if body.signature_prop is not None
            else src["signature_prop"]
        )
        poses = (
            _vault_validate_poses(
                body.poses, src["name"], prop
            )
            if body.poses is not None
            else json.loads(src["poses_json"] or "[]")
        )
        sheet_path = (
            body.sheet_path.strip()
            if body.sheet_path is not None
            else src["sheet_path"]
        )
        top = conn.execute(
            "SELECT MAX(version) AS v FROM vault_characters"
            " WHERE niche_id = ? AND name = ?",
            (niche_id, src["name"]),
        ).fetchone()
        version = (top["v"] or 0) + 1
        cur = conn.execute(
            "INSERT INTO vault_characters (niche_id, name, description,"
            " signature_prop, role, poses_json, sheet_path, version,"
            " status, is_active, source, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, ?, ?, ?)",
            (
                niche_id,
                src["name"],
                description,
                prop,
                role,
                json.dumps(poses),
                sheet_path,
                version,
                src["source"] if "source" in src.keys() else "builtin",
                utcnow(),
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _vault_row(row)


@app.post("/api/niches/{niche_id}/vault/characters/{char_id}/sheet")
async def upload_vault_sheet(
    niche_id: int, char_id: int, file: UploadFile = File(...)
) -> dict:
    """Upload a character sheet image: saves it under
    studio/data/reference/vault/ and creates a NEW DRAFT version
    carrying that sheet. Non-image uploads are a plain 400."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=400, detail="sheet ek image file honi chahiye"
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400, detail="sheet file khaali hai"
        )
    ext = {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/jpeg": ".jpg",
    }.get(file.content_type or "", ".png")
    with db() as conn:
        src = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if src is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        top = conn.execute(
            "SELECT MAX(version) AS v FROM vault_characters"
            " WHERE niche_id = ? AND name = ?",
            (niche_id, src["name"]),
        ).fetchone()
        version = (top["v"] or 0) + 1
        slug = re.sub(
            r"[^a-z0-9]+", "-",
            f"{src['name']}".lower(),
        ).strip("-") or "character"
        folder = DATA_DIR / "reference" / "vault"
        folder.mkdir(parents=True, exist_ok=True)
        rel = f"reference/vault/n{niche_id}-{slug}-v{version}{ext}"
        (DATA_DIR / rel).write_bytes(data)
        cur = conn.execute(
            "INSERT INTO vault_characters (niche_id, name, description,"
            " signature_prop, role, poses_json, sheet_path, version,"
            " status, is_active, source, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, ?, ?, ?)",
            (
                niche_id,
                src["name"],
                src["description"],
                src["signature_prop"],
                src["role"],
                src["poses_json"],
                rel,
                version,
                src["source"] if "source" in src.keys() else "builtin",
                utcnow(),
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _vault_row(row)


@app.post("/api/niches/{niche_id}/vault/characters/{char_id}/approve")
def approve_vault_character(niche_id: int, char_id: int) -> dict:
    """Approve a draft character (draft -> approved). Only an
    approved character can be locked."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        if row["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"is character ki status '{row['status']}' hai"
                " — sirf draft approve ho sakta hai",
            )
        conn.execute(
            "UPDATE vault_characters SET status = 'approved',"
            " updated_at = ? WHERE id = ?",
            (utcnow(), char_id),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?", (char_id,)
        ).fetchone()
    return _vault_row(row)


@app.post("/api/niches/{niche_id}/vault/characters/{char_id}/lock")
def lock_vault_character(niche_id: int, char_id: int) -> dict:
    """Lock an approved character (approved -> locked, active).
    The previously locked version of the same character becomes
    'superseded' (kept, so an old video can still find it). Only
    the active locked version is used by bulk — one video never
    mixes v1/v2."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        if row["status"] != "approved":
            raise HTTPException(
                status_code=400,
                detail=f"is character ki status '{row['status']}' hai"
                " — pehle approve karein, phir lock karein",
            )
        conn.execute(
            "UPDATE vault_characters SET status = 'superseded',"
            " is_active = 0, updated_at = ? WHERE niche_id = ?"
            " AND name = ? AND status = 'locked' AND id != ?",
            (utcnow(), niche_id, row["name"], char_id),
        )
        conn.execute(
            "UPDATE vault_characters SET status = 'locked',"
            " is_active = 1, updated_at = ? WHERE id = ?",
            (utcnow(), char_id),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?", (char_id,)
        ).fetchone()
    return _vault_row(row)


@app.delete("/api/niches/{niche_id}/vault/characters/{char_id}")
def delete_vault_character(niche_id: int, char_id: int) -> dict:
    """Delete a character. Built-in characters: DRAFT only —
    approved / locked / superseded versions are kept, so an old
    video always finds the version it used. The user's OWN
    characters (source='user'): any status, sheet file included
    — remove apna main character ka rasta hai."""

    with db() as conn:
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        if row["status"] != "draft" and (
            row["source"] if "source" in row.keys() else "builtin"
        ) != "user":
            raise HTTPException(
                status_code=400,
                detail=f"is character ki status '{row['status']}' hai"
                " — sirf draft delete ho sakta hai",
            )
        # User ka apna character: kisi bhi status me remove ho
        # sakta hai (draft/approved/locked) — uski sheet file bhi
        # saath delete hoti hai. Built-in 70 kabhi delete nahi hote.
        sheet_rel = row["sheet_path"] or ""
        conn.execute(
            "DELETE FROM vault_characters WHERE id = ?", (char_id,)
        )
    if sheet_rel and (
        row["source"] if "source" in row.keys() else "builtin"
    ) == "user":
        try:
            _p = media_path(sheet_rel)
            if _p is not None and _p.is_file():
                # Sirf tab delete karo jab koi aur version wahi file
                # use na kar raha ho.
                with db() as conn:
                    n = conn.execute(
                        "SELECT COUNT(*) AS n FROM vault_characters"
                        " WHERE sheet_path = ?",
                        (sheet_rel,),
                    ).fetchone()["n"]
                if n == 0:
                    _p.unlink(missing_ok=True)
        except OSError:
            pass
    return {"deleted": True, "id": char_id}


@app.get("/api/vault/main")
def get_main_vault_character() -> dict:
    """The user's locked main character, or null when none is set.
    The main rides every Magic/bulk run in its niche (and in
    no-niche runs too) — full description verbatim + its sheet
    as the reference image."""
    with db() as conn:
        return {"main_character": _vault_main(conn)}


@app.post("/api/vault/my-character", status_code=201)
async def create_my_character(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(...),
    niche_id: int = Form(...),
    signature_prop: str = Form(""),
) -> dict:
    """Apna Main Character add karo: character sheet image upload
    karo (single sheet ya front/side/back), naam + description
    (paragraph) + niche. Entry source='user', role='main', DRAFT
    banti hai — phir approve -> lock -> 'Set as my main
    character'. Sheet sirf is PC ke data/ me rehti hai — kabhi
    ZIP/repo/update me nahi. Naam + description lazmi hain; file
    image honi chahiye."""
    name = (name or "").strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="character ka naam likhein"
        )
    description = (description or "").strip()
    if not description:
        raise HTTPException(
            status_code=400,
            detail="description likhein — poora paragraph, taake har"
            " scene me wahi character aaye",
        )
    prop = (signature_prop or "").strip()
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=400, detail="sheet ek image file honi chahiye"
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400, detail="sheet file khaali hai"
        )
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="sheet 10 MB se bari nahi honi chahiye"
        )
    ext = {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/jpeg": ".jpg",
    }.get(file.content_type or "", ".png")
    with db() as conn:
        niche = conn.execute(
            "SELECT id FROM niches WHERE id = ?", (niche_id,)
        ).fetchone()
        if niche is None:
            raise HTTPException(status_code=404, detail="niche not found")
        top = conn.execute(
            "SELECT MAX(version) AS v FROM vault_characters"
            " WHERE niche_id = ? AND name = ?",
            (niche_id, name),
        ).fetchone()
        version = (top["v"] or 0) + 1
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "character"
        folder = DATA_DIR / "reference" / "vault"
        folder.mkdir(parents=True, exist_ok=True)
        rel = f"reference/vault/n{niche_id}-{slug}-v{version}{ext}"
        (DATA_DIR / rel).write_bytes(data)
        poses = _vault_default_poses(name, prop)
        cur = conn.execute(
            "INSERT INTO vault_characters (niche_id, name, description,"
            " signature_prop, role, poses_json, sheet_path, version,"
            " status, is_active, source, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, 'user', ?, ?)",
            (
                niche_id,
                name,
                description,
                prop,
                "main",
                json.dumps(poses),
                rel,
                version,
                utcnow(),
                utcnow(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _vault_row(row)


@app.post("/api/niches/{niche_id}/vault/characters/{char_id}/set-main")
def set_main_vault_character(niche_id: int, char_id: int) -> dict:
    """Set this LOCKED character as my main character. Sirf ek
    main hota hai — purana main hat jata hai (replace). Main
    character har Magic/bulk run me har scene me aata hai: poori
    description verbatim + uski sheet reference image ke tor par."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        if row["status"] != "locked":
            raise HTTPException(
                status_code=400,
                detail=f"is character ki status '{row['status']}' hai"
                " — pehle approve karein, phir lock karein; sirf"
                " locked character main ban sakta hai",
            )
        conn.execute(
            "UPDATE vault_characters SET is_main = 0, updated_at = ?"
            " WHERE is_main = 1",
            (utcnow(),),
        )
        conn.execute(
            "UPDATE vault_characters SET is_main = 1, updated_at = ?"
            " WHERE id = ?",
            (utcnow(), char_id),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?", (char_id,)
        ).fetchone()
    return _vault_row(row)


@app.post("/api/niches/{niche_id}/vault/characters/{char_id}/unset-main")
def unset_main_vault_character(niche_id: int, char_id: int) -> dict:
    """Main character hatayen (character locked rehta hai, sirf
    main flag hat-ta hai)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?"
            " AND niche_id = ?",
            (char_id, niche_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="vault character not found"
            )
        conn.execute(
            "UPDATE vault_characters SET is_main = 0, updated_at = ?"
            " WHERE id = ?",
            (utcnow(), char_id),
        )
        row = conn.execute(
            "SELECT * FROM vault_characters WHERE id = ?", (char_id,)
        ).fetchone()
    return _vault_row(row)


def _split_style_response(
    text: str, fallback_description: str
) -> tuple[str, str]:
    """Split a 'STYLE: ... MASTER PROMPT: ...' Gemini answer. If the
    markers are missing, the whole text becomes the master prompt
    and the user's own description becomes the style description —
    never a failure on parse."""
    upper = text.upper()
    mp_idx = upper.find("MASTER PROMPT:")
    if mp_idx == -1:
        return fallback_description, text
    style_part = text[:mp_idx].strip()
    if style_part.upper().startswith("STYLE:"):
        style_part = style_part[len("STYLE:"):]
    master = text[mp_idx + len("MASTER PROMPT:"):].strip()
    return (
        style_part.strip() or fallback_description,
        master or text,
    )


@app.post("/api/style-dna/from-description", status_code=201)
def create_style_dna_from_description(body: StyleDnaFromDescriptionIn) -> dict:
    """Write a Style DNA from a plain-language description
    (StickFilm 'New category' parity): Gemini writes the style
    description + the master prompt, and the row is saved. No key
    -> plain 400; a provider failure -> 502. A duplicate name is a
    plain 400."""
    name = body.name.strip()
    description = body.description.strip()
    with db() as conn:
        keys = _gemini_keys(conn)
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="style likhne ke liye Gemini key Settings me lagayen",
            )
        prompt = (
            "Write a Style DNA for a faceless video channel. The user"
            " describes the look like this:\n"
            f"{description}\n\n"
            "Output exactly two parts, in this order:\n"
            "STYLE: one paragraph describing the visual style (colours,"
            " linework, character design, lighting).\n"
            "MASTER PROMPT: the full master prompt that turns any script"
            " into image prompts in this exact style, one prompt per"
            " 3-5 seconds of narration.\n"
            "The style must be 2D or 3D animated — never photorealistic,"
            " never a real camera look."
        )
        try:
            text, _attempts = _gemini_try_keys(
                keys,
                lambda k: gemini_generate_text(k, prompt, max_tokens=1500),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        style_desc, master_prompt = _split_style_response(text, description)
        try:
            cur = conn.execute(
                "INSERT INTO style_dna (name, description, master_prompt)"
                " VALUES (?, ?, ?)",
                (name, style_desc, master_prompt),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{name}' naam ka Style DNA pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM style_dna WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.post("/api/master-prompts/reverse-engineer", status_code=201)
def reverse_engineer_master_prompt(body: ReverseEngineerIn) -> dict:
    """Reverse-engineer a viral short into a master prompt (WAPCut
    Master Prompt Studio parity): paste what you saw (hook, visual
    style, pacing, captions, CTA) and Gemini writes the locked
    master prompt, saved to the library. No key -> plain 400; a
    provider failure -> 502. A duplicate name is a plain 400."""
    name = (body.name or "Reverse-Engineered Master Prompt").strip()
    category = (body.category or "viral-short").strip()
    if category not in MASTER_PROMPT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="category hook / story / style-dna / viral-short me se"
            " honi chahiye",
        )
    notes = body.notes.strip()
    with db() as conn:
        keys = _gemini_keys(conn)
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="master prompt likhne ke liye Gemini key Settings me"
                " lagayen",
            )
        prompt = (
            "Reverse-engineer a viral short video into a detailed master"
            " prompt. The user watched it and wrote these notes:\n"
            f"{notes}\n\n"
            "Write ONE master prompt that locks the same look: hook"
            " style, visual style (colours, linework, character design),"
            " pacing (one visual per 3-5 seconds of narration), caption"
            " style, and ending CTA. The master prompt must take a"
            " [SCRIPT] and output image prompts, one per 3-5 seconds."
            " Output only the master prompt, no extra headings."
        )
        try:
            text, _attempts = _gemini_try_keys(
                keys,
                lambda k: gemini_generate_text(k, prompt, max_tokens=1500),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        try:
            cur = conn.execute(
                "INSERT INTO master_prompts (name, category, template,"
                " style_dna_id, source, created_at)"
                " VALUES (?, ?, ?, NULL, ?, ?)",
                (name, category, text, "Reverse-engineered from notes", utcnow()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"'{name}' naam ka master prompt pehle se hai",
            )
        row = conn.execute(
            "SELECT * FROM master_prompts WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _master_prompt_detail(conn, row)


# --- Phase 7 slice 1: StoryCraft research notes ---------------------------


def _research_note_row(row) -> dict:
    """A research note as the API returns it. Slice 2: Deep Research
    notes carry kind='deep-research' + the parsed facts list, so the
    UI can show facts + sources; plain notes carry kind='note' and
    an empty facts list. A corrupt facts_json parses to [] — never
    a crash, never an invented fact."""
    note = dict(row)
    try:
        facts = json.loads(row["facts_json"] or "[]")
    except (ValueError, TypeError):
        facts = []
    note["facts"] = facts if isinstance(facts, list) else []
    note["kind"] = row["kind"] if "kind" in row.keys() else "note"
    return note


@app.get("/api/projects/{project_id}/research-notes")
def list_research_notes(project_id: int) -> list:
    """Research notes for a project, newest first."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = conn.execute(
            "SELECT * FROM research_notes WHERE project_id = ?"
            " ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [_research_note_row(r) for r in rows]


@app.post("/api/projects/{project_id}/deep-research", status_code=201)
def deep_research(project_id: int, body: DeepResearchIn) -> dict:
    """Slice 2: Deep Research — the step BEFORE the script. Gemini
    (gemini-3.5-flash, free tier) researches the topic into 4-6 key
    facts with a source per fact; the result is saved as a research
    note (kind 'deep-research') the user can read, edit and write a
    script from. No key -> plain 400; a provider failure -> 502;
    a badly formatted answer still saves its raw text with an empty
    facts list — never a fake fact."""
    topic = (body.topic or "").strip()
    if not topic:
        raise HTTPException(
            status_code=400, detail="research ke liye topic likhein"
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        keys = _gemini_keys(conn)
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="Gemini key Settings me lagayen — bina key ke"
                " research nahi ho sakti",
            )
        # _gemini_try_keys returns (result, attempts); result here is
        # the (text, facts) tuple from gemini_deep_research.
        try:
            (text, facts), _attempts = _gemini_try_keys(
                keys, lambda k: gemini_deep_research(k, topic)
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        if facts:
            content = "\n\n".join(
                f"Fact: {f['fact']}\nSource: {f.get('source') or '—'}"
                for f in facts
            )
        else:
            content = text
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO research_notes (project_id, title, content,"
            " kind, facts_json, created_at, updated_at)"
            " VALUES (?, ?, ?, 'deep-research', ?, ?, ?)",
            (project_id, topic, content, json.dumps(facts), now, now),
        )
        row = conn.execute(
            "SELECT * FROM research_notes WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _research_note_row(row)


@app.get("/api/storycraft/options")
def storycraft_options() -> dict:
    """Slice 2: the Thinking Levels + script models the UI offers.
    Real data from the same maps the generation path uses, so the
    picker can never offer a level or model the backend does not
    know."""
    return {
        "thinking_levels": [
            {
                "id": key,
                "label": cfg["label"],
                "words": (
                    "80-100"
                    if key == "low"
                    else "140-160"
                    if key == "medium"
                    else "200-260"
                ),
            }
            for key, cfg in THINKING_LEVELS.items()
        ],
        "models": [
            {
                "id": key,
                "label": (
                    "Fast — tez draft"
                    if key == "fast"
                    else "Deep — gehri, slow"
                    if key == "deep"
                    else "Code — structured, precise"
                ),
                "model": spec["model"],
            }
            for key, spec in GEMINI_SCRIPT_MODELS.items()
        ],
    }


@app.post("/api/projects/{project_id}/research-notes", status_code=201)
def create_research_note(project_id: int, body: ResearchNoteIn) -> dict:
    """Save a research note. Empty content is a plain 400."""
    title = (body.title or "").strip()
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(
            status_code=400, detail="research note khaali nahi ho sakta"
        )
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO research_notes (project_id, title, content,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, title or "Untitled note", content, now, now),
        )
        row = conn.execute(
            "SELECT * FROM research_notes WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _research_note_row(row)


@app.put("/api/research-notes/{note_id}")
def update_research_note(note_id: int, body: ResearchNoteIn) -> dict:
    """Edit a research note. Empty content is a plain 400. Slice 2:
    editing a Deep Research note re-parses its facts from the new
    content, so the facts list never goes stale."""
    title = (body.title or "").strip()
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(
            status_code=400, detail="research note khaali nahi ho sakta"
        )
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM research_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="research note not found"
            )
        if (row["kind"] or "note") == "deep-research":
            conn.execute(
                "UPDATE research_notes SET title = ?, content = ?,"
                " facts_json = ?, updated_at = ? WHERE id = ?",
                (
                    title or "Untitled note",
                    content,
                    json.dumps(_parse_research_facts(content)),
                    utcnow(),
                    note_id,
                ),
            )
        else:
            conn.execute(
                "UPDATE research_notes SET title = ?, content = ?,"
                " updated_at = ? WHERE id = ?",
                (title or "Untitled note", content, utcnow(), note_id),
            )
        row = conn.execute(
            "SELECT * FROM research_notes WHERE id = ?", (note_id,)
        ).fetchone()
    return _research_note_row(row)


@app.delete("/api/research-notes/{note_id}")
def delete_research_note(note_id: int) -> dict:
    """Delete a research note."""
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM research_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="research note not found"
            )
        conn.execute(
            "DELETE FROM research_notes WHERE id = ?", (note_id,)
        )
    return {"deleted": True, "id": note_id}


@app.post("/api/research-notes/{note_id}/write-script", status_code=201)
def write_script_from_research(
    note_id: int, body: WriteScriptIn | None = None
) -> dict:
    """Write a script from a research note: the note's title is the
    topic and its content goes to Gemini as context, through the
    same free-tier path as topic-only script creation. No Gemini key
    -> the same plain 400, never a fake script. Slice 2: the body
    carries Thinking Level + model (empty = Medium + Fast, so old
    callers that POST with no body keep working); a Deep Research
    note sends its parsed facts as the context, so the script is
    built from the researched facts."""
    options = body or WriteScriptIn()
    try:
        level = _validate_thinking_level(options.thinking_level)
        model = _validate_script_model(options.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    with db() as conn:
        note = conn.execute(
            "SELECT * FROM research_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if note is None:
            raise HTTPException(
                status_code=404, detail="research note not found"
            )
        topic = note["title"] or "Research notes"
        if (note["kind"] or "note") == "deep-research":
            try:
                facts = json.loads(note["facts_json"] or "[]")
            except (ValueError, TypeError):
                facts = []
            if isinstance(facts, list) and facts:
                facts_text = "\n".join(
                    f"- {f.get('fact', '')}"
                    f" (Source: {f.get('source') or '—'})"
                    for f in facts
                    if f.get("fact")
                )
                prompt_topic = (
                    f"{topic}\n\nResearched key facts (use only"
                    f" these facts in the script):\n{facts_text}"
                )
            else:
                prompt_topic = (
                    f"{topic}\n\nResearch notes:\n{note['content']}"
                )
        else:
            prompt_topic = (
                f"{topic}\n\nResearch notes:\n{note['content']}"
            )
        try:
            text, source = _generate_script_text(
                conn, prompt_topic, thinking_level=level, model=model
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return _insert_script(conn, note["project_id"], topic, text, source)


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn) -> dict:
    now = utcnow()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, created_at, updated_at) VALUES (?, ?, ?)",
            (body.name.strip(), now, now),
        )
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.get("/api/projects")
def list_projects() -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/projects/{project_id}")
def get_project(project_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return dict(row)


@app.post("/api/assets", status_code=201)
def create_asset(body: AssetIn) -> dict:
    """Record a local file path only. No upload yet (Phase 2+)."""
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (body.project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        cur = conn.execute(
            "INSERT INTO assets (project_id, kind, path, created_at)"
            " VALUES (?, ?, ?, ?)",
            (body.project_id, body.kind, body.path, utcnow()),
        )
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.get("/api/assets")
def list_assets(
    project_id: int | None = None,
    q: str | None = None,
    tag: str | None = None,
) -> list:
    """Assets, newest first. q searches the file name/path and kind
    (server-side, on the real rows — not client-side hiding). tag
    returns only assets carrying that exact tag. Each asset carries
    its real tags list."""
    with db() as conn:
        where = []
        params: list = []
        if project_id is not None:
            where.append("a.project_id = ?")
            params.append(project_id)
        if q and q.strip():
            where.append("(a.path LIKE ? OR a.kind LIKE ?)")
            like = f"%{q.strip()}%"
            params += [like, like]
        if tag and tag.strip():
            where.append(
                "EXISTS (SELECT 1 FROM asset_tags t"
                " WHERE t.asset_id = a.id AND t.tag = ?)"
            )
            params.append(tag.strip().lower())
        sql = "SELECT a.* FROM assets a"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY a.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        out = [dict(r) for r in rows]
        if out:
            ids = [r["id"] for r in out]
            marks = ",".join("?" * len(ids))
            tag_rows = conn.execute(
                f"SELECT asset_id, tag FROM asset_tags"
                f" WHERE asset_id IN ({marks}) ORDER BY tag",
                ids,
            ).fetchall()
            by_asset: dict[int, list[str]] = {i: [] for i in ids}
            for tr in tag_rows:
                by_asset[tr["asset_id"]].append(tr["tag"])
            for r in out:
                r["tags"] = by_asset.get(r["id"], [])
    return out


def _normalize_tag(raw: str) -> str:
    """A tag, lowercased and trimmed — or a plain 400 when it is not
    a usable tag (empty, too long, or funny characters)."""
    tag = (raw or "").strip().lower()
    if not tag or len(tag) > 30:
        raise HTTPException(
            status_code=400,
            detail="tag 1–30 characters ka hona chahiye",
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9 _\-]*", tag):
        raise HTTPException(
            status_code=400,
            detail="tag mein sirf harf, number, space, - aur _ allowed hain",
        )
    return tag


@app.get("/api/assets/tags")
def list_asset_tags() -> list:
    """Every tag in use, with how many assets carry it."""
    with db() as conn:
        rows = conn.execute(
            "SELECT tag, COUNT(*) AS count FROM asset_tags"
            " GROUP BY tag ORDER BY count DESC, tag"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/assets/{asset_id}/tags", status_code=201)
def add_asset_tag(asset_id: int, body: AssetTagIn) -> dict:
    """Tag one asset. Adding the same tag twice is a no-op (the tag
    is already there) — the asset's real tag list comes back."""
    tag = _normalize_tag(body.tag)
    with db() as conn:
        asset = conn.execute(
            "SELECT id FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None:
            raise HTTPException(status_code=404, detail="asset not found")
        conn.execute(
            "INSERT OR IGNORE INTO asset_tags (asset_id, tag, created_at)"
            " VALUES (?, ?, ?)",
            (asset_id, tag, utcnow()),
        )
        tags = [
            r["tag"]
            for r in conn.execute(
                "SELECT tag FROM asset_tags WHERE asset_id = ? ORDER BY tag",
                (asset_id,),
            ).fetchall()
        ]
    return {"asset_id": asset_id, "tag": tag, "tags": tags}


@app.delete("/api/assets/{asset_id}/tags/{tag}")
def remove_asset_tag(asset_id: int, tag: str) -> dict:
    """Remove one tag from an asset. Unknown asset or a tag the asset
    does not carry is a plain 404 — nothing is silently ignored."""
    norm = _normalize_tag(tag)
    with db() as conn:
        asset = conn.execute(
            "SELECT id FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None:
            raise HTTPException(status_code=404, detail="asset not found")
        cur = conn.execute(
            "DELETE FROM asset_tags WHERE asset_id = ? AND tag = ?",
            (asset_id, norm),
        )
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="is asset par ye tag nahi hai"
            )
        tags = [
            r["tag"]
            for r in conn.execute(
                "SELECT tag FROM asset_tags WHERE asset_id = ? ORDER BY tag",
                (asset_id,),
            ).fetchall()
        ]
    return {"asset_id": asset_id, "tag": norm, "tags": tags}


@app.post("/api/jobs", status_code=201)
def create_job(body: JobIn) -> dict:
    with db() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (body.project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO jobs (project_id, kind, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (body.project_id, body.kind, body.status, now, now),
        )
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.get("/api/jobs")
def list_jobs(
    project_id: int | None = None, kind: str | None = None
) -> list:
    """All jobs, newest first — the honest render queue source: every
    row carries its real status, error and timestamps. kind filters
    (e.g. kind=render for the render queue)."""
    with db() as conn:
        where = []
        params: list = []
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if kind and kind.strip():
            where.append("kind = ?")
            params.append(kind.strip())
        sql = "SELECT * FROM jobs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/settings")
def list_settings() -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT key, value, note FROM settings ORDER BY key"
        ).fetchall()
    return [
        {"key": r["key"], "value": mask_value(r["key"], r["value"]), "note": r["note"]}
        for r in rows
    ]


@app.get("/api/settings/{key}")
def get_setting(key: str) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT key, value, note FROM settings WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="setting not found")
    return {
        "key": row["key"],
        "value": mask_value(row["key"], row["value"]),
        "note": row["note"],
    }


@app.put("/api/settings/{key}")
def put_setting(key: str, body: SettingIn) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT key FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            # v0.14.1: seeded setting ki row na ho (purani DB, seed
            # chhoot gaya) to 404 ki bajaye row bana lo — warna
            # Settings ka har control us setting par dead hota hai.
            known = {k: n for k, _v, n in DEFAULT_SETTINGS}
            if key not in known:
                raise HTTPException(status_code=404, detail="setting not found")
            conn.execute(
                "INSERT INTO settings (key, value, note) VALUES (?, ?, ?)",
                (key, "", known[key]),
            )
        # Small-bug fix: the Settings edit box used to start empty, so
        # saving without typing wiped the key — and for secret keys the
        # masked display value must never be saved back. A blank save
        # leaves a secret key untouched.
        if key in SECRET_KEYS and not body.value.strip():
            pass
        else:
            conn.execute(
                "UPDATE settings SET value = ? WHERE key = ?",
                (body.value, key),
            )
        row = conn.execute(
            "SELECT key, value, note FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return {
        "key": row["key"],
        "value": mask_value(row["key"], row["value"]),
        "note": row["note"],
    }


# --- Phase 7 slice 3: multi-API keys + voice providers ---------------

def _gemini_key_row(conn, key_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM gemini_api_keys WHERE id = ?", (key_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="gemini key not found")
    return dict(row)


def _gemini_key_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "label": row["label"] or f"Key {row['id']}",
        "preview": _mask_secret(row["key_value"]),
        "position": row["position"],
        "created_at": row["created_at"],
    }


@app.get("/api/gemini-keys")
def list_gemini_keys() -> list:
    """All configured Gemini keys in rotation order, masked. The
    first key is tried first; a dead key moves to the next one."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM gemini_api_keys ORDER BY position, id"
        ).fetchall()
    return [_gemini_key_public(dict(r)) for r in rows]


@app.post("/api/gemini-keys", status_code=201)
def add_gemini_key(body: GeminiKeyIn) -> dict:
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key khaali nahi ho sakti")
    with db() as conn:
        top = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS m FROM gemini_api_keys"
        ).fetchone()["m"]
        cur = conn.execute(
            "INSERT INTO gemini_api_keys (label, key_value, position, created_at)"
            " VALUES (?, ?, ?, ?)",
            ((body.label or "").strip(), key, top + 1, utcnow()),
        )
        row = _gemini_key_row(conn, cur.lastrowid)
    return _gemini_key_public(row)


@app.post("/api/gemini-keys/{key_id}/test")
def test_gemini_key(key_id: int) -> dict:
    """Test one Gemini key (AutoCut 'Test Key' parity): a TINY
    generateContent call on the script model (gemini-3.5-flash) —
    the model the app actually uses for scripts — so a key that
    lists models but cannot generate is caught here, not later in
    a real script run. Costs a few tokens only (one-word reply,
    maxOutputTokens 8). Returns ok + the model's reply, or
    ok=false with the provider's own message. The key itself is
    never returned."""
    import urllib.error
    import urllib.parse
    import urllib.request

    with db() as conn:
        row = _gemini_key_row(conn, key_id)
    key = row["key_value"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_SCRIPT_MODEL}:generateContent"
    )
    payload = json.dumps(
        {
            "contents": [
                {"parts": [{"text": "Reply with one word: OK"}]},
            ],
            "generationConfig": {"maxOutputTokens": 8},
        }
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code == 400 and "api key" in body.lower():
            return {
                "ok": False,
                "message": "Key ghalat hai — Google AI Studio se nayi key lein",
                "help_url": "https://aistudio.google.com/app/apikey",
            }
        return {
            "ok": False,
            "message": f"Gemini key fail hui (HTTP {exc.code}): {body}",
        }
    except OSError as exc:
        return {
            "ok": False,
            "message": f"Gemini se connect nahi ho saka: {exc}",
        }
    text = ""
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        text = ""
    return {
        "ok": True,
        "message": (
            f"key theek hai — {GEMINI_SCRIPT_MODEL} ne jawab diya"
            + (f" ({text})" if text else "")
        ),
    }


@app.delete("/api/gemini-keys/{key_id}")
def delete_gemini_key(key_id: int) -> dict:
    with db() as conn:
        _gemini_key_row(conn, key_id)
        conn.execute("DELETE FROM gemini_api_keys WHERE id = ?", (key_id,))
    return {"deleted": True, "id": key_id}


@app.post("/api/gemini-keys/{key_id}/move")
def move_gemini_key(key_id: int, body: GeminiKeyMoveIn) -> dict:
    """Move a key up or down in the rotation order (first = tried
    first). Swaps positions with the neighbour; the ends stay put."""
    direction = (body.direction or "").strip().lower()
    if direction not in ("up", "down"):
        raise HTTPException(
            status_code=400, detail="direction 'up' ya 'down' honi chahiye"
        )
    with db() as conn:
        row = _gemini_key_row(conn, key_id)
        neighbour = conn.execute(
            "SELECT * FROM gemini_api_keys WHERE position"
            + (" < ?" if direction == "up" else " > ?")
            + " ORDER BY position"
            + (" DESC" if direction == "up" else " ASC")
            + ", id DESC LIMIT 1",
            (row["position"],),
        ).fetchone()
        if neighbour is None:
            return _gemini_key_public(row)
        neighbour = dict(neighbour)
        conn.execute(
            "UPDATE gemini_api_keys SET position = ? WHERE id = ?",
            (neighbour["position"], key_id),
        )
        conn.execute(
            "UPDATE gemini_api_keys SET position = ? WHERE id = ?",
            (row["position"], neighbour["id"]),
        )
        row = _gemini_key_row(conn, key_id)
    return _gemini_key_public(row)


def _voice_provider_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": "custom",
        "base_url": row["base_url"],
        "key_set": bool(row["api_key"]),
        "enabled": bool(row["enabled"]),
        "test_status": row["test_status"],
        "test_message": row["test_message"],
        "test_at": row["test_at"],
    }


def _voice_providers_list(conn) -> list:
    """Built-ins (Edge-TTS, HeyGen clone) plus separately-added
    custom providers. A custom provider is only a registry entry +
    a reachability test — it never claims a voice works until its
    own API is wired."""
    heygen_key = bool(_heygen_key(conn))
    heygen_voice = _heygen_voice_id(conn)
    out = [
        {
            "id": "edge-tts",
            "name": "Edge-TTS (free)",
            "kind": "builtin",
            "base_url": "",
            "key_set": False,
            "enabled": True,
            "test_status": "ok",
            "test_message": "Microsoft free voices — no key, no test needed",
            "test_at": None,
        },
        {
            "id": "heygen",
            "name": "HeyGen clone voice",
            "kind": "builtin",
            "base_url": "https://api.heygen.com",
            "key_set": heygen_key,
            "enabled": True,
            "test_status": "ok" if (heygen_key and heygen_voice) else "not-tested",
            "test_message": (
                "Key + clone voice set hain — tayyar hai"
                if (heygen_key and heygen_voice)
                else (
                    "Key set hai — apni clone voice_id bhi Settings me lagayen"
                    if heygen_key
                    else "HeyGen key Settings me lagayen — bina key ke awaz nahi ban sakti"
                )
            ),
            "test_at": None,
        },
    ]
    rows = conn.execute(
        "SELECT * FROM voice_providers ORDER BY id"
    ).fetchall()
    for r in rows:
        out.append(_voice_provider_public(dict(r)))
    return out


@app.get("/api/voice-providers")
def list_voice_providers() -> list:
    """The VoiceForge provider registry: built-ins first, then every
    separately-added provider with its stored test result."""
    with db() as conn:
        return _voice_providers_list(conn)


@app.post("/api/voice-providers", status_code=201)
def add_voice_provider(body: VoiceProviderIn) -> dict:
    name = (body.name or "").strip()
    base_url = (body.base_url or "").strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="provider ka naam likhna parega"
        )
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="base URL http:// ya https:// se shuru honi chahiye",
        )
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO voice_providers (name, base_url, api_key, created_at)"
            " VALUES (?, ?, ?, ?)",
            (name, base_url, (body.api_key or "").strip(), utcnow()),
        )
        row = conn.execute(
            "SELECT * FROM voice_providers WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _voice_provider_public(dict(row))


@app.post("/api/voice-providers/{provider_id}/test")
def test_voice_provider(provider_id: int) -> dict:
    """Harmless reachability check for a separately-added provider:
    one GET to its base URL. A reply means the address is reachable —
    it does NOT prove voice generation works for this provider, and
    the stored message says so plainly."""
    import urllib.error
    import urllib.request

    with db() as conn:
        row = conn.execute(
            "SELECT * FROM voice_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="voice provider not found"
            )
        base_url = (dict(row)["base_url"] or "").strip()
        if not base_url:
            status = "failed"
            message = "base URL khaali hai — test ke liye base URL dein"
        else:
            req = urllib.request.Request(base_url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    code = resp.status
                status = "ok"
                message = (
                    f"base URL reachable (HTTP {code}) — voice generation"
                    " is NOT verified for this provider"
                )
            except urllib.error.HTTPError as exc:
                # Any HTTP answer proves the address is alive.
                status = "ok"
                message = (
                    f"base URL reachable (HTTP {exc.code}) — voice generation"
                    " is NOT verified for this provider"
                )
            except (urllib.error.URLError, OSError) as exc:
                status = "failed"
                message = (
                    f"connection failed: {exc} — provider reachable nahi hai,"
                    " base URL check karein"
                )
        conn.execute(
            "UPDATE voice_providers SET test_status = ?, test_message = ?,"
            " test_at = ? WHERE id = ?",
            (status, message, utcnow(), provider_id),
        )
        row = conn.execute(
            "SELECT * FROM voice_providers WHERE id = ?", (provider_id,)
        ).fetchone()
    return _voice_provider_public(dict(row))


@app.delete("/api/voice-providers/{provider_id}")
def delete_voice_provider(provider_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM voice_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="voice provider not found"
            )
        conn.execute(
            "DELETE FROM voice_providers WHERE id = ?", (provider_id,)
        )
    return {"deleted": True, "id": provider_id}


# --- Phase 7 slice 3: job checkpoints / resume ------------------------

RESUMABLE_JOB_KINDS = ("render", "image-generate", "transcribe")


def _timeline_for_render_job(conn, job: dict) -> int | None:
    """Which timeline a render job belongs to: the options it was
    queued with, else its run's timeline, else the project's latest
    timeline. None when the project has no timeline at all."""
    try:
        options = json.loads(job.get("options_json") or "{}")
    except (TypeError, ValueError):
        options = {}
    if options.get("timeline_id"):
        return int(options["timeline_id"])
    if job.get("run_id"):
        run = conn.execute(
            "SELECT timeline_id FROM runs WHERE id = ?", (job["run_id"],)
        ).fetchone()
        if run and run["timeline_id"]:
            return int(run["timeline_id"])
    row = conn.execute(
        "SELECT id FROM timelines WHERE project_id = ? ORDER BY id DESC LIMIT 1",
        (job["project_id"],),
    ).fetchone()
    return int(row["id"]) if row else None


@app.post("/api/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: int, background_tasks: BackgroundTasks) -> dict:
    """Resume an interrupted or failed job: it restarts from the
    beginning with the same inputs (renders and transcriptions have
    no mid-way checkpoint to continue from), and the note says so
    plainly. Run-step jobs cannot resume alone — the whole run must
    be started again."""
    with db() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        job = dict(job)
        if job["status"] not in ("interrupted", "failed"):
            raise HTTPException(
                status_code=400,
                detail=f"ye job resume nahi ho sakta — status: {job['status']}",
            )
        kind = job["kind"]
        if kind == "render":
            timeline_id = _timeline_for_render_job(conn, job)
            if timeline_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="is render job ka timeline nahi mila — timeline dobara render karein",
                )
            worker = ("render", timeline_id)
        elif kind == "image-generate":
            scene = None
            if job.get("scene_id"):
                scene = conn.execute(
                    "SELECT script_id FROM scenes WHERE id = ?",
                    (job["scene_id"],),
                ).fetchone()
            if scene is None:
                raise HTTPException(
                    status_code=400,
                    detail="is image job ka scene nahi mila — images dobara generate karein",
                )
            worker = ("image", scene["script_id"])
        elif kind == "transcribe":
            tr = conn.execute(
                "SELECT * FROM transcriptions WHERE job_id = ?", (job_id,)
            ).fetchone()
            if tr is None:
                raise HTTPException(
                    status_code=400,
                    detail="is transcribe job ki file nahi mili — dobara transcribe karein",
                )
            disk = DATA_DIR / tr["source_path"]
            if not disk.is_file():
                raise HTTPException(
                    status_code=400,
                    detail="is transcribe job ki file nahi mili — dobara transcribe karein",
                )
            worker = ("transcribe", (dict(tr), disk))
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{kind}' jobs resume nahi hote — dobara chalayen"
                    " (render, image aur transcribe jobs resume hote hain)"
                ),
            )
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            ("queued", None, utcnow(), job_id),
        )
    if worker[0] == "render":
        background_tasks.add_task(run_render, job_id, worker[1])
        note = "render dobara shuru se chalega — beech se resume nahi hota"
    elif worker[0] == "image":
        background_tasks.add_task(process_image_jobs, worker[1])
        note = "image generation dobara shuru se chalegi"
    else:
        tr, disk = worker[1]
        background_tasks.add_task(
            _run_transcription, job_id, tr["id"], disk, tr["model"]
        )
        note = "transcription dobara shuru se chalegi"
    return {"job_id": job_id, "status": "queued", "kind": kind, "note": note}


# --- Phase 7 slice 3: backup + restore -------------------------------

@app.get("/api/backup")
def download_backup() -> FileResponse:
    """One-click backup: a ZIP of the SQLite DB (a consistent
    snapshot taken with the sqlite3 backup API) + every file under
    studio/data/ except renders/ — renders are regenerable outputs,
    re-render to get them back. The ZIP is built in a temp file and
    streamed; the temp file is deleted after the download."""
    import tempfile

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tmpdir = Path(tempfile.mkdtemp(prefix="kreafy-backup-"))
    db_snap = tmpdir / "studio.db"
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(db_snap)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    zip_path = tmpdir / f"kreafy-backup-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_snap, arcname="studio.db")
        for path in sorted(DATA_DIR.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(DATA_DIR)
            if rel.parts[0] == "renders":
                continue
            zf.write(path, arcname=str(Path("data") / rel))
    filename = f"kreafy-backup-{stamp}.zip"

    def _cleanup() -> None:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(_cleanup),
    )


@app.post("/api/restore")
async def restore_backup(file: UploadFile = File(...)) -> dict:
    """Restore a backup ZIP: verify it first (ZIP intact, studio.db
    present and opens with the expected tables), then replace the
    live data — every table copied from the backup DB, and the data/
    files replaced (renders/ is untouched: it was never in the
    backup). Refuses while any job is queued or running, so a restore
    can never land mid-render."""
    import tempfile

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400, detail="khaali file hai — backup ZIP dein"
        )
    if len(data) > 1024 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="backup ZIP 1 GB se bara hai"
        )
    tmpdir = Path(tempfile.mkdtemp(prefix="kreafy-restore-"))
    try:
        zip_path = tmpdir / "backup.zip"
        zip_path.write_bytes(data)
        try:
            zf = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400, detail="ye ZIP file nahi hai — backup ZIP dein"
            )
        bad = zf.testzip()
        if bad is not None:
            raise HTTPException(
                status_code=400,
                detail=f"backup ZIP kharab hai — file '{bad}' nahi khuli",
            )
        names = zf.namelist()
        if "studio.db" not in names:
            raise HTTPException(
                status_code=400,
                detail="backup me studio.db nahi hai — ye Kreafy backup nahi lagta",
            )
        zf.extract("studio.db", tmpdir)
        db_tmp = tmpdir / "studio.db"
        probe = sqlite3.connect(f"file:{db_tmp}?mode=ro", uri=True)
        try:
            tables = {
                r[0]
                for r in probe.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            probe.close()
        for needed in ("projects", "jobs", "settings", "assets"):
            if needed not in tables:
                raise HTTPException(
                    status_code=400,
                    detail=f"backup DB me '{needed}' table nahi hai"
                    " — ye Kreafy backup nahi lagta",
                )
        with db() as conn:
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM jobs"
                " WHERE status IN ('queued', 'running')"
            ).fetchone()["n"]
            if active:
                raise HTTPException(
                    status_code=400,
                    detail="pehle chalti jobs khatam hone dein"
                    " — restore ke waqt koi job nahi chalni chahiye",
                )
            live_tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            # FK order cannot be trusted across tables, so enforcement
            # is off during the copy; the backup is a consistent
            # snapshot, so integrity is whole again at the end.
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.execute(f"ATTACH DATABASE '{db_tmp}' AS backup")
                try:
                    for table in sorted(tables & live_tables):
                        if table.startswith("sqlite_"):
                            continue
                        conn.execute(f'DELETE FROM "{table}"')
                        conn.execute(
                            f'INSERT INTO "{table}" SELECT * FROM backup."{table}"'
                        )
                finally:
                    # The copy opened a transaction that still holds the
                    # attached DB — commit first, or DETACH fails with
                    # "database backup is locked".
                    conn.commit()
                    conn.execute("DETACH DATABASE backup")
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
            counts = {
                name: conn.execute(
                    f'SELECT COUNT(*) AS n FROM "{name}"'
                ).fetchone()["n"]
                for name in ("projects", "assets", "jobs")
            }
        # Files: replace data/ (except renders/) with the backup's data/.
        for child in DATA_DIR.iterdir():
            if child.name == "renders":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        files_restored = 0
        for member in zf.namelist():
            if not member.startswith("data/") or member.endswith("/"):
                continue
            target = DATA_DIR / member[len("data/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            files_restored += 1
        zf.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return {
        "restored": True,
        "projects": counts["projects"],
        "assets": counts["assets"],
        "jobs": counts["jobs"],
        "files": files_restored,
        "note": "renders/ backup me nahi tha — videos dobara render karein",
    }


@app.get("/api/style-dna")
def list_style_dna() -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM style_dna ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/caption-styles")
def list_caption_styles() -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM caption_styles ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]

# ==========================================================================
# Release Packaging (v0.14.0): update / setup / output / free keys
# ==========================================================================
# Ye section release ZIP ke liye hai: public GitHub Releases se
# one-click update, first-run Setup, date-wise output/ ka management
# aur har user ki APNI free keys. Koi key yahan hardcoded nahi hoti;
# keys sirf is PC ki SQLite DB me rehti hain — update unhe kabhi
# overwrite nahi karta (update.py sirf code badalta hai, DB + data/
# + output/ ko chhoota hi nahi).
# ==========================================================================


def _version_newer(latest: str, current: str) -> bool:
    """True when dotted version `latest` is newer than `current`."""

    def parts(v: str) -> list:
        out = []
        for p in v.strip().lstrip("v").split("."):
            try:
                out.append(int(p))
            except ValueError:
                out.append(0)
        return out

    return parts(latest) > parts(current)


# --- Update: public GitHub Releases ---------------------------------------
# Students ke paas private test repo ki access NAHI hai, is liye update
# PUBLIC GitHub Releases API se aata hai — bina auth, bina login:
#   GET https://api.github.com/repos/<owner>/<repo>/releases/latest
# Ali update is tarah ship karta hai: public repo par Release banao,
# tag vX.Y.Z, ZIP attach karo. Jab tak repo public nahi aur Release
# nahi, check honestly "nahi mila" kehta hai — kabhi fake "up to
# date" nahi.
_UPDATE_CHECK_CACHE: dict = {"at": 0.0, "data": None}
_UPDATE_CHECK_TTL_S = 3600
_UPDATE_APPLY_STATE: dict = {
    "state": "idle",
    "detail": "",
    "updated_at": "",
}
_UPDATE_DEFAULT_REPO = "nazakataleofficial-coder/kreafy-creator-studio"
# v0.14.1 — Drive update source: jab tak public GitHub Release na
# ho, update Drive mirror ZIP se aata hai (link-shared file, bina
# login). Ali ki current install isi se one-click update hoti hai —
# dobara ZIP copy-paste nahi karna parta. Source Settings me badla
# ja sakta hai (github | drive); Drive fileId bhi setting hai.
_UPDATE_DEFAULT_DRIVE_FILE_ID = "1lpAUWGaQfSQJCxlRkCCyVDrpuP403AVT"


def _drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _check_drive(file_id: str) -> tuple:
    """Drive mirror ZIP se version padho: ZIP download karo (~400 KB),
    us ke andar app/VERSION (ya VERSION) padho. Returns
    (latest, size, error) — latest None ho to error bhara hota hai."""
    import urllib.error
    import urllib.request
    import zipfile

    url = _drive_download_url(file_id)
    tmpdir = Path(tempfile.mkdtemp(prefix="studio-update-check-"))
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Kreafy-Creator-Studio"}, method="GET"
        )
        zip_path = tmpdir / "mirror.zip"
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                zip_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            return None, 0, f"Drive ZIP download nahi ho saka (HTTP {exc.code})"
        except OSError as exc:
            return None, 0, f"Drive se connect nahi ho saka: {exc}"
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                hit = [n for n in names if n.endswith("/VERSION") or n == "VERSION"]
                if not hit:
                    return None, 0, "Drive ZIP me VERSION nahi mili — ye release ZIP nahi lagta"
                version = zf.read(hit[0]).decode("utf-8").strip() or None
        except zipfile.BadZipFile:
            return None, 0, "Drive se mili file ZIP nahi hai"
        if not version:
            return None, 0, "Drive ZIP me VERSION khaali hai"
        return version, zip_path.stat().st_size, ""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.get("/api/update/check")
def update_check(force: bool = False) -> dict:
    """Latest Release (GitHub) ya Drive mirror ZIP vs local VERSION.
    Cached 1 hour unless force=true. A missing repo / missing
    Release / no network is reported honestly (reachable=false +
    plain error), never faked."""
    import urllib.error
    import urllib.request

    with db() as conn:
        repo = _setting_value(conn, "update_repo") or _UPDATE_DEFAULT_REPO
        source = (
            _setting_value(conn, "update_source") or "github"
        ).strip().lower()
        if source not in ("github", "drive"):
            source = "github"
        drive_file_id = (
            _setting_value(conn, "update_drive_file_id")
            or _UPDATE_DEFAULT_DRIVE_FILE_ID
        ).strip()
    now = time.time()
    if (
        not force
        and _UPDATE_CHECK_CACHE["data"] is not None
        and _UPDATE_CHECK_CACHE["data"].get("source") == source
        and now - _UPDATE_CHECK_CACHE["at"] < _UPDATE_CHECK_TTL_S
    ):
        return _UPDATE_CHECK_CACHE["data"]
    result: dict = {
        "current": APP_VERSION,
        "source": source,
        "repo": repo,
        "reachable": False,
        "update_available": False,
        "latest": None,
        "tag": None,
        "name": None,
        "published_at": None,
        "release_url": None,
        "notes": "",
        "assets": [],
        "asset": None,
        "error": "",
    }
    if source == "drive":
        latest, size, err = _check_drive(drive_file_id)
        if latest is None:
            result["error"] = err
            _UPDATE_CHECK_CACHE.update({"at": now, "data": result})
            return result
        url = _drive_download_url(drive_file_id)
        asset = {
            "name": f"Kreafy-Creator-Studio-{latest}.zip",
            "size": size,
            "download_url": url,
        }
        result.update(
            {
                "reachable": True,
                "latest": latest,
                "tag": latest,
                "name": f"Kreafy Creator Studio {latest} (Drive mirror)",
                "assets": [asset],
                "asset": asset,
                "update_available": _version_newer(
                    latest.lstrip("v"), APP_VERSION_NUM
                ),
            }
        )
        _UPDATE_CHECK_CACHE.update({"at": now, "data": result})
        return result
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Kreafy-Creator-Studio",
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        result["error"] = (
            f"GitHub par is repo ki koi public Release nahi mili"
            f" (HTTP {exc.code}) — update ke liye repo ko public"
            " karna aur Release (tag + ZIP) banana zaroori hai."
        )
        _UPDATE_CHECK_CACHE.update({"at": now, "data": result})
        return result
    except OSError as exc:
        result["error"] = f"GitHub se connect nahi ho saka: {exc}"
        _UPDATE_CHECK_CACHE.update({"at": now, "data": result})
        return result
    tag = (data.get("tag_name") or "").strip()
    latest = tag.lstrip("v") or None
    assets = [
        {
            "name": a.get("name"),
            "size": a.get("size"),
            "download_url": a.get("browser_download_url"),
        }
        for a in (data.get("assets") or [])
        if (a.get("name") or "").endswith(".zip")
    ]
    result.update(
        {
            "reachable": True,
            "latest": f"v{latest}" if latest else None,
            "tag": tag,
            "name": data.get("name"),
            "published_at": data.get("published_at"),
            "release_url": data.get("html_url"),
            "notes": data.get("body") or "",
            "assets": assets,
            "asset": assets[0] if assets else None,
            "update_available": bool(latest)
            and _version_newer(latest, APP_VERSION_NUM),
        }
    )
    _UPDATE_CHECK_CACHE.update({"at": now, "data": result})
    return result


@app.get("/api/update/status")
def update_status() -> dict:
    """In-app update ka state: idle / downloading / applying /
    done / failed, plus apply_update.py ki aakhri report (agar hai)."""
    out = dict(_UPDATE_APPLY_STATE)
    status_file = DATA_DIR / "update-status.json"
    if status_file.exists():
        try:
            out["last"] = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return out


@app.get("/api/update/changelog")
def update_changelog() -> dict:
    """Is install ki CHANGELOG.md — update ke baad Settings me
    dikhayi jati hai."""
    for cand in (APP_DIR / "CHANGELOG.md", ROOT_DIR / "CHANGELOG.md"):
        if cand.exists():
            try:
                return {
                    "available": True,
                    "version": APP_VERSION,
                    "changelog": cand.read_text(encoding="utf-8")[:8000],
                }
            except OSError:
                pass
    return {"available": False, "version": APP_VERSION, "changelog": ""}


def _find_script(name: str) -> Path | None:
    """scripts/ me file dhoondo — package me app/scripts/, dev me
    repo-root/scripts/."""
    for cand in (APP_DIR / "scripts" / name, ROOT_DIR / "scripts" / name):
        if cand.exists():
            return cand
    return None


def _spawn_detached(cmd: list, log_path: Path) -> None:
    """Process jo backend ke band hone ke baad bhi chalta rahe —
    update apply ke liye zaroori hai (update.py backend ko band
    karta hai)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "ab")
    kwargs: dict = {
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def _update_dry_run(url: str) -> dict:
    """ZIP download karo, validate karo, gin lo — kuch badle baghair.
    Valid = ZIP ke andar ek top folder me app/ ya studio/ ke neeche
    backend/main.py hai."""
    import urllib.error
    import urllib.request

    tmpdir = Path(tempfile.mkdtemp(prefix="studio-update-dry-"))
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Kreafy-Creator-Studio"},
            method="GET",
        )
        zip_path = tmpdir / "release.zip"
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                zip_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            return {
                "dry_run": True,
                "valid": False,
                "error": f"ZIP download nahi ho saka (HTTP {exc.code})",
            }
        except OSError as exc:
            return {
                "dry_run": True,
                "valid": False,
                "error": f"ZIP download nahi ho saka: {exc}",
            }
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            return {
                "dry_run": True,
                "valid": False,
                "error": "Download hui file ZIP nahi hai",
            }
        root = None
        for cand in ("app/backend/main.py", "studio/backend/main.py"):
            if any(n.endswith(cand) for n in names):
                root = cand.split("/")[0]
                break
        if root is None:
            return {
                "dry_run": True,
                "valid": False,
                "error": "ZIP me app/backend/main.py nahi hai — ye release ZIP nahi lagta",
            }
        version = None
        for cand in (f"{root}/VERSION", "VERSION"):
            hit = [n for n in names if n.endswith(cand)]
            if hit:
                try:
                    with zipfile.ZipFile(zip_path) as zf:
                        version = (
                            zf.read(hit[0]).decode("utf-8").strip() or None
                        )
                except (KeyError, OSError, ValueError):
                    version = None
                break
        skip_dirs = {".git", "node_modules", ".venv", "venv", "dist",
                     "__pycache__", "backups", "logs"}
        files = 0
        for n in names:
            if n.endswith("/"):
                continue
            parts = n.split("/")
            if len(parts) < 2 or parts[0] != root and parts[0] != "Kreafy-Creator-Studio":
                continue
            rel = "/".join(parts[1:]) if parts[0] == "Kreafy-Creator-Studio" else n
            if any(p in skip_dirs for p in rel.split("/")):
                continue
            if rel.startswith("output/") or "/data/" in rel or rel.endswith(".db"):
                continue
            files += 1
        return {
            "dry_run": True,
            "valid": True,
            "version": version,
            "files": files,
            "bytes": zip_path.stat().st_size,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


class UpdateApplyIn(BaseModel):
    asset_url: str = ""
    dry_run: bool = False


@app.post("/api/update/apply", status_code=202)
def update_apply(body: UpdateApplyIn) -> dict:
    """Release ZIP download + apply. Asli kaam detached
    scripts/apply_update.py karta hai (backend band ho jata hai,
    is liye background task kaafi nahi). dry_run=true sirf validate
    karta hai, kuch badalta nahi. DB / settings / data/ / output/
    ko update kabhi touch nahi karta."""
    url = (body.asset_url or "").strip()
    if not url:
        chk = update_check(force=False)
        asset = chk.get("asset") or {}
        url = asset.get("download_url") or ""
        if not url:
            raise HTTPException(
                status_code=400,
                detail="Koi update ZIP nahi mila — pehle Check for Update"
                " karein; Release me ZIP attach hona chahiye",
            )
    if body.dry_run:
        return _update_dry_run(url)
    if _UPDATE_APPLY_STATE.get("state") in ("downloading", "applying"):
        raise HTTPException(
            status_code=409,
            detail="Update pehle se chal raha hai — status dekhein",
        )
    apply_py = _find_script("apply_update.py")
    if apply_py is None:
        raise HTTPException(
            status_code=500,
            detail="apply_update.py nahi mila — ye release update apply nahi kar sakti",
        )
    _UPDATE_APPLY_STATE.update(
        {"state": "downloading", "detail": url, "updated_at": utcnow()}
    )
    log_path = APP_DIR / "logs" / "update-apply.log"
    _spawn_detached(
        [
            sys.executable,
            str(apply_py),
            "--zip-url",
            url,
            "--app-dir",
            str(ROOT_DIR),
            "--status-file",
            str(DATA_DIR / "update-status.json"),
        ],
        log_path,
    )
    return {
        "state": "started",
        "detail": url,
        "status_url": "/api/update/status",
    }


# --- Setup: first-run Install Requirements -------------------------------
# Students ko sirf Python 3.11+ ek dafa install karna hai (PATH ticked).
# Uske baad Setup button sab kuch sambhalta hai: pip deps, Playwright
# Chromium, FFmpeg. Har step green tick se verify hota hai; "Ready"
# tabhi dikhta hai jab required steps ok hon. Koi step kabhi chupke
# se fail nahi hota — fail ho to saaf message aata hai.
_SETUP_RUNS: dict = {}


def _check_python() -> dict:
    ver = sys.version_info
    return {
        "ok": ver >= (3, 10),
        "version": f"{ver.major}.{ver.minor}.{ver.micro}",
        "detail": f"{sys.executable} (Python {ver.major}.{ver.minor}.{ver.micro})",
    }


def _check_backend_deps() -> list:
    import importlib.util

    out = []
    for mod, required in (
        ("fastapi", True),
        ("uvicorn", True),
        ("multipart", True),
        ("PIL", False),
        ("playwright", False),
        ("faster_whisper", False),
        # v0.14.1: edge-tts REQUIRED hai — VoiceForge samples + TTS
        # isi se chalte hain; fresh PC par is ke baghair har voice
        # play 503 deta tha (Ali ke PC test ka Issue 1 + 2).
        ("edge_tts", True),
    ):
        found = importlib.util.find_spec(mod) is not None
        out.append(
            {
                "module": mod,
                "ok": found,
                "required": required,
                "detail": "installed" if found else "missing",
            }
        )
    return out


def _check_chromium() -> dict:
    """Playwright ka Chromium browser — Canvas/Flow (free images)
    ke liye chahiye. App iske baghair bhi chalti hai."""
    roots = []
    if os.name == "nt":
        roots.append(
            Path(os.path.expandvars("%USERPROFILE%"))
            / "AppData"
            / "Local"
            / "ms-playwright"
        )
    else:
        roots.append(Path.home() / ".cache" / "ms-playwright")
    for root in roots:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir() or not d.name.startswith("chromium"):
                continue
            exe = (
                d / "chrome-win" / "chrome.exe"
                if os.name == "nt"
                else d / "chrome-linux" / "chrome"
            )
            if exe.exists():
                return {"ok": True, "path": str(exe)}
    return {"ok": False, "path": None}


def _check_ffmpeg() -> dict:
    """System ffmpeg, ya Setup se install hua app/bin/ffmpeg."""
    candidates = []
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(Path(found))
    local = APP_DIR / "bin" / "ffmpeg" / (
        "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    )
    if local.exists():
        candidates.append(local)
    for exe in candidates:
        try:
            proc = subprocess.run(
                [str(exe), "-version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
                return {
                    "ok": True,
                    "path": str(exe),
                    "version": first,
                }
        except OSError:
            continue
    return {"ok": False, "path": None, "version": None}


def _check_shortcut() -> dict:
    """Desktop shortcut — sirf Windows par supported."""
    if os.name != "nt":
        return {"ok": False, "path": None, "supported": False}
    desktop = Path(os.path.expandvars("%USERPROFILE%")) / "Desktop"
    link = desktop / "Kreafy Creator Studio.lnk"
    return {
        "ok": link.exists(),
        "path": str(link),
        "supported": True,
    }


def _setup_status_data() -> dict:
    py = _check_python()
    deps = _check_backend_deps()
    chromium = _check_chromium()
    ffmpeg = _check_ffmpeg()
    shortcut = _check_shortcut()
    required_ok = py["ok"] and all(
        d["ok"] for d in deps if d["required"]
    ) and ffmpeg["ok"]
    last_run = None
    status_file = DATA_DIR / "setup-status.json"
    if status_file.exists():
        try:
            last_run = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last_run = None
    return {
        "python": py,
        "backend_deps": deps,
        "chromium": chromium,
        "ffmpeg": ffmpeg,
        "desktop_shortcut": shortcut,
        "ready": required_ok,
        "recommended_missing": (
            [] if chromium["ok"] else ["chromium"]
        ),
        "last_run": last_run,
    }


@app.get("/api/setup/status")
def setup_status() -> dict:
    """Live checks — kuch install nahi hota, sirf batata hai kya
    maujood hai aur kya missing hai."""
    return _setup_status_data()


def _setup_run_persist(run_id: str, rec: dict) -> None:
    """Run record ko disk par likho — backend restart ho bhi jaye to
    run ka haal (steps_done + state) milta rahe. Pehle sirf memory
    me tha: restart par poll 404 deta tha aur UI ko lagta tha Setup
    chala hi nahi."""
    try:
        d = DATA_DIR / "setup-runs"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{run_id}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _setup_run_worker(run_id: str, steps: list) -> None:
    """Background Setup run: pip deps, Chromium, FFmpeg. Har step ka
    result run record me likha jata hai (memory + disk); khatam ho to
    setup-status.json update hota hai (taake refresh ke baad bhi
    "Ready" dikhe). Green tick SIRF tab jab step verify ho — pip ka
    returncode 0 kaafi nahi, install ke baad dobara check hota hai
    ke module asal me import ho raha hai. Koi step kabhi chupke se
    fail nahi hota: fail ho to asal error text + Retry (dobara run)
    milta hai, aur jab tak items missing hain tab tak success report
    nahi hoti."""
    rec = _SETUP_RUNS[run_id]
    results: dict = {}

    def mark(step: str, ok: bool, detail: str) -> None:
        results[step] = {"ok": ok, "detail": detail}
        rec["steps_done"] = dict(results)
        rec["current"] = step if not ok else ""
        _setup_run_persist(run_id, rec)

    for step in steps:
        rec["current"] = step
        _setup_run_persist(run_id, rec)
        if step == "backend_deps":
            req = BASE_DIR / "requirements.txt"
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req)],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                if proc.returncode != 0:
                    mark(
                        step,
                        False,
                        "pip install fail — log: "
                        + (proc.stderr or proc.stdout or "")[-300:],
                    )
                    continue
                # pip 0 kaafi nahi — verify karo ke required modules
                # (edge-tts shamil) asal me import ho rahe hain.
                missing = [
                    d["module"]
                    for d in _check_backend_deps()
                    if d["required"] and not d["ok"]
                ]
                if missing:
                    mark(
                        step,
                        False,
                        "pip install hua magar ye modules phir bhi nahi"
                        f" mile: {', '.join(missing)} — pip log check"
                        " karein ya dobara try karein",
                    )
                else:
                    mark(step, True, "Backend packages install ho gaye (verified)")
            except OSError as exc:
                mark(step, False, f"pip nahi chal saka: {exc}")
        elif step == "chromium":
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                ok = proc.returncode == 0 and _check_chromium()["ok"]
                mark(
                    step,
                    ok,
                    "Chromium install ho gaya (verified)"
                    if ok
                    else "Playwright Chromium install fail — "
                    + (proc.stderr or proc.stdout or "")[-300:],
                )
            except OSError as exc:
                mark(step, False, f"playwright nahi chal saka: {exc}")
        elif step == "ffmpeg":
            if sys.platform == "win32":
                mark(step, *_setup_ffmpeg_windows())
            else:
                have = _check_ffmpeg()
                if have["ok"]:
                    mark(step, True, f"ffmpeg mil gaya: {have['path']}")
                else:
                    mark(
                        step,
                        False,
                        "ffmpeg nahi mila — Linux/Mac par system package"
                        " se install karein (apt install ffmpeg / brew"
                        " install ffmpeg), phir dobara check karein",
                    )
        else:
            mark(step, False, "unknown step")
    ok_all = all(r["ok"] for r in results.values())
    rec["state"] = "done" if ok_all else "failed"
    rec["current"] = ""
    _setup_run_persist(run_id, rec)
    try:
        (DATA_DIR / "setup-status.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "steps": results,
                    "ok": ok_all,
                    "updated_at": utcnow(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _setup_ffmpeg_windows() -> tuple:
    """Windows: gyan.dev ka free static FFmpeg build download karo,
    app/bin/ffmpeg/ me extract karo, verify karo. ~80 MB download —
    sirf tab jab ffmpeg missing ho."""
    import urllib.error
    import urllib.request
    import zipfile as _zf

    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    dest_dir = APP_DIR / "bin" / "ffmpeg"
    tmpdir = Path(tempfile.mkdtemp(prefix="studio-ffmpeg-"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kreafy-Creator-Studio"})
        zip_path = tmpdir / "ffmpeg.zip"
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                zip_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            return False, f"FFmpeg download nahi ho saka (HTTP {exc.code})"
        except OSError as exc:
            return False, f"FFmpeg download nahi ho saka: {exc}"
        try:
            with _zf.ZipFile(zip_path) as zf:
                names = zf.namelist()
                bins = [n for n in names if n.endswith("/bin/ffmpeg.exe") or n.endswith("/bin/ffprobe.exe")]
                if not bins:
                    return False, "FFmpeg ZIP me ffmpeg.exe nahi mila"
                dest_dir.mkdir(parents=True, exist_ok=True)
                for n in bins:
                    data = zf.read(n)
                    (dest_dir / Path(n).name).write_bytes(data)
        except _zf.BadZipFile:
            return False, "Download hui file ZIP nahi hai"
        check = _check_ffmpeg()
        if check["ok"]:
            return True, f"FFmpeg install ho gaya: {check['path']}"
        return False, "FFmpeg extract ho gaya magar verify nahi ho saka"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


class SetupRunIn(BaseModel):
    steps: list = Field(default_factory=list)
    dry_run: bool = False


@app.post("/api/setup/run", status_code=202)
def setup_run(body: SetupRunIn) -> dict:
    """Setup chalao: backend_deps (pip install), chromium
    (playwright install), ffmpeg (Windows download). steps khaali ho
    to sirf missing steps chalte hain. dry_run=true sirf plan batata
    hai, kuch install nahi karta."""
    status = _setup_status_data()
    missing = []
    if not all(d["ok"] for d in status["backend_deps"] if d["required"]):
        missing.append("backend_deps")
    if not status["chromium"]["ok"]:
        missing.append("chromium")
    if not status["ffmpeg"]["ok"]:
        missing.append("ffmpeg")
    wanted = [s for s in (body.steps or missing) if s in ("backend_deps", "chromium", "ffmpeg")]
    run_id = f"setup-{int(time.time())}"
    if body.dry_run:
        return {
            "run_id": run_id,
            "dry_run": True,
            "state": "dry-run",
            "steps": wanted,
            "note": "Dry run — kuch install nahi hoga",
        }
    if not wanted:
        return {
            "run_id": run_id,
            "state": "done",
            "steps": [],
            "note": "Sab kuch pehle se tayyar hai — kuch install nahi karna",
        }
    _SETUP_RUNS[run_id] = {
        "state": "running",
        "steps": wanted,
        "steps_done": {},
        "current": wanted[0],
        "started_at": utcnow(),
    }
    _setup_run_persist(run_id, _SETUP_RUNS[run_id])
    threading.Thread(
        target=_setup_run_worker, args=(run_id, wanted), daemon=True
    ).start()
    return {"run_id": run_id, "state": "running", "steps": wanted}


@app.get("/api/setup/run/{run_id}")
def setup_run_status(run_id: str) -> dict:
    rec = _SETUP_RUNS.get(run_id)
    if rec is None:
        # Backend restart ke baad memory khaali hoti hai — disk se
        # padho (worker har mark par persist karta hai).
        try:
            p = DATA_DIR / "setup-runs" / f"{run_id}.json"
            if p.exists():
                rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rec = None
    if rec is None:
        raise HTTPException(status_code=404, detail="setup run not found")
    return dict(rec)


@app.post("/api/setup/desktop-shortcut")
def desktop_shortcut() -> dict:
    """Desktop par "Kreafy Creator Studio" shortcut banao — taake
    students ko folder kholna hi na pare. Sirf Windows par kaam
    karta hai; baaki OS par saaf 400 aata hai."""
    if os.name != "nt":
        raise HTTPException(
            status_code=400,
            detail="Desktop shortcut sirf Windows par banta hai",
        )
    bat = ROOT_DIR / "Start Kreafy Studio.bat"
    if not bat.exists():
        bat = ROOT_DIR / "start-studio.bat"
    desktop = Path(os.path.expandvars("%USERPROFILE%")) / "Desktop"
    link = desktop / "Kreafy Creator Studio.lnk"
    ps = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut('{link}'); "
        f"$l.TargetPath = '{bat}'; "
        f"$l.WorkingDirectory = '{ROOT_DIR}'; "
        "$l.Description = 'Kreafy Creator Studio — double-click to start'; "
        "$l.Save()"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Shortcut nahi ban saka: {exc}"
        )
    if proc.returncode != 0 or not link.exists():
        raise HTTPException(
            status_code=500,
            detail="Shortcut nahi ban saka: "
            + (proc.stderr or proc.stdout or "unknown error")[-300:],
        )
    return {"created": True, "path": str(link)}


# --- Output: date-wise videos ka management ------------------------------
@app.get("/api/output/info")
def output_info() -> dict:
    """output/ folder: path, aaj ka folder, kul files + size, har
    date ka hisaab. Videos yahin rehti hain — update inhe kabhi
    touch nahi karta."""
    total_bytes = 0
    total_files = 0
    by_date = []
    if OUTPUT_DIR.exists():
        for day in sorted(OUTPUT_DIR.iterdir(), reverse=True):
            if not day.is_dir():
                continue
            files = [p for p in day.iterdir() if p.is_file()]
            size = sum(p.stat().st_size for p in files)
            by_date.append(
                {"date": day.name, "files": len(files), "size_bytes": size}
            )
            total_files += len(files)
            total_bytes += size
    return {
        "path": str(OUTPUT_DIR),
        "today": _today_str(),
        "files": total_files,
        "size_bytes": total_bytes,
        "by_date": by_date,
    }


@app.post("/api/output/open")
def output_open() -> dict:
    """output/ folder OS ke file explorer me kholo. Headless PC par
    fail ho to saaf error + path milta hai (koi fake 'khul gaya'
    nahi)."""
    output_dir_for_today()
    try:
        if os.name == "nt":
            os.startfile(str(OUTPUT_DIR))  # noqa: S606 - local path only
        elif sys.platform == "darwin":
            subprocess.run(["open", str(OUTPUT_DIR)], check=True, timeout=15)
        else:
            subprocess.run(
                ["xdg-open", str(OUTPUT_DIR)], check=True, timeout=15
            )
    except Exception as exc:  # noqa: BLE001 - plain message is the point
        raise HTTPException(
            status_code=500,
            detail=f"Folder khud nahi khula: {exc} — path: {OUTPUT_DIR}",
        )
    return {"path": str(OUTPUT_DIR)}


class OutputCleanIn(BaseModel):
    confirm: bool = False


@app.post("/api/output/clean")
def output_clean(body: OutputCleanIn) -> dict:
    """30 din se purane renders delete karo. confirm=true ke baghair
    kuch nahi hota — pehle call hamesha 400 deti hai taake UI confirm
    le sake. Aaj ki videos kabhi delete nahi hotin (wo 30 din purani
    nahi hotin)."""
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true bhej kar dobara karein — 30 din se purane renders delete honge",
        )
    cutoff = time.time() - 30 * 86400
    deleted = 0
    freed = 0
    if OUTPUT_DIR.exists():
        for p in OUTPUT_DIR.rglob("*"):
            if p.is_file() and p.stat().st_mtime < cutoff:
                freed += p.stat().st_size
                try:
                    p.unlink()
                    deleted += 1
                except OSError:
                    pass
        for day in list(OUTPUT_DIR.iterdir()):
            if day.is_dir():
                try:
                    if not any(day.iterdir()):
                        day.rmdir()
                except OSError:
                    pass
    return {"deleted_files": deleted, "freed_bytes": freed}


# --- Free keys: har user ki APNI keys --------------------------------------
# Keys sirf is PC ki SQLite DB me rehti hain (settings table / rotation
# table) — kabhi ZIP, repo ya update me nahi. Koi key yahan pre-filled
# nahi hoti. Badge saaf batata hai: FREE / TRIAL / PAID. "used_by"
# honestly kehta hai ke key aaj kis feature me chalti hai — "wiring
# next" ka matlab hai slot tayyar hai, feature agli slice me aayega.
FREE_KEYS = [
    {
        "id": "gemini",
        "name": "Gemini",
        "badge": "FREE",
        "get_url": "https://aistudio.google.com",
        "used_by": "Script, deep research, prompts, images (API)",
        "note": "Text FREE hai. Images API se FREE NAHI — free images ke liye Canvas web route use karein.",
        "setting": None,
    },
    {
        "id": "groq",
        "name": "Groq",
        "badge": "FREE",
        "get_url": "https://console.groq.com",
        "used_by": "Transcription (Whisper) + fast text — wiring next",
        "note": "Whisper 2,000 req/day · 8h audio/day · text 30 RPM.",
        "setting": "groq_api_key",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "badge": "FREE",
        "get_url": "https://openrouter.ai",
        "used_by": "Script generation — Gemini key na ho to free fallback",
        "note": "Free models — key khud free, billing nahi chahiye.",
        "setting": "openrouter_api_key",
    },
    {
        "id": "huggingface",
        "name": "Hugging Face",
        "badge": "FREE",
        "get_url": "https://huggingface.co/settings/tokens",
        "used_by": "Text/images (Inference API) — wiring next",
        "note": "Free, rate-limited.",
        "setting": "huggingface_api_key",
    },
    {
        "id": "pollinations",
        "name": "Pollinations",
        "badge": "FREE",
        "get_url": "https://pollinations.ai",
        "used_by": "Images/text — test image ban sakti hai (neeche button)",
        "note": "KOI KEY CHAHIYE HI NAHI.",
        "setting": None,
        "no_key": True,
    },
    {
        "id": "pexels",
        "name": "Pexels",
        "badge": "FREE",
        "get_url": "https://www.pexels.com/api",
        "used_by": "Stock photos/videos — wiring next",
        "note": "Sirf signup, no billing.",
        "setting": "pexels_api_key",
    },
    {
        "id": "pixabay",
        "name": "Pixabay",
        "badge": "FREE",
        "get_url": "https://pixabay.com/api",
        "used_by": "Stock photos/videos — wiring next",
        "note": "Sirf signup, no billing.",
        "setting": "pixabay_api_key",
    },
    {
        "id": "elevenlabs",
        "name": "ElevenLabs",
        "badge": "FREE",
        "get_url": "https://elevenlabs.io",
        "used_by": "Voice (TTS) — wiring next",
        "note": "Free 10,000 characters/month.",
        "setting": "elevenlabs_api_key",
    },
    {
        "id": "deepgram",
        "name": "Deepgram",
        "badge": "TRIAL",
        "get_url": "https://console.deepgram.com",
        "used_by": "Transcription alternative — wiring next",
        "note": "$200 FREE CREDIT (trial hai, forever-free nahi).",
        "setting": "deepgram_api_key",
    },
    {
        "id": "heygen",
        "name": "HeyGen",
        "badge": "PAID",
        "get_url": "https://app.heygen.com",
        "used_by": "Voice clone (apni key + apni voice_id)",
        "note": "Free allowance khatam ho chuka hai — paid samajh kar use karein.",
        "setting": "heygen_api_key",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "badge": "PAID",
        "get_url": "https://platform.openai.com/api-keys",
        "used_by": "Text/voice — wiring next",
        "note": "FREE NAHI — billing chahiye.",
        "setting": "openai_api_key",
    },
]


@app.get("/api/free-keys")
def free_keys() -> list:
    """Free-keys catalog + har key ki configured state (sirf bool —
    key kabhi wapas nahi aati). Gemini rotation table se bhi dekha
    jata hai."""
    with db() as conn:
        out = []
        for item in FREE_KEYS:
            configured = False
            if item["id"] == "pollinations":
                configured = True  # no key required
            elif item["id"] == "gemini":
                n = conn.execute(
                    "SELECT COUNT(*) AS n FROM gemini_api_keys"
                    " WHERE TRIM(key_value) <> ''"
                ).fetchone()["n"]
                configured = n > 0 or bool(
                    _setting_value(conn, "gemini_api_key")
                )
            elif item.get("setting"):
                configured = bool(_setting_value(conn, item["setting"]))
            d = dict(item)
            d["configured"] = configured
            out.append(d)
    return out


def _free_key_test(provider: str, key: str) -> tuple:
    """Ek provider ki key ko live check karo (chhota sa read-only
    call). Returns (ok, message). Key kabhi message me nahi aati."""
    import urllib.error
    import urllib.request

    def call(url: str, headers: dict, timeout: int = 20) -> tuple:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except OSError as exc:
            return False, str(exc)

    if provider == "gemini":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-3.5-flash:generateContent"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(
                {"contents": [{"parts": [{"text": "Say OK"}]}]}
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                json.loads(resp.read().decode("utf-8"))
            return True, "Gemini key theek hai — free text chal sakta hai"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            if exc.code == 400 and "api key" in body.lower():
                return (
                    False,
                    "Key ghalat hai — Google AI Studio se nayi key lein"
                    " (https://aistudio.google.com/app/apikey)",
                )
            return False, f"Gemini ne mana kar diya (HTTP {exc.code}) — key check karein"
        except OSError as exc:
            return False, f"Gemini se connect nahi ho saka: {exc}"
    if provider == "groq":
        ok, info = call(
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {key}"},
        )
        return ok, "Groq key theek hai" if ok else f"Groq ne mana kar diya ({info})"
    if provider == "openrouter":
        ok, info = call(
            "https://openrouter.ai/api/v1/models",
            {"Authorization": f"Bearer {key}"},
        )
        return ok, "OpenRouter key theek hai" if ok else f"OpenRouter ne mana kar diya ({info})"
    if provider == "huggingface":
        ok, info = call(
            "https://huggingface.co/api/whoami-v2",
            {"Authorization": f"Bearer {key}"},
        )
        if ok and isinstance(info, dict) and info.get("name"):
            return True, f"Hugging Face key theek hai ({info['name']})"
        return ok, "Hugging Face key theek hai" if ok else f"Hugging Face ne mana kar diya ({info})"
    if provider == "elevenlabs":
        ok, info = call(
            "https://api.elevenlabs.io/v1/user",
            {"xi-api-key": key},
        )
        if ok and isinstance(info, dict):
            sub = info.get("subscription") or {}
            return True, (
                "ElevenLabs key theek hai — "
                f"{sub.get('character_count', '?')}/{sub.get('character_limit', '?')} characters used"
            )
        return ok, "ElevenLabs key theek hai" if ok else f"ElevenLabs ne mana kar diya ({info})"
    if provider == "deepgram":
        ok, info = call(
            "https://api.deepgram.com/v1/projects",
            {"Authorization": f"Token {key}"},
        )
        return ok, "Deepgram key theek hai" if ok else f"Deepgram ne mana kar diya ({info})"
    if provider == "pexels":
        ok, info = call(
            "https://api.pexels.com/v1/search?query=test&per_page=1",
            {"Authorization": key},
        )
        return ok, "Pexels key theek hai" if ok else f"Pexels ne mana kar diya ({info})"
    if provider == "pixabay":
        ok, info = call(
            "https://pixabay.com/api/?key=" + urllib.parse.quote(key) + "&q=test&per_page=3",
            {},
        )
        return ok, "Pixabay key theek hai" if ok else f"Pixabay ne mana kar diya ({info})"
    if provider == "heygen":
        ok, info = call(
            "https://api.heygen.com/v2/voices?limit=1",
            {"X-Api-Key": key},
        )
        return ok, "HeyGen key theek hai" if ok else f"HeyGen ne mana kar diya ({info})"
    if provider == "openai":
        ok, info = call(
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {key}"},
        )
        return ok, "OpenAI key theek hai" if ok else f"OpenAI ne mana kar diya ({info})"
    return False, "unknown provider"


@app.post("/api/free-keys/{provider}/test")
def test_free_key(provider: str) -> dict:
    """Stored key ko live test karo. Bina key ke saaf 400 — kabhi
    fake 'ok' nahi."""
    provider = provider.strip().lower()
    item = next((f for f in FREE_KEYS if f["id"] == provider), None)
    if item is None:
        raise HTTPException(status_code=404, detail="provider not found")
    if item.get("no_key"):
        raise HTTPException(
            status_code=400,
            detail="Pollinations ko key chahiye hi nahi — test image wala button use karein",
        )
    with db() as conn:
        if provider == "gemini":
            keys = _gemini_keys(conn)
            key = keys[0] if keys else ""
        elif item.get("setting"):
            key = _setting_value(conn, item["setting"])
        else:
            key = ""
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"Pehle apni {item['name']} key add karein — phir test hoga",
        )
    ok, message = _free_key_test(provider, key)
    return {"provider": provider, "ok": ok, "message": message}


# --- Unified API Keys (v0.14.1) -------------------------------------------
# Settings me pehle keys 3 alag jagah bikhri hui thin (raw "Keys &
# engines" dump + Gemini rotation + neeche "Free keys" table) — wahi
# key (gemini_api_key) do jagah dikhti thi aur aam user ko samajh
# nahi aata tha ke asal me kaun si key kahan chalti hai. Ab EK
# grouped endpoint hai: purpose ke hisaab se group (AI Text /
# Images / Voice / Stock), har row me friendly name + badge +
# status + masked preview (sirf aakhri 4 chars) + Test/Delete/Add.
# Gemini rotation group ke andar hi rehta hai. Koi key kabhi poori
# nahi aati — preview hamesha _mask_secret se banta hai.
_KEY_GROUPS = {
    "gemini": "AI Text",
    "openrouter": "AI Text",
    "groq": "AI Text",
    "huggingface": "AI Text",
    "openai": "AI Text",
    "pollinations": "Images",
    "pexels": "Stock",
    "pixabay": "Stock",
    "elevenlabs": "Voice",
    "deepgram": "Voice",
    "heygen": "Voice",
}
_KEY_GROUP_ORDER = ["AI Text", "Images", "Voice", "Stock"]


def _keys_catalog(conn) -> list:
    out = []
    for item in FREE_KEYS:
        pid = item["id"]
        base = {
            "id": pid,
            "name": item["name"],
            "group": _KEY_GROUPS.get(pid, "AI Text"),
            "badge": item["badge"],
            "get_url": item.get("get_url", ""),
            "used_by": item.get("used_by", ""),
            "note": item.get("note", ""),
        }
        if pid == "gemini":
            rows = conn.execute(
                "SELECT * FROM gemini_api_keys ORDER BY position, id"
            ).fetchall()
            keys = [_gemini_key_public(dict(r)) for r in rows]
            out.append(
                {
                    **base,
                    "kind": "rotation",
                    "configured": len(keys) > 0,
                    "preview": keys[0]["preview"] if keys else "",
                    "keys": keys,
                }
            )
        elif item.get("no_key"):
            out.append(
                {
                    **base,
                    "kind": "no-key",
                    "configured": True,
                    "preview": "",
                    "keys": [],
                }
            )
        else:
            val = _setting_value(conn, item["setting"])
            out.append(
                {
                    **base,
                    "kind": "single",
                    "configured": bool(val),
                    "preview": _mask_secret(val) if val else "",
                    "keys": [],
                }
            )
    out.sort(key=lambda r: (_KEY_GROUP_ORDER.index(r["group"]), r["name"]))
    return out


@app.get("/api/keys")
def list_keys() -> list:
    """Grouped API keys — Settings ke naye "API Keys" section ke
    liye. Har row masked hai (aakhri 4 chars), koi poori key nahi."""
    with db() as conn:
        return _keys_catalog(conn)


class KeySetIn(BaseModel):
    value: str = ""
    label: str = ""


@app.post("/api/keys/{provider}", status_code=201)
def set_key(provider: str, body: KeySetIn) -> dict:
    """Ek key add/set karo. Gemini rotation table me jati hai
    (multi-key); baaki providers ki setting me. Blank value 400."""
    provider = provider.strip().lower()
    item = next((f for f in FREE_KEYS if f["id"] == provider), None)
    if item is None:
        raise HTTPException(status_code=404, detail="provider not found")
    if item.get("no_key"):
        raise HTTPException(
            status_code=400, detail="Is provider ko key chahiye hi nahi"
        )
    value = (body.value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="key khaali nahi ho sakti")
    with db() as conn:
        if provider == "gemini":
            top = conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS m FROM gemini_api_keys"
            ).fetchone()["m"]
            cur = conn.execute(
                "INSERT INTO gemini_api_keys (label, key_value, position, created_at)"
                " VALUES (?, ?, ?, ?)",
                ((body.label or "").strip(), value, top + 1, utcnow()),
            )
            row = _gemini_key_row(conn, cur.lastrowid)
            return _gemini_key_public(row)
        conn.execute(
            "INSERT INTO settings (key, value, note) VALUES (?, ?, '')"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (item["setting"], value),
        )
    with db() as conn:
        return _keys_catalog(conn)


@app.delete("/api/keys/{provider}")
def delete_key(provider: str) -> dict:
    """Ek single-key provider ki key clear karo. Gemini ki keys
    ek-ek karke rotation list se delete hoti hain (is endpoint se
    poori rotation clear nahi hoti)."""
    provider = provider.strip().lower()
    item = next((f for f in FREE_KEYS if f["id"] == provider), None)
    if item is None:
        raise HTTPException(status_code=404, detail="provider not found")
    if provider == "gemini":
        raise HTTPException(
            status_code=400,
            detail="Gemini keys ek-ek karke delete karein — rotation list me Delete button",
        )
    if item.get("no_key"):
        raise HTTPException(
            status_code=400, detail="Is provider ki koi key hoti hi nahi"
        )
    with db() as conn:
        conn.execute(
            "UPDATE settings SET value = '' WHERE key = ?", (item["setting"],)
        )
    return {"deleted": True, "provider": provider}


@app.post("/api/keys/{provider}/test")
def test_key(provider: str) -> dict:
    """Stored key ko live test karo — friendly message + key lene ka
    link (help_url) saath aata hai, raw JSON kabhi nahi."""
    provider = provider.strip().lower()
    item = next((f for f in FREE_KEYS if f["id"] == provider), None)
    if item is None:
        raise HTTPException(status_code=404, detail="provider not found")
    if item.get("no_key"):
        return {
            "provider": provider,
            "ok": True,
            "message": "Pollinations ko key chahiye hi nahi — test image wala button use karein",
            "help_url": item.get("get_url", ""),
        }
    with db() as conn:
        if provider == "gemini":
            keys = _gemini_keys(conn)
            key = keys[0] if keys else ""
        else:
            key = _setting_value(conn, item["setting"])
    if not key:
        return {
            "provider": provider,
            "ok": False,
            "message": f"Pehle apni {item['name']} key add karein — phir test hoga",
            "help_url": item.get("get_url", ""),
        }
    ok, message = _free_key_test(provider, key)
    return {
        "provider": provider,
        "ok": ok,
        "message": message,
        "help_url": item.get("get_url", ""),
    }


class PollinationsIn(BaseModel):
    prompt: str = ""


@app.post("/api/pollinations/test")
def pollinations_test(body: PollinationsIn) -> dict:
    """Pollinations se ek asli image banao — bina key ke. Free route
    ka live proof. Image studio/data/pollinations-test/ me save hoti
    hai aur /files/ se dikhti hai."""
    import urllib.error
    import urllib.request

    prompt = (body.prompt or "").strip() or (
        "a lighthouse at sunset, cinematic, detailed"
    )
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + "?width=1280&height=720&nologo=true"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "Kreafy-Creator-Studio"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Pollinations ne mana kar diya (HTTP {exc.code})",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=502, detail=f"Pollinations se connect nahi ho saka: {exc}"
        )
    if "image" not in ctype or len(data) < 10_000:
        raise HTTPException(
            status_code=502,
            detail="Pollinations se image nahi mili — dobara try karein",
        )
    folder = DATA_DIR / "pollinations-test"
    folder.mkdir(parents=True, exist_ok=True)
    ext = ".png" if "png" in ctype else ".jpg"
    name = f"test_{int(time.time())}{ext}"
    (folder / name).write_bytes(data)
    return {
        "prompt": prompt,
        "path": f"pollinations-test/{name}",
        "url": f"/files/pollinations-test/{name}",
        "bytes": len(data),
    }


# --- Slice 6: Watermark Cleaner -------------------------------------------
# Gemini sparkle corner badge remover (Flow / Nano Banana images).
# Pure module studio/backend/watermark_cleaner.py karta hai kaam:
# detect_badge (locate) + clean_image (reverse-blend + inpaint).
# Module numpy + PIL top par import karta hai — numpy opencv ke saath
# aata hai, is liye opencv na ho to module import bhi fail ho sakta
# hai. Is liye yahan LAZY import hai, har endpoint ke andar
# (try/except ImportError -> honest 503), main.py ke top par kabhi
# nahi — app opencv ke baghair bhi start hoti hai.
# Jobs studio/data/watermark/<uuid>/ me hain (gitignored, ZIP me
# kabhi nahi jate) + job.json. /files/ mount DATA_DIR serve karta
# hai; orig/cleaned URLs relative paths hain (watermark/<job>/<file>)
# — frontend ka fileUrl() un par /files/ lagata hai (assets wali
# convention), warna URL double ho jata hai.

WM_DIR = DATA_DIR / "watermark"
WM_MAX_FILES = 20
WM_MAX_BYTES = 20 * 1024 * 1024
_WM_ID_RE = re.compile(r"^[0-9a-f-]{8,64}$")
_WM_OPENCV_MSG = (
    "OpenCV install nahi hai — Watermark Cleaner ke liye Setup se "
    "opencv-python-headless install karein, ya: pip install "
    "opencv-python-headless"
)


def _wm_require_cv2():
    """watermark_cleaner lazily load karein; na mile to honest 503."""
    try:
        import watermark_cleaner as wc
    except ImportError:
        raise HTTPException(status_code=503, detail=_WM_OPENCV_MSG)
    if not wc.opencv_available():
        raise HTTPException(status_code=503, detail=_WM_OPENCV_MSG)
    return wc


def _wm_job_dir(job_id: str) -> Path:
    if not _WM_ID_RE.match(job_id or ""):
        raise HTTPException(status_code=404, detail="watermark job nahi mila")
    return WM_DIR / job_id


def _wm_load_job(job_id: str) -> dict:
    folder = _wm_job_dir(job_id)
    job_file = folder / "job.json"
    if not job_file.is_file():
        raise HTTPException(status_code=404, detail="watermark job nahi mila")
    try:
        return json.loads(job_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(
            status_code=500, detail="watermark job read nahi ho saka"
        )


def _wm_save_job(job: dict) -> None:
    folder = _wm_job_dir(job["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(
        json.dumps(job, indent=2), encoding="utf-8"
    )


def _wm_clamp_intensity(value) -> float:
    try:
        v = float(value if value is not None else 1.0)
    except (TypeError, ValueError):
        v = 1.0
    return max(0.5, min(2.0, v))


def _wm_badge_summary(badge: dict | None) -> dict | None:
    """detect_badge ka result job.json ke liye (mask numpy array hai —
    JSON me nahi ja sakta, is liye sirf plain fields)."""
    if not badge:
        return None
    return {
        "found": True,
        "corner": badge["corner"],
        "bbox": [int(v) for v in badge["bbox"]],
    }


class WmCleanIn(BaseModel):
    intensity: float | None = 1.0


class WmStroke(BaseModel):
    x: float = 0.0
    y: float = 0.0
    r: float = 0.02


class WmManualIn(BaseModel):
    image: str = ""
    strokes: list[WmStroke] = []
    intensity: float | None = 1.0


@app.post("/api/watermark/upload", status_code=201)
async def watermark_upload(files: list[UploadFile] = File(...)) -> dict:
    """Tasveerein upload karein (max 20, har ek <= 20 MB, png/jpg/webp)
    — upload par hi har image par detect_badge chalta hai."""
    wc = _wm_require_cv2()
    if not files:
        raise HTTPException(
            status_code=400, detail="koi tasveer nahi di — png, jpg ya webp dein"
        )
    if len(files) > WM_MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"ek dafa me max {WM_MAX_FILES} tasveerein dein",
        )
    job_id = uuid.uuid4().hex
    folder = WM_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    images: list[dict] = []
    skipped: list[str] = []
    for f in files:
        fname = safe_filename(f.filename or "unnamed")
        ext = Path(fname).suffix.lower()
        if ext not in IMAGE_EXTS:
            skipped.append(f"{fname}: tasveer nahi hai — png, jpg ya webp dein")
            continue
        data = await f.read()
        if len(data) > WM_MAX_BYTES:
            skipped.append(f"{fname}: 20 MB se bari hai — chhoti file dein")
            continue
        name = f"{int(time.time())}_{fname}"
        (folder / name).write_bytes(data)
        badge = None
        try:
            arr = wc.load_image(data)
            badge = _wm_badge_summary(wc.detect_badge(arr))
        except Exception:
            # Detection fail ho to upload fail nahi hota — badge
            # unknown rehta hai, Clean par dobara try hota hai.
            badge = None
        images.append(
            {
                "name": name,
                "orig_url": f"watermark/{job_id}/{name}",
                "badge": badge,
                "cleaned_url": None,
                "report": None,
            }
        )
    if not images:
        shutil.rmtree(folder, ignore_errors=True)
        detail = (
            "koi tasveer save nahi hui — " + "; ".join(skipped)
            if skipped
            else "koi tasveer save nahi hui — png, jpg ya webp file dein"
        )
        raise HTTPException(status_code=400, detail=detail)
    job = {
        "id": job_id,
        "created": utcnow(),
        "status": "uploaded",
        "intensity": 1.0,
        "images": images,
        "summary": None,
        "skipped": skipped,
    }
    _wm_save_job(job)
    return job


def _wm_clean_one(args):
    """Ek image clean karein — ThreadPoolExecutor(4) ke liye worker.
    (wc, folder, image, intensity) -> updated image entry."""
    wc, folder, image, intensity = args
    orig_path = folder / image["name"]
    data = orig_path.read_bytes()
    arr = wc.load_image(data)
    cleaned, report = wc.clean_image(arr, intensity=intensity)
    ext = Path(image["name"]).suffix.lower() or ".png"
    clean_name = f"cleaned_{image['name']}"
    if report.get("found"):
        (folder / clean_name).write_bytes(
            wc.save_image(cleaned, ext.lstrip("."))
        )
    else:
        # Koi badge nahi — cleaned file original ki copy hai.
        (folder / clean_name).write_bytes(data)
    image["cleaned_url"] = f"watermark/{_wm_job_id(folder)}/{clean_name}"
    image["report"] = report
    return image


def _wm_job_id(folder: Path) -> str:
    return folder.name


@app.post("/api/watermark/{job_id}/clean")
def watermark_clean(job_id: str, body: WmCleanIn) -> dict:
    """Job ki saari images clean karein — 4-at-a-time."""
    wc = _wm_require_cv2()
    job = _wm_load_job(job_id)
    intensity = _wm_clamp_intensity(body.intensity)
    folder = _wm_job_dir(job_id)
    with ThreadPoolExecutor(max_workers=4) as pool:
        job["images"] = list(
            pool.map(
                _wm_clean_one,
                [(wc, folder, img, intensity) for img in job["images"]],
            )
        )
    with_badge = sum(
        1 for img in job["images"] if (img.get("report") or {}).get("found")
    )
    clean_ge_90 = sum(
        1
        for img in job["images"]
        if (img.get("report") or {}).get("found")
        and (img["report"].get("clean_pct") or 0) >= 90
    )
    remaining = sum(
        1
        for img in job["images"]
        if (img.get("report") or {}).get("found")
        and (img["report"].get("clean_pct") or 0) < 90
    )
    job["intensity"] = intensity
    job["status"] = "done"
    job["summary"] = {
        "total": len(job["images"]),
        "with_badge": with_badge,
        "clean_ge_90": clean_ge_90,
        "remaining": remaining,
    }
    _wm_save_job(job)
    return job


@app.post("/api/watermark/{job_id}/manual")
def watermark_manual(job_id: str, body: WmManualIn) -> dict:
    """Ek image par haath se paint kiye strokes se dobara clean karein.
    Cleaned version ho to usi par, warna original par."""
    wc = _wm_require_cv2()
    job = _wm_load_job(job_id)
    name = (body.image or "").strip()
    image = next((i for i in job["images"] if i["name"] == name), None)
    if image is None:
        raise HTTPException(
            status_code=404, detail="ye tasveer is job me nahi hai"
        )
    if not body.strokes:
        raise HTTPException(
            status_code=400,
            detail="pehle tasveer par paint karein — koi stroke nahi mila",
        )
    intensity = _wm_clamp_intensity(body.intensity)
    folder = _wm_job_dir(job_id)
    clean_name = f"cleaned_{image['name']}"
    src = folder / clean_name
    if not src.is_file():
        src = folder / image["name"]
    arr = wc.load_image(src.read_bytes())
    h, w = arr.shape[:2]
    mask = wc.strokes_to_mask(
        w,
        h,
        [{"x": s.x, "y": s.y, "r": s.r} for s in body.strokes],
        intensity,
    )
    cleaned, report = wc.clean_image(arr, intensity=intensity, extra_mask=mask)
    ext = Path(image["name"]).suffix.lower() or ".png"
    if report.get("found") or report.get("manual"):
        (folder / clean_name).write_bytes(
            wc.save_image(cleaned, ext.lstrip("."))
        )
        image["cleaned_url"] = f"watermark/{job_id}/{clean_name}"
    image["report"] = report
    job["intensity"] = intensity
    _wm_save_job(job)
    return image


@app.get("/api/watermark/jobs")
def watermark_list_jobs() -> list:
    """Saare watermark jobs — newest pehle."""
    if not WM_DIR.is_dir():
        return []
    jobs: list[dict] = []
    for folder in WM_DIR.iterdir():
        if not folder.is_dir():
            continue
        job_file = folder / "job.json"
        if not job_file.is_file():
            continue
        try:
            jobs.append(json.loads(job_file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    jobs.sort(key=lambda j: j.get("created", ""), reverse=True)
    return jobs


@app.get("/api/watermark/{job_id}")
def watermark_get_job(job_id: str) -> dict:
    return _wm_load_job(job_id)


@app.get("/api/watermark/{job_id}/images.zip")
def watermark_download_zip(job_id: str) -> StreamingResponse:
    """Job ki saari cleaned images ek ZIP me (cleaned na ho to
    original)."""
    job = _wm_load_job(job_id)
    folder = _wm_job_dir(job_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in job["images"]:
            clean_name = f"cleaned_{img['name']}"
            path = folder / clean_name
            if not path.is_file():
                path = folder / img["name"]
            if path.is_file():
                zf.writestr(path.name, path.read_bytes())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="watermark-cleaned-{job_id[:8]}.zip"'
            )
        },
    )


# --- Prebuilt frontend (production mode) -----------------------------------
# Jab frontend/dist maujood hai (release ZIP), backend khud hi dashboard
# serve karta hai — Vite dev server / Node.js ki zaroorat nahi. Ye mount
# file ke AAKHIR me hai taake /api/*, /files/* aur /output-files/*
# routes pehle match hon.
_DIST_DIR = APP_DIR / "frontend" / "dist"
if (_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=_DIST_DIR, html=True), name="frontend")
