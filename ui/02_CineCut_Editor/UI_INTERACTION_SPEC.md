# CineCut Professional Editor — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Main Editing Workspace

**Purpose:** Full multi-track editor with preview, browser, inspector

**UI controls / subviews:** Media import, Player, Timeline, Tracks, Inspector, Save.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_main-editing-workspace.html` and `screenshots/01_main-editing-workspace.png`.

**Approval:** Pending manual review.

## 02. Media & Stock Browser

**Purpose:** Import video, audio, images, subtitles and references

**UI controls / subviews:** Local files, Project files, Favorites, Sort, Search, B-roll.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_media-stock-browser.html` and `screenshots/02_media-stock-browser.png`.

**Approval:** Pending manual review.

## 03. Text & Titles

**Purpose:** Title overlays and lower thirds with adjustable typography

**UI controls / subviews:** Font, Weight, Size, Alignment, Shadow, Safe area.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_text-titles.html` and `screenshots/03_text-titles.png`.

**Approval:** Pending manual review.

## 04. Animated Captions

**Purpose:** Word-accurate captions with style and segment editing

**UI controls / subviews:** Caption language, Word timing, Font, Highlight, Animation, Export SRT.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_animated-captions.html` and `screenshots/04_animated-captions.png`.

**Approval:** Pending manual review.

## 05. Caption Style Library

**Purpose:** Saved subtitle themes and per-word color styles

**UI controls / subviews:** Minimal, Kinetic, Cinematic, Neon, Brand kit, Preset.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_caption-style-library.html` and `screenshots/05_caption-style-library.png`.

**Approval:** Pending manual review.

## 06. Transitions Browser

**Purpose:** Cut, fade, wipe and motion transition presets

**UI controls / subviews:** Duration, Ease, Preview, Apply all, Random, Favorites.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_transitions-browser.html` and `screenshots/06_transitions-browser.png`.

**Approval:** Pending manual review.

## 07. Effects & Filters

**Purpose:** Color, blur, masks, LUT and composition effects

**UI controls / subviews:** Effects, Intensity, Mask, Blend, LUT, Reset.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_effects-filters.html` and `screenshots/07_effects-filters.png`.

**Approval:** Pending manual review.

## 08. Color Grading

**Purpose:** Exposure, contrast, color temperature, curves and LUT

**UI controls / subviews:** Exposure, Contrast, Saturation, White balance, Curves, LUT.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_color-grading.html` and `screenshots/08_color-grading.png`.

**Approval:** Pending manual review.

## 09. Motion & Zoom

**Purpose:** Stable smooth zoom, transform and interpolation

**UI controls / subviews:** Scale, X/Y position, Anchor, Ease, Stabilization, Camera move.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_motion-zoom.html` and `screenshots/09_motion-zoom.png`.

**Approval:** Pending manual review.

## 10. Background Removal

**Purpose:** Keying, subject cutout and safe mask refinements

**UI controls / subviews:** Key color, Tolerance, Feather, Spill, Preview mask, Apply.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_background-removal.html` and `screenshots/10_background-removal.png`.

**Approval:** Pending manual review.

## 11. Audio Mixer

**Purpose:** Narration, music, SFX, ducking and track volumes

**UI controls / subviews:** Master gain, Voice gain, Music gain, Ducking, Fade, Limiter.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_audio-mixer.html` and `screenshots/11_audio-mixer.png`.

**Approval:** Pending manual review.

## 12. Keyframe Editor

**Purpose:** Precise transforms, bezier easing and frame controls

**UI controls / subviews:** Property, Keyframe, Interpolation, Hold, Delete, Copy.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_keyframe-editor.html` and `screenshots/12_keyframe-editor.png`.

**Approval:** Pending manual review.

## 13. AI Assist Tools

**Purpose:** Suggested cuts, silence removal and auto B-roll

**UI controls / subviews:** Detect silence, Suggest cuts, Find B-roll, Auto captions, Auto reframe.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_ai-assist-tools.html` and `screenshots/13_ai-assist-tools.png`.

**Approval:** Pending manual review.

## 14. Scene & Clip Organizer

**Purpose:** Arrange chapters, scene versions, approved shots

**UI controls / subviews:** Scene list, Scene order, Asset used, Approved, Duplicate, Replace.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `14_scene-clip-organizer.html` and `screenshots/14_scene-clip-organizer.png`.

**Approval:** Pending manual review.

## 15. Preview & Review

**Purpose:** Review frame by frame with comments and safe areas

**UI controls / subviews:** Playback, Loop, Safe margins, Compare, Frame step, Notes.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `15_preview-review.html` and `screenshots/15_preview-review.png`.

**Approval:** Pending manual review.

## 16. Export Editor Project

**Purpose:** Final delivery, quality controls and metadata

**UI controls / subviews:** Codec, FPS, Bitrate, Resolution, Audio codec, Burn captions.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `16_export-editor-project.html` and `screenshots/16_export-editor-project.png`.

**Approval:** Pending manual review.

## 17. Undo History & Recovery

**Purpose:** Autosave revisions and recover interrupted work

**UI controls / subviews:** Snapshot, Last save, Undo, Redo, Restore, Project diff.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `17_undo-history-recovery.html` and `screenshots/17_undo-history-recovery.png`.

**Approval:** Pending manual review.

## 18. First Run & Empty State

**Purpose:** First-time setup, empty workspace and guided start

**UI controls / subviews:** New project, Import media, Use template, Choose engine, Get help.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `18_first-run-empty-state.html` and `screenshots/18_first-run-empty-state.png`.

**Approval:** Pending manual review.

## 19. Processing & Progress

**Purpose:** Honest async job progress, cancellation and checkpoints

**UI controls / subviews:** Queued, Running, Pause, Cancel, Checkpoint, Job history.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `19_processing-progress.html` and `screenshots/19_processing-progress.png`.

**Approval:** Pending manual review.

## 20. Failure, Retry & Recovery

**Purpose:** Actionable failure details, safe retry and output recovery

**UI controls / subviews:** Error code, Failed step, View log, Retry, Change engine, Restore.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `20_failure-retry-recovery.html` and `screenshots/20_failure-retry-recovery.png`.

**Approval:** Pending manual review.

## 21. Save & Export Confirmation

**Purpose:** Preview, destination, overwrite protection and confirmation

**UI controls / subviews:** File name, Destination, Version, Review, Approve, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `21_save-export-confirmation.html` and `screenshots/21_save-export-confirmation.png`.

**Approval:** Pending manual review.

