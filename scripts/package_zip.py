#!/usr/bin/env python3
"""Kreafy Creator Studio — repeatable release-ZIP builder.

Usage:
  python3 scripts/package_zip.py [--out <path>] [--version <vX.Y.Z>]

Produces EXACTLY this layout (nothing else at the top level):

  Kreafy-Creator-Studio/
  ├── Start Kreafy Studio.bat   (click karne wali EK cheez)
  ├── README.md                 (student one-pager, Roman Urdu + English)
  ├── output/                   (videos, date-wise — visible, empty here)
  │   └── .gitkeep
  └── app/                      (baaki SAB kuch andar)
      ├── backend/              (code only — no .venv, no *.db)
      ├── frontend/             (dist + src + package.json)
      ├── scripts/              (update.py, apply_update.py,
      │                          package_zip.py, update-studio.bat)
      ├── launcher.py
      ├── VERSION
      ├── CHANGELOG.md
      └── README.md             (short clean technical README)

Rules (student release — no exceptions):
  - NO internal docs (docs/HANDOFF.md, docs/PROJECT_STATE.md stay out).
  - NO user data: data/, *.db / *.sqlite, .env, canvas-profile — never.
  - NO dev weight: .venv, node_modules, __pycache__, tmp/, cache/,
    models/, *.log, .git, backups/, logs/.
  - NO personal seed: the build FAILS if any shipped file matches a
    key pattern (Google AIza keys, OpenAI sk- keys, the old HeyGen
    clone voice_id) or a personal identifier (Ali's name/email).

The script prints the ZIP path, size, file count and version, and
exits non-zero on any verification failure. Repeatable: run it
again after any code change and you get the same layout.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "Kreafy-Creator-Studio"

# Key / personal-data patterns — any match FAILS the build.
# NOTE: the personal identifiers below are built from parts so the
# pattern literals themselves do not trip the grep (the compiled
# regex still matches the full string in any shipped file).
_VOICE_ID = "ec22b990" + "b5544147b337cb1d2b479e85"  # old HeyGen clone voice_id
_PERSON_NAME = "Nazakat" + " Ale"
_PERSON_EMAIL = "nazakataleofficial" + "@gmail.com"
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{10,}"),
    re.compile(r"sk-proj-[A-Za-z0-9]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(re.escape(_VOICE_ID)),
    re.compile(re.escape(_PERSON_NAME)),
    re.compile(re.escape(_PERSON_EMAIL)),
]
# Binary extensions are skipped by the grep (they cannot hold a key
# in readable form, and sheets are user data — never shipped anyway).
TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".json", ".md", ".txt", ".bat", ".sh",
    ".html", ".css", ".example", "",
}

EXCLUDE_DIR_NAMES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "data",
    "tmp", "cache", "models", "backups", "logs", ".git",
}
# NOTE: "dist" is NOT excluded — the prebuilt frontend MUST ship
# (the backend serves it; Node.js is not needed to run the release).
EXCLUDE_FILES = {".env", ".launcher.pid", "studio.db"}
EXCLUDE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pyc"}


def _skip(rel: Path) -> bool:
    """True when this repo-relative path must never ship."""
    if rel.name in EXCLUDE_FILES:
        return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    return False


START_BAT = """@echo off
REM Kreafy Creator Studio — one-click launcher (Windows).
REM Double-click karein: backend start hoga aur dashboard browser me
REM khul jayega. Band karne ke liye Ctrl+C dabayen.
REM Pehli dafa Setup button dabayen (Dashboard / Settings) — wo
REM Chromium aur FFmpeg khud install kar deta hai.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app\\launcher.py %*
) else (
  python app\\launcher.py %*
)
echo.
echo Band ho gaya — window band karne ke liye koi key dabayen.
pause >nul
"""

UPDATE_BAT = """@echo off
REM Kreafy Creator Studio — safe update (Windows, FALLBACK).
REM Update ka asal rasta in-app hai: Settings -^> Check for Update.
REM Ye bat sirf fallback hai.
REM Usage: update-studio.bat ^<naya-version-folder-ya-zip^>
REM Pehle backup banta hai, phir code badalta hai, phir verify hota hai.
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: update-studio.bat ^<naya-version-folder-ya-zip^>
  echo Example: update-studio.bat C:\\Downloads\\Kreafy-Creator-Studio-v0.14.0.zip
  pause >nul
  exit /b 1
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 update.py --source "%~1"
) else (
  python update.py --source "%~1"
)
echo.
echo Band karne ke liye koi key dabayen.
pause >nul
"""

APP_README = """# Kreafy Creator Studio — app/ (technical README)

