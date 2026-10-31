# Master PRD v0.1 — Kreafy Creator Studio

**Audience:** YouTube/Facebook automation creators. **Mission:** fast professional long-form documentary, faceless video and Shorts/Reels production with modular, reusable tools.
**Current status:** requirements draft; no implementation.

## Key user journeys
1. Quick tool: Dashboard → standalone action → appropriate studio tab → import/run/preview/save/use in project.
2. Idea-to-video: topic → research/script approval → scenes → voice/images/motion → CineCut → QA → export.
3. Repurpose: import long video → transcript → highlight candidates → intelligent crop/captions → review → 9:16 exports.
4. Recovery: restart after interruption; preserve verified outputs; reconcile incomplete jobs; resume remaining stages.

## Testable requirements
| ID | Feature | Required verification |
|---|---|---|
| UI-001 | Six consistent pages | Browser navigation passes |
| UI-002 | Approved multi-tool colorful launcher | Visual screenshots reviewed |
| UI-003 | Studios plus individual quick tools | Deep-link correct tabs, shared backend |
| PRJ-001 | Create, resume, duplicate, archive projects | Restart persistence |
| AST-001 | Central searchable asset library | Import/search/preview |
| AST-002 | Asset lineage and safe delete | References and dependency warnings |
| TMP-001 | Creator production templates | Editable generated project |
| AUD-001 | Local transcribe | Timed editable transcript; valid SRT/VTT |
| AUD-002 | Local TTS | Valid audible export |
| AUD-003 | Authorized clone, dubbing, enhance | Consent and output tests |
| WR-001 | Script, hook, prompts, sources | Editable structured output |
| IMG-001 | Image batches and consistency references | Outputs linked to manifest |
| VID-001 | Multi-track editor | Real media save/reopen/export |
| VID-002 | Captions, zoom, effects, transitions | Rendered frame and timing checks |
| CLP-001 | Highlights/reframing | Reviewable candidate clips and timecodes |
| MOT-001 | Text/image-to-video and animation | Actual supported configured model output |
| DOC-001 | Scene-manifest automation | Regenerate a single scene without losing others |
| RND-001 | Durable queue and retries | Crash/restart reconciliation |
| RND-002 | 16:9 and 9:16 export | ffprobe and visual playback |
| API-001 | Provider capabilities and secret vault | Model routing, masking, credential checks |
| API-011 | Multiple keys, health and compliant fallback | Quota grouping, backoff and logs |
| SYS-001 | Low-resource scheduling | Bounded CPU/RAM use |
| SYS-002 | Verified releases and updater | Backups and migration rollback |
| SEC-001 | Secure localhost | Origin/auth/file traversal validation |
| QA-001 | Real media test evidence | Tests and artifact verification |

## Nonfunctional
Local-first, offline after models installed where feasible; no fabricated real-time progress; explicit cloud costs; license and rights compliance; accessible UX; project data separate from app updates. AI image/video generation on 8 GB CPU may be too slow and requires actual benchmarks.

## Phase gates
G0 PRD/design review; G1 license/hardware feasibility; G2 persisted foundation; G3 real audio-to-video pipeline; G4 editing/clipping; G5 documentary automation; G6 security and QA; G7 release/updater.

No phase is complete on screenshots or model claims alone. Human final preview required.
