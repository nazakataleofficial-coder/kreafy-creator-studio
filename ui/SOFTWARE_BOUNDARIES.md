# Software boundaries — prevent duplicated workflows and mixed UI

| Software area | Owns | Uses shared capabilities | Should not duplicate |
|---|---|---|---|
| App Core | Projects, account/local configuration, global settings, six navigation pages | all modules | per-studio engine logic |
| VoiceForge | transcription, TTS, authorized clone, dubbing, podcast audio | asset library, job queue | CineCut video timeline |
| CineCut | user-controlled multi-track editing and video composition | VoiceForge transcript, Render Studio | independent second asset database |
| ClipForge | long-to-short analysis, highlight selection and smart reframing | CineCut captions/timeline, export | full manual editor duplicated |
| StickMan | character/whiteboard animation workflow | VoiceForge audio, Motion Studio motion | seventh global sidebar tab |
| Documentary Director | scene-manifest-led complete documentary journey | StoryCraft/VisualForge/VoiceForge/CineCut/Render | duplicate images/voice engines |
| VisualForge | image creation, reference locking and image editing | shared assets, provider routing | separate project asset store |
| StoryCraft | research, hooks, scripts, prompt library, visual prompt text | cited sources, project revision | claim unverifiable research |
| Motion Studio | animation, image-to-video and camera movement | StickMan optional workspace, provider engine | own export engine |
| Asset Vault | assets, folders, brand kits, licensing/provenance | Media Library (same store) | a second independent asset database |
| Render Studio | FFmpeg/render jobs, final quality and delivery | all studios | changes to editorial media without review |

**Important:** All tool icons and app-level flows are prototypes, not existing logic. Screen-specific approval needed before the implementation freeze.
