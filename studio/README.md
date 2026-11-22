# Kreafy Creator Studio — v0.14.0 (Release Packaging)

Localhost-only video production studio. Phase 1 is the foundation:
a working dashboard, projects, asset records, jobs, settings, and the
Style DNA library (Option A seed). Phase 2 slice 1 adds the first real
feature: the CineCut sync timeline — upload a voiceover and images,
auto-sync them on a timeline, edit clips and captions, export SRT and
render a real MP4 with FFmpeg. Slices 1–5 + Release Packaging built
(see `docs/PROJECT_STATE.md`).

## Run it — students / fresh PC (ZIP release)

Unzip `Kreafy-Creator-Studio-v0.14.0.zip`, then double-click
**`Start Kreafy Studio.bat`** (top level — click karne wali EK cheez).
Structure inside the ZIP:

```
Kreafy-Creator-Studio/
├── Start Kreafy Studio.bat   (launcher)
├── README.md                 (student one-pager, Roman Urdu + English)
├── output/                   (final videos, date-wise: YYYY-MM-DD/)
└── app/                      (backend/, frontend/, scripts/, data/,
                               launcher.py, VERSION, CHANGELOG.md)
```

Prerequisite (sirf ek dafa): **Python 3.11+** from python.org with
"Add Python to PATH" ticked. **Node.js is NOT needed to run the app**
— the frontend ships prebuilt (`frontend/dist`); Node is only needed
to rebuild the frontend from source (`npm install && npm run build`).
First run: Dashboard/Settings me **Setup — Install Requirements**
button pip deps + Playwright Chromium + FFmpeg install/verify karta
hai (green ticks, "Ready" state); Desktop shortcut bhi wahin se banta
hai (Windows only). Updates: Settings → **Check for Update** (public
GitHub Releases, no login; default repo
`nazakataleofficial-coder/kreafy-creator-studio` — Release v0.14.0
banna baaki hai, tab tak update-check honestly "koi public Release
nahi" batata hai). Output videos `output/YYYY-MM-DD/` me jate hain;
update output/, database, settings ya canvas-profile ko kabhi touch
nahi karta. Keys (Gemini, Groq, ...) har user apni khud ki dalta hai —
Settings → Free keys (FREE / TRIAL / PAID badge + get-key link);
app zero keys ke saath bhi kaam karta hai.

## Run it locally (dev, from the repo)

You need Python 3.10+ on your PC (Node.js 18+ only to rebuild the
frontend). FFmpeg must be installed for rendering.

### 1. Backend (FastAPI + SQLite)

```powershell
cd studio/backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The API listens on http://127.0.0.1:8000 only — never on your network.
Check it: http://127.0.0.1:8000/api/health

The SQLite database is created at `studio/backend/studio.db` on first
start. It is gitignored and stays on your PC.

### 2. Frontend (Vite + React + TypeScript)

```powershell
cd studio/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — sidebar has exactly 6 pages: Dashboard,
Projects, All Tools, Media Library, Templates, Settings.

## What Phase 2 slice 1 (CineCut) includes

- **Uploads**: voiceover file (mp3/wav/m4a) and multiple images
  (png/jpg/webp) per project, stored under `studio/data/` (gitignored).
- **Auto-sync**: images spread across the voiceover duration (3 s per
  image when there is no voiceover). Slice 2 makes this script-beat by
  default: pass per-scene texts and clip lengths follow word counts;
  equal split remains only as a fallback. Clip start/end and
  captions are editable; clips can be reordered (a real swap — times
  are re-laid end to end).
- **Style DNA + caption styles**: apply a locked style and a caption
  style to a timeline (from the Phase 1 seed data, incl. Urdu styles).
  Slice 2 adds 4 ClipNova styles (Minimal, Cinema Subtitle, Hormozi
  Green, Beast Pop) — 8 caption styles total — and the render really
  draws the chosen one.
- **SRT export**: real SRT from clip captions and timings
  (`GET /api/timelines/{id}/srt`).
- **Render**: FFmpeg concat of the images at clip durations +
  voiceover audio → MP4 1920×1080, 30 fps, under
  `output/YYYY-MM-DD/<project>_YYYY-MM-DD_HHMM.mp4` (install root;
  purane `studio/data/renders/` paths fallback read se khulte hain
  aur access par migrate hote hain).
  Slice 2 render: Ken Burns slow zoom (alternating in/out), 0.5 s
  crossfades between clips, captions burned in with the chosen caption
  style. Job status is polled via `GET /api/jobs/{id}`.
- **Free TTS (best-effort)**: `POST /api/projects/{id}/tts` tries
  Edge-TTS (Microsoft voices, no key; install with `pip install
  edge-tts`). It is blocked on some networks — when it fails the
  endpoint returns HTTP 503 with a plain message and nothing breaks;
  uploading a voiceover file is the reliable path.
  `GET /api/tts-voices` returns the real live voice list when Edge-TTS
  is reachable, else `available: false` and a curated library of 20
  real Microsoft voice IDs (en-US / en-GB / hi-IN / ur-PK) marked
  unverified here. `POST /api/tts-voices/{id}/preview` generates a
  short sample (cached under `studio/data/tts-previews/`, honest 503
  where Edge-TTS is blocked). The saved default voice
  (`default_tts_voice` setting) is used by the TTS endpoint and
  one-click runs when no voice is given; the CineCut "VoiceForge —
  Voice Library" section lists the voices with a filter, Play sample
  and Set as default.
- **Local Whisper status**: `GET /api/whisper-status` checks (never
  downloads) whether faster-whisper is installed and which models are
  already cached, and probes the real transcription path — it reports
  `transcribe_ready` honestly. Transcription itself is live since
  Phase 5 slice 2 (below).
- **Local Whisper transcription (Phase 5 slice 2)**: `POST /api/transcribe`
  (audio/video upload, cached model only — never a download) runs a
  background `transcribe` job; `GET /api/transcriptions/{id}` returns
  the full text + word timestamps; `.../srt` and `.../vtt` export
  subtitles; `POST /api/transcriptions/{id}/use-as-script` turns a
  transcript into a project script. The PyAV bug that blocked this
  (faster-whisper 1.2.1 vs PyAV 19.0.2) is fixed by decoding with ffmpeg
  instead of faster-whisper's broken `decode_audio`. Verified live on
  the 45.71 s Eiffel VO: 143 words, timestamps real, 96/98 unique words
  matching the known script. CineCut has a "VoiceForge — Transcription"
  section (file upload, cached-model picker, transcript + word chips,
  SRT/VTT download, Use as script).
- **HeyGen clone voice (Phase 5 slice 3)**: `POST /api/projects/{id}/heygen/speak`
  (text max 5000 chars, language en/hi) runs a background `heygen-voice`
  job against HeyGen `POST /v3/models/audio/tts` (X-Api-Key, body
  {model heygen-voice-1-turbo, voice_id, text, language,
  expressivenessBoost 1.0}) with the user's own key from Settings
  (`heygen_api_key`, masked; `heygen_voice_id` seeded to Ale's clone
  "Nazakat Ale"). The audio is downloaded and saved as a VO asset;
  for Urdu/Hindi the 106 Hz pitch lock applies (ffmpeg rubberband
  x1.0495, tempo 1.0) — English is never pitch-shifted. No key means the
  job fails honestly with the key message and nothing is saved.
  HeyGen is NOT a free-tier default (Turbo is paid; Turbo Free is free
  until 30 Nov 2026) and every generation needs Ale's say-so. The exact
  request payload is logged to `studio/data/heygen-speech-request-sample.json`
  (no key in it). **No live HeyGen call was made in the build VM** —
  the live voice test waits for Ale. CineCut has a "VoiceForge — HeyGen
  clone" section (text, language picker, Generate disabled without a key,
  permission + free notes, finished VOs with audio player + pitch badge).
