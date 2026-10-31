# ClipForge AI — Long Video to Shorts — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Import Long Video

**Purpose:** Local, Drive or authorized source upload and playback

**UI controls / subviews:** Video source, Duration, File size, Language, Analysis type, Start.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_import-long-video.html` and `screenshots/01_import-long-video.png`.

**Approval:** Pending manual review.

## 02. AI Analysis

**Purpose:** Topic boundaries, speakers and candidate moments

**UI controls / subviews:** Transcription, Topic shift, Speaker turns, Energy, Keywords, Engagement.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_ai-analysis.html` and `screenshots/02_ai-analysis.png`.

**Approval:** Pending manual review.

## 03. Highlight Candidates

**Purpose:** Time-coded candidates, reasons and editable scores

**UI controls / subviews:** Score, Duration, Topic, Hook, Preview, Reject.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_highlight-candidates.html` and `screenshots/03_highlight-candidates.png`.

**Approval:** Pending manual review.

## 04. Choose Shorts

**Purpose:** Select candidate shorts and batch preview

**UI controls / subviews:** Select all, Exclude, Reorder, Clip count, Duration, Review.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_choose-shorts.html` and `screenshots/04_choose-shorts.png`.

**Approval:** Pending manual review.

## 05. Trim & Edit Short

**Purpose:** Frame-accurate trim, split and reorder

**UI controls / subviews:** Start time, End time, Trim, Split, Remove filler, Undo.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_trim-edit-short.html` and `screenshots/05_trim-edit-short.png`.

**Approval:** Pending manual review.

## 06. Smart Reframe

**Purpose:** 9:16 safe crop and face/speaker focus

**UI controls / subviews:** Face track, Auto crop, Anchor, Padding, Keyframes, Safe area.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_smart-reframe.html` and `screenshots/06_smart-reframe.png`.

**Approval:** Pending manual review.

## 07. Caption Designer

**Purpose:** Word-level subtitles with highlight presets

**UI controls / subviews:** Auto captions, Language, Font, Words per line, Animation, Position.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_caption-designer.html` and `screenshots/07_caption-designer.png`.

**Approval:** Pending manual review.

## 08. AI B-Roll & Overlays

**Purpose:** Context shots, logos and cutaway overlays

**UI controls / subviews:** B-roll source, Overlay, Insert time, Duration, Scale, Rights.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_ai-b-roll-overlays.html` and `screenshots/08_ai-b-roll-overlays.png`.

**Approval:** Pending manual review.

## 09. Brand Kit & CTAs

**Purpose:** Channel logo, colors, intro/outro and CTA placement

**UI controls / subviews:** Brand kit, Watermark, Logo, CTA, Social icons, Safe area.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_brand-kit-ctas.html` and `screenshots/09_brand-kit-ctas.png`.

**Approval:** Pending manual review.

## 10. Clip Quality Review

**Purpose:** Crop, audio, subtitle, content and duplicates checks

**UI controls / subviews:** Black frames, Audio peaks, Caption cut, Duplicate, Safe crop, Approve.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_clip-quality-review.html` and `screenshots/10_clip-quality-review.png`.

**Approval:** Pending manual review.

## 11. Shorts Export Presets

**Purpose:** YouTube Shorts, Instagram Reels and Facebook formats

**UI controls / subviews:** 9:16, 1080x1920, FPS, Codec, Caption burn, Watermark.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_shorts-export-presets.html` and `screenshots/11_shorts-export-presets.png`.

**Approval:** Pending manual review.

## 12. Batch Queue

**Purpose:** Multiple shorts queued, retry and progress status

**UI controls / subviews:** Selected, Pending, Running, Failed, Resume, Output folder.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_batch-queue.html` and `screenshots/12_batch-queue.png`.

**Approval:** Pending manual review.

## 13. Clip History

**Purpose:** Compare clips and export revisions without re-analysis

**UI controls / subviews:** Original, Version, Score, Export date, Reuse, Archive.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_clip-history.html` and `screenshots/13_clip-history.png`.

**Approval:** Pending manual review.

## 14. First Run & Empty State

**Purpose:** First-time setup, empty workspace and guided start

**UI controls / subviews:** New project, Import media, Use template, Choose engine, Get help.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `14_first-run-empty-state.html` and `screenshots/14_first-run-empty-state.png`.

**Approval:** Pending manual review.

## 15. Processing & Progress

**Purpose:** Honest async job progress, cancellation and checkpoints

**UI controls / subviews:** Queued, Running, Pause, Cancel, Checkpoint, Job history.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `15_processing-progress.html` and `screenshots/15_processing-progress.png`.

**Approval:** Pending manual review.

## 16. Failure, Retry & Recovery

**Purpose:** Actionable failure details, safe retry and output recovery

**UI controls / subviews:** Error code, Failed step, View log, Retry, Change engine, Restore.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `16_failure-retry-recovery.html` and `screenshots/16_failure-retry-recovery.png`.

**Approval:** Pending manual review.

## 17. Save & Export Confirmation

**Purpose:** Preview, destination, overwrite protection and confirmation

**UI controls / subviews:** File name, Destination, Version, Review, Approve, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `17_save-export-confirmation.html` and `screenshots/17_save-export-confirmation.png`.

**Approval:** Pending manual review.

