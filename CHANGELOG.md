# Changelog — Kreafy Creator Studio

## v0.15.0 — Slice 6: Watermark Cleaner (2026-11-22)

Gemini sparkle corner badge remover (Flow / Nano Banana images) — free,
local, no API. Upload images, auto-detect the corner badge, clean it
(reverse-blend + Telea inpaint), manual paint for leftovers, ZIP download.

- **Backend** (`/api/watermark/*`): upload (max 20 files, <= 20 MB each,
  detect on upload), clean (4-at-a-time, per-image clean %), manual
  strokes (painted mask re-clean), job list + get, cleaned images ZIP.
  OpenCV is optional — endpoints return an honest 503 in plain Roman
  Urdu when it is missing; the app still starts without it
  (`opencv-python-headless>=4.8` in requirements.txt, lazy import).
- **Frontend**: new Watermark Cleaner tool — drag & drop + file picker,
  per-image before/after toggle, badge status in plain words, intensity
  slider 0.5–2.0, manual paint canvas on the after image + Re-run,
  Download ZIP, recent jobs. Project-independent: opens without a
  project pick. Dashboard card + sidebar + All Tools menu.
- **Verified**: detection 9/9 synthetic badges, 0 false positives on
  9 badge-free real Flow images, mean clean ~91% (white-box test 0
  failures); end-to-end curl + Playwright UI audit + fresh-unzip boot.

## v0.14.1 — Bugfix release (2026-11-22)

First real Windows PC test (Ali, 2026-11-22) found 4 issues; all fixed
here. Public release will be THIS version, not v0.14.0.

### Fix round 2 — same version (2026-11-22, Ali ki UI verdict)

Ali: "Bkwas UI bana dia, har chez ek e jga" — har page par sab kuch
stack tha, aur cheezein apni sahi jagah par nahi thi. Governing rule:
ek tool = ek kaam; us tool me sirf wohi jo us kaam ke liye required
hai; har cheez apni sahi jagah par ho.

- **Focused tool views**: project view me ab ek waqt par SIRF ek tool
  dikhta hai (tool-switcher chips upar). All Tools sirf clean menu hai
  (11 cards) — koi embedded studio UI nahi. VoiceForge ke andar
  sub-tabs (Generate voice / Voice Library / Transcription / HeyGen
  Clone); StoryCraft ke andar sub-tabs (Script / Niches / Character
  Vault / Research Notes). TTS form CineCut se VoiceForge Generate tab
  me gaya; Script StoryCraft ke Script tab me; Magic Mode Director view
  me; Deliverables Render view me; Timeline / Style+captions / Render
  alag views (timeline na ho to saaf note).
- **Master Prompt Library alag option**: StoryCraft ke top se hata di —
  ab sidebar menu + All Tools card + apna page; "Use in script" lagate
  hi StoryCraft ke Script tab par wapas jata hai.
- **Character Vault cards**: har niche card par uske mains ki thumbnails
  ki row seedha dikhti hai (bina click kiye) + poori cast sheet. Asal
  wajah: cast sheets sirf build VM ke data/ me thi, Ali ke PC par file
  hi nahi thi — is liye card par tasveer kabhi nahi aati thi. 7 cast
  sheets ab app ke saath ship hoti hain
  (`backend/reference/cast-sheets/`), pehli boot par data/ me copy +
  har character ka thumbnail banta hai (sheet order 7 sheets dekh kar
  verify kiya — Portugal/Sarajevo seed order jaisi, baaki 5 me farq hai).
- **Edge-TTS list vs generate mismatch**: list (plain HTTPS GET) kaam
  karti thi, generate (WebSocket synthesis) fail hota tha — UI ek hi
  waqt "reachable — 318 voices" aur 503 bolta tha. Ab EK verdict hai:
  list + chhota synthesis probe; `available` sirf tab True jab probe
  chale (10-min cache). List, Generate aur Preview — teeno ek hi
  message dikhate hain.

