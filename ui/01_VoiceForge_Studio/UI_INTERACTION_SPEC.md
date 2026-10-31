# VoiceForge Audio Studio — UI Interaction Specification

**Design only; no functional implementation.** Every numbered HTML and PNG in this folder is a separately reviewable screen.

## 01. Text to Speech

**Purpose:** Original approved Vocify-style spacious script editor and delivery controls

**UI controls / subviews:** Script, Voice, Language, Speed, Pitch, Volume.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `01_text-to-speech.html` and `screenshots/01_text-to-speech.png`.

**Approval:** Pending manual review.

## 02. Dialogue Multi-Speaker

**Purpose:** Line-by-line speaker assignment and conversation preview

**UI controls / subviews:** Speaker A, Speaker B, Add speaker, Speaker gaps, Emotion, Timeline.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `02_dialogue-multi-speaker.html` and `screenshots/02_dialogue-multi-speaker.png`.

**Approval:** Pending manual review.

## 03. SRT Dubbing

**Purpose:** Timed subtitle import, editable cues and matched narration

**UI controls / subviews:** Import SRT, Timestamps, Auto fit, Voice, Subtitle preview, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `03_srt-dubbing.html` and `screenshots/03_srt-dubbing.png`.

**Approval:** Pending manual review.

## 04. Dub Translation

**Purpose:** Source language to target language with dub preview

**UI controls / subviews:** Source media, Source language, Target language, Speaker map, Sync mode, Consent.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `04_dub-translation.html` and `screenshots/04_dub-translation.png`.

**Approval:** Pending manual review.

## 05. Transcript Editor

**Purpose:** Word and segment editing, speaker tags and exports

**UI controls / subviews:** Import media, Language, Diarization, Word timing, SRT, TXT.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `05_transcript-editor.html` and `screenshots/05_transcript-editor.png`.

**Approval:** Pending manual review.

## 06. Podcast Studio

**Purpose:** Hosts, guests, segments, intro/outro and music tracks

**UI controls / subviews:** Host voice, Guest voice, Chapters, Intro music, Room tone, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `06_podcast-studio.html` and `screenshots/06_podcast-studio.png`.

**Approval:** Pending manual review.

## 07. Voice Clone

**Purpose:** Consented voice profile with sample checks and approval

**UI controls / subviews:** Sample upload, Voice consent, Language, Noise check, Profile name, Test phrase.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `07_voice-clone.html` and `screenshots/07_voice-clone.png`.

**Approval:** Pending manual review.

## 08. Voice Library

**Purpose:** Searchable voice cards with language, accent and filters

**UI controls / subviews:** Search voice, Male/Female, Accent, Language, Style, Favorites.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `08_voice-library.html` and `screenshots/08_voice-library.png`.

**Approval:** Pending manual review.

## 09. Voice Detail

**Purpose:** Voice preview, supported languages and delivery range

**UI controls / subviews:** Voice demo, Emotion support, Pitch range, Voice ID, Engine, Favorite.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `09_voice-detail.html` and `screenshots/09_voice-detail.png`.

**Approval:** Pending manual review.

## 10. Pronunciation Dictionary

**Purpose:** Custom pronunciations, pauses, names and phonetics

**UI controls / subviews:** Word, Phoneme, Alias, Language, Apply rule, Test.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `10_pronunciation-dictionary.html` and `screenshots/10_pronunciation-dictionary.png`.

**Approval:** Pending manual review.

## 11. Speech Enhancement

**Purpose:** Noise clean, normalization, silence and equalization

**UI controls / subviews:** Upload audio, Denoise, Normalize, Silence trim, EQ, Compare.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `11_speech-enhancement.html` and `screenshots/11_speech-enhancement.png`.

**Approval:** Pending manual review.

## 12. Music and SFX

**Purpose:** Licensed/local SFX browser and soundtrack placement

**UI controls / subviews:** Type, Mood, Duration, License, Preview, Use in timeline.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `12_music-and-sfx.html` and `screenshots/12_music-and-sfx.png`.

**Approval:** Pending manual review.

## 13. Generation & Progress

**Purpose:** Truthful audio jobs, cancel, retries and task log

**UI controls / subviews:** Running, Paused, Failed, Input hash, Retry, Log.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `13_generation-progress.html` and `screenshots/13_generation-progress.png`.

**Approval:** Pending manual review.

## 14. History & Versions

**Purpose:** Saved generations, compare and reuse in any project

**UI controls / subviews:** Date, Voice, Engine, Duration, Version, Use in project.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `14_history-versions.html` and `screenshots/14_history-versions.png`.

**Approval:** Pending manual review.

## 15. Audio Export

**Purpose:** Validated audio export and delivery settings

**UI controls / subviews:** WAV, MP3, Sample rate, Bitrate, Normalization, Subtitle SRT.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `15_audio-export.html` and `screenshots/15_audio-export.png`.

**Approval:** Pending manual review.

## 16. First Run & Empty State

**Purpose:** First-time setup, empty workspace and guided start

**UI controls / subviews:** New project, Import media, Use template, Choose engine, Get help.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `16_first-run-empty-state.html` and `screenshots/16_first-run-empty-state.png`.

**Approval:** Pending manual review.

## 17. Processing & Progress

**Purpose:** Honest async job progress, cancellation and checkpoints

**UI controls / subviews:** Queued, Running, Pause, Cancel, Checkpoint, Job history.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `17_processing-progress.html` and `screenshots/17_processing-progress.png`.

**Approval:** Pending manual review.

## 18. Failure, Retry & Recovery

**Purpose:** Actionable failure details, safe retry and output recovery

**UI controls / subviews:** Error code, Failed step, View log, Retry, Change engine, Restore.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `18_failure-retry-recovery.html` and `screenshots/18_failure-retry-recovery.png`.

**Approval:** Pending manual review.

## 19. Save & Export Confirmation

**Purpose:** Preview, destination, overwrite protection and confirmation

**UI controls / subviews:** File name, Destination, Version, Review, Approve, Export.

**Expected journey:** choose the relevant project → provide/import required data → configure available controls → preview/review → save/use in project or export.

**Verification to plan before implementation:** typed input and file validation; model/provider compatibility; honest processing status; output inspection; revision persistence; safe cancel/retry and errors; accessible labels/keyboard flow.

**Review files:** `19_save-export-confirmation.html` and `screenshots/19_save-export-confirmation.png`.

**Approval:** Pending manual review.

