# Kreafy UI System — v0.1 Concepts (Manual Review)

## Locked direction
- Local-first, premium charcoal/dark navy with gold primary actions. Individual studios have distinct accents.
- Exactly 6 global navigation items: Dashboard, Projects, All Tools, Media Library, Templates, Settings.
- Studios + standalone quick tools share the same backend intent; no duplicated media libraries.
- VoiceForge uses the approved spacious Vocify-like layout with Text, Dialogue, SRT Dubbing, Dub Translation, Transcript, Podcast, Clone, Voice Library and related controls.
- All images in this package are **design reference mockups**, not completed or connected functionality.

## Global components
Persistent product navigation, studio selection, sub-tool switcher, project selector, file picker, import wizard, editable forms, sliders, toggles, preview/player, timeline, saved history, progress panel, quality checks, model selection, credentials, modal confirmations, safe-trash, keyboard shortcuts and error recovery.

## Standard interaction states
Empty/no content, editing, validation, queued, processing, canceling, failed with meaningful code, cooldown, successful with output validation, saving, save conflict, offline/no engine, missing model, quota exhausted, permission required, and recovery.

## Critical policies
Show real progress only when a job backend can substantiate it. No promise of unlimited AI generations. Paid API calls must require explicit opt-in and cost guard. Google Gemini keys in the same project can share quotas. Every engine control is conditional on actual supported capabilities. Voice cloning requires clear consent and rights. Never persist credentials in browser script or GitHub. Preserve imported source media and user's project files during upgrades.

## Implementation acceptance gates (future phase)
Navigation/flow, accessibility (visible focus, labels, keyboard), desktop viewport, asset permissions and path validation, undo/redo and autosave semantics, real output rendered, SRT valid, preview playable, interrupted jobs resumable, API billing prompts, multi-model fallback respect provider limits. Test on low-resource Windows machine.

## Review status
Only product-level design direction and certain previous visual concepts were approved. All new screen-specific layouts are **pending human approval**. Review each individually, record change requests in REVIEW_CHECKLIST.csv, then create a revised frozen UI specification before coding.