### Fixed
- **503 on samples + VoiceForge play (Issue 1+2)**: `edge-tts` was
  deliberately NOT in `requirements.txt`, so a fresh PC never got it —
  VoiceForge "Play sample", TTS generate and `GET /api/tts-voices`
  all 503'd. `edge-tts>=6.1` is now a required dependency; the
  launcher re-installs when it is missing; Setup's `backend_deps`
  step verifies the modules actually import after pip (returncode 0
  alone is not enough).
- **Tools not clickable (Issue 3)**: all 10 tools were live, but only
  CineCut had an Open button — Dashboard cards, sidebar and All Tools
  just went to All Tools, where 8 live tools had no button at all.
  Every tool now opens its real section inside the CineCut project
  view (pick a project → auto-scroll to the tool's section); All
  Tools has an Open button on EVERY live tool card.
- **AQ. Gemini keys (Issue C/D)**: since 28 May 2026 Google AI Studio
  issues `AQ.` auth keys; the app sent the key as `?key=` in the URL,
  which Google rejects with 400 API_KEY_INVALID for AQ. keys (verified
  live: same key via `x-goog-api-key` header → 200). All 6 Gemini call
  sites now send the `x-goog-api-key` header. No prefix/length
  validation anywhere — `AQ.` and `AIza` both accepted.
- **Key masking + friendly errors (Issue C)**: keys now show only the
  last 4 characters everywhere (was first-4 + dots in some places);
  invalid Gemini key test returns "Key ghalat hai — Google AI Studio
  se nayi key lein" + aistudio.google.com link instead of raw JSON.
- **Setup ran but ffmpeg + Chromium still missing (Issue E1)**: the
  frontend poll loop capped at 200 × 3 s (10 min) — long downloads
  outlasted it; a backend restart lost the in-memory run (poll 404);
  failure details vanished on refresh. Polling now runs until
  done/failed (generous cap), tolerates poll errors via the disk
  record, shows elapsed time + current step, renders the last run's
  steps after refresh, and each failed step has its own Retry button.
- **API Keys UI restructure (Issue E2)**: the ~20-row raw "Keys &
  engines" dump + separate Gemini rotation + separate Free keys table
  are replaced by ONE grouped "API Keys" section (AI Text / Images /
  Voice / Stock) — friendly name, FREE/TRIAL/PAID badge, set/not-set
  status, masked last-4 preview, Test + Delete, one Add flow; Gemini
  rotation lives inside the AI Text group. The legacy `gemini_api_key`
  setting is cleared on migration so the key appears exactly once.
  Non-key settings moved under an "Advanced" collapsible.
- **One-click updates via Drive (Spec A)**: the updater now supports
  a configurable source — GitHub Releases OR the Google Drive mirror
  ZIP (default fileId `1lpAUWGaQfSQJCxlRkCCyVDrpuP403AVT`); the
  Settings Update section has a source selector, and the "Update
  available" badge works with the Drive source too. One download
  does check + apply. v0.14.1 can reach Ali's CURRENT install
  one-click via the Drive source — no public GitHub Release needed.
- **.venv location (EXTRA)**: new venvs are created at
  `app/backend/.venv` (packaged) / `studio/backend/.venv` (dev) so
  the install root stays clean (only launcher + output/); the old
  root `.venv` is still accepted as a fallback.
- **Frontend request timeout**: `request()` had no timeout — a hung
  endpoint could freeze a page on "Loading…" forever. Now 120 s
  with a plain Roman Urdu timeout message.

### Not verified
- Real Windows first run (Start bat, Setup, desktop shortcut) — this
  VM is Linux. Live Canvas/Flow generation (Ali's Google sign-in on
  his PC). Real public-release update round-trip (no public repo /
  Release yet).

## v0.14.0 — Release Packaging (2026-11-22)

Student release: clean ZIP, one-click launcher, date-wise output,
public GitHub Releases updater, first-run Setup, per-user free keys,
and "My Main Character" (user-uploaded character sheet).

### Added
- **Release ZIP layout**: top level is only `Start Kreafy Studio.bat`
  + `README.md` + `output/`; everything else lives in `app/`
  (backend, frontend, scripts, data, VERSION, CHANGELOG.md).
- **Date-wise output**: all final videos (renders, clip finals,
  thumbnails) go to `output/YYYY-MM-DD/<project>_YYYY-MM-DD_HHMM.mp4`.
  Old renders under `studio/data/renders/` still open (fallback read)
  and migrate into today's output folder on access.
- **In-app Check for Update** (`GET /api/update/check`,
  `POST /api/update/apply`): public GitHub Releases API, no login,
  no auth. Compares the release tag with local VERSION, downloads
  the release ZIP asset, applies it via `scripts/update.py`
  (backup → replace code → verify → rollback on failure). Update
  never touches `output/`, the database, settings, or Canvas
  profiles. "Update available" badge on app startup. Update source
  (owner/repo) is configurable in Settings; default is
  `nazakataleofficial-coder/kreafy-creator-studio`.
- **First-run Setup** (`GET/POST /api/setup/*`): pip backend deps,
  Playwright Chromium, FFmpeg (Windows auto-download), each step
  verified with a green tick; "Ready" only when required steps pass.
  Desktop-shortcut button (Windows) creates a Desktop shortcut.
  `start-studio.bat` only does a light check and points at Setup.
- **Free keys** (`GET /api/free-keys`, `POST /api/free-keys/{provider}/test`,
  `POST /api/pollinations/test`): every key row shows a FREE / TRIAL /
  PAID badge and a get-key link. New key slots: OpenRouter, Hugging
  Face, ElevenLabs. OpenRouter free model is the script fallback when
  no Gemini key is set. Pollinations needs no key at all (live test
  image). The app works with zero keys — a feature that needs a key
  says so honestly instead of failing silently.
- **My Main Character** (`POST /api/vault/my-character`,
  `GET /api/vault/main`, set-main / unset-main): upload your own
  character sheet (image + name + paragraph description + niche),
  approve → lock → "Set as my main character". The locked main
  character is used in EVERY scene of every Magic/bulk run: its full
  description is injected verbatim into every image prompt and its
  sheet rides along as the reference image (Char Reference method).
  Built-in 70 characters stay untouched as the shipped library;
  user characters are a separate "my characters" set, stored only
  in local `data/` — never in the ZIP, repo, or update.
- **Output management** (`GET /api/output/info`, `POST /api/output/open`,
  `POST /api/output/clean`): output path, folder size, open-in-explorer,
  clean renders older than 30 days (confirm first).
- **Version footer**: app version shown in the footer; changelog
  available in Settings after an update.
- **HeyGen scrub**: no personal clone voice_id or name is seeded
  anymore — every user adds their own HeyGen key + clone voice_id
  in Settings. Existing installs keep their saved voice_id in the
  local database.
- `scripts/package_zip.py`: repeatable release-ZIP builder. Verifies
  the built ZIP for key patterns (AIza, sk-, the old voice_id) and
  FAILS the build on any match; `*.db`/`*.sqlite`, `.venv`,
  `node_modules`, `data/` are always excluded.

### Changed
- Backend serves the prebuilt frontend (`frontend/dist`) at :8000 —
  Node.js is NOT needed to run the release, only to rebuild the
  frontend from source.
- Launcher is layout-aware (package `app/` vs dev `studio/`), creates
  `ROOT/.venv` when no Python has FastAPI yet, and skips Vite when
  `dist` exists.

### Not verified (needs a real PC)
- Live Canvas/Flow image generation (needs the user's Google sign-in).
- Windows first run (Start bat, Setup, desktop shortcut).
- Real public-release update round-trip (needs the public repo +
  Release v0.14.0 to exist first).
