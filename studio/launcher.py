#!/usr/bin/env python3
"""Kreafy Creator Studio — one-click localhost launcher.

Double-click `Start Kreafy Studio.bat` (Windows) or run:
  python3 app/launcher.py        (release ZIP layout)
  python3 studio/launcher.py     (dev layout, is repo se)

Do layouts supported hain (code paths se decide hota hai):
  - Package layout: <install>/app/{backend,frontend,scripts,...}
    + <install>/output/ (videos) + <install>/Start Kreafy Studio.bat
  - Dev layout:     <repo>/studio/{backend,frontend,...}

Package layout me backend prebuilt frontend (frontend/dist) khud
serve karta hai — Vite / Node.js ki zaroorat NAHI. Dev layout me
dist na ho to Vite dev server chalta hai (Node.js chahiye).

What it does, in order:
  1. Checks the PC has what the app needs (Python 3.10+, FFmpeg).
     FFmpeg / Playwright missing sirf warning hain — dashboard
     phir bhi khulta hai, aur Setup button (Dashboard / Settings)
     unhe install kar deta hai.
  2. Finds a Python that can run the backend (install ka .venv
     pehle, phir system Python). Agar kisi me FastAPI nahi hai to
     install ka .venv bana kar requirements ek dafa install karta hai.
  3. Starts the backend (FastAPI on http://127.0.0.1:8000), waits
     until it answers, then opens the dashboard in the browser.
     Dev layout me (dist na ho) Vite dev server bhi start hota hai
     (http://127.0.0.1:5173).
  4. On Ctrl+C it stops everything cleanly and checks the ports are
     free again. Projects, jobs aur assets data/ + output/ me rehte
     hain — launcher unhe kabhi touch nahi karta, restart par sab
     kuch waisa hi milta hai.

If the app is already running, the launcher says so and just opens
the dashboard instead of starting a second copy.

Flags:
  --no-browser   start the servers but do not open the browser
  --check        only check the prerequisites, then exit (0 = ok)
  --stop         stop a launcher-started instance (uses the PID file)

No paid tool, no key and no download is bundled here. Everything
runs on localhost only (127.0.0.1) — nothing is exposed to the
network.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

# --- Layout detection -----------------------------------------------------
# launcher.py do jagah ho sakta hai: app/launcher.py (release ZIP) ya
# studio/launcher.py (dev repo). Us se paths nikalte hain.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "app":
    # Release ZIP layout: <install>/app/launcher.py
    APP_DIR = _HERE
    ROOT = APP_DIR.parent
else:
    # Dev layout: <repo>/studio/launcher.py
    APP_DIR = _HERE
    ROOT = APP_DIR.parent
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
LOGS_DIR = APP_DIR / "logs"
PID_FILE = APP_DIR / ".launcher.pid"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
HEALTH_URL = f"{BACKEND_URL}/api/health"
# Package layout me dashboard backend khud serve karta hai (:8000);
# dev layout me (dist na ho) Vite dev server (:5173).
DASHBOARD_URL = BACKEND_URL if (DIST_DIR / "index.html").exists() else FRONTEND_URL

WAIT_TIMEOUT = 90  # seconds to wait for each server to answer


def log(msg: str) -> None:
    print(f"[launcher] {msg}", flush=True)


def _candidate_pythons() -> list:
    """Pythons to try, best first: backend venv, install venv (purana
    — v0.14.0 tak venv install root par banta tha), this one.
    v0.14.1 se naya venv app/backend/.venv me banta hai (top level
    saaf rehta hai: sirf launcher + output/ + app/), lekin purana
    ROOT/.venv abhi bhi candidate hai taake Ali ki pehli install
    ka venv zaya na ho."""
    cands = []
    if os.name == "nt":
        cands += [BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
                  ROOT / ".venv" / "Scripts" / "python.exe"]
    else:
        cands += [BACKEND_DIR / ".venv" / "bin" / "python",
                  ROOT / ".venv" / "bin" / "python"]
    cands.append(Path(sys.executable))
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            cands.append(Path(found))
    out, seen = [], set()
    for c in cands:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _python_has_fastapi(python: Path) -> bool:
    try:
        r = subprocess.run(
            [str(python), "-c", "import fastapi, uvicorn"],
            capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _python_has_playwright(python: Path) -> bool:
    """Playwright = Gemini Canvas provider (free images). Without it
    the app still runs, but Canvas reports 'available: false'."""
    try:
        r = subprocess.run(
            [str(python), "-c", "import playwright"],
            capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _python_has_edge_tts(python: Path) -> bool:
    """edge-tts = VoiceForge samples + free TTS. v0.14.1 se required."""
    try:
        r = subprocess.run(
            [str(python), "-c", "import edge_tts"],
            capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def find_python() -> Path | None:
    """First Python that can run the backend, or None."""
    for cand in _candidate_pythons():
        if cand.exists() and _python_has_fastapi(cand):
            return cand
    return None


def _ffmpeg_found() -> str | None:
    """System ffmpeg, ya Setup se install hua app/bin/ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = APP_DIR / "bin" / "ffmpeg" / (
        "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    )
    if local.exists():
        return str(local)
    return None


def check_prereqs(verbose: bool = True) -> dict:
    """Check everything the app needs. Returns {name: (ok, detail)}.
    Node/npm sirf dev mode me chahiye (dist na ho) — package layout
    me backend prebuilt dashboard serve karta hai."""
    checks = {}
    py = sys.executable
    ver = sys.version_info
    checks["python"] = (
        ver >= (3, 10),
        f"{py} (Python {ver.major}.{ver.minor}.{ver.micro})")
    backend_py = find_python()
    checks["fastapi"] = (
        backend_py is not None,
        str(backend_py) if backend_py else
        "koi Python FastAPI ke saath nahi mila")
    dist_ok = (DIST_DIR / "index.html").exists()
    checks["frontend"] = (
        dist_ok,
        "prebuilt dashboard (dist) maujood hai — Node.js nahi chahiye"
        if dist_ok else "dist nahi hai — dev mode, Vite chahiye")
    if not dist_ok:
        node = shutil.which("node")
        checks["node"] = (node is not None, node or "node nahi mila")
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        checks["npm"] = (npm is not None, npm or "npm nahi mila")
    ffmpeg = _ffmpeg_found()
    checks["ffmpeg"] = (
        ffmpeg is not None,
        ffmpeg or "ffmpeg nahi mila — render/transcribe nahi chalega")
    # Playwright = Gemini Canvas provider (free images). App bina iske
    # bhi chalti hai, is liye sirf WARN — Setup button install kar deta hai.
    pw = _python_has_playwright(backend_py) if backend_py else False
    checks["playwright"] = (
        pw,
        "Canvas (free images) tayyar hai" if pw else
        "Playwright nahi mila — Canvas nahi chalega; Setup button se install karein")
    if verbose:
        for name, (ok, detail) in checks.items():
            mark = "OK  " if ok else ("WARN" if name in ("ffmpeg", "playwright") else "FAIL")
            log(f"{mark} {name}: {detail}")
    return checks


def install_backend_deps(python: Path) -> bool:
    """One-time `pip install -r requirements.txt`. Returns success."""
    req = BACKEND_DIR / "requirements.txt"
    log(f"Backend packages install ho rahe hain ({python} -m pip install) ...")
    try:
        r = subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(req)],
            timeout=600)
        return r.returncode == 0 and _python_has_fastapi(python)
    except Exception as exc:  # noqa: BLE001 - plain message is the point
        log(f"pip install fail: {exc}")
        return False


