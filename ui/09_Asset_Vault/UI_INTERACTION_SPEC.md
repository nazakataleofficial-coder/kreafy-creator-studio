# Asset Vault & Brand Kits — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. All Assets

**Purpose:** Shared videos, images, voice clips, sound and subtitle items

**UI controls / subviews:** Type, Search, Sort, Favorite, Used by, Collection.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_all-assets.html` and `screenshots/01_all-assets.png`.

**Approval:** Pending manual review.

## 02. Folders & Collections

**Purpose:** Organize reusable assets and smart collections

**UI controls / subviews:** Folder, Tag, Collection, Smart filter, Add, Move.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_folders-collections.html` and `screenshots/02_folders-collections.png`.

**Approval:** Pending manual review.

## 03. Project Asset Inspector

**Purpose:** Technical metadata and every project that uses an asset

**UI controls / subviews:** Dimensions, Duration, Hash, Original, Used by, Versions.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_project-asset-inspector.html` and `screenshots/03_project-asset-inspector.png`.

**Approval:** Pending manual review.

## 04. Brand Kit Manager

**Purpose:** Channel identities with logos, colors, typography

**UI controls / subviews:** Logo, Primary color, Font, Watermark, Intro, CTA.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_brand-kit-manager.html` and `screenshots/04_brand-kit-manager.png`.

**Approval:** Pending manual review.

## 05. Character References

**Purpose:** Approved reusable character photos and appearance locks

**UI controls / subviews:** Identity, Reference, Wardrobe, Styles, Project uses, Permission.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_character-references.html` and `screenshots/05_character-references.png`.

**Approval:** Pending manual review.

## 06. Audio & SFX Collection

**Purpose:** Browse voice, narration, licensed music and SFX

**UI controls / subviews:** Narration, Music, SFX, Duration, License, Preview.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_audio-sfx-collection.html` and `screenshots/06_audio-sfx-collection.png`.

**Approval:** Pending manual review.

## 07. Import Media

**Purpose:** Safely import and index media with validations

**UI controls / subviews:** Upload, Watch folder, File type, Tags, Project, Analyze.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_import-media.html` and `screenshots/07_import-media.png`.

**Approval:** Pending manual review.

## 08. Duplicates & Missing

**Purpose:** Detect duplicate media and disconnected paths

**UI controls / subviews:** Hash, Duplicate, Missing, Used by, Relink, Archive.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_duplicates-missing.html` and `screenshots/08_duplicates-missing.png`.

**Approval:** Pending manual review.

## 09. Safe Trash & Recovery

**Purpose:** Recover deleted media before permanent cleanup

**UI controls / subviews:** Trash, Dependencies, Restore, Retention, Delete, Audit.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_safe-trash-recovery.html` and `screenshots/09_safe-trash-recovery.png`.

**Approval:** Pending manual review.

## 10. Usage & Provenance

**Purpose:** Where each asset originated and how it was generated

**UI controls / subviews:** Provider, Prompt, Model, Rights, References, Use in.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_usage-provenance.html` and `screenshots/10_usage-provenance.png`.

**Approval:** Pending manual review.

## 11. Brand Preset Library

**Purpose:** Shared typography, colors and outro/CTA templates

**UI controls / subviews:** Brand, Style, Platform, Font, Watermark, Apply.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_brand-preset-library.html` and `screenshots/11_brand-preset-library.png`.

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

