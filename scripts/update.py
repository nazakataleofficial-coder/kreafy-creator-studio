#!/usr/bin/env python3
"""Kreafy Creator Studio — safe update.

Usage:
  python3 scripts/update.py --source <new-version-dir-or-zip>

  --source  Naya version: ek folder, ya GitHub release ZIP
            (uske andar app/backend/main.py ya
            studio/backend/main.py hona chahiye).
  --app-dir  App ki folder (default: is script se do level upar,
            yaani install root / repo root).

Do layouts supported hain:
  - Package layout: <install>/app/{backend,frontend,scripts,...}
    + <install>/output/ (videos) + <install>/Start Kreafy Studio.bat
  - Dev layout:     <repo>/studio/{backend,frontend,...}

Flow (yehi order, har step pehle verify hota hai):
  1. Naya version check — source me app/ ya studio/ ke neeche
     backend/main.py hai?
  2. App chal rahi ho to band karo — sirf launcher ki PID file se;
     agar app chal rahi hai aur PID file nahi hai to RUK JAO
     (kisi aur ka process kill nahi karte).
  3. BACKUP pehle — app/backend/studio.db + app/data/
     (renders/ ke baghair) + puray code ka snapshot (`code/`) —
     taa ke rollback purana code bhi wapas la sake, sirf data nahi.
     -> app/backups/backup-<timestamp>.zip
     output/ (aapki videos) backup me NAHI aata aur update use
     kabhi touch nahi karta.
  4. Pehle wali halat note karo — projects/jobs/assets ki ginti
     (read-only SQLite query).
  5. Code badlo — source se copy, magar YE KABHI NAHI:
     .git, node_modules, .venv, __pycache__, backups/,
     logs/, output/, app/data/**, app/backend/studio.db*
     (aapka kaam safe). NOTE: frontend/dist ZAROOR copy hota hai —
     release ka prebuilt frontend hi UI hai; dist skip karne se
     update ke baad purana UI rehta (bug tha, v0.14.0 me fix).
  6. Backend start karke verify karo — /api/health 200 + projects
     ki ginti pehle wali ke barabar. Agar verify fail ho to
     ROLLBACK: backup wapas restore karo aur dobara verify karo.
  7. Kamyabi par backend dobara band kar do — app launcher se
     kholne ke liye tayyar hai.

Kuch ghalat ho to script khud batata hai kya hua aur backup kahan
hai — kabhi chup-chap fail nahi hota. Koi paid cheez, key ya
download isme nahi hai.
"""

import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

# Launcher import: app/launcher.py (package) ya studio/launcher.py
# (dev) — jo mile, uska folder sys.path me daalo.
# Install root dhoondo: update.py scripts/ me hota hai — package
# layout me app/scripts/update.py (root = 2 level upar), dev me
# scripts/update.py (root = 1 level upar).
def _find_install_root() -> Path:
    # apply_update.py ZIP se nikla hua update.py chalata hai (temp
    # dir me) — us waqt install root env se milta hai.
    _env = os.environ.get("KREAFY_APP_DIR")
    if _env:
        _p = Path(_env)
        for _sub in ("app", "studio"):
            if (_p / _sub / "launcher.py").exists():
                return _p
    here = Path(__file__).resolve()
    for cand in (here.parent.parent, here.parent.parent.parent,
                 here.parent):
        for _sub in ("app", "studio"):
            if (cand / _sub / "launcher.py").exists():
                return cand
    return here.parent.parent


_APP_DIR_DEFAULT = _find_install_root()
for _sub in ("app", "studio"):
    _lp = _APP_DIR_DEFAULT / _sub / "launcher.py"
    if _lp.exists():
        sys.path.insert(0, str(_lp.parent))
        break
import launcher  # noqa: E402  (reuse: python finder, health wait, stop)

EXCLUDE_DIR_NAMES = {".git", "node_modules", ".venv", "venv",
                     "__pycache__", "backups", "logs", "output"}
EXCLUDE_FILES = {".launcher.pid"}


def log(msg: str) -> None:
    print(f"[update] {msg}", flush=True)


def _app_subdir(app_dir: Path) -> str:
    """'app' (package layout) ya 'studio' (dev layout) — jo mile."""
    if (app_dir / "app" / "backend" / "main.py").exists():
        return "app"
    return "studio"