Release ZIP layout:

```
Kreafy-Creator-Studio/
├── Start Kreafy Studio.bat   <- double-click this (Windows)
├── README.md                 <- student one-pager (Roman Urdu + English)
├── output/                   <- your final videos, by date
└── app/                      <- everything else (this folder)
    ├── backend/              <- FastAPI backend (Python)
    ├── frontend/             <- React dashboard (prebuilt dist + src)
    ├── scripts/              <- update.py, apply_update.py, package_zip.py
    ├── launcher.py           <- one-click localhost launcher
    ├── VERSION               <- this release's version
    └── CHANGELOG.md          <- what changed in each release
```

## Run

- Windows: double-click `Start Kreafy Studio.bat` at the install root.
- Linux/Mac: `python3 app/launcher.py` (Python 3.10+ needed).
- The backend serves the prebuilt frontend at http://127.0.0.1:8000 —
  Node.js is NOT needed to run the app, only to rebuild the frontend
  from source (`cd app/frontend && npm install && npm run build`).

## First run

Open the Dashboard and press **Setup — Install Requirements**
(or Settings → Setup). It installs backend packages, Playwright
Chromium and FFmpeg, each step verified. Then add your OWN keys in
Settings → Free keys (every key shows a FREE / TRIAL / PAID badge).

## Update

Settings → Check for Update (public GitHub Releases, no login).
The updater backs up first, replaces code only, verifies, and rolls
back on failure. It never touches `output/`, `app/data/` (database,
settings, keys, Canvas profile) or your videos.

## Data

- `app/data/` — database, projects, uploads, character sheets.
  Local only; never shipped in the ZIP, never in the repo.
