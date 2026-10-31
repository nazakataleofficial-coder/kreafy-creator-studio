# VisualForge Image Studio — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Text to Image

**Purpose:** Prompt, model, reference images and batch gallery

**UI controls / subviews:** Prompt, Negative prompt, Model, Style, Aspect ratio, Image count.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_text-to-image.html` and `screenshots/01_text-to-image.png`.

**Approval:** Pending manual review.

## 02. Image to Image

**Purpose:** Transformation strength and prompt/reference control

**UI controls / subviews:** Source image, Strength, Preserve structure, Model, Seed, Aspect ratio.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_image-to-image.html` and `screenshots/02_image-to-image.png`.

**Approval:** Pending manual review.

## 03. Consistent Character

**Purpose:** Character reference identity, scene and outfit locking

**UI controls / subviews:** Character ID, Reference, Face consistency, Clothing, Environment, Seed.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_consistent-character.html` and `screenshots/03_consistent-character.png`.

**Approval:** Pending manual review.

## 04. Bulk Image Generator

**Purpose:** Scene-manifest image batches with per-scene prompts

**UI controls / subviews:** Scene list, Model, Parallel jobs, Retry failed, Quality, Save assets.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_bulk-image-generator.html` and `screenshots/04_bulk-image-generator.png`.

**Approval:** Pending manual review.

## 05. Image Editor & Inpaint

**Purpose:** Mask brush, replace object and regenerate region

**UI controls / subviews:** Brush size, Mask, Replace prompt, Feather, Strength, Compare.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_image-editor-inpaint.html` and `screenshots/05_image-editor-inpaint.png`.

**Approval:** Pending manual review.

## 06. Background Removal

**Purpose:** Subject mask, transparent PNG and edge refinement

**UI controls / subviews:** Source, Threshold, Feather, Background, PNG, Edge.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_background-removal.html` and `screenshots/06_background-removal.png`.

**Approval:** Pending manual review.

## 07. Upscale & Enhance

**Purpose:** Resolution upscale, sharpening and denoise

**UI controls / subviews:** Scale, Denoise, Sharpen, Face restore, Output format, Compare.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_upscale-enhance.html` and `screenshots/07_upscale-enhance.png`.

**Approval:** Pending manual review.

## 08. Style Transfer

**Purpose:** Reference-based stylistic transformation

**UI controls / subviews:** Style reference, Strength, Preserve face, Palette, Variations, Preview.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_style-transfer.html` and `screenshots/08_style-transfer.png`.

**Approval:** Pending manual review.

## 09. Reference Image Manager

**Purpose:** Reusable characters, scenes, objects and style sets

**UI controls / subviews:** Reference ID, Category, Tags, Used in, Version, Remove.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_reference-image-manager.html` and `screenshots/09_reference-image-manager.png`.

**Approval:** Pending manual review.

## 10. Image Comparison

**Purpose:** Before/after, 4-way images and difference inspection

**UI controls / subviews:** Compare mode, Zoom, Side by side, Reference, Favorite, Approve.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_image-comparison.html` and `screenshots/10_image-comparison.png`.

**Approval:** Pending manual review.

## 11. Style & Model Presets

**Purpose:** Provider capabilities, local hardware and image templates

**UI controls / subviews:** Provider, Model, Seed, Style, Resolution, Reference support.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_style-model-presets.html` and `screenshots/11_style-model-presets.png`.

**Approval:** Pending manual review.

## 12. Image History & Gallery

**Purpose:** Saved images, metadata, source prompts and projects

**UI controls / subviews:** Prompt, Model, Dimensions, Favorite, Project, Trash.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_image-history-gallery.html` and `screenshots/12_image-history-gallery.png`.

**Approval:** Pending manual review.

## 13. Image Export & Handoff

**Purpose:** Safe image export and use in Documentary or CineCut

**UI controls / subviews:** PNG, JPG, WebP, Resolution, Metadata, Use in project.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_image-export-handoff.html` and `screenshots/13_image-export-handoff.png`.

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