def ensure_backend_python() -> Path:
    """Return a working backend Python, installing deps once if needed.
    Naya venv app/backend/.venv me banta hai (v0.14.1 — top level
    saaf rehta hai), purana ROOT/.venv abhi bhi use hota hai agar
    maujood ho."""
    found = find_python()
    if found:
        # requirements.txt badal sakti hai (jaise Canvas ke liye
        # Playwright, v0.14.1 me edge-tts) — FastAPI milna kaafi nahi;
        # agar Playwright ya edge-tts missing hai to deps dobara
        # install karo (pehle se maujood packages dobara install
        # nahi hote, sirf missing aate hain).
        if not _python_has_playwright(found) or not _python_has_edge_tts(found):
            log("Playwright ya edge-tts nahi mila — "
                "backend packages dobara install ho rahe hain ...")
            if not install_backend_deps(found):
                log("WARN: pip install fail — app bina Canvas/TTS ke bhi "
                    "chalegi; Setup button se dobara try karein.")
        return found
    # No Python has FastAPI yet — backend ka .venv banao, phir us me
    # requirements install karo.
    venv_dir = BACKEND_DIR / ".venv"
    venv_py = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    if not venv_py.exists():
        log(f"Virtual environment ban raha hai ({venv_dir}) ...")
        try:
            venv.create(venv_dir, with_pip=True)
        except Exception as exc:  # noqa: BLE001
            log(f"venv nahi ban saka: {exc}")
    if venv_py.exists() and install_backend_deps(venv_py):
        return venv_py
    for cand in _candidate_pythons():
        if cand.exists() and install_backend_deps(cand):
            return cand
    log("ERROR: FastAPI install nahi ho saka. Python 3.10+ install karein,")
    log("phir dobara chalain. Ya khud: pip install -r app/backend/requirements.txt")
    sys.exit(1)


