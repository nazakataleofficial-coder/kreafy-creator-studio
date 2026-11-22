#!/usr/bin/env python3
"""Kreafy Creator Studio — detached update worker.

In-app update (POST /api/update/apply) isko detached chalata hai,
kyun ke update.py backend ko band karta hai — backend khud apna
update apply nahi kar sakta.

Flow:
  1. Release ZIP download karo (public GitHub Releases asset URL).
  2. scripts/update.py --source <zip> chalao (backup -> replace
     code -> verify -> rollback on failure). Output/ , data/ aur
     DB ko update.py kabhi touch nahi karta.
  3. Status JSON likho (backend /api/update/status se padhta hai).
  4. Kamyabi par launcher dobara chalao (backend + dashboard
     wapas up) — detached, taake ye worker exit kar sake.

Usage:
  python3 scripts/apply_update.py --zip-url <url>
      --app-dir <install-root> --status-file <path>

Koi key, koi paid cheez isme nahi hai.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def _write_status(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        print(f"[apply-update] status nahi likh saka: {exc}", flush=True)


def _find_script(app_dir: Path, name: str) -> Path | None:
    for cand in (app_dir / "app" / "scripts" / name,
                 app_dir / "studio" / "scripts" / name,
                 app_dir / "scripts" / name):
        if cand.exists():
            return cand
    return None


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kreafy Creator Studio update worker")
    ap.add_argument("--zip-url", required=True)
    ap.add_argument("--app-dir", required=True)
    ap.add_argument("--status-file", required=True)
    args = ap.parse_args(argv)

    app_dir = Path(args.app_dir).resolve()
    status_file = Path(args.status_file)
    started = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    _write_status(status_file, {
        "state": "downloading",
        "detail": args.zip_url,
        "started_at": started,
    })
    print(f"[apply-update] ZIP download: {args.zip_url}", flush=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="studio-update-apply-"))
    zip_path = tmpdir / "release.zip"
    try:
        req = urllib.request.Request(
            args.zip_url,
            headers={"User-Agent": "Kreafy-Creator-Studio"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                zip_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            _write_status(status_file, {
                "state": "failed",
                "detail": f"ZIP download nahi ho saka (HTTP {exc.code})",
                "started_at": started,
            })
            return 1
        except OSError as exc:
            _write_status(status_file, {
                "state": "failed",
                "detail": f"ZIP download nahi ho saka: {exc}",
                "started_at": started,
            })
            return 1

        # update.py: ZIP ke andar wala chalao, installed wala nahi —
        # installed v0.14.0 ka update.py package layout me launcher
        # import nahi kar sakta tha (bug), is liye aane wali release
        # ka update.py hi source of truth hai. ZIP me na mile to
        # installed wala fallback hai.
        update_py = None
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for _m in zf.namelist():
                    if _m.endswith("/scripts/update.py") or \
                            _m == "scripts/update.py":
                        update_py = tmpdir / "update.py"
                        update_py.write_bytes(zf.read(_m))
                        break
        except zipfile.BadZipFile:
            update_py = None
        if update_py is None:
            update_py = _find_script(app_dir, "update.py")
        if update_py is None:
            _write_status(status_file, {
                "state": "failed",
                "detail": "update.py nahi mila — ye release update apply nahi kar sakti",
                "started_at": started,
            })
            return 1

        _write_status(status_file, {
            "state": "applying",
            "detail": f"update.py chal raha hai ({zip_path.stat().st_size} bytes)",
            "started_at": started,
        })
        _env = dict(os.environ)
        _env["KREAFY_APP_DIR"] = str(app_dir)
        proc = subprocess.run(
            [sys.executable, str(update_py), "--source", str(zip_path),
             "--app-dir", str(app_dir)],
            capture_output=True, text=True, timeout=1800, env=_env,
        )
        tail = (proc.stdout or "") + (proc.stderr or "")
        tail = tail[-2000:]
        if proc.returncode != 0:
            _write_status(status_file, {
                "state": "failed",
                "detail": "update.py fail ho gaya — rollback check karein",
                "log": tail,
                "started_at": started,
            })
            return 1

        # Kamyabi: launcher dobara chalao (backend + dashboard wapas).
        launcher_py = None
        for cand in (app_dir / "app" / "launcher.py",
                     app_dir / "studio" / "launcher.py"):
            if cand.exists():
                launcher_py = cand
                break
        restarted = False
        if launcher_py is not None:
            kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "stdin": subprocess.DEVNULL,
            }
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen(
                [sys.executable, str(launcher_py), "--no-browser"],
                **kwargs,
            )
            restarted = True
        _write_status(status_file, {
            "state": "done",
            "detail": "Update ho gaya — app dobara start ho rahi hai"
            if restarted else
            "Update ho gaya — launcher khud chalain (Start Kreafy Studio.bat)",
            "log": tail,
            "started_at": started,
        })
        return 0
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