- **ClipForge long video (Phase 6 slice 1)**: `POST /api/projects/{id}/source-videos`
  (mp4/mov/webm, max 2 GB streamed to disk) runs a background
  `source-video` job: the same local Whisper worker as `POST /api/transcribe`
  (cached models only, never a download) transcribes the video's audio
  with word timestamps; `GET /api/projects/{id}/source-videos` lists them
  and `GET /api/source-videos/{id}` returns the full transcript. Verified
  live on the 63.57 s Turkey fraud video: 167 words, timestamps valid.
  CineCut has a "ClipForge — Long video" section (upload, model picker,
  video player, transcript + word chips, SRT/VTT download).
- **ClipForge moment detection (Phase 6 slice 2)**: `POST /api/source-videos/{id}/detect-moments`
  (201) scores 15–60 s candidate windows built from consecutive Whisper
  segments, using only the real word timestamps — density (words per
  second, reference 3.0), keywords (hook words: questions, numbers,
  emotion words, English + Roman Urdu), silence (real pauses around the
  window), length (1.0 for 20–45 s); weights 0.35 / 0.30 / 0.20 / 0.15;
  non-maximum suppression keeps at most 5 non-overlapping moments;
  re-running replaces the old moments. No transcription yet → plain 400,
  no fake moments. `GET /api/source-videos/{id}/moments` lists them.
  Audio energy is deliberately NOT scored — it is not measured, so it is
  not invented. Verified live on the Turkey video: 2 moments (4.46–32.62 s,
  score 1.0, 87 words; 33.38–63.36 s, score 0.9, 66 words); both
  boundaries spot-checked against the real word timestamps; failure path
  (400) verified. CineCut shows a "Find moments" button, score badges,
  the score breakdown, and Preview (seeks the video player to the moment).
- **ClipForge 9:16 reframe + captions (Phase 6 slice 3)**: `POST /api/moments/{id}/reframe`
  (202, body `{caption_style}` — one of the 8 renderable styles, default
  "Bold White") cuts the moment's range from the source video, centre-crops
  to 9:16 (centre crop first; face tracking comes later and is never
  claimed), scales to 1080x1920, and burns the moment's real Whisper
  segments in as timed captions in the chosen style (fontsize ~1.3x for
  the narrower frame). Output is a `clip-preview` asset under
  `studio/data/clip-previews/` with its own `clip-reframe` job row
  (queued → running → done/failed); `GET /api/moments/{id}/reframes` lists
  them, `GET /api/reframes/{id}` returns one. Missing source file → plain
  400 at queue time, no fake clip; unknown style → 400; unknown moment →
  404. Verified live on Turkey moment 1 (4.46–32.62 s): 1080x1920,
  28.167 s, H.264+AAC, no black segments; 6 frame checks — every burned
  caption is the line actually spoken at that time (Bold White); a second
  style (Karaoke Yellow) renders yellow correctly. CineCut moment cards
  gain a caption-style picker + "9:16 preview" button, a portrait player
  (270px wide) and a Download link, with 2-second polling while rendering.
