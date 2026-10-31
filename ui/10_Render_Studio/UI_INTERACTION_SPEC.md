# Render Studio & Delivery — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Export Setup

**Purpose:** Full video/audio/image options and delivery formats

**UI controls / subviews:** Container, Codec, Resolution, FPS, Bitrate, Audio.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_export-setup.html` and `screenshots/01_export-setup.png`.

**Approval:** Pending manual review.

## 02. Platform Export Presets

**Purpose:** YouTube, Facebook, TikTok and Instagram presets

**UI controls / subviews:** YouTube, Facebook, TikTok, Reels, Shorts, Custom.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_platform-export-presets.html` and `screenshots/02_platform-export-presets.png`.

**Approval:** Pending manual review.

## 03. Render Queue

**Purpose:** Local task slots, GPU/CPU constraints and progress

**UI controls / subviews:** Queue, Priority, Hardware, ETA unknown, Cancel, Resume.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_render-queue.html` and `screenshots/03_render-queue.png`.

**Approval:** Pending manual review.

## 04. Batch Export

**Purpose:** Multiple deliverables, projects and output templates

**UI controls / subviews:** Selected projects, Targets, Naming, Folder, Queue, Dry run.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_batch-export.html` and `screenshots/04_batch-export.png`.

**Approval:** Pending manual review.

## 05. Quality Inspection

**Purpose:** ffprobe validation, audio level, black frames and captions

**UI controls / subviews:** Video playable, Audio present, Bitrate, Black frames, Safe area, SRT.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_quality-inspection.html` and `screenshots/05_quality-inspection.png`.

**Approval:** Pending manual review.

## 06. Hardware & Performance

**Purpose:** CPU, RAM, disk, threads and concurrency limits

**UI controls / subviews:** CPU threads, RAM limit, GPU, Concurrent jobs, Temp disk, Cache.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_hardware-performance.html` and `screenshots/06_hardware-performance.png`.

**Approval:** Pending manual review.

## 07. Codec & Format Settings

**Purpose:** Codec support and audio/video compatibility

**UI controls / subviews:** H.264, H.265, VP9, CRF, Audio codec, Pixel format.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_codec-format-settings.html` and `screenshots/07_codec-format-settings.png`.

**Approval:** Pending manual review.

## 08. Render Failure Recovery

**Purpose:** Detailed errors, safe retries and file preservation

**UI controls / subviews:** Failed job, Log, Input hash, Retry, Checkpoint, Quarantine.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_render-failure-recovery.html` and `screenshots/08_render-failure-recovery.png`.

**Approval:** Pending manual review.

## 09. Rendered Outputs Gallery

**Purpose:** Project output history and downloadable verified files

**UI controls / subviews:** Master video, Subtitles, Thumbnail, Project, Checksum, Open.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_rendered-outputs-gallery.html` and `screenshots/09_rendered-outputs-gallery.png`.

**Approval:** Pending manual review.

## 10. Storage Cleanup

**Purpose:** Cached proxies, temp files, verified retention

**UI controls / subviews:** Cache, Temp, Media originals, Trash, Safety, Disk report.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_storage-cleanup.html` and `screenshots/10_storage-cleanup.png`.

**Approval:** Pending manual review.

## 11. Package & Delivery

**Purpose:** MP4 plus subtitles, thumbnail, chapter and description

**UI controls / subviews:** MP4, SRT, Thumbnail, Metadata, Folder, Create package.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_package-delivery.html` and `screenshots/11_package-delivery.png`.

**Approval:** Pending manual review.

## 12. First Run & Empty State

**Purpose:** First-time setup, empty workspace and guided start

**UI controls / subviews:** New project, Import media, Use template, Choose engine, Get help.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_first-run-empty-state.html` and `screenshots/12_first-run-empty-state.png`.

**Approval:** Pending manual review.

## 13. Processing & Progress

**Purpose:** Honest async job progress, cancellation and checkpoints

**UI controls / subviews:** Queued, Running, Pause, Cancel, Checkpoint, Job history.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_processing-progress.html` and `screenshots/13_processing-progress.png`.

**Approval:** Pending manual review.

## 14. Failure, Retry & Recovery

**Purpose:** Actionable failure details, safe retry and output recovery

**UI controls / subviews:** Error code, Failed step, View log, Retry, Change engine, Restore.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `14_failure-retry-recovery.html` and `screenshots/14_failure-retry-recovery.png`.

**Approval:** Pending manual review.

## 15. Save & Export Confirmation

**Purpose:** Preview, destination, overwrite protection and confirmation

**UI controls / subviews:** File name, Destination, Version, Review, Approve, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `15_save-export-confirmation.html` and `screenshots/15_save-export-confirmation.png`.

**Approval:** Pending manual review.

