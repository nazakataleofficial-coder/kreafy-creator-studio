# Motion Studio — AI Video & Animation — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Image to Video

**Purpose:** Input frame, motion prompt, camera action and preview

**UI controls / subviews:** Source image, Duration, Motion prompt, Camera, Model, Resolution.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_image-to-video.html` and `screenshots/01_image-to-video.png`.

**Approval:** Pending manual review.

## 02. Text to Video

**Purpose:** Text prompt, provider model and output preview

**UI controls / subviews:** Prompt, Negative prompt, Model, Seconds, Aspect ratio, Seed.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_text-to-video.html` and `screenshots/02_text-to-video.png`.

**Approval:** Pending manual review.

## 03. Camera Controls

**Purpose:** Pan, zoom, dolly, orbit and smooth speed curves

**UI controls / subviews:** Pan X, Pan Y, Zoom, Orbit, Dolly, Ease.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_camera-controls.html` and `screenshots/03_camera-controls.png`.

**Approval:** Pending manual review.

## 04. Animation Presets

**Purpose:** Motion recipes for documentaries and explainer videos

**UI controls / subviews:** Slow zoom, Parallax, Orbit, Reveal, Shake off, Preset.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_animation-presets.html` and `screenshots/04_animation-presets.png`.

**Approval:** Pending manual review.

## 05. Keyframes & Paths

**Purpose:** Visual keyframes, anchors and trajectories

**UI controls / subviews:** Timeline, X/Y, Scale, Rotation, Ease, Loop.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_keyframes-paths.html` and `screenshots/05_keyframes-paths.png`.

**Approval:** Pending manual review.

## 06. Character Animation

**Purpose:** Pose/reference driven motion, stickman quick access

**UI controls / subviews:** Reference pose, Character ID, Action, Expression, Duration, Sync.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_character-animation.html` and `screenshots/06_character-animation.png`.

**Approval:** Pending manual review.

## 07. Video Variants

**Purpose:** Compare runs, clip quality and provider metadata

**UI controls / subviews:** Variant, Model, Seed, Time, Rating, Approve.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_video-variants.html` and `screenshots/07_video-variants.png`.

**Approval:** Pending manual review.

## 08. Video Generation Queue

**Purpose:** Async jobs, remote polling, cancellation and retries

**UI controls / subviews:** Queued, Running, Canceled, Failed, Cost, Cooldown.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_video-generation-queue.html` and `screenshots/08_video-generation-queue.png`.

**Approval:** Pending manual review.

## 09. Motion Export & Use

**Purpose:** Rendered video clips and handoff to CineCut

**UI controls / subviews:** MP4, FPS, Resolution, Audio, Use in scene, Save.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_motion-export-use.html` and `screenshots/09_motion-export-use.png`.

**Approval:** Pending manual review.

## 10. First Run & Empty State

**Purpose:** First-time setup, empty workspace and guided start

**UI controls / subviews:** New project, Import media, Use template, Choose engine, Get help.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_first-run-empty-state.html` and `screenshots/10_first-run-empty-state.png`.

**Approval:** Pending manual review.

## 11. Processing & Progress

**Purpose:** Honest async job progress, cancellation and checkpoints

**UI controls / subviews:** Queued, Running, Pause, Cancel, Checkpoint, Job history.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_processing-progress.html` and `screenshots/11_processing-progress.png`.

**Approval:** Pending manual review.

## 12. Failure, Retry & Recovery

**Purpose:** Actionable failure details, safe retry and output recovery

**UI controls / subviews:** Error code, Failed step, View log, Retry, Change engine, Restore.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_failure-retry-recovery.html` and `screenshots/12_failure-retry-recovery.png`.

**Approval:** Pending manual review.

## 13. Save & Export Confirmation

**Purpose:** Preview, destination, overwrite protection and confirmation

**UI controls / subviews:** File name, Destination, Version, Review, Approve, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_save-export-confirmation.html` and `screenshots/13_save-export-confirmation.png`.

**Approval:** Pending manual review.