- **ClipForge approval gating + final render (Phase 6 slice 4 — Phase 6 complete)**: moments carry an `approval` column (`pending` / `approved` / `rejected`, default `pending`); `POST /api/moments/{id}/approve`, `POST /api/moments/{id}/reject`, `GET /api/source-videos/{id}/approved-moments`. `POST /api/moments/{id}/render` (202, optional `{caption_style}` — empty means the latest done reframe's style, else "Bold White") renders the moment's 9:16 reframe as a FINAL clip: same shared `_render_vertical_9x16` pipeline as slice 3 (centre crop, 1080x1920, burned captions from the real Whisper segments with absolute source times, H.264+AAC), output is a `clip-final` asset under `studio/data/clip-finals/` with its own `clip-final` job row. An unapproved moment → plain 400 "pehle approve karein — bina approval ke final clip nahi banta", no clip produced. One final clip per moment: re-render reuses the row and replaces the file only after the new render succeeds (old file deleted after success). Per final clip: `GET /api/moments/{id}/final-clips`, `GET /api/source-videos/{id}/final-clips`, `GET /api/final-clips/{id}`, `GET /api/final-clips/{id}/srt` (the moment's Whisper segments clipped to the window, shifted to clip-relative times, as a downloadable .srt), `PATCH /api/final-clips/{id}` (rename; empty title → 400), `DELETE /api/final-clips/{id}` (file + asset row + clip row gone; the moment stays approved). Re-running detect-moments deletes the old moments' reframes + final clips (rows, assets, files, caption dirs, error logs) — the clip row is deleted before its asset row, because the row still references the asset (foreign key). Verified live on the Turkey video: moment 1 approved, moment 2 left pending; render of moment 2 → 400, no clip; render of moment 1 → exactly 1 final clip, 1080x1920, 28.167 s, no black segments, 2 frame checks (captions are the lines actually spoken at those times), SRT 8 segments clip-relative 0.000–28.160; rename shows the new title; delete removes file + row and the moment stays approved; re-render reuses the row and swaps the file only after success. CineCut moment cards gain an approval badge + Approve / Reject buttons + a "Render final clip" button (approved only), and an "Approved clips — final 9:16" section lists final clips with a portrait player, Download final clip, Download SRT, Rename and Delete. Health phase is `6-clipforge-slice4`. No 7th page. Phase 6 is COMPLETE.
- **Sentence-level visuals (2026-11-21)**: scripts split into one
  scene per sentence (abbreviation-safe; long sentences chunked) —
  `POST /api/scripts/{id}/resplit-sentences` re-splits an existing
  script. One-click runs and auto-sync build one clip per sentence:
  each clip stores its own Ken Burns effect (zoom-in / zoom-out /
  pan-left / pan-right, rotating so neighbours never match), 0.5 s
  crossfades between clips, burned captions follow the sentence text,
  minimum 2 s per clip. When images are fewer than sentences the
  project's images cycle (`i mod n`) with a different effect each
  time; placeholders appear only when the project has zero images, and
  reused images are flagged `asset_reused` in the timeline. CineCut
  clip cards show the effect badge + "Reused image" note. Verified
  live on the Eiffel script: 7 scenes → 14 sentence scenes → 14 clips,
  0 placeholders, 7 reused, 45.714 s, no black segments.
- **Preview**: the CineCut page plays the voiceover while showing the
  image of the clip at the current time.

## What Phase 2 does NOT include

- No word-level captions, no Kokoro, no
  paid APIs except HeyGen (Phase 5 slice 3, key + Ale's say-so only).
  Word-by-word karaoke highlighting needs transcription first (Phase 5)
  — "Karaoke Yellow" renders as static yellow bold text until then.
  (Transcription itself is live since Phase 5 slice 2 — see above;
  HeyGen clone voice is live since Phase 5 slice 3 — see above.)
- ClipForge (Phase 6), StickMan + StoryCraft (Phase 7 slice 1),
  Motion Studio + Asset Vault + Render Studio polish (Phase 7
  slice 2), Hardening (Phase 7 slice 3) and Distribution (Phase 7
  slice 4 — one-click launcher + safe updates) are live — see below.
  Phase 7 is complete.

## Phase 2 slice 2 — script-beat sync + character + Ken Burns + burned-in captions (2026-11-20, test repo only)

Built and verified 2026-11-20 (see `docs/PROJECT_STATE.md`):
script-beat auto-sync (clip lengths follow scene word counts, equal
split only as fallback), main-character upload per project (name +
reference image, timeline responses carry `character_name`), Ken Burns
zoom + 0.5 s crossfades + burned-in captions in the render (caption
styles really applied: Bold White, Karaoke Yellow, Minimal, Cinema
Subtitle, Hormozi Green, Beast Pop, Urdu Modern Sans, Urdu
Nastaliq-style — each drawn by ffmpeg drawtext), free Edge-TTS voice
list + local Whisper availability check (both honest about this PC),
free-tier limits visible on the Settings page.
Verified with a real render: the Eiffel Tower test video v2 —
45.71 s voiceover + 6 scenes → 45.714 s MP4 1920×1080, beat timings
match word counts, visible zoom movement, captions visible, no black
segments. Saved as `eiffel-tower-test-video-v2.mp4`.

## What Phase 1 includes

- **Backend** (`studio/backend/`): FastAPI on 127.0.0.1:8000.
  SQLite tables: projects, assets, jobs, settings, style_dna,
  caption_styles, timelines, clips. Endpoints: `/api/health`,
  `/api/projects`, `/api/assets`, `/api/jobs`, `/api/settings`,
  `/api/style-dna`, `/api/caption-styles`, plus Phase 2:
  `/api/projects/{id}/upload-voice`, `/api/projects/{id}/upload-images`,
  `/api/projects/{id}/tts`, `/api/projects/{id}/timeline/auto-sync`,
  `/api/timelines/{id}`, `/api/timelines/{id}/clips/{clip_id}`,
  `/api/timelines/{id}/apply-style`, `/api/timelines/{id}/srt`,
  `/api/timelines/{id}/render`. Uploaded files are served for preview
  at `/files/` (localhost only). Slice 2 adds:
  `/api/projects/{id}/character` (POST upload + GET),
  `/api/tts-voices` (live Edge-TTS voice list, or the curated
  20-voice library when blocked) + `/api/tts-voices/{id}/preview`
  (cached sample, honest 503 where blocked),
  `/api/whisper-status` (local Whisper check, never downloads).
  Auto-sync accepts scene texts (`captions`, `mode`) for script-beat
  timing; clip reorder is a real swap with times re-laid end to end.
- **Frontend** (`studio/frontend/`): dark premium design
  (background #0F0F0F, gold accent #C8A96B), 6 pages, real data
  from the API — no fake figures.
- **Style DNA library** (Templates page): 5 styles seeded from the
  inspiration-video review — Studio Ghibli-inspired hand-drawn,
  Claymation / Stop-motion, Cyberpunk Neon, Sticky Figure,
  Retro Space Collage — each with a master-prompt template.
- **Urdu caption styles** (Templates page): Urdu Modern Sans,
  Urdu Nastaliq-style, plus Bold White and Karaoke Yellow.
- **Free-first settings**: transcription defaults to local Whisper;
  a Groq key is never required; Gemini free tier is shown as
  20 requests per model per day. API keys are stored locally only
  and are never displayed back in full.

## What Phase 1 does NOT include

- No transcription, no caption generation, no rendering, no video
  export (FFmpeg is only checked, not used to render yet).
- No Whisper model download, no paid API calls, no uploads yet
  (assets record a local file path only).
- No installer bundled yet — see "Phase 7 slice 4 — Distribution"
  below for the one-click launcher (it still needs Python 3.10+ and
  Node.js 18+ installed first). This runs on your PC only.

## Phase 2 slice 1 — CineCut sync timeline (2026-11-20, test repo only)

Built and verified 2026-11-20 (see `docs/PROJECT_STATE.md`): upload
voiceover + images, auto-sync timeline, clip/caption editing, Style DNA
apply, SRT export, FFmpeg MP4 render (1920×1080, 30 fps, plain cuts),
best-effort free Edge-TTS (503 when blocked), VO-synced preview.
Verified with a real render: 9.0 s voiceover + 3 images → 9.0 s MP4,
correct frames at 1 s / 4 s / 7 s, no black frames.

## Phase 3 slice 1 — Script + scene breakdown (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`): scripts +
scenes in SQLite; `POST /api/projects/{id}/scripts` (paste/type always
works, no key; topic-only uses the optional Gemini free-tier key from
Settings, and returns a plain 400 without one); scene splitting
(blank-line paragraphs are beats, long paragraphs split ~2 sentences per
scene, scenes over 60 words chunked); template-built image prompts
(Style DNA + main character by name, no AI call); scene edit +
regenerate-prompt; Script section in CineCut (topic, textarea, scene
list with editable text/prompt/duration, "Use scene texts in timeline");
the Dashboard pipeline "Script" stage is now real — done when the
project has a saved script. Verified with the Eiffel Tower script
(144 words → 7 scenes, prompts carry Ghibli style + Victor Lustig) and
a live dashboard screenshot (Script · Done, 6 of 6 stages, 100%).

## Phase 3 slice 2 — One-click run (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`): `runs`
table + per-step jobs (`run_id` link); `POST /api/projects/{id}/run`
(script → voice → images → timeline → captions → render), `GET
/api/runs/{id}`, `GET /api/projects/{id}/runs`; uploaded voiceover or
free Edge-TTS (fails honestly where blocked — no fake audio); scenes
without images get real placeholder title cards (flagged
`placeholder=1`, "Placeholder - real image needed"); timeline keeps
Style DNA / caption style / character; SRT file per run + MP4 render
(the render step job IS the render job). "One-click video" section in
CineCut (voice source, caption style, Start Video, six-step progress,
MP4 + SRT downloads) and "Placeholder — real image needed" badges on
timeline clips. Verified with the Eiffel Tower project: all 6 steps
done, 45.714 s MP4, 7 clips, clip 7 placeholder, captions burned in,
no black segments; failure paths verified (no voice, Edge-TTS
blocked); full UI run done from the browser. Two bugs found and fixed
while testing: run↔timeline foreign key on timeline replacement, and
the placeholder footer overlapping burned-in captions. Deliverable:
`~/workspace/your_files/eiffel-tower-one-click-run.mp4`.

## Phase 3 slice 3 — Per-scene regenerate + deliverables (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`) — Phase 3
is now complete. `POST /api/timelines/{id}/clips/{id}/replace-image`
swaps one clip's image (flagged `image_replaced=1`, everything else
untouched) and `POST /api/timelines/{id}/rerender` re-renders the same
timeline; the old MP4 is never deleted — the new render is a new
timestamped file. Deliverables: `GET /api/projects/{id}/deliverables`
(current MP4 + latest thumbnail + saved YouTube metadata);
`POST /api/projects/{id}/thumbnail` pulls a real 1280x720 frame from
the rendered MP4 (default: middle of the first clip; `timestamp_s`
for any other moment; 400 when no video exists yet);
`POST /api/projects/{id}/metadata/generate` drafts title /
description / tags from the real script (template only, no AI, no
key), `PUT /api/projects/{id}/metadata` saves hand edits. CineCut
clip cards have "Replace image" + "Image replaced" badges, the Render
section has a Re-render button, and a new "5. Deliverables" section
shows the MP4 download, thumbnail preview + regenerate, and the
YouTube metadata form with Save + Copy buttons. Verified with the
Eiffel Tower project: clip 7 placeholder → real Lustig image,
re-render job 47 done (45.714 s, old MP4 untouched), frame at 42 s
shows Lustig + burned caption, thumbnail is the real frame at
2.381 s (1280x720), metadata generated from the script and edit
round-trip persists; failure paths verified. Deliverable:
`~/workspace/your_files/eiffel-tower-rerendered-scene7.mp4`.

## Phase 4 slice 1 — VisualForge prompt list (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`):
`GET /api/scripts/{id}/prompts` and `GET /api/projects/{id}/prompts`
return every scene's image prompt with the Style DNA + main character
it was built from, each marked `status: "pending"` until slice 2
generates the image, plus an honest Gemini free-tier quota
(`daily_limit` from Settings, `used_today` counted from real
`image-generate` jobs — 0 so far, `generation_available: false`).
CineCut has a new "VisualForge — Image Prompts" section after the
Script section: quota line, "Export prompts (.txt)" (client-side
download, one numbered prompt per scene), and per-scene cards with the
scene text, an editable prompt textarea (shares the scene drafts with
the Scenes list), Save prompt / Regenerate prompt / Copy buttons.
No key or payment needed; nothing is generated in this slice. The
VisualForge tool card now reads "Phase 4 — prompt list live (image
generation in slice 2)". Verified with the Eiffel Tower script (id 2):
7 prompts, all carrying Ghibli style + Victor Lustig, all pending;
prompt edit persists and regenerate-prompt restores the template;
exported .txt has all 7 numbered prompts; `npm run build` passes and
a live browser screenshot shows the section. Health phase is
`4-visualforge-slice1`.

## Phase 4 slice 2 — VisualForge bulk generate + queue (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`):
`POST /api/scripts/{id}/generate-images` queues one `image-generate`
job per scene (jobs table, `kind='image-generate'`, linked by
`scene_id`); `GET /api/scripts/{id}/generation-status` returns the
per-scene status (queued / running / done / failed + error text +
generated image path) and the real quota. The daily limit is enforced
twice: at queue time the quota is *reserved* (done + running +
queued today vs `gemini_free_limit_per_day`, 20) — scenes past the
limit are created as failed jobs with "aaj ki free images khatam —
kal dobara" and never run; at run time each job re-checks before
calling Gemini. A missing Gemini key is not rejected at queue time:
jobs fail honestly on their turn with "Gemini key Settings me
lagayen — bina key ke image nahi ban sakti". With a key set, the
worker calls `gemini-2.0-flash-preview-image-generation` via REST
(stdlib urllib, same pattern as script generation), sends the scene
prompt plus the main character's reference image as `inlineData`
(16:9 frames), saves the returned image as a project asset under
`studio/data/projects/{id}/`, and marks the job done with the file
path. One worker at a time runs (asyncio lock), jobs processed in
order. The exact request body of the first generation is saved to
`studio/data/gemini-image-request-sample.json` (local, gitignored —
the key is in the URL query, never in this file) so the call is
provably correct even before any key exists. The prompts endpoint now
returns the real per-scene status and `generation_available: true`
only when a key is set. CineCut's VisualForge section has a
"Generate all images" button (disabled with the plain key hint when
no key is set), a daily-quota bar, live per-scene status badges with
error text, generated-image thumbnails, and 2-second polling while
anything is queued or generating. Honest caveat: Google documents
this image model as a paid-tier model (per-image billing), so the
"20/day free" cap is the project's own limit — the first real
generation with a key will prove whether the key's plan allows it;
any provider refusal surfaces as a plain job error, never a fake
image. Real image generation is therefore still unverified in this
VM (no key here). The VisualForge tool card now reads "Phase 4 —
bulk generate live (Gemini, 20/day)". Verified: Eiffel script → 7
jobs queued, all 7 failed with the exact key message, no fake image;
limit test (limit temporarily 1, fresh 2-scene script) → 1 queued +
1 limit-blocked with the exact limit message, limit restored to 20;
request-sample file checked (model, responseModalities TEXT+IMAGE,
16:9, prompt + 311,152-char webp reference inlineData, no key);
`npm run build` passes; live browser screenshot shows the disabled
Generate button, quota bar, and 7 Failed badges with the error.
Health phase is `4-visualforge-slice2`.

## Phase 4 slice 3 — VisualForge image verification + use (2026-11-21, test repo only)

Built and verified overnight (see `docs/PROJECT_STATE.md`).
StickFilm-style mandatory check: a generated image does NOT go into
a timeline until Ale approves it. New tables `scene_images`
(scene → candidate image, source 'generated' or 'uploaded') and
`image_verdicts` (one verdict per image: approved / rejected +
optional reason + decided_at; no verdict means "pending", never
silently approved). Generated images are linked to their scene when
the worker saves them; uploaded images enter the same flow via
`POST /api/scenes/{scene_id}/attach-image`. Endpoints:
`GET /api/scripts/{id}/images` (every scene with its candidate
images + verdicts), `POST /api/images/{id}/approve`,
`POST /api/images/{id}/reject` (optional reason),
`POST /api/images/{id}/regenerate` (re-queues that scene — quota
respected, no double queue, no key → the job fails honestly with
the key message), `POST /api/scripts/{id}/use-approved` (rebuilds
the CineCut timeline from the approved images in scene order;
scenes without one keep the old clip or get a clearly-marked
placeholder title card; the response says plainly which scenes
were filled and which were not — at least one approved image is
required), `GET /api/scripts/{id}/images.zip` (ZIP of the approved
images only, named `scene-01…`, 400 when nothing is approved).
`timeline_detail` now carries `asset_approved` per clip. CineCut's
VisualForge section shows each candidate image with its verdict
badge + Approve / Reject (+ reason) / Regenerate buttons, an
"Attach uploaded image" picker per scene, a "Use approved in
timeline" button, a "Download approved (.zip)" button, and a live
summary ("2 approved · 0 pending · 1 rejected — sirf approved
images timeline me jati hain."); timeline clip cards show a green
"✓ Approved VisualForge image" badge. The VisualForge tool card
now reads "Phase 4 — verification live (approve → use in
timeline)". Verified live with uploaded images as stand-ins (no
Gemini key in this VM, so real generation is still unverified):
fresh project "VF Verify Test", 3-scene script, 3 uploaded images
attached → all pending; approve 2, reject 1 with reason → verdicts
persist on re-GET; regenerate the rejected one → job failed with
the exact key message; use-approved → "2 of 3 scenes filled —
scenes 3 still need an image", timeline clips approved/approved/
placeholder; ZIP contains exactly `scene-01.webp` +
`scene-02.webp`; failure paths verified (approve an unlinked image
→ 400, use-approved with none approved → 400, ZIP with none → 400).
`npm run build` passes; live browser screenshots show the verdict
badges + buttons and the approved badges on the clip cards. Health
phase is `4-visualforge-slice3`. **Phase 4 is now complete.**

## Canvas free image route — VisualForge Gemini Canvas provider (2026-11-21, test repo only)

Built and verified as far as the login gate allows (see
`docs/PROJECT_STATE.md`). Why: the Gemini API image models have a
free-tier limit of 0 on Ale's key (both image models return 429), so
API images need billing — Canvas is the free route, via the Gemini
web app on the user's own Google login + Gemini Pro quota (the same
place the inspiration tools get their "free" images). Own route
against gemini.google.com directly; NOT Mr Hasnain's third-party
Canvas app or any third-party Canvas link.