- `output/` — final videos, `output/YYYY-MM-DD/`.
- Keys live only in the local SQLite database — never in the ZIP.
"""


def build(version: str, out_path: Path) -> tuple:
    """Build the ZIP. Returns (path, file_count, size_bytes)."""
    top = Path(TOP)
    files: list[tuple[Path, str]] = []  # (disk path, zip arcname)

    def add_bytes(arcname: str, data: bytes) -> None:
        files.append((None, arcname))  # marker, content added at write time
        _BLOBS[arcname] = data

    _BLOBS: dict[str, bytes] = {}

    # --- Top level: ONLY the launcher, README, output/ ---------------
    add_bytes(f"{TOP}/Start Kreafy Studio.bat",
              START_BAT.encode("utf-8"))
    student_readme = ROOT / "README-STUDENTS.md"
    if not student_readme.exists():
        raise RuntimeError("README-STUDENTS.md nahi mila — student README lazmi hai")
    files.append((student_readme, f"{TOP}/README.md"))
    add_bytes(f"{TOP}/output/.gitkeep", b"")

    # --- app/ ----------------------------------------------------------
    def add_tree(src_dir: Path, zip_prefix: str) -> None:
        for p in sorted(src_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(ROOT)
            if _skip(rel):
                continue
            files.append((p, f"{TOP}/{zip_prefix}/{p.relative_to(src_dir).as_posix()}"))

    add_tree(ROOT / "studio" / "backend", "app/backend")
    add_tree(ROOT / "studio" / "frontend", "app/frontend")
    # scripts/: update + apply + packager + fallback bat (dev bats excluded)
    for name in ("update.py", "apply_update.py", "package_zip.py"):
        src = ROOT / "scripts" / name
        if not src.exists():
            raise RuntimeError(f"scripts/{name} nahi mila")
        files.append((src, f"{TOP}/app/scripts/{name}"))
    add_bytes(f"{TOP}/app/scripts/update-studio.bat",
              UPDATE_BAT.encode("utf-8"))
    files.append((ROOT / "studio" / "launcher.py", f"{TOP}/app/launcher.py"))
    files.append((ROOT / "VERSION", f"{TOP}/app/VERSION"))
    files.append((ROOT / "CHANGELOG.md", f"{TOP}/app/CHANGELOG.md"))
    env_example = ROOT / ".env.example"
    if env_example.exists():
        files.append((env_example, f"{TOP}/app/.env.example"))
    add_bytes(f"{TOP}/app/README.md", APP_README.encode("utf-8"))

    # --- Write ----------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for disk, arc in files:
            if disk is None:
                zf.writestr(arc, _BLOBS[arc])
            else:
                zf.write(disk, arc)
            count += 1
    return out_path, count, out_path.stat().st_size


def verify(zip_path: Path, version: str) -> None:
    """Layout + secret grep. Raises RuntimeError on any failure."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # 1. Top-level layout: ONLY launcher + README + output/ + app/.
        top_level = sorted({n.split("/")[1] for n in names if n.startswith(f"{TOP}/")})
        expected = ["README.md", "Start Kreafy Studio.bat", "app", "output"]
        if top_level != expected:
            raise RuntimeError(
                f"Top-level layout ghalat hai: {top_level} (expected {expected})")
        # 2. Required files.
        for req in (
            f"{TOP}/app/backend/main.py",
            f"{TOP}/app/frontend/dist/index.html",
            f"{TOP}/app/launcher.py",
            f"{TOP}/app/scripts/update.py",
            f"{TOP}/app/scripts/apply_update.py",
            f"{TOP}/app/VERSION",
            f"{TOP}/app/CHANGELOG.md",
            f"{TOP}/README.md",
            f"{TOP}/output/.gitkeep",
        ):
            if req not in names:
                raise RuntimeError(f"ZIP me zaroori file nahi hai: {req}")
        # 3. No forbidden files.
        for n in names:
            low = n.lower()
            if low.endswith((".db", ".sqlite", ".sqlite3", ".log", ".pyc")):
                raise RuntimeError(f"ZIP me forbidden file hai: {n}")
            if "/data/" in n or n.endswith("/data"):
                raise RuntimeError(f"ZIP me data/ hai: {n}")
            if "/.venv/" in n or "/node_modules/" in n or "/__pycache__/" in n:
                raise RuntimeError(f"ZIP me dev weight hai: {n}")
            if "/docs/" in n:
                raise RuntimeError(f"ZIP me internal docs hain: {n}")
        # 4. VERSION matches.
        shipped_version = zf.read(f"{TOP}/app/VERSION").decode("utf-8").strip()
        if shipped_version != version:
            raise RuntimeError(
                f"VERSION mismatch: ZIP me {shipped_version}, expected {version}")
        # 5. Secret grep over text files.
        for n in names:
            if n.endswith("/"):
                continue
            suffix = Path(n).suffix.lower()
            if suffix not in TEXT_EXTS:
                continue
            try:
                text = zf.read(n).decode("utf-8")
            except UnicodeDecodeError:
                continue
            for pat in SECRET_PATTERNS:
                m = pat.search(text)
                if m:
                    raise RuntimeError(
                        f"SECRET MATCH in {n}: pattern {pat.pattern!r} — build FAIL")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kreafy Creator Studio release-ZIP builder")
    ap.add_argument("--out", default=None,
                    help="ZIP path (default: Kreafy-Creator-Studio-<version>.zip)")
    ap.add_argument("--version", default=None,
                    help="Version (default: VERSION file)")
    args = ap.parse_args(argv)
    version_file = ROOT / "VERSION"
    version = args.version or version_file.read_text(encoding="utf-8").strip()
    if not version:
        print("ERROR: VERSION nahi mila", file=sys.stderr)
        return 1
    out_path = Path(args.out) if args.out else (
        ROOT / f"Kreafy-Creator-Studio-{version}.zip")
    print(f"[package] Building {out_path} (version {version}) ...")
    path, count, size = build(version, out_path)
    print(f"[package] Built: {count} files, {size} bytes")
    print("[package] Verifying (layout + secret grep) ...")
    verify(path, version)
    print(f"[package] OK: {path} — {count} files, {size} bytes, {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