def _skip(rel: Path) -> bool:
    """True when this install-root-relative path must never be
    copied over. output/ (videos), data/ (user data) aur DB
    kabhi overwrite nahi hote."""
    if rel.name in EXCLUDE_FILES:
        return True
    if rel == Path("studio.db"):  # stray 0-byte file at repo root
        return True
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    pos = rel.as_posix()
    if pos.startswith("app/data/") or pos.startswith("studio/data/"):
        return True
    if pos.startswith("app/backend/studio.db") or pos.startswith(
        "studio/backend/studio.db"
    ):
        return True
    return False


def _db_counts(app_dir: Path) -> dict:
    sub = _app_subdir(app_dir)
    db = app_dir / sub / "backend" / "studio.db"
    if not db.exists():
        return {"projects": 0, "jobs": 0, "assets": 0}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = {}
        for table in ("projects", "jobs", "assets"):
            try:
                out[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                out[table] = -1  # table nahi hai — purana DB ho sakta hai
        return out
    finally:
        conn.close()


def _make_backup(app_dir: Path) -> tuple:
    """DB + data/ (no renders/) + code snapshot -> app/backups/*.zip.

    The code snapshot is what makes rollback real: restoring only the
    DB would leave the new (broken) code in place and the app still
    dead. `code/` holds the same files the copy step would overwrite
    (same exclusions), so a rollback puts the old code back too.
    output/ backup me nahi aata — videos boht bari hoti hain aur
    update unhe chhoota hi nahi.
    """
    sub = _app_subdir(app_dir)
    backups = app_dir / sub / "backups"
    backups.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = backups / f"backup-{ts}.zip"
    db = app_dir / sub / "backend" / "studio.db"
    data = app_dir / sub / "data"
    files, total_bytes = 0, 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if db.exists():
            z.write(db, "backend/studio.db")
            files += 1
            total_bytes += db.stat().st_size
            for suffix in ("-journal", "-wal"):
                side = Path(str(db) + suffix)
                if side.exists():
                    z.write(side, f"backend/studio.db{suffix}")
                    files += 1
                    total_bytes += side.stat().st_size
        if data.exists():
            for p in sorted(data.rglob("*")):
                if p.is_dir():
                    continue
                rel = p.relative_to(data)
                if rel.parts and rel.parts[0] == "renders":
                    continue
                z.write(p, f"data/{rel.as_posix()}")
                files += 1
                total_bytes += p.stat().st_size
        for p in sorted(app_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(app_dir)
            if _skip(rel):
                continue
            z.write(p, f"code/{rel.as_posix()}")
            files += 1
            total_bytes += p.stat().st_size
    return path, files, total_bytes


def _restore_backup(app_dir: Path, backup_zip: Path,
                    new_files: list | None = None) -> None:
    """Backup ZIP ko wapas lagao: code + DB + data/ (renders/ ko chhoo nahi).

    `new_files` — files the failed update copied in: pehle delete karo,
    taa ke naya version ki koi nayi file purane code me na reh jaye.
    """
    sub = _app_subdir(app_dir)
    with zipfile.ZipFile(backup_zip) as z:
        names = z.namelist()
        if "backend/studio.db" not in names:
            raise RuntimeError(
                f"backup me studio.db nahi hai — restore nahi ho sakta: {backup_zip}")
        has_code = any(n.startswith("code/") for n in names)
        if not has_code:
            log("WARN: is backup me code snapshot nahi hai — sirf DB + data "
                "wapas lagenge, code waisa hi rahega.")
        db = app_dir / sub / "backend" / "studio.db"
        for suffix in ("", "-journal", "-wal"):
            side = Path(str(db) + suffix)
            if side.exists():
                side.unlink()
        data = app_dir / sub / "data"
        if data.exists():
            for p in sorted(data.rglob("*"), reverse=True):
                if p.is_dir():
                    if p.name != "renders" and not any(
                            part == "renders" for part in p.relative_to(data).parts):
                        try:
                            p.rmdir()
                        except OSError:
                            pass
                elif not (p.relative_to(data).parts
                          and p.relative_to(data).parts[0] == "renders"):
                    p.unlink()
        if new_files:
            for rel in new_files:
                target = app_dir / rel
                if target.exists():
                    target.unlink()
        if has_code:
            tmp = app_dir / sub / ".code-restore-tmp"
            if tmp.exists():
                shutil.rmtree(tmp)
            for name in names:
                if name.startswith("code/"):
                    z.extract(name, tmp)
            code_root = tmp / "code"
            for p in sorted(code_root.rglob("*")):
                if p.is_dir():
                    continue
                rel = p.relative_to(code_root)
                dest = app_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            shutil.rmtree(tmp)
        for name in names:
            if name == "backend/studio.db" or name.startswith("data/"):
                z.extract(name, app_dir / sub)


def _resolve_source(source: Path, tmpdir: Path) -> Path:
    """Folder ya ZIP -> naya version ki root folder (main.py check).
    Release ZIP me top folder Kreafy-Creator-Studio/ hota hai, uske
    andar app/backend/main.py. Dev ZIP/folder me studio/ hota hai."""
    if source.is_dir():
        root = source
    elif source.is_file() and source.suffix == ".zip":
        with zipfile.ZipFile(source) as z:
            z.extractall(tmpdir)
        # GitHub release ZIP me ek top-level folder hota hai:
        # Kreafy-Creator-Studio/app/backend/main.py
        candidates = [p for p in tmpdir.iterdir() if p.is_dir()]
        root = None
        for cand in candidates:
            if ((cand / "app" / "backend" / "main.py").exists()
                    or (cand / "studio" / "backend" / "main.py").exists()
                    or (cand / "backend" / "main.py").exists()):
                root = cand
                break
        if root is None:
            root = tmpdir
    else:
        raise RuntimeError(f"source nahi mila: {source}")
    ok = (
        (root / "app" / "backend" / "main.py").exists()
        or (root / "studio" / "backend" / "main.py").exists()
        or (root / "backend" / "main.py").exists()
    )
    if not ok:
        raise RuntimeError(
            "source me app/backend/main.py ya studio/backend/main.py"
            " nahi hai — ye naya version nahi lagta")
    return root


def _copy_code(src_root: Path, app_dir: Path) -> list:
    """Source -> app dir, exclusions ke saath. Returns copied rel paths.
    Release ZIP ka top folder (Kreafy-Creator-Studio/) skip karke uske
    andar wali cheezein copy hoti hain (app/, Start Kreafy Studio.bat,
    README.md, output/.gitkeep)."""
    # Agar source root khud app/ ya studio/ hai (bare folder), to
    # uska content seedha copy karo; warna top folder ke andar wali
    # app//studio/ dhoondo.
    if (src_root / "backend" / "main.py").exists():
        src_app = src_root
        dst_app = app_dir / _app_subdir(app_dir)
        base_pairs = [(src_app, dst_app)]
        copied = []
        for src, dst in base_pairs:
            for p in sorted(src.rglob("*")):
                if p.is_dir():
                    continue
                rel = p.relative_to(src)
                if _skip(dst.relative_to(app_dir) / rel):
                    continue
                dest = dst / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
                copied.append((dst / rel).relative_to(app_dir))
        return copied
    copied = []
    for p in sorted(src_root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(src_root)
        # Release ZIP: top folder ke andar app/ + root files.
        if rel.parts and rel.parts[0] in ("app", "studio"):
            if _skip(rel):
                continue
        elif rel.parts and rel.parts[0] == "Kreafy-Creator-Studio":
            inner = Path(*rel.parts[1:])
            if _skip(inner):
                continue
            rel = inner
        else:
            # Top-level single file (jaise README) — seedha copy.
            if _skip(rel):
                continue
        dest = app_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        copied.append(rel)
    return copied


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_backend_for_check(app_dir: Path) -> subprocess.Popen:
    sub = _app_subdir(app_dir)
    backend_py = launcher.ensure_backend_python()
    log(f"Verify ke liye backend start ho raha hai ({backend_py}) ...")
    proc = launcher._start(
        [str(backend_py), "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(launcher.BACKEND_PORT)],
        app_dir / sub / "backend", "backend.log")
    return proc


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kreafy Creator Studio safe update")
    ap.add_argument("--source", required=True,
                    help="Naya version: folder ya GitHub release ZIP")
    ap.add_argument("--app-dir", default=None,
                    help="App ki folder (default: install root / repo root)")
    args = ap.parse_args(argv)

    app_dir = (Path(args.app_dir).resolve() if args.app_dir
               else _APP_DIR_DEFAULT)
    source = Path(args.source)
    log(f"App dir: {app_dir}")
    log(f"Source: {source}")

    # 1. Source check (kuch badalne se pehle).
    try:
        with tempfile.TemporaryDirectory(prefix="studio-update-") as tmp:
            src_root = _resolve_source(source, Path(tmp))
            log(f"Source OK: {src_root}")
            sub = _app_subdir(app_dir)

            # 2. App chal rahi hai? Band karo — sirf PID file se.
            if launcher.port_in_use(launcher.BACKEND_PORT):
                if launcher._read_pid_file():
                    log("App chal rahi hai — launcher instance band ho raha hai ...")
                    launcher.stop_running()
                else:
                    log("ERROR: backend port 8000 pehle se use me hai, magar ye "
                        "launcher se start nahi hua lagta. Pehle app band karein, "
                        "phir update chalain.")
                    return 1

            # 3. Backup PEHLE.
            backup_path, backup_files, backup_bytes = _make_backup(app_dir)
            log(f"Backup bana: {backup_path.name} "
                f"({backup_files} files, {backup_bytes / 1048576:.1f} MB)")

            # 4. Pehle wali halat note karo.
            before = _db_counts(app_dir)
            log(f"Pehle: {before['projects']} projects, {before['jobs']} jobs, "
                f"{before['assets']} assets")

            # 5. Code badlo.
            pkg_before = _file_hash(
                app_dir / sub / "frontend" / "package.json")
            req_before = _file_hash(
                app_dir / sub / "backend" / "requirements.txt")
            copied = _copy_code(src_root, app_dir)
            log(f"Code copy ho gaya: {len(copied)} files")

            # requirements.txt badla ho to backend deps dobara install
            # karo (jaise Canvas ke liye Playwright) — warna naya code
            # purani deps ke saath chalega aur naya provider dead hoga.
            req_after = _file_hash(
                app_dir / sub / "backend" / "requirements.txt")
            if req_before != req_after:
                backend_py = launcher.find_python()
                py = str(backend_py) if backend_py else sys.executable
                log("requirements.txt badla hai — pip install chal raha hai ...")
                r = subprocess.run(
                    [py, "-m", "pip", "install", "-r",
                     str(app_dir / sub / "backend" / "requirements.txt")],
                    timeout=900)
                if r.returncode != 0:
                    log("WARN: pip install fail — backend purani deps ke saath "
                        "bhi chal sakta hai; launcher dobara check karega.")

            # package.json badla ho aur dist NA ho (dev mode) to
            # frontend deps dobara install karo. Package layout me
            # dist prebuilt hota hai — npm ki zaroorat nahi.
            pkg_after = _file_hash(
                app_dir / sub / "frontend" / "package.json")
            if pkg_before != pkg_after and not (
                app_dir / sub / "frontend" / "dist" / "index.html"
            ).exists():
                npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
                log("package.json badla hai — npm install chal raha hai ...")
                r = subprocess.run([npm, "install"],
                                   cwd=app_dir / sub / "frontend",
                                   timeout=900)
                if r.returncode != 0:
                    log("WARN: npm install fail — frontend purani deps ke saath "
                        "bhi chal sakta hai; launcher dobara check karega.")

            # 6. Verify: backend start karo, health + data check karo.
            proc = _start_backend_for_check(app_dir)
            try:
                healthy = launcher.wait_for_health()
                after = _db_counts(app_dir) if healthy else {}
                ok = healthy and after.get("projects") == before["projects"]
                if not ok:
                    log("ERROR: verify fail — "
                        f"health={'OK' if healthy else 'FAIL'}, "
                        f"projects pehle={before['projects']} "
                        f"ab={after.get('projects')}")
                    log("Rollback ho raha hai — backup wapas lag raha hai ...")
                    launcher._stop_proc(proc, "backend")
                    _restore_backup(app_dir, backup_path, new_files=copied)
                    proc2 = _start_backend_for_check(app_dir)
                    try:
                        if launcher.wait_for_health():
                            log("Rollback OK — purana version wapas chal raha hai. "
                                f"Backup: {backup_path.name}")
                        else:
                            log("ERROR: rollback ke baad bhi backend health nahi "
                                f"de raha. Backup yahan hai, khud restore karein: "
                                f"{backup_path}")
                    finally:
                        launcher._stop_proc(proc2, "backend")
                    return 1
            finally:
                launcher._stop_proc(proc, "backend")

            log(f"Verify OK — health 200, projects {after['projects']} "
                f"(pehle {before['projects']}), jobs {after['jobs']}, "
                f"assets {after['assets']}")
            log("Update ho gaya. App launcher se kholein: Start Kreafy Studio.bat")
            log(f"Backup mehfooz hai: {backup_path}")
            return 0
    except RuntimeError as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