**First-run steps (Ali's PC):** 1. Start the app with the launcher.
2. In CineCut → VisualForge, pick "Gemini Canvas (free — Gemini Pro
quota)". 3. Click "Canvas login kholein" — a browser window opens;
sign into Google (the Gemini Pro account) and close the window. The
login is saved in the persistent profile
(`studio/data/canvas-profile/`, gitignored) — no password or OTP is
ever asked for by the app, and no credentials are stored anywhere.
4. Click "Generate all images (Canvas — free)". One-time setup
(first time only): `pip install playwright` (the launcher installs
`requirements.txt` for you) and `python -m playwright install
chromium` for the browser binary.

How it works: `POST /api/scripts/{id}/generate-images` takes
`{provider: "api" | "canvas"}` (default "api"); jobs remember their
provider (`jobs.provider`), the API daily quota counts API jobs only,
and regenerate stays on the same provider. `GET
/api/canvas/status` reports Playwright + Chromium + Google login
readiness (cached 60 s). The worker checks the login ONCE per bulk
run — no Google session means every Canvas job is `blocked` (not
failed) with the exact message "Canvas ke liye Google login nahi
hai — VisualForge me 'Canvas login kholein' se ek dafa Google
sign-in karein, phir dobara try karein". A changed Google page fails
with "Canvas page badal gaya — provider update chahiye". Canvas
images save through the same helper as API images, so they enter
the same approve / reject / use-approved flow. Honest caveats:
browser automation is fragile / ToS-grey — if Google changes the
page, the selectors in `studio/backend/canvas_provider.py` need
updating; the LIVE generation is unverified in the build VM
(gemini.google.com is proxy-blocked there and no Google login
exists) — the first real generation happens on Ali's PC after his
one-time sign-in. Health phase is `canvas-visualforge`. Version
0.9.0.