def ensure_frontend_deps() -> None:
    """`npm install` once, only when node_modules / the vite bin is missing.
    Sirf dev mode me chalta hai (dist na ho)."""
    vite_js = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if (FRONTEND_DIR / "node_modules").exists() and vite_js.exists():
        return
    npm = "npm.cmd" if os.name == "nt" else "npm"
    log("Frontend packages pehli dafa install ho rahe hain (npm install) ...")
    r = subprocess.run([npm, "install"], cwd=FRONTEND_DIR, timeout=900)
    if r.returncode != 0:
        log("ERROR: npm install fail ho gaya. Node.js 18+ install karein,")
        log("phir dobara chalain.")
        sys.exit(1)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_health(timeout: int = WAIT_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_frontend(timeout: int = WAIT_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(FRONTEND_URL, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _open_browser() -> None:
    try:
        webbrowser.open(DASHBOARD_URL)
    except Exception as exc:  # noqa: BLE001 - browser is a nicety
        log(f"Browser khud nahi khula ({exc}) — khud kholein: {DASHBOARD_URL}")


def _start(cmd: list, cwd: Path, log_name: str) -> subprocess.Popen:
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = open(LOGS_DIR / log_name, "ab")
    kwargs = {"cwd": cwd, "stdout": log_file, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(cmd, **kwargs)


def _stop_proc(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    log(f"{name} band ho raha hai ...")
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        log(f"{name} terminate nahi hua — force stop ...")
        proc.kill()
        proc.wait(timeout=10)


def _write_pid_file(backend_pid: int, frontend_pid: int | None) -> None:
    PID_FILE.write_text(json.dumps(
        {"backend": backend_pid, "frontend": frontend_pid}), encoding="utf-8")


def _read_pid_file() -> dict | None:
    try:
        return json.loads(PID_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def stop_running() -> bool:
    """Stop a launcher-started instance. True if anything was stopped."""
    pids = _read_pid_file()
    stopped = False
    if pids:
        for name in ("frontend", "backend"):
            pid = pids.get(name)
            if not pid:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                stopped = True
                log(f"{name} (pid {pid}) ko stop signal bheja.")
            except ProcessLookupError:
                pass
            except Exception as exc:  # noqa: BLE001
                log(f"{name} stop nahi ho saka: {exc}")
        for _ in range(10):
            if not port_in_use(BACKEND_PORT) and not port_in_use(FRONTEND_PORT):
                break
            time.sleep(1)
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass
    return stopped


def app_already_running() -> bool:
    """True when a healthy backend answers AND the dashboard loads."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            if resp.status != 200:
                return False
    except Exception:
        return False
    try:
        with urllib.request.urlopen(DASHBOARD_URL, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def main(argv: list) -> int:
    if "--check" in argv:
        checks = check_prereqs()
        failed = [n for n, (ok, _) in checks.items()
                  if not ok and n not in ("ffmpeg", "playwright")]
        if failed:
            log(f"Check FAIL: {', '.join(failed)}")
            return 1
        log("Check OK — sab kuch tayyar hai.")
        return 0

    if "--stop" in argv:
        if stop_running():
            log("Launcher instance band ho gaya.")
        else:
            log("Koi launcher instance nahi chal raha tha.")
        return 0

    no_browser = "--no-browser" in argv

    if app_already_running():
        log("App pehle se chal raha hai — dobara start nahi kar raha.")
        log(f"Dashboard: {DASHBOARD_URL}   API: {BACKEND_URL}/api/health")
        if not no_browser:
            _open_browser()
        return 0

    log("Kreafy Creator Studio start ho raha hai ...")
    checks = check_prereqs()
    if not checks["python"][0]:
        log("ERROR: Python 3.10+ chahiye — python.org se install karein.")
        return 1
    dist_ok = checks["frontend"][0]
    if not dist_ok and (not checks["node"][0] or not checks["npm"][0]):
        log("ERROR: Node.js 18+ (npm ke saath) chahiye — nodejs.org se install karein.")
        log("(Sirf dev mode me — release ZIP me prebuilt dashboard hota hai.)")
        return 1
    if not checks["ffmpeg"][0]:
        log("WARN: ffmpeg nahi mila — dashboard khulega, render/transcribe nahi chalega.")
        log("      Dashboard khulne ke baad Settings -> Setup se install karein.")
    if not checks["playwright"][0]:
        log("WARN: Playwright (Chromium) nahi mila — Canvas free images nahi chalengi.")
        log("      Dashboard khulne ke baad Settings -> Setup se install karein.")

    backend_py = ensure_backend_python()
    log(f"Backend Python: {backend_py}")
    if not dist_ok:
        ensure_frontend_deps()

    backend = _start(
        [str(backend_py), "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        BACKEND_DIR, "backend.log")
    log(f"Backend start ho gaya (pid {backend.pid}) — health ka intezar ...")
    if not wait_for_health():
        log("ERROR: backend 90 s me health nahi de saka. Log dekhein:")
        log(f"  {LOGS_DIR / 'backend.log'}")
        _stop_proc(backend, "backend")
        return 1
    log("Backend OK — http://127.0.0.1:8000/api/health")

    frontend = None
    if not dist_ok:
        # Vite ko seedha node se chalao (npm run dev ke through nahi):
        # npm ek sh wrapper banata hai aur uska node child terminate
        # karne par bhi zinda reh jata hai — phir port 5173 band nahi
        # hoti. Seedha vite.js chalane se launcher ka child hi vite
        # hota hai aur Ctrl+C par saaf band hota hai.
        node = shutil.which("node")
        vite_js = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
        frontend = _start(
            [node, str(vite_js), "--host", "127.0.0.1",
             "--port", str(FRONTEND_PORT)],
            FRONTEND_DIR, "frontend.log")
        log(f"Frontend start ho gaya (pid {frontend.pid}) — load ka intezar ...")
        if not wait_for_frontend():
            log("ERROR: frontend 90 s me load nahi hua. Log dekhein:")
            log(f"  {LOGS_DIR / 'frontend.log'}")
            _stop_proc(frontend, "frontend")
            _stop_proc(backend, "backend")
            return 1
        log("Frontend OK.")
    else:
        log("Dashboard prebuilt hai — backend khud serve karta hai (Node.js nahi chahiye).")

    _write_pid_file(backend.pid, frontend.pid if frontend else None)
    log("")
    log(f"Dashboard: {DASHBOARD_URL}")
    log(f"API health: {HEALTH_URL}")
    log("Band karne ke liye Ctrl+C dabayen — servers saaf band honge.")
    if not no_browser:
        _open_browser()

    def _handle_stop(signum, frame):  # noqa: ARG001
        raise KeyboardInterrupt

    old_sigint = signal.signal(signal.SIGINT, _handle_stop)
    try:
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_stop)
    except Exception:
        pass
    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                log("ERROR: backend achanak band ho gaya. Log dekhein:")
                log(f"  {LOGS_DIR / 'backend.log'}")
                if frontend:
                    _stop_proc(frontend, "frontend")
                return 1
            if frontend and frontend.poll() is not None:
                log("ERROR: frontend achanak band ho gaya. Log dekhein:")
                log(f"  {LOGS_DIR / 'frontend.log'}")
                _stop_proc(backend, "backend")
                return 1
    except KeyboardInterrupt:
        log("")
        log("Band ho raha hai ...")
    finally:
        signal.signal(signal.SIGINT, old_sigint)
    if frontend:
        _stop_proc(frontend, "frontend")
    _stop_proc(backend, "backend")
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass
    for _ in range(10):
        if not port_in_use(BACKEND_PORT) and not port_in_use(FRONTEND_PORT):
            break
        time.sleep(1)
    if port_in_use(BACKEND_PORT) or port_in_use(FRONTEND_PORT):
        log("WARN: koi port abhi bhi band nahi hui (8000/5173) — "
            "dobara start karne se pehle check karein.")
    else:
        log("Dono ports khaali hain — app saaf band ho gaya.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
