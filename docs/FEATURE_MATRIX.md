# Studio & Tool Feature Matrix — proposals, not finished code

**Approved presentation:** Nine studio cards PLUS individual quick-action cards; each quick tool deep-links to an existing studio tab and shares the backend. Studio names and exact boundaries are proposed, not frozen.

| Studio | Actions / subtools |
|---|---|
| VoiceForge Audio Studio | Transcribe, TTS, Authorized Voice Cloning, Dubbing, Audio Enhancement, Voice Library |
| StoryCraft Studio | Topic Research, Hook/Script Writing, Prompt Vault, Visual Prompt Generation, Script Versions |
| VisualForge Studio | Image Generator, Bulk Image Jobs, Reference-based Consistency, Image Editing and Variation |
| CineCut Editor | Multitrack Timeline, Captions, Zooms, Transitions, Effects, Audio Mixing, Keyframes |
| ClipForge AI | Highlight Detection, Long-to-Short, Speaker/Faces, Smart Reframing, Vertical Exports |
| Documentary Director | Topic-to-Video, Storyboard/Scene Manifest, Workflow Stages, Scene Regeneration |
| Motion Studio | Text/Image-to-Video Adapters, Stick-figure Animation, Motion Presets |
| Asset Vault | Shared Media Library, Reference Files, Brand Kits, Collection, Asset Lineage |
| Render Studio | Queue, Batch Processing, Export Presets, ffprobe/QA, Recovery |

## Six navigation pages
Dashboard (studios and tools), Projects (all production instances), All Tools (catalog), Media Library (same Asset Vault storage), Templates (reusable production recipes), Settings (engines, API, system). Do not create duplicate databases for Asset Vault vs Media Library.

## Quick action mapping
Transcribe → VoiceForge/Transcribe; Text-to-Speech → VoiceForge/TTS; Captions → CineCut/Captions; Generate Images → VisualForge/Generate; AI Clipper → ClipForge/Highlights; Video Generator → Motion/Generate; Script Writer → StoryCraft/Scripts; Prompt Library → StoryCraft/Prompt Vault.

## Per-tool contract checklist
Inputs/formats; outputs/formats; settings/presets; model/provider eligibility; local CPU/GPU/RAM needs; cancellation/retries; errors; provenance; cost/consent; manual review and acceptance fixtures.

## Out of scope until separately authorized
Guaranteed unlimited cloud image/video generation, platform publishing, automatic external account controls, scraping restricted content, exact clones of proprietary competitor software.