## Connect Google + Google Flow — VisualForge second free provider (2026-11-21, test repo only)

Built and verified as far as the login gate allows (see
`docs/PROJECT_STATE.md`). One Google sign-in now opens both free
providers: **Settings → "Connect Google (Canvas + Flow)"** signs
the shared browser profile (`studio/data/canvas-profile/`,
gitignored) into Google once — the same login serves Gemini Canvas
(gemini.google.com) and Google Flow (flow.google.com), no second
sign-in. `POST /api/google/disconnect` signs out again (deletes the
profile contents). **Google Flow** is the second bulk image route:
its image engine is Imagen, free under the same Gemini Pro quota;
pick "Google Flow (free — Gemini Pro quota, Imagen)" in VisualForge.
If Flow fails on a scene, the worker retries that scene once on
Canvas, on the same job (the job then records provider `canvas`).
Canvas stays the default free provider. A missing Google login
blocks Flow jobs with "Flow ke liye Google login nahi hai —
Settings me 'Connect Google' se ek dafa Google sign-in karein, phir
dobara try karein". Flow's video generation (Veo) is NOT included —
still images only. The Gemini key Test in Settings now checks the
script model with a tiny `gemini-3.5-flash:generateContent` call
(one-word reply) instead of list-models. First-run steps (Ali's
PC): 1. "Connect Google" — sign in, close the browser. 2. In
VisualForge pick Canvas or Flow. 3. "Generate all images". Honest
caveats: Flow's live page was never probed from the build VM
(flow.google.com is unreachable there and no Google login exists) —
its selectors are best-effort and the Canvas fallback exists for
exactly that; the first real Flow generation happens on Ali's PC
after his one-time sign-in.

## StoryCraft Deep Research + Thinking Levels (2026-11-21, test repo only)

StoryCraft gains a **Deep Research** step — script se pehle topic ki
tehqeeq: topic likhein, Gemini (free tier, `gemini-3.5-flash`) 4-6 key
facts + sources jama karta hai, phir unhi facts se script banti hai
(research note me facts + sources dikhte hain, edit bhi ho sakte
hain). Script generation me **Thinking Level** (Low — tez draft
~80-100 words, Medium — balanced ~140-160, High — gehri script
~200-260) aur **Model** picker (Fast `gemini-3.5-flash`, Deep
`gemini-3.8-flash`, Code `gemini-3.6-flash` — structured, precise)
— dono Script section aur research notes se script likhwane par
lagte hain; pasted text par nahi. Bad level/model → saaf 400, key
nahi → saaf 400, koi fake script nahi. Honest caveat: is VM ke app
DB me koi Gemini key nahi hai, is liye app ke andar live generation
Ali ke PC par key lagane ke baad hogi (Settings me key paste karein,
phir ek Deep Research + ek script chalakar dekhein). Health phase is
`storycraft-deep-research`. Version 0.11.0.

## Magic Mode — One-Click Autopilot v2 (2026-11-21, test repo only)

Magic Mode is one button in the CineCut project view (before the
One-click section): topic + script likhein, voice character
chunein — baaki sab software kare. Script khali ho to Deep Research
se script khud banega. Voice: uploaded voiceover, Edge-TTS library,
ya HeyGen clone (quota/key na ho to band dikhta hai, fake option
nahi). Caption style (default Bold White), aspect 16:9 / 9:16 / 1:1
(default 16:9 — images, timeline aur render teeno badalte hain),
Style DNA preset (default last used), language English / Roman Urdu
(default English). Length script se niklegi (lafz ÷ ~150/minute) —
koi length select nahi hai. Ek progress bar (Script → Images →
Voice → Timeline → Captions → Render) + aakhir me summary (kitni
images bani / ruki hui / fail, placeholders, duration, MP4 +
thumbnail). Voice fail ho to run fail (saaf Roman Urdu error);
images fail/block ho to placeholder cards se video banegi aur
summary me likha hoga. Fail image par Retry Ladder khud chalta hai:
pehle prompt check (policy lafz pehle hi badal do), phir reword,
phir simple close-up scene, phir padosi shot ki image alag crop se
("fallback used") — kabhi skip nahi, kabhi gap nahi, sab automatic.
Consistency khud hoti hai: locked character
description + naam har prompt me, Style DNA block, "do not change
face, beard, clothes or style", character sheet reference image, aur
scene rule (zyada se zyada 2-3 mains, background simple/generic).
Honest caveat: live Canvas/Flow images aur HeyGen voice is VM me
verify nahi ho sake (Google login + quota Ali ke PC par) — images
block hui to summary me saaf likha hoga. Health phase is
`retry-ladder`. Version 0.13.1.

