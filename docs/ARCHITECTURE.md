# Technical Architecture — proposal; NOT implemented

Local React/TypeScript web UI ↔ authenticated 127.0.0.1 API (Python/FastAPI candidate) ↔ durable job orchestrator ↔ interchangeable engine adapters ↔ SQLite + filesystem. FFmpeg is the primary render/composition candidate.

## Major domain entities
Project, ScriptRevision, SceneManifest, Asset, AssetUsage, PromptVersion, VoiceProfile, CaptionTrack, TimelineRevision, GenerationJob, JobAttempt, RenderOutput, ProviderConnection, Capability, QuotaGroup, Template, BrandKit, AuditEvent, ReleaseState.

## Cross-module I/O contracts
- Audio: codec, sample rate, channels, duration_ms, language, source/model metadata.
- Transcript: source ID, time-aligned segments/words (where supported), language, speaker labels, revisions.
- Image: dimensions, ratio, file hash, prompt version, seed/reference IDs, usage rights.
- Scene: stable ID, script segment, audio timing, visual IDs, keyframe motion, transitions, captions, QA.
- Job: stable ID, idempotency key/input hash, states, attempts, status history, outputs, error, checkpoint.

## Runtime safety
- Persist jobs; reconcile incomplete attempts after crash, preserve verified outputs.
- Resource aware scheduler for baseline 8 GB Windows CPU/iGPU machine; load large models on demand.
- Separate application installation from local user projects/data, backups and model cache.
- Secrets OS-protected; never browser bundle or git; loopback origin/authorization/file path restrictions.
- API routing respects supported provider model capabilities, quota groups, backoff, budget approvals, no quota evasion.
- Release integrity verification, backup, migration, rollback; do not overwrite user data.

## Validate before implementation
Editor UI decision (custom/OpenCut classic); AutoClip/OpenShorts adaptation; VoiceStudio AGPL constraints; AI model licenses and hardware benchmarks; deployment packaging; DB migrations and queue.
