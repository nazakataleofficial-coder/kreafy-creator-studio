# Phased Implementation Roadmap — proposal only

- Phase 0 — Planning freeze: source audit, complete PRD, licensing, feasibility, UI screenshot selection, golden fixture definitions, risk register.
- Phase 1 — Foundation: localhost dashboard with approved six-page nav, SQLite projects, asset library, job management, settings and persistence.
- Phase 2 — First real media pipeline: transcribe/audio input → Kokoro or imported narration → captions → image/video timeline → FFmpeg MP4.
- Phase 3 — CineCut and ClipForge: multi-track, effects, highlight detection, 9:16 reframing, regression tests.
- Phase 4 — StoryCraft and VisualForge: research/script, scene breakdown, batch visual references, provider adapters and consistent asset IDs.
- Phase 5 — Documentary Director and Motion: scene-manifest-driven production, per-scene regeneration, animation and optional video AI.
- Phase 6 — Hardening: QA, performance on 8 GB target, security, recovery, accessibility, multilingual and license validation.
- Phase 7 — Distribution: installer/localhost launcher, verified GitHub releases, backup migrations, rollback and multi-copy update tests.

## Definition of Done
No phase called complete unless actual runnable code exists, unit/integration/E2E tests pass using real media, outputs playable, regressions checked, documented limitations and commit SHAs stored. Planning-only commits do not satisfy product implementation.