## Flow provider hardening (Slice 5, 2026-11-22, test repo only)

VisualForge ka Flow provider ab sakht hai (see
`docs/PROJECT_STATE.md`): **Fast mode** 1–4 ek saath (asal speed =
min(setting, usable accounts) — 1 account ho to sequential, UI me
saaf likha hai); **3 accounts tak rotation** (har account apni
Google profile, quota/limit par 15 min rest + agle account par,
429 par backoff — kabhi retry storm nahi; koi password/token store
nahi); **"Unusual Activity"** pehchana jata hai aur job 'blocked'
hoti hai — silent Canvas fallback nahi — in-app 1-minute guided
recovery (Flow ki site data clear → reload → queue resume, "Recover
karein" button se khud hota hai); **queue history + ZIP
re-download** (har batch save hota hai, pause/resume karta hai);
**ready indicator** (green + project ID fragment); **`#name` /
`@name` chaining** (Vault ke locked characters — `#Captain`
define karein, `@Captain` se har scene me wahi character, preview
button se pehle dekh lein). UI: VisualForge ke Flow block me sab
kuch (7th page nahi). Honest caveat: live Flow generation, live
Unusual Activity, live multi-account sign-in aur live queue ZIP is
VM me verify nahi ho sake (Google login Ali ke PC par) — pehli live
generation Fast mode 2 se, accounts 2–3 par sign-in, aur ek asli
recovery Ali ke PC par hogi. Health phase is `flow-hardening`.
Version 0.14.0.

## Slice 4 — Character Vault (2026-11-21, test repo only)

Built and verified (see `docs/PROJECT_STATE.md`). Har niche ke 10
approved characters ek dafa upload + lock hote hain (versions v1,
v2... — locked version kabhi edit nahi hota, edit naya draft version
banata hai). Niche select karte hi mains khud select hote hain;
locked description + pose har scene prompt me khud jata hai; sheet
image har generation ke saath reference jati hai; bulk sheet ke
baghair block hota hai (guard). Har batch ke baad software khud
tooti/khaali images ko dobara banata hai (auto-QC) — similarity
score sirf record hota hai, regenerate trigger nahi karta, kyunke
calibration ne prove kiya ke pixel similarity drift pehchan nahi
sakti (apni sheet se 0.329–0.428, doosri niche ki sheet se
0.286–0.472 — overlap). UI: StoryCraft me "Character Vault" section
(Niches ke baad, 7th page nahi) + Magic Mode aur VisualForge forms
me niche select. Ali ke PC par dobara copy karni hogi: 14 reference
sheet images (`studio/data/reference/stick-direction/`) — binary
files push/ZIP me nahi jati, is liye app un ke baghair bhi chalta
hai (sheet_path khaali ho to project character reference use hota
hai, kabhi crash nahi).

## Slice 3 PATCH — Retry Ladder + Fallback (2026-11-21, test repo only)

Built and verified (see `docs/PROJECT_STATE.md`). Fail image ka
professional tareeqa — kabhi skip nahi, kabhi gap nahi, sab
automatic. Generate karne se pehle har prompt policy-trigger lafzon
ke liye scan hota hai (pehle hi auto-reword); fail ho to retry queue
(main batch ke baad) — reword, phir simple close-up scene, phir
padosi shot ki image alag crop/zoom se ("fallback used"). Key nahi
ya daily limit khatam ho to dobara nahi chalata (faida nahi). Summary
me likha hota hai: kaunsa prompt fail hua, kyun (exact error), kis
retry se bana, kis shot par fallback laga. VisualForge scene cards
aur Magic summary me retry/fallback badges dikhte hain. Honest
caveat: live Canvas/Flow generation is VM me verify nahi ho saki
(Google login Ali ke PC par) — ladder ke asli provider attempts
sirf fake provider se test hue hain.

## Phase 7 slice 1 — StickMan + StoryCraft (2026-11-21, test repo only)

Built and verified (see `docs/PROJECT_STATE.md`). StickMan is a tool,
never the default video style — Ale rejected stickman videos for his
own content twice, so the studio only builds prompts + frames on
demand. New tables `stickman_poses` (7 poses, seeded, descriptions
editable), `stickman_prompts` (one per scene: pose, action,
expression, props, background, prompt), `master_prompts` (name,
category hook / story / style-dna / viral-short, template, optional
Style DNA link, source) and `research_notes` (per project). Seeds:
9 master prompts reverse-engineered from the real inspiration
videos in `~/workspace/creator-studio-inspiration/VIDEO_NOTES.md`
(Sticky Figure, Ghibli, Claymation, Cyberpunk Neon, Locked Visual
Style, Flat Vector Comic, Viral Short Reverse-Engineer, 2D
Stickman, Viral Hook Generator — 4 linked to Style DNA, 5 honestly
unlinked). `POST /api/scripts/{id}/stickman-prompts` builds one
template-built prompt per scene from the scene's own words (pose by
keyword, rotating fallback so neighbours differ — no AI call, no
key). `POST /api/scenes/{id}/stickman-frame` renders a REAL
1920x1080 stick-figure PNG with Pillow (head circle + body/limb
lines in the chosen pose, face per expression, simple props) and
saves it as a project image asset with source 'stickman' — approve
it in VisualForge and "Use approved in timeline" puts it in the
CineCut timeline. `pillow>=10.0` is in `requirements.txt` (lazy
import — the app still starts without it, the frame endpoint returns
a plain 503). Master Prompt library CRUD + research notes CRUD +
`POST /api/research-notes/{id}/write-script` (reuses the Gemini
script path; no key → the same plain 400, never a fake script).
CineCut gains "StickMan — Stick-figure prompts" and "StoryCraft —
Master Prompt Library" + "StoryCraft — Research notes" sections
(after VisualForge, before One-click video). Verified live with the
Eiffel script (14 sentence scenes → 14 prompts, all 7 poses; 2
frames rendered and viewed — standing vs celebrating, visibly
different; approved frame confirmed in timeline 12). `npm run
build` passes; Playwright screenshots show both new sections with
zero new console errors. Health phase is
`7-stickman-storycraft-slice1`.

## Phase 7 slice 2 — Motion Studio + Asset Vault + Render Studio polish (2026-11-21, test repo only)

Built and verified (see `docs/PROJECT_STATE.md`). Motion Studio:
8 presets (zoom-in/out, pan-left/right, slow-zoom-in/out, drift,
pulse) — a Motion dropdown on each CineCut clip card, stored on the
clip. Atmosphere: vignette, film grain, warm grade — real ffmpeg
filters, applied once after captions. Asset Vault: server-side
search + tags on `GET /api/assets`, `asset_tags` table, add/remove
tag endpoints, tag chips + tag-filter dropdown in Media Library (no
fake seeded tags). Render Studio: quality 720p / 1080p / 4K on the
render endpoint (default 1080p), options stored on the job row, and
an honest Render queue (real status + options + elapsed + error +
Download MP4). **4K is two passes**: pass 1 renders the proven
1080p pipeline to a temp file, pass 2 upscales it to 3840x2160
(lanczos) — a single-graph 4K render OOM-killed this VM three times
(ffmpeg SIGKILLed at frame ~281–284/1371, peak RSS 5.5–5.7 GB), so
the two-pass route is what ships; 4K is labelled an upscale
everywhere, as it is. Verified live: drift/pulse/zoom-in proven on
viewed frames (lamp-post x=273 px at pulse peak vs 287 px at
trough); vignette + grain proven A/B (corners 45–55% darker, centre
identical; sky noise 5.1 vs 0.03); tags/search/filter via API and UI;
720p ffprobe 1280x720; 4K two-pass (job 95) ffprobe 3840x2160,
45.7 s. `npm run build` passes; Playwright screenshots show the new
controls with zero new console errors. Health phase is
`7-motion-assetvault-render-slice2`.

- **Hardening + multi-API keys + voice providers (Phase 7 slice 3)**:
  the script model is now `gemini-3.5-flash` (verified live with the
  connector helper; `gemini-2.0-flash` is retired, `gemini-2.5-flash`
  is not available to new users). Settings holds MORE THAN ONE Gemini
  API key (`gemini_api_keys` table, add/remove/reorder in the UI) and
  requests rotate through them on 401/403/429; when all keys fail the
  error names every attempt, never a fake success. VoiceForge has a
  provider registry (`voice_providers` table): Edge-TTS free and the
  HeyGen clone are built in, and any other provider (A123 Pro, or a
  future one) can be added separately in Settings with a Test button
  that does one harmless reachability check and says plainly that
  voice generation is NOT verified by it. Jobs are checkpointed: a
  backend killed mid-run leaves its jobs `interrupted` (the startup
  sweep marks them, with a plain message) instead of `running`
  forever, and `POST /api/jobs/{id}/resume` re-queues render /
  image-generate / transcribe jobs — restarting from the beginning,
  saying so. `GET /api/backup` downloads a ZIP of the database +
  `studio/data` (no `renders/`); `POST /api/restore` verifies the ZIP
  and restores it, refusing while jobs run. The five most common
  failures (no Gemini key, no voiceover, bad upload, render fail,
  unknown id) all return plain Roman Urdu/English messages naming
  what to do next. The Dashboard jobs panel is renamed "Jobs", shows
  each job's error, and has a Resume button on resumable jobs.
  Verified live: rotation proof (two dummy keys → "saari Gemini keys
  fail ho gayin (key 1: 400, key 2: 400)"); provider add/test/remove
  round-trip; stale job 70 resumed to done (76.5 s, 1920x1080) and a
  fresh kill-mid-render test (interrupted → resumed → done, 36.4 s);
  backup/restore round-trip on a scratch project; timings on this VM
  as a proxy — backend startup 1.6 s, one-click Eiffel run 67.1 s,
  1080p render 76.5 s, 720p render 37.9 s, Whisper tiny on the 63.6 s
  Turkey clip 12.0 s (167 words). This VM is not an 8 GB Windows PC:
  4K two-pass will struggle there, so 720p/1080p stay the default.
  Health phase is `7-hardening-slice3`. The in-app Gemini with-key
  test still needs Ali's PC (he enters the key in Settings there);
  the Canvas free-image route comes after slice 4.

## Phase 7 slice 4 — Distribution (one-click launcher + safe updates)

Built and verified 2026-11-21 (see `docs/PROJECT_STATE.md`) — Phase 7
is now complete, all 7 phases done.

**One-click launcher** — `studio/launcher.py` (Python 3 stdlib only) +
`start-studio.bat` (Windows) + `start-studio.sh` (Linux/Mac).
Double-click (or `python3 studio/launcher.py`) and it: checks the PC
(Python 3.10+, Node.js + npm, FFmpeg — FFmpeg missing is a warning,
the dashboard still opens), finds a Python that can run the backend
(repo `.venv` first, else system Python; installs
`studio/backend/requirements.txt` once with pip if none has FastAPI),
installs frontend deps once if `node_modules` is missing, starts the
backend (127.0.0.1:8000) and the frontend (Vite dev server on
127.0.0.1:5173), waits for `/api/health` 200 and the frontend 200,
opens the dashboard in the browser, and on Ctrl+C stops both cleanly
and checks both ports are free again. If the app is already running
it says so and just opens the dashboard. Flags: `--check` (prereqs
only), `--stop`, `--no-browser`. Your projects, jobs and assets live
in `studio/backend/studio.db` + `studio/data/` — the launcher never
touches them, so a restart keeps everything. First run on a PC needs
Python 3.10+ and Node.js 18+ installed (nodejs.org, python.org) —
the launcher detects a missing one and says so plainly; there is no
bundled installer yet. On Linux/Mac, first run
`chmod +x start-studio.sh update-studio.sh` (the GitHub push does not
carry the executable bit). Logs land in `studio/logs/` (gitignored);
the PID file is `studio/.launcher.pid` (gitignored).

**Safe update** — `scripts/update.py` + `update-studio.bat` /
`update-studio.sh`: `update-studio.bat <naya-version-folder-ya-zip>`
(accepts a folder or a GitHub release ZIP). It checks the source,
stops only a launcher-started instance (refuses if the backend port
is busy without a launcher PID file — it never kills an unknown
process), backs up FIRST to `studio/backups/backup-<ts>.zip`
(`studio.db` + `studio/data/` except `renders/` + a full code
snapshot under `code/`), records the project/job/asset counts, copies
the new code (never `.git`, `node_modules`, `.venv`, `dist`,
`__pycache__`, `backups/`, `logs/`, `studio.db*`, `studio/data/`),
runs `npm install` if `package.json` changed, then starts the backend
and verifies `/api/health` 200 + the project count unchanged. If
verification fails it ROLLS BACK — deletes the files the failed
update copied, restores code + DB + data/ from the backup, and
verifies the old version is back. Old backups accumulate in
`studio/backups/` — delete old ones by hand.

**Releases** — tag `v0.8.0` matches the app version 0.8.0 (health
phase `7-distribution-slice4`). The GitHub release itself could NOT
be created from the build agent: the GitHub connector exposes no
`create_release` / `create_ref` tool, so no tag or release exists yet.
Exact steps (2 minutes, GitHub web UI, repo stays private): open
`https://github.com/nazakataleofficial-coder/kreafy-creator-studio-test/releases/new`
→ tag `v0.8.0` (create new tag on publish) → target `main` @ the
slice-4 commit → title `v0.8.0 — Phase 7 complete: Distribution` →
publish. The release ZIP was verified locally instead: built from the
working copy with GitHub-source-ZIP exclusions (no `node_modules`,
`.venv`, `dist`, `studio.db`, `data/`, `.git` inside).

Verified live: `--check` all OK; launcher run — health 200, frontend
200, 10 real projects, dashboard screenshot with real data (10
Projects, 107 Jobs, 29 Assets, 5 Style DNA); already-running second
run exits 0 with a plain message; Ctrl+C clean stop (both ports free,
no orphans, PID file removed); data survives restarts; update
round-trip on a scratch copy only (backup 282 files / 3.6 MB, 281
files copied, verify OK, new phase marker present, scratch project
survives); broken-source update → verify FAIL → "Rollback OK", old
code back, project survives. Two bugs found by the slice's own tests
and fixed: `npm run dev` left an orphan vite node holding port 5173
after stop (Vite is now run directly with node), and the first backup
had DB+data only so rollback left the broken code in place (the backup
now snapshots the code too).

## FULL final test (2026-11-21, test repo only)

Ali's order: complete all phases, then test everything so nothing is missing.
Tested live on a fresh scratch project ("Final Test", Eiffel script, real VO
+ real images): one-click run → 1080p video 45.714 s, 14 sentence clips,
0 placeholders, 0 black segments, frames viewed; 720p render; deliverables
(thumbnail 1280×720 + YouTube title/description/tags); CineCut auto-sync +
clip edit + SRT; VisualForge API (no-key fail) + Canvas gate (14 jobs
`blocked`, honest message — live generation waits for Ali's Google sign-in
on his PC); VoiceForge (Edge-TTS 503, HeyGen no-key fail, no live HeyGen
call); ClipForge full re-run (Turkey video → 167 words → 2 moments → 9:16
reframe, caption-clock regression confirmed by viewed frames → approval
gating → final clip → SRT → rename → delete); StickMan + StoryCraft; Motion
presets + Asset Vault search/tags + render queue; multi-API keys rotation;
voice providers registry; backup/restore round-trip; job resume after a
mid-render kill; 4K two-pass (3840×2160, 45.714 s); transcription SRT/VTT +
use-as-script; error paths; launcher `--check` + live start/stop; safe
update dry-run on a scratch copy; frontend build + Playwright UI smoke
(0 bad responses, 0 pageerrors).

Fixes made in this slice (all verified live): (1) auto-sync used placeholder
images — now filters them like the run pipeline; (2) launcher installs
backend deps when Playwright is missing on an existing install; (3)
update.py runs `pip install -r requirements.txt` when requirements.txt
changes; (4) Canvas status message no longer appends the raw "(Error)"
class; (5) SIGTERM-killed renders report a plain Roman Urdu message
instead of ffmpeg's "Exiting normally, received signal 15." (ffmpeg exits
255, not -15); (6) `--check` now checks Playwright (WARN-only); (7)
timeline/character GETs return 200 `null` instead of 404 for empty state —
the UI's 74–90 console 404s per page load are gone; (8) stale dashboard
labels fixed (Motion Studio "Planned — Phase 5" → "Phase 7 — motion
presets live"; Quick Tools "Planned" → the studios that do them).

Full checklist: `docs/PROJECT_STATE.md` (FULL final test section) and
`~/workspace/goals/kreafy-creator-studio-completion/files/FULL-FINAL-TEST-CHECKLIST.md`.
Next: the 10-video cross-check.

## Project layout

```
studio/
  README.md            <- this file
  .gitignore           <- studio.db, node_modules, .venv, dist, __pycache__
  backend/
    main.py            <- FastAPI app + SQLite + seed on startup + CineCut (uploads, timeline, SRT, render)
    seed_data.py       <- Style DNA, caption styles, free-tier settings
    requirements.txt   <- fastapi, uvicorn, python-multipart (edge-tts is optional, lazy import)
  data/                <- gitignored: uploads (projects/{id}/) + renders
  frontend/
    package.json       <- Vite + React + TypeScript
    vite.config.ts     <- dev server on 127.0.0.1:5173
    index.html
    src/               <- App.tsx (6 pages + CineCut view), api.ts, styles.css
```

The existing planning docs (`docs/`, `ui/`, `design/`) are untouched
by this build.

## 10-video cross-check (2026-11-21)

Ali's order: every function of the 10 inspiration SaaS in `VIDEO_NOTES.md`
must exist in this SaaS. Checklist: `docs/CROSS-CHECK-10-VIDEOS.md`
(85 rows — PRESENT / PARTIAL / BUILT / EXCLUDED, with live evidence).

Built in this slice: 14 caption styles + word-level "One Word Pop";
9 atmosphere presets (Vintage Sepia, Noir, VHS Noise, Golden Hour,
Cool Winter, Warm Sunset, Dreamy Pastel, Moody Dark, Letterbox 2.5:1);
caption size % / position / on-off; ClipForge aspects 9:16 / 1:1 / 4:5 / 3:4;
max-moments (1–10) + target-length (15–90 s); master-prompt import
(.txt/.md) + reverse-engineer; Niches CRUD + Gemini "Suggest topics";
Style DNA from description; Gemini key Test + Get Free Key links;
transcript TXT export + full-text edit + Copy SRT; final-clip Copy link +
Reuse; Character Match / Style Match toggles + timecode-named ZIP;
Cancel job ("Stop run"); drag-&-drop upload zones.

Two bugs found + fixed by the slice's own tests: cancelled renders left
partial unplayable MP4s (now deleted); character_match=false left the
character words in the prompt (now stripped, no reference image sent).

Left in the GAP-LIST (not built): face tracking + split screen,
blurred-background fill, Razor/Undo/Snapping, clip scale/position/rotation,
manual keyframes, true karaoke fill, voice styles, Clone-a-Voice dialog,
multi-provider TTS generation, project queue, background music,
transcription use-case templates, transitions chooser, in-app update check.
Deliberately excluded (not gaps): trials/paywalls, YouTube downloading,
Google Flow/Veo credits, theme switcher, Groq hard dependency.

## v0.14.1 (2026-11-22) — bugfix release, first real Windows PC test ke baad
- **503 on samples / edge-tts missing:** `edge-tts` ab required dependency hai — fresh install par pip se aata hai, launcher dobara install karta hai, Setup verify karta hai.
- **Tools not clickable:** har tool ab Dashboard / sidebar / All Tools se apna section kholta hai (CineCut project view ke andar, auto-scroll). Dashboard par 10 cards hain (StickMan bhi).
- **AQ. Gemini keys:** calls ab `x-goog-api-key` header bhejte hain (28 May 2026 se AI Studio AQ. keys deta hai; `?key=` un par 400 deta hai).
- **API Keys:** EK grouped section (AI Text / Images / Voice / Stock) — keys sirf aakhri 4 chars dikhte hain; invalid key par friendly error + AI Studio link.
- **Setup:** polling ab done/failed tak chalti hai, har failed step ka Retry button hai, last run refresh ke baad bhi dikhta hai.
- **One-click updates:** source GitHub Releases YA Google Drive mirror (Settings me selector). NOTE: v0.14.0 installs tak v0.14.1 in-app one-click nahi pahunch sakta (un me Drive-source code nahi hai) — bridge public GitHub Release hai; v0.14.1 se onward dono sources one-click.
- **.venv:** naye installs me `app/backend/.venv` (ya dev me `studio/backend/.venv`) me banta hai.
- **Fix round 2 (same v0.14.1, 2026-11-22) — UI redesign (Ali ki verdict):** project view me ek waqt par SIRF ek tool dikhta hai (tool-switcher chips); All Tools sirf clean menu hai (11 cards); VoiceForge aur StoryCraft ke andar sub-tabs hain; Master Prompt Library alag option hai (sidebar + All Tools card); Vault niche cards par mains ki thumbnails seedha dikhti hain (7 cast sheets ab app ke saath ship hoti hain); Edge-TTS ka EK verdict hai — list aur Generate kabhi alag nahi bolenge (list + synthesis probe).
