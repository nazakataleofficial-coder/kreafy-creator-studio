export const API_BASE = "http://127.0.0.1:8000/api";

export interface Project {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: number;
  project_id: number;
  kind: string;
  path: string;
  created_at: string;
  /** 1 when this image is a generated placeholder title card (a scene
   *  with no uploaded image), 0 / absent for a real upload. */
  placeholder?: number;
  /** User tags on this asset (Asset Vault, Phase 7 slice 2). */
  tags?: string[];
}

export interface Job {
  id: number;
  project_id: number;
  kind: string;
  status: string;
  error: string | null;
  output_path: string | null;
  created_at: string;
  updated_at: string;
  /** Render options this job was queued with (quality + atmosphere),
   *  as stored JSON — absent for jobs queued before Phase 7 slice 2. */
  options_json?: string | null;
}

export interface Clip {
  id: number;
  timeline_id: number;
  asset_id: number;
  position: number;
  start_s: number;
  end_s: number;
  caption_text: string;
  asset_path: string;
  asset_kind: string;
  /** 1 when the clip's image is a placeholder title card. */
  asset_placeholder?: number;
  /** 1 when this clip's image was approved in VisualForge. */
  asset_approved?: number;
  /** 1 when this clip's image was swapped by per-scene regenerate. */
  image_replaced?: number;
  /** Ken Burns effect of this clip (zoom-in / zoom-out / pan-left / pan-right). */
  effect?: string;
  /** 1 when this clip reuses an image already shown in an earlier clip. */
  asset_reused?: number;
}

/** Display labels for the per-clip Ken Burns effects. */
export const CLIP_EFFECT_LABELS: Record<string, string> = {
  "zoom-in": "Zoom in",
  "zoom-out": "Zoom out",
  "pan-left": "Pan left",
  "pan-right": "Pan right",
  "slow-zoom-in": "Slow zoom in",
  "slow-zoom-out": "Slow zoom out",
  drift: "Drift (diagonal pan)",
  pulse: "Pulse (breathe in/out)",
};

/** The motion presets, in the order the render rotates them. */
export const CLIP_EFFECTS = [
  "zoom-in",
  "zoom-out",
  "pan-left",
  "pan-right",
  "slow-zoom-in",
  "slow-zoom-out",
  "drift",
  "pulse",
];

/** Render quality choices (Phase 7 slice 2). */
export const RENDER_QUALITIES = ["720p", "1080p", "4K"] as const;

export interface RenderOptions {
  quality?: string;
  vignette?: boolean;
  grain?: boolean;
  warm?: boolean;
  /** Named atmosphere preset (cross-check slice) — one of
   *  ATMOSPHERE_PRESETS, or "" for none. */
  atmosphere_preset?: string;
  /** Caption font size, % of the style's own size (50–150). */
  caption_size_pct?: number;
  /** Caption position: bottom / center / top. */
  caption_position?: string;
  /** false = burn no captions at all (ClipNova "Captions: None"). */
  captions?: boolean;
}

/** Named atmosphere presets (cross-check slice — AutoCut Studio PRO
 *  parity). Each is a real ffmpeg filter chain on the backend. */
export const ATMOSPHERE_PRESETS = [
  "Vintage Sepia",
  "Noir (Black & White)",
  "VHS Noise",
  "Golden Hour",
  "Cool Winter",
  "Warm Sunset",
  "Dreamy Pastel",
  "Moody Dark",
  "Letterbox 2.5:1",
] as const;

/** ClipForge aspect ratios (cross-check slice — ClipNova parity). */
export const VERTICAL_ASPECTS = ["9:16", "1:1", "4:5", "3:4"] as const;

/** Caption position choices. */
export const CAPTION_POSITIONS = ["bottom", "center", "top"] as const;

export interface Timeline {
  id: number;
  project_id: number;
  style_dna_id: number | null;
  caption_style_id: number | null;
  vo_duration_s: number;
  vo_asset_id: number | null;
  created_at: string;
  updated_at: string;
  clips: Clip[];
  character_name: string | null;
  character_image_path: string | null;
}

export interface Character {
  id: number;
  project_id: number;
  name: string;
  image_path: string;
  created_at: string;
  updated_at: string;
}

export interface TtsVoice {
  /** Microsoft Edge-TTS ShortName, e.g. en-US-AriaNeural. */
  voice_id: string;
  /** Friendly name, e.g. Aria. */
  name: string;
  locale: string;
  /** English / Hindi / Urdu. */
  language: string;
  gender: string;
  /** False for the curated fallback list on a PC where Edge-TTS is
   *  unreachable; true only when the live list was actually read. */
  verified_here: boolean;
}

export interface TtsVoices {
  available: boolean;
  reason: string;
  /** True only when a real synthesis probe worked here (v0.14.1 fix
   *  round 2) — list and Generate can never disagree again. */
  synthesis_ok: boolean;
  /** "live" when the real voice list was read, "curated" fallback. */
  list_source: string;
  /** True when the voices are the curated fallback (Edge-TTS blocked). */
  curated: boolean;
  /** Saved default voice (VoiceForge favourite). */
  default_voice: string;
  voices: TtsVoice[];
  /** VoiceForge provider registry (built-ins + separately-added). */
  providers: VoiceProvider[];
}

/** One grouped API-key row (v0.14.1 unified /api/keys). */
export interface KeyRow {
  id: string;
  name: string;
  group: string;
  badge: "FREE" | "TRIAL" | "PAID";
  get_url: string;
  used_by: string;
  note: string;
  kind: "single" | "rotation" | "no-key";
  configured: boolean;
  /** Masked preview — dots + last 4 chars, never the full key. */
  preview: string;
  keys: GeminiKey[];
}

/** Key test result — friendly message + key lene ka link. */
export interface KeyTestResult {
  provider: string;
  ok: boolean;
  message: string;
  help_url?: string;
}

/** One Gemini API key in the rotation list (Phase 7 slice 3). */
export interface GeminiKey {
  id: number;
  label: string;
  /** Masked preview — dots + last 4 chars, never the full key. */
  preview: string;
  position: number;
  created_at: string;
}

/** One VoiceForge provider (Phase 7 slice 3). Built-ins have string
 *  ids ('edge-tts', 'heygen'); separately-added ones have numeric ids. */
export interface VoiceProvider {
  id: number | string;
  name: string;
  kind: string;
  base_url: string;
  key_set: boolean;
  enabled: boolean;
  test_status: string;
  test_message: string;
  test_at: string | null;
}

export interface RestoreResult {
  restored: boolean;
  projects: number;
  assets: number;
  jobs: number;
  files: number;
  note: string;
}

export interface TtsPreview {
  voice_id: string;
  path: string;
  url: string;
  cached: boolean;
}

export interface WhisperStatus {
  available: boolean;
  transcribe_ready: boolean;
  audio_reader_ok: boolean | null;
  probe_error: string | null;
  engines: string[];
  version: string | null;
  models_cached: string[];
  cli_binary: string | null;
  note: string;
}

export interface TranscriptionWord {
  word: string;
  start: number;
  end: number;
}

export interface TranscriptionSegment {
  start: number;
  end: number;
  text: string;
  words: TranscriptionWord[];
}

export interface Transcription {
  id: number;
  project_id: number;
  job_id: number | null;
  model: string;
  language: string;
  source_filename: string;
  source_path: string;
  duration_s: number;
  full_text: string;
  created_at: string;
  job_status: string | null;
  job_error: string | null;
  words?: TranscriptionWord[];
  segments?: TranscriptionSegment[];
  word_count?: number;
}

export interface HeyGenVoice {
  id: number;
  project_id: number;
  job_id: number | null;
  asset_id: number | null;
  voice_id: string;
  language: string;
  pitch_applied: boolean;
  pitch_factor: number;
  duration_s: number;
  asset_path: string | null;
  job_status: string | null;
  job_error: string | null;
  created_at: string;
}

export interface HeyGenStatus {
  key_configured: boolean;
  voice_id: string;
  voice_name: string;
  model: string;
  pitch_factor: number;
  pitch_languages: string[];
  rubberband_available: boolean;
  free_note: string;
}

export interface HeyGenSpeakJob {
  job_id: number;
  status: string;
  language: string;
  voice_id: string;
  model: string;
}

export interface TranscriptionJob {
  job_id: number;
  transcription_id: number;
  status: string;
  model: string;
}

export interface SourceVideo {
  id: number;
  project_id: number;
  asset_id: number | null;
  job_id: number | null;
  transcription_id: number | null;
  duration_s: number;
  created_at: string;
  source_filename: string;
  asset_path: string | null;
  video_url: string | null;
  job_status: string | null;
  job_error: string | null;
  model: string;
  language: string;
  word_count: number;
  full_text?: string;
  words?: TranscriptionWord[];
  segments?: TranscriptionSegment[];
  transcription_duration_s?: number;
}

export interface SourceVideoJob {
  job_id: number;
  source_video_id: number;
  transcription_id: number;
  status: string;
  model: string;
  duration_s: number;
}

/** A scored ClipForge moment (Phase 6 slice 2). The score is
 *  explainable: score_breakdown holds the four real components
 *  (density / keywords / silence / length) measured from the
 *  transcription's word timestamps. No energy component — energy is
 *  not measured, so it is not invented either. */
export interface Moment {
  id: number;
  source_video_id: number;
  start_s: number;
  end_s: number;
  score: number;
  score_breakdown: {
    density: number;
    keywords: number;
    silence: number;
    length: number;
    hook_hits: number;
    words_per_second: number;
    gap_before_s: number;
    gap_after_s: number;
  };
  title: string;
  excerpt: string;
  word_count: number;
  created_at: string;
  /** Approval state (Phase 6 slice 4): 'pending' (default, never
   *  renders as final), 'approved' (may render), 'rejected'
   *  (never renders). */
  approval: string;
}

export interface MomentsResult {
  source_video_id: number;
  moments: Moment[];
  count: number;
  note: string | null;
}

/** A vertical preview of a ClipForge moment (Phase 6 slice 3).
 *  Centre-cropped to the chosen aspect (9:16 / 1:1 / 4:5 / 3:4 —
 *  cross-check slice) with the moment's real segments burned in as
 *  captions in caption_style ("One Word Pop" burns one real Whisper
 *  word at a time, always centred). job_status is queued / running /
 *  done / failed; video_url is null until the render succeeds — a
 *  failed reframe has a job error, never a fake clip. */
export interface Reframe {
  id: number;
  moment_id: number;
  job_id: number | null;
  asset_id: number | null;
  caption_style: string;
  aspect: string;
  caption_size_pct: number;
  caption_position: string;
  captions: number;
  width: number;
  height: number;
  duration_s: number;
  created_at: string;
  job_status: string | null;
  job_error: string | null;
  asset_path: string | null;
  video_url: string | null;
}

/** A FINAL vertical clip of an approved ClipForge moment (Phase 6
 *  slice 4). One per moment: a re-render reuses the row and the old
 *  file is deleted only after the new render succeeds. job_status is
 *  queued / running / done / failed; video_url is null until the
 *  render succeeds — a failed render has a job error, never a fake
 *  clip. moment_title is the moment's title at render time; title
 *  is the renameable display title. aspect / caption_size_pct /
 *  caption_position / captions are the render settings (cross-check
 *  slice — they inherit the latest done reframe when not given). */
export interface FinalClip {
  id: number;
  moment_id: number;
  reframe_id: number | null;
  job_id: number | null;
  asset_id: number | null;
  title: string;
  caption_style: string;
  aspect: string;
  caption_size_pct: number;
  caption_position: string;
  captions: number;
  width: number;
  height: number;
  duration_s: number;
  created_at: string;
  job_status: string | null;
  job_error: string | null;
  asset_path: string | null;
  video_url: string | null;
  moment_title: string | null;
  source_video_id: number | null;
}

/** One pose from the StickMan pose library (Phase 7 slice 1).
 *  The name is the contract with the renderer; the description is
 *  editable from the UI. */
export interface StickmanPose {
  id: number;
  name: string;
  description: string;
}

/** One template-built stick-figure prompt for a scene (Phase 7
 *  slice 1). The prompt is built from the scene's own words — no
 *  AI call, no key. */
export interface StickmanPrompt {
  id: number;
  scene_id: number;
  pose: string;
  action: string;
  expression: string;
  props: string;
  background: string;
  prompt: string;
  created_at: string;
}

/** A rendered stickman frame linked to a scene (Phase 7 slice 1).
 *  verdict comes from the image approval flow. */
export interface StickmanFrame {
  scene_id: number;
  asset_id: number;
  pose: string;
  expression: string;
  props: string;
  path: string;
  url: string;
  verdict: string;
}

export interface StickmanPromptRow {
  scene_id: number;
  position: number;
  text: string;
  prompt: StickmanPrompt | null;
  frame: {
    asset_id: number;
    path: string;
    verdict: string;
  } | null;
}

export interface StickmanPromptsList {
  script_id: number;
  prompts: StickmanPromptRow[];
}

export interface GenerateStickmanPromptsResponse {
  script_id: number;
  prompt_ids: number[];
  count: number;
}

/** A Master Prompt from the StoryCraft library (Phase 7 slice 1).
 *  category is hook / story / style-dna / viral-short.
 *  style_dna_name is null when the style has no Style DNA entry. */
export interface MasterPrompt {
  id: number;
  name: string;
  category: string;
  template: string;
  style_dna_id: number | null;
  style_dna_name: string | null;
  source: string;
  created_at: string;
}

/** A niche (cross-check slice — AutoCut Writer / Video 7 parity):
 *  a topic family with an optional default Style DNA. */
export interface Niche {
  id: number;
  name: string;
  description: string;
  /** Main characters, one per line — 100% consistent in every scene. */
  main_characters: string;
  default_style_dna_id: number | null;
  default_style_dna_name?: string | null;
  created_at: string;
}

/** Slice 4 (Character Vault): one locked character sheet entry.
 *  Shapes mirror the backend contract in main.py (vault endpoints) —
 *  no invented fields. */
export interface VaultPose {
  name: string;
  description: string;
}

export interface VaultCharacter {
  id: number;
  niche_id: number;
  name: string;
  description: string;
  signature_prop: string;
  role: "main" | "secondary";
  poses: VaultPose[];
  sheet_path: string | null;
  sheet_url: string | null;
  /** Per-character thumbnail cut from the niche cast sheet (v0.14.1
   *  fix round 2); null for user-uploaded characters (sheet_url). */
  thumb_url: string | null;
  version: number;
  status: "draft" | "approved" | "locked" | "superseded";
  is_active: boolean;
  /** "builtin" = one of the 70 shipped characters; "user" = uploaded. */
  source: "builtin" | "user";
  /** True when this locked character is the user's main character. */
  is_main: boolean;
}

export interface VaultNicheSummary {
  niche_id: number;
  niche_name: string;
  character_count: number;
  mains_locked: number;
  mains_expected: number;
  missing_mains: string[];
  guard_ok: boolean;
  sheet_path: string | null;
  sheet_url: string | null;
  sheet_exists: boolean;
  /** Locked mains with thumbnails (v0.14.1 fix round 2) — the niche
   *  card shows these at first glance, no click needed. */
  mains: { name: string; thumb_url: string | null }[];
}

export interface VaultNicheDetail {
  niche_id: number;
  niche_name: string;
  characters: VaultCharacter[];
  locked: {
    niche_id: number;
    niche_name: string;
    main_characters: string[];
    mains: VaultCharacter[];
    secondaries: VaultCharacter[];
    character_count: number;
    sheet_path: string | null;
    sheet_url: string | null;
    sheet_exists: boolean;
  };
}

/** One niche as Magic options report it (Slice 4). */
export interface VaultNicheOption {
  id: number;
  name: string;
  main_characters: string[];
  character_count: number;
  sheet_url: string | null;
  sheet_exists: boolean;
  guard_ok: boolean;
  missing_mains: string[];
}

/** Release Packaging (v0.14.0): update / setup / output / free keys.
 *  Shapes mirror the backend contract in main.py — no invented fields. */
export interface UpdateCheck {
  current: string;
  source?: string;
  repo: string;
  reachable: boolean;
  update_available: boolean;
  latest: string | null;
  tag: string | null;
  name: string | null;
  published_at: string | null;
  release_url: string | null;
  notes: string;
  assets: { name: string; size: number; download_url: string }[];
  asset: { name: string; size: number; download_url: string } | null;
  error: string;
}

export interface UpdateStatus {
  state: string;
  detail: string;
  updated_at: string;
  last?: { state: string; detail: string; started_at?: string; log?: string };
}

export interface SetupStatus {
  python: { ok: boolean; version: string; detail: string };
  backend_deps: { module: string; ok: boolean; required: boolean; detail: string }[];
  chromium: { ok: boolean; path: string | null };
  ffmpeg: { ok: boolean; path: string | null; version: string | null };
  desktop_shortcut: { ok: boolean; path: string | null; supported: boolean };
  ready: boolean;
  recommended_missing: string[];
  last_run: { run_id: string; steps: Record<string, { ok: boolean; detail: string }>; ok: boolean; updated_at: string } | null;
}

export interface SetupRun {
  run_id: string;
  state: string;
  steps: string[];
  steps_done?: Record<string, { ok: boolean; detail: string }>;
  current?: string;
  dry_run?: boolean;
  note?: string;
}

export interface OutputInfo {
  path: string;
  today: string;
  files: number;
  size_bytes: number;
  by_date: { date: string; files: number; size_bytes: number }[];
}

export interface FreeKey {
  id: string;
  name: string;
  badge: "FREE" | "TRIAL" | "PAID";
  get_url: string;
  used_by: string;
  note: string;
  setting: string | null;
  no_key?: boolean;
  configured: boolean;
}

/** A StoryCraft research note on a project (Phase 7 slice 1).
 * Slice 2: Deep Research notes carry kind='deep-research' + the
 * parsed facts list; plain notes carry kind='note' + []. */
export interface ResearchNote {
  id: number;
  project_id: number;
  title: string;
  content: string;
  kind: string;
  facts: { fact: string; source: string }[];
  created_at: string;
  updated_at: string;
}

/** Slice 2: Thinking Levels + script models offered by the backend. */
export interface StorycraftOptions {
  thinking_levels: { id: string; label: string; words: string }[];
  models: { id: string; label: string; model: string }[];
}

export interface Script {
  id: number;
  project_id: number;
  topic: string;
  full_text: string;
  source: string;
  created_at: string;
  updated_at: string;
  scene_count?: number;
  scenes?: Scene[];
}

export interface Scene {
  id: number;
  script_id: number;
  position: number;
  text: string;
  image_prompt: string;
  duration_s: number;
}

/** Per-scene regenerate + deliverables (Phase 3 slice 3). The thumbnail
 *  is a real frame pulled from the rendered MP4; the metadata is drafted
 *  from the real script (template only) and hand-edited. */
export interface Thumbnail {
  id: number;
  project_id: number;
  path: string;
  timestamp_s: number;
  source_job_id: number | null;
  created_at: string;
}

export interface YoutubeMetadata {
  project_id: number;
  title: string;
  description: string;
  tags: string;
  updated_at: string | null;
}

export interface Deliverables {
  project_id: number;
  video: { job_id: number; output_path: string; duration_s: number } | null;
  thumbnail: Thumbnail | null;
  metadata: YoutubeMetadata | null;
}

/** VisualForge prompt list (Phase 4 slice 1): every scene's image
 *  prompt, with the Style DNA + main character it was built from.
 *  status is "pending" until slice 2 generates the image. */
export interface ScenePrompt {
  scene_id: number;
  position: number;
  text: string;
  image_prompt: string;
  duration_s: number;
  status: string;
}

export interface PromptsList {
  script_id: number;
  topic: string;
  style_dna_name: string | null;
  character_name: string | null;
  prompts: ScenePrompt[];
  quota: {
    daily_limit: number;
    used_today: number;
    remaining: number;
    generation_available: boolean;
    note: string;
  };
  providers?: {
    api: { available: boolean; note: string };
    canvas: { available: boolean; note: string };
    flow: { available: boolean; note: string };
  };
}

/** Gemini Canvas provider readiness (free image route). logged_in
 *  means the Canvas browser profile has a signed-in Google session;
 *  needs_login means the user must sign in once first. */
export interface CanvasStatus {
  provider: string;
  available: boolean;
  logged_in: boolean;
  needs_login: boolean;
  profile_exists: boolean;
  message: string;
  detail: string;
  setup_steps: string[];
}

/** Connect Google readiness (one sign-in for Canvas + Flow).
 *  logged_in means the shared profile has a signed-in Google
 *  session; canvas/flow carry each service's own verdict. */
export interface GoogleStatus {
  provider: string;
  available: boolean;
  logged_in: boolean;
  needs_login: boolean;
  profile_exists: boolean;
  message: string;
  detail: string;
  canvas: { logged_in: boolean; message: string };
  flow: { logged_in: boolean; message: string };
  setup_steps: string[];
}

/** Flow provider hardening (Slice 5): one account = one Google
 *  browser profile. status: active | limited | unusual |
 *  not_logged_in. limited_until is an ISO time until which the
 *  account rests after a quota/limit hit. */
export interface FlowAccount {
  id: number;
  name: string;
  profile_dir: string;
  status: string;
  last_used_at: string | null;
  limited_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlowAccountStatus {
  id: number;
  name: string;
  status: string;
  logged_in: boolean;
  ready: boolean;
  project_id_fragment: string | null;
  detail: string;
  unusual_activity: boolean;
  last_used_at: string | null;
  limited_until: string | null;
}

/** Flow readiness: ready means at least one account is logged in
 *  and not limited/unusual. effective_concurrency is the Fast-mode
 *  wave size the backend can really run (1 account = 1, however
 *  high the setting). recovery_steps appear only when an account
 *  is flagged unusual — the 1-minute guided recovery. */
export interface FlowStatus {
  provider: string;
  available: boolean;
  ready: boolean;
  fast_concurrency: number;
  effective_concurrency: number;
  accounts: FlowAccountStatus[];
  message: string;
  recovery_steps: string[];
  recovery_tip: string;
}

export interface FlowQueue {
  batch_id: string;
  script_id: number;
  topic: string;
  total: number;
  done: number;
  failed: number;
  blocked: number;
  queued: number;
  created_at: string;
  finished_at: string | null;
}

export interface FlowQueueState {
  script_id: number;
  paused: boolean;
}

export interface ChainResolveResult {
  prompt: string;
  resolved: { marker: string; name: string; kind: string }[];
  unknown: string[];
  niche_id: number | null;
  niche_name: string | null;
}

export interface GenerationScene {
  scene_id: number;
  position: number;
  text: string;
  image_prompt: string;
  duration_s: number;
  status: string;
  job_id: number | null;
  error: string | null;
  image_path: string | null;
  asset_id: number | null;
  /** Slice 3 PATCH (Retry Ladder): how this scene's image arrived. */
  retry_fixed_by?: string | null;
  fallback_used?: boolean;
  retry_steps?: number;
  precheck_reworded?: boolean;
}

export interface GenerationStatus {
  script_id: number;
  topic: string;
  project_id: number;
  quota: {
    daily_limit: number;
    used_today: number;
    running_today: number;
    queued_today: number;
    reserved_today: number;
    remaining: number;
    canvas_done_today?: number;
    canvas_blocked_today?: number;
  };
  scenes: GenerationScene[];
}

export interface GenerateImagesResponse {
  script_id: number;
  provider: string;
  queued_job_ids: number[];
  skipped_done_scene_ids: number[];
  skipped_queued_scene_ids: number[];
  limit_blocked_job_ids: number[];
  quota: GenerationStatus["quota"];
}

/** Image verification (Phase 4 slice 3): every scene's candidate
 *  images with Ale's verdict. No verdict means "pending" — an image
 *  never enters a timeline until it is approved. */
export interface SceneImage {
  asset_id: number;
  path: string;
  source: "generated" | "uploaded" | string;
  verdict: "approved" | "rejected" | "pending" | string;
  reason: string;
  decided_at: string | null;
  job_status: string | null;
  job_error: string | null;
}

export interface ScriptImagesScene {
  scene_id: number;
  position: number;
  text: string;
  images: SceneImage[];
}

export interface ScriptImages {
  script_id: number;
  topic: string;
  project_id: number;
  scenes: ScriptImagesScene[];
}

export interface ImageVerdict {
  asset_id: number;
  scene_id: number;
  verdict: string;
  reason: string;
  decided_at: string;
}

export interface UseApprovedResult {
  script_id: number;
  timeline: Timeline;
  filled_scene_positions: number[];
  unfilled_scene_positions: number[];
  summary: string;
}

/** One-click run (Phase 3 slice 2): the run row plus its six step jobs
 *  (Script, Voice, Images, Timeline, Captions, Render), in order. */export interface Run {
  id: number;
  project_id: number;
  script_id: number;
  timeline_id: number | null;
  vo_asset_id: number | null;
  caption_style_id: number | null;
  voice_text: string;
  voice: string;
  status: string;
  error: string | null;
  output_path: string | null;
  srt_path: string | null;
  created_at: string;
  updated_at: string;
  steps: Job[];
}

/** Magic Mode (Slice 3): one topic + script in, finished MP4 out.
 *  Shapes mirror the backend contract in main.py (magic_options /
 *  start_magic / _magic_detail) — no invented fields. */
export type MagicStageStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "blocked";

export interface MagicStage {
  status: MagicStageStatus;
  detail: string;
}

export interface MagicSummary {
  words?: number;
  est_duration_s?: number;
  scenes?: number;
  images_generated?: number;
  images_skipped_done?: number;
  images_failed?: number;
  images_retried?: number;
  images_blocked?: number;
  images_fallback_flow?: number;
  /** Slice 4 (Character Vault): auto-QC counts + the vault niche used. */
  images_qc_checked?: number;
  images_qc_regenerated?: number;
  vault_niche?: string | null;
  /** Slice 3 PATCH (Retry Ladder): ladder counts + per-scene log. */
  images_retry_fixed?: number;
  images_fallback_used?: number;
  images_precheck_reworded?: number;
  images_retry_log?: {
    scene_id: number;
    scene_position: number | null;
    job_id: number;
    error: string;
    fixed_by: string | null;
  }[];
  uploaded_images?: number;
  placeholders_used?: number;
  voice_chars?: number;
  voice_chunks?: number;
  voice_kind?: string;
  duration_s?: number;
  output_path?: string | null;
  thumbnail_path?: string | null;
  warnings?: string[];
}

export interface MagicRun {
  id: number;
  project_id: number;
  topic: string;
  script_text?: string;
  voice_kind?: string;
  voice_id?: string;
  vo_asset_id?: number | null;
  caption_style_id?: number | null;
  style_dna_id?: number | null;
  aspect?: string;
  language?: string;
  status: "queued" | "running" | "done" | "failed";
  stages: Record<string, MagicStage>;
  summary: MagicSummary;
  error?: string | null;
}

export interface MagicOptions {
  caption_styles: {
    id: number;
    name: string;
    css?: string;
    bg?: string;
    fg?: string;
    description?: string;
    language?: string;
  }[];
  aspects: { value: string; label: string }[];
  languages: { value: string; label: string }[];
  style_dna: {
    id: number;
    name: string;
    instructions?: string;
    description?: string;
    master_prompt?: string;
  }[];
  last_used_style_dna_id: number | null;
  /** Slice 4 (Character Vault): niches the Magic run can lock onto. */
  niches: VaultNicheOption[];
  voices: {
    uploaded: { id: number; path: string; duration_s: number; created_at: string }[];
    edge: {
      available: boolean;
      source: string;
      note: string;
      list: { id: string; label: string; locale: string; language: string; gender: string }[];
    };
    heygen: {
      available: boolean;
      key_configured: boolean;
      voice_id: string | null;
      voice_name: string;
      model: string;
      note: string;
    };
  };
  defaults: {
    voice_kind: string;
    vo_asset_id: number | null;
    voice_id: string;
    caption_style_id: number | null;
    style_dna_id: number | null;
    aspect: string;
    language: string;
  };
}

export interface MagicStartBody {
  topic: string;
  script_text: string;
  voice_kind: "upload" | "edge" | "heygen";
  voice_id: string;
  vo_asset_id: number | null;
  caption_style_id: number | null;
  style_dna_id: number | null;
  aspect: string;
  language: string;
  /** Slice 4: Character Vault niche — null = no Vault, free characters. */
  niche_id: number | null;
  scene_characters?: Record<string, string>;
}

/** The six Magic stages, in backend order. */
export const MAGIC_STAGES = [
  "script",
  "images",
  "voice",
  "timeline",
  "captions",
  "render",
] as const;

const API_ORIGIN = "http://127.0.0.1:8000";

/** Public URL for a stored file. `output/...` paths live at the
 * install root (served by /output-files/), everything else under
 * studio/data/ (served by /files/). */
export function fileUrl(path: string): string {
  const clean = path.replace(/^\/+/, "");
  if (clean.startsWith("output/")) {
    return `${API_ORIGIN}/output-files/${clean.slice("output/".length)}`;
  }
  return `${API_ORIGIN}/files/${clean}`;
}

export function srtUrl(timelineId: number): string {
  return `${API_BASE}/timelines/${timelineId}/srt`;
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Setting {
  key: string;
  value: string;
  note: string;
}

export interface StyleDna {
  id: number;
  name: string;
  description: string;
  master_prompt: string;
}

export interface CaptionStyle {
  id: number;
  name: string;
  description: string;
  language: string;
}

export interface Health {
  status: string;
  service: string;
  phase: string;
  version: string;
  database: string;
  ffmpeg: { available: boolean; version: string | null; path: string | null };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // v0.14.1: har request ka 120 s timeout hai — pehle fetch kabhi
  // timeout nahi hota tha, to ek latka hua endpoint (jaise browser
  // probe) poora page "Loading…" par hamesha ke liye rok deta tha.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120_000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${text}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error(
        "Request timeout (120 s) — backend jawab nahi de raha, dobara try karein",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<Health>("/health"),
  projects: () => request<Project[]>("/projects"),
  createProject: (name: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  assets: (projectId?: number, q?: string, tag?: string) => {
    const params = new URLSearchParams();
    if (projectId !== undefined) params.set("project_id", String(projectId));
    if (q) params.set("q", q);
    if (tag) params.set("tag", tag);
    const qs = params.toString();
    return request<Asset[]>(qs ? `/assets?${qs}` : "/assets");
  },
  assetTags: () =>
    request<{ tag: string; count: number }[]>("/assets/tags"),
  addAssetTag: (assetId: number, tag: string) =>
    request<{ asset_id: number; tag: string; tags: string[] }>(
      `/assets/${assetId}/tags`,
      { method: "POST", body: JSON.stringify({ tag }) },
    ),
  removeAssetTag: (assetId: number, tag: string) =>
    request<{ asset_id: number; tag: string; tags: string[] }>(
      `/assets/${assetId}/tags/${encodeURIComponent(tag)}`,
      { method: "DELETE" },
    ),
  jobs: (kind?: string) =>
    request<Job[]>(kind ? `/jobs?kind=${encodeURIComponent(kind)}` : "/jobs"),
  job: (id: number) => request<Job>(`/jobs/${id}`),
  resumeJob: (id: number) =>
    request<{ job_id: number; status: string; kind: string; note: string }>(
      `/jobs/${id}/resume`,
      { method: "POST" },
    ),
  cancelJob: (id: number) =>
    request<{ id: number; status: string }>(`/jobs/${id}/cancel`, {
      method: "POST",
    }),
  settings: () => request<Setting[]>("/settings"),
  updateSetting: (key: string, value: string) =>
    request<Setting>(`/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  // --- Multi-API keys + voice providers (Phase 7 slice 3) ---
  geminiKeys: () => request<GeminiKey[]>("/gemini-keys"),
  addGeminiKey: (label: string, key: string) =>
    request<GeminiKey>("/gemini-keys", {
      method: "POST",
      body: JSON.stringify({ label, key }),
    }),
  deleteGeminiKey: (id: number) =>
    request<{ deleted: boolean; id: number }>(`/gemini-keys/${id}`, {
      method: "DELETE",
    }),
  moveGeminiKey: (id: number, direction: "up" | "down") =>
    request<GeminiKey>(`/gemini-keys/${id}/move`, {
      method: "POST",
      body: JSON.stringify({ direction }),
    }),
  testGeminiKey: (id: number) =>
    request<{ ok: boolean; message: string; help_url?: string }>(
      `/gemini-keys/${id}/test`,
      { method: "POST" },
    ),
  // --- Unified API Keys (v0.14.1) — grouped Settings section ---
  keys: () => request<KeyRow[]>("/keys"),
  setKey: (provider: string, value: string, label?: string) =>
    request(`/keys/${encodeURIComponent(provider)}`, {
      method: "POST",
      body: JSON.stringify({ value, label: label ?? "" }),
    }),
  deleteKey: (provider: string) =>
    request<{ deleted: boolean; provider: string }>(
      `/keys/${encodeURIComponent(provider)}`,
      { method: "DELETE" },
    ),
  testKey: (provider: string) =>
    request<KeyTestResult>(`/keys/${encodeURIComponent(provider)}/test`, {
      method: "POST",
    }),
  voiceProviders: () => request<VoiceProvider[]>("/voice-providers"),
  addVoiceProvider: (name: string, base_url: string, api_key: string) =>
    request<VoiceProvider>("/voice-providers", {
      method: "POST",
      body: JSON.stringify({ name, base_url, api_key }),
    }),
  deleteVoiceProvider: (id: number | string) =>
    request<{ deleted: boolean; id: number }>(`/voice-providers/${id}`, {
      method: "DELETE",
    }),
  testVoiceProvider: (id: number | string) =>
    request<VoiceProvider>(`/voice-providers/${id}/test`, {
      method: "POST",
    }),
  restoreBackup: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<RestoreResult>("/restore", form);
  },
  styleDna: () => request<StyleDna[]>("/style-dna"),
  captionStyles: () => request<CaptionStyle[]>("/caption-styles"),
  // --- CineCut (Phase 2) ---
  uploadVoice: (projectId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<Asset & { duration_s: number }>(
      `/projects/${projectId}/upload-voice`,
      form,
    );
  },
  uploadImages: (projectId: number, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return upload<Asset[]>(`/projects/${projectId}/upload-images`, form);
  },
  tts: (projectId: number, text: string, voice: string) =>
    request<Asset & { duration_s: number }>(`/projects/${projectId}/tts`, {
      method: "POST",
      body: JSON.stringify({ text, voice }),
    }),
  autoSync: (projectId: number, captions?: string[], mode?: string) =>
    request<Timeline>(`/projects/${projectId}/timeline/auto-sync`, {
      method: "POST",
      body: JSON.stringify({
        ...(captions !== undefined ? { captions } : {}),
        ...(mode !== undefined ? { mode } : {}),
      }),
    }),
  // --- Main character (Phase 2 slice 2) ---
  character: (projectId: number) =>
    request<Character>(`/projects/${projectId}/character`),
  uploadCharacter: (projectId: number, name: string, file: File) => {
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    return upload<Character>(`/projects/${projectId}/character`, form);
  },
  // --- Scripts + scenes (Phase 3 slice 1) ---
  scripts: (projectId: number) =>
    request<Script[]>(`/projects/${projectId}/scripts`),
  createScript: (
    projectId: number,
    topic: string,
    fullText: string,
    thinkingLevel?: string,
    model?: string,
  ) =>
    request<Script>(`/projects/${projectId}/scripts`, {
      method: "POST",
      body: JSON.stringify({
        topic,
        full_text: fullText,
        thinking_level: thinkingLevel ?? "medium",
        model: model ?? "fast",
      }),
    }),
  scriptScenes: (scriptId: number) =>
    request<Scene[]>(`/scripts/${scriptId}/scenes`),
  updateScene: (
    sceneId: number,
    patch: { text?: string; image_prompt?: string; duration_s?: number },
  ) =>
    request<Scene>(`/scenes/${sceneId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  regenerateScenePrompt: (sceneId: number) =>
    request<Scene>(`/scenes/${sceneId}/regenerate-prompt`, {
      method: "POST",
    }),
  deleteScript: (scriptId: number) =>
    request<{ deleted: boolean; id: number }>(`/scripts/${scriptId}`, {
      method: "DELETE",
    }),
  // --- Sentence-level visuals: re-split a script into one scene per
  // sentence, so the visual changes on every sentence. ---
  resplitSentences: (scriptId: number) =>
    request<Script>(`/scripts/${scriptId}/resplit-sentences`, {
      method: "POST",
    }),
  // --- VisualForge prompt list (Phase 4 slice 1) ---
  scriptPrompts: (scriptId: number) =>
    request<PromptsList>(`/scripts/${scriptId}/prompts`),
  projectPrompts: (projectId: number) =>
    request<PromptsList>(`/projects/${projectId}/prompts`),
  // --- VisualForge bulk generation (Phase 4 slice 2) ---
  generateImages: (
    scriptId: number,
    provider: string = "api",
    opts?: {
      character_match?: boolean;
      style_match?: boolean;
      /** Slice 4: lock images to this Vault niche's characters. */
      niche_id?: number | null;
      scene_characters?: Record<string, string>;
    },
  ) =>
    request<GenerateImagesResponse>(`/scripts/${scriptId}/generate-images`, {
      method: "POST",
      body: JSON.stringify({
        provider,
        character_match: opts?.character_match ?? true,
        style_match: opts?.style_match ?? true,
        ...(opts?.niche_id !== undefined && opts.niche_id !== null
          ? { niche_id: opts.niche_id }
          : {}),
        ...(opts?.scene_characters
          ? { scene_characters: opts.scene_characters }
          : {}),
      }),
    }),
  generationStatus: (scriptId: number) =>
    request<GenerationStatus>(`/scripts/${scriptId}/generation-status`),
  // --- Gemini Canvas provider (free image route) ---
  canvasStatus: () => request<CanvasStatus>(`/canvas/status`),
  openCanvasLogin: () =>
    request<{ message: string }>(`/canvas/open-login`, {
      method: "POST",
    }),
  // --- Connect Google (one sign-in for Canvas + Flow) ---
  googleStatus: () => request<GoogleStatus>(`/google/status`),
  openGoogleLogin: () =>
    request<{ message: string }>(`/google/open-login`, {
      method: "POST",
    }),
  disconnectGoogle: () =>
    request<{ disconnected: boolean; removed_entries: number }>(
      `/google/disconnect`,
      { method: "POST" },
    ),
  // --- Flow provider hardening (Slice 5) ---
  flowStatus: () => request<FlowStatus>(`/flow/status`),
  flowAccounts: () =>
    request<{ accounts: FlowAccount[] }>(`/flow/accounts`),
  flowAddAccount: (name?: string) =>
    request<FlowAccount>(`/flow/accounts`, {
      method: "POST",
      body: JSON.stringify(name ? { name } : {}),
    }),
  flowRemoveAccount: (accountId: number) =>
    request<{ removed: boolean; id: number }>(
      `/flow/accounts/${accountId}`,
      { method: "DELETE" },
    ),
  flowOpenAccountLogin: (accountId: number) =>
    request<{ message: string }>(`/flow/accounts/${accountId}/open-login`, {
      method: "POST",
    }),
  flowRecoverAccount: (accountId: number) =>
    request<{
      account_id: number;
      status: string;
      logged_in: boolean;
      detail: string;
    }>(`/flow/accounts/${accountId}/recover`, { method: "POST" }),
  flowSetSettings: (fastConcurrency: number) =>
    request<{ fast_concurrency: number }>(`/flow/settings`, {
      method: "POST",
      body: JSON.stringify({ fast_concurrency: fastConcurrency }),
    }),
  flowQueues: () => request<{ queues: FlowQueue[] }>(`/flow/queues`),
  flowQueueState: (scriptId: number) =>
    request<FlowQueueState>(`/scripts/${scriptId}/queue-state`),
  flowPauseQueue: (scriptId: number) =>
    request<FlowQueueState>(`/scripts/${scriptId}/queue/pause`, {
      method: "POST",
    }),
  flowResumeQueue: (scriptId: number) =>
    request<{
      script_id: number;
      paused: boolean;
      resumed: boolean;
      queued_jobs: number;
    }>(`/scripts/${scriptId}/queue/resume`, { method: "POST" }),
  flowResolveChain: (prompt: string, nicheId?: number | null) =>
    request<ChainResolveResult>(`/flow/resolve-chain`, {
      method: "POST",
      body: JSON.stringify({ prompt, niche_id: nicheId ?? null }),
    }),
  // --- VisualForge image verification + use (Phase 4 slice 3) ---
  scriptImages: (scriptId: number) =>
    request<ScriptImages>(`/scripts/${scriptId}/images`),
  attachImageToScene: (sceneId: number, assetId: number) =>
    request<SceneImage>(`/scenes/${sceneId}/attach-image`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId }),
    }),
  approveImage: (assetId: number) =>
    request<ImageVerdict>(`/images/${assetId}/approve`, { method: "POST" }),
  rejectImage: (assetId: number, reason?: string) =>
    request<ImageVerdict>(`/images/${assetId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  regenerateImage: (assetId: number) =>
    request<{
      asset_id: number;
      scene_id: number;
      script_id: number;
      job_id: number | null;
      outcome: string;
      message: string;
    }>(`/images/${assetId}/regenerate`, { method: "POST" }),
  useApproved: (scriptId: number) =>
    request<UseApprovedResult>(`/scripts/${scriptId}/use-approved`, {
      method: "POST",
    }),
  approvedImagesZipUrl: (scriptId: number) =>
    `${API_BASE}/scripts/${scriptId}/images.zip`,
  // --- Free voices + Whisper status (Phase 2 slice 2) ---
  ttsVoices: () => request<TtsVoices>("/tts-voices"),
  ttsPreview: (voiceId: string) =>
    request<TtsPreview>(`/tts-voices/${encodeURIComponent(voiceId)}/preview`, {
      method: "POST",
    }),
  getSetting: (key: string) =>
    request<Setting>(`/settings/${encodeURIComponent(key)}`),
  whisperStatus: () => request<WhisperStatus>("/whisper-status"),
  // --- Local Whisper transcription (Phase 5 slice 2) ---
  transcribe: (projectId: number, file: File, model: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("model", model);
    form.append("project_id", String(projectId));
    return upload<TranscriptionJob>("/transcribe", form);
  },
  listTranscriptions: (projectId: number) =>
    request<Transcription[]>(`/projects/${projectId}/transcriptions`),
  getTranscription: (transcriptionId: number) =>
    request<Transcription>(`/transcriptions/${transcriptionId}`),
  transcriptionSrtUrl: (transcriptionId: number) =>
    `${API_BASE}/transcriptions/${transcriptionId}/srt`,
  transcriptionVttUrl: (transcriptionId: number) =>
    `${API_BASE}/transcriptions/${transcriptionId}/vtt`,
  transcriptionTxtUrl: (transcriptionId: number) =>
    `${API_BASE}/transcriptions/${transcriptionId}/txt`,
  updateTranscription: (transcriptionId: number, fullText: string) =>
    request<Transcription>(`/transcriptions/${transcriptionId}`, {
      method: "PUT",
      body: JSON.stringify({ full_text: fullText }),
    }),
  useTranscriptionAsScript: (transcriptionId: number, topic?: string) =>
    request<Script>(`/transcriptions/${transcriptionId}/use-as-script`, {
      method: "POST",
      body: JSON.stringify({ topic: topic ?? "" }),
    }),
  // --- ClipForge long video (Phase 6 slice 1) ---
  uploadSourceVideo: (projectId: number, file: File, model: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("model", model);
    form.append("project_id", String(projectId));
    return upload<SourceVideoJob>(
      `/projects/${projectId}/source-videos`,
      form,
    );
  },
  listSourceVideos: (projectId: number) =>
    request<SourceVideo[]>(`/projects/${projectId}/source-videos`),
  getSourceVideo: (sourceVideoId: number) =>
    request<SourceVideo>(`/source-videos/${sourceVideoId}`),
  // --- ClipForge moments (Phase 6 slice 2) ---
  detectMoments: (
    sourceVideoId: number,
    opts?: { max_moments?: number; target_length_s?: number | null },
  ) =>
    request<MomentsResult>(`/source-videos/${sourceVideoId}/detect-moments`, {
      method: "POST",
      body: JSON.stringify(opts ?? {}),
    }),
  listMoments: (sourceVideoId: number) =>
    request<Moment[]>(`/source-videos/${sourceVideoId}/moments`),
  // --- ClipForge vertical reframe + captions (Phase 6 slice 3) ---
  reframeMoment: (
    momentId: number,
    opts: {
      caption_style: string;
      aspect?: string;
      caption_size_pct?: number;
      caption_position?: string;
      captions?: boolean;
    },
  ) =>
    request<Reframe>(`/moments/${momentId}/reframe`, {
      method: "POST",
      body: JSON.stringify(opts),
    }),
  listReframes: (momentId: number) =>
    request<Reframe[]>(`/moments/${momentId}/reframes`),
  // --- ClipForge approval gating + final render (Phase 6 slice 4) ---
  approveMoment: (momentId: number) =>
    request<Moment>(`/moments/${momentId}/approve`, { method: "POST" }),
  rejectMoment: (momentId: number) =>
    request<Moment>(`/moments/${momentId}/reject`, { method: "POST" }),
  listApprovedMoments: (sourceVideoId: number) =>
    request<Moment[]>(`/source-videos/${sourceVideoId}/approved-moments`),
  renderFinalClip: (
    momentId: number,
    opts?: {
      caption_style?: string;
      aspect?: string;
      caption_size_pct?: number;
      caption_position?: string;
      captions?: boolean;
    },
  ) =>
    request<FinalClip>(`/moments/${momentId}/render`, {
      method: "POST",
      body: JSON.stringify({
        caption_style: opts?.caption_style ?? "",
        aspect: opts?.aspect ?? "",
        caption_size_pct: opts?.caption_size_pct ?? null,
        caption_position: opts?.caption_position ?? "",
        captions: opts?.captions ?? null,
      }),
    }),
  listFinalClipsByMoment: (momentId: number) =>
    request<FinalClip[]>(`/moments/${momentId}/final-clips`),
  listFinalClipsBySourceVideo: (sourceVideoId: number) =>
    request<FinalClip[]>(`/source-videos/${sourceVideoId}/final-clips`),
  getFinalClip: (finalClipId: number) =>
    request<FinalClip>(`/final-clips/${finalClipId}`),
  renameFinalClip: (finalClipId: number, title: string) =>
    request<FinalClip>(`/final-clips/${finalClipId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteFinalClip: (finalClipId: number) =>
    request<{ deleted: boolean; final_clip_id: number; moment_id: number }>(
      `/final-clips/${finalClipId}`,
      { method: "DELETE" },
    ),
  reuseFinalClip: (finalClipId: number, projectId: number) =>
    request<Asset>(`/final-clips/${finalClipId}/reuse`, {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    }),
  finalClipSrtUrl: (finalClipId: number) =>
    `${API_BASE}/final-clips/${finalClipId}/srt`,
  // --- StickMan + StoryCraft (Phase 7 slice 1) ---
  stickmanPoses: () => request<StickmanPose[]>("/stickman-poses"),
  updateStickmanPose: (poseId: number, description: string) =>
    request<StickmanPose>(`/stickman-poses/${poseId}`, {
      method: "PUT",
      body: JSON.stringify({ description }),
    }),
  generateStickmanPrompts: (scriptId: number) =>
    request<GenerateStickmanPromptsResponse>(
      `/scripts/${scriptId}/stickman-prompts`,
      { method: "POST" },
    ),
  stickmanPrompts: (scriptId: number) =>
    request<StickmanPromptsList>(`/scripts/${scriptId}/stickman-prompts`),
  updateStickmanPrompt: (
    promptId: number,
    patch: {
      pose?: string;
      action?: string;
      expression?: string;
      props?: string;
      background?: string;
      prompt?: string;
    },
  ) =>
    request<StickmanPrompt>(`/stickman-prompts/${promptId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  renderStickmanFrame: (sceneId: number, pose?: string, props?: string) =>
    request<StickmanFrame>(`/scenes/${sceneId}/stickman-frame`, {
      method: "POST",
      body: JSON.stringify({ pose: pose ?? "", props: props ?? "" }),
    }),
  masterPrompts: () => request<MasterPrompt[]>("/master-prompts"),
  createMasterPrompt: (body: {
    name: string;
    category: string;
    template: string;
    style_dna_id?: number | null;
    source?: string;
  }) =>
    request<MasterPrompt>("/master-prompts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateMasterPrompt: (
    promptId: number,
    patch: {
      name?: string;
      category?: string;
      template?: string;
      style_dna_id?: number | null;
      source?: string;
    },
  ) =>
    request<MasterPrompt>(`/master-prompts/${promptId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteMasterPrompt: (promptId: number) =>
    request<{ deleted: boolean; id: number }>(`/master-prompts/${promptId}`, {
      method: "DELETE",
    }),
  importMasterPrompt: (file: File, category: string = "style-dna") => {
    const form = new FormData();
    form.append("file", file);
    form.append("category", category);
    return upload<MasterPrompt>("/master-prompts/import", form);
  },
  reverseEngineerMasterPrompt: (
    name: string,
    notes: string,
    category: string = "viral-short",
  ) =>
    request<MasterPrompt>("/master-prompts/reverse-engineer", {
      method: "POST",
      body: JSON.stringify({ name, notes, category }),
    }),
  createStyleDnaFromDescription: (name: string, description: string) =>
    request<StyleDna>("/style-dna/from-description", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  // --- Niches (cross-check slice — AutoCut Writer / Video 7) ---
  niches: () => request<Niche[]>("/niches"),
  createNiche: (body: {
    name: string;
    description?: string;
    main_characters?: string;
    default_style_dna_id?: number | null;
  }) =>
    request<Niche>("/niches", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateNiche: (
    nicheId: number,
    patch: {
      name?: string;
      description?: string;
      main_characters?: string;
      default_style_dna_id?: number | null;
    },
  ) =>
    request<Niche>(`/niches/${nicheId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteNiche: (nicheId: number) =>
    request<{ deleted: boolean; id: number }>(`/niches/${nicheId}`, {
      method: "DELETE",
    }),
  suggestTopics: (nicheId: number) =>
    request<{ niche_id: number; topics: string[] }>(
      `/niches/${nicheId}/suggest-topics`,
      { method: "POST" },
    ),
  researchNotes: (projectId: number) =>
    request<ResearchNote[]>(`/projects/${projectId}/research-notes`),
  createResearchNote: (projectId: number, title: string, content: string) =>
    request<ResearchNote>(`/projects/${projectId}/research-notes`, {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  updateResearchNote: (noteId: number, title: string, content: string) =>
    request<ResearchNote>(`/research-notes/${noteId}`, {
      method: "PUT",
      body: JSON.stringify({ title, content }),
    }),
  deleteResearchNote: (noteId: number) =>
    request<{ deleted: boolean; id: number }>(`/research-notes/${noteId}`, {
      method: "DELETE",
    }),
  writeScriptFromResearch: (
    noteId: number,
    thinkingLevel?: string,
    model?: string,
  ) =>
    request<Script>(`/research-notes/${noteId}/write-script`, {
      method: "POST",
      body: JSON.stringify({
        thinking_level: thinkingLevel ?? "medium",
        model: model ?? "fast",
      }),
    }),
  // --- Slice 2: Deep Research + StoryCraft options ---
  storycraftOptions: () =>
    request<StorycraftOptions>(`/storycraft/options`),
  deepResearch: (projectId: number, topic: string) =>
    request<ResearchNote>(`/projects/${projectId}/deep-research`, {
      method: "POST",
      body: JSON.stringify({ topic }),
    }),
  // --- HeyGen clone voice (Phase 5 slice 3) ---
  heygenSpeak: (
    projectId: number,
    text: string,
    language: string,
    voiceId?: string,
  ) =>
    request<HeyGenSpeakJob>(`/projects/${projectId}/heygen/speak`, {
      method: "POST",
      body: JSON.stringify({
        text,
        language,
        ...(voiceId ? { voice_id: voiceId } : {}),
      }),
    }),
  heygenVoices: (projectId: number) =>
    request<HeyGenVoice[]>(`/projects/${projectId}/heygen-voices`),
  heygenStatus: () => request<HeyGenStatus>("/heygen/status"),
  projectTimeline: (projectId: number) =>
    request<Timeline>(`/projects/${projectId}/timeline`),
  updateClip: (
    timelineId: number,
    clipId: number,
    patch: { start_s?: number; end_s?: number; caption_text?: string; position?: number; effect?: string },
  ) =>
    request<Timeline>(`/timelines/${timelineId}/clips/${clipId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  applyStyle: (
    timelineId: number,
    patch: { style_dna_id?: number; caption_style_id?: number },
  ) =>
    request<Timeline>(`/timelines/${timelineId}/apply-style`, {
      method: "POST",
      body: JSON.stringify(patch),
    }),
  renderTimeline: (timelineId: number, options?: RenderOptions) =>
    request<Job>(`/timelines/${timelineId}/render`, {
      method: "POST",
      body: JSON.stringify(options ?? {}),
    }),
  // --- One-click run (Phase 3 slice 2) ---
  startRun: (
    projectId: number,
    body: {
      script_id: number;
      voiceover_asset_id?: number;
      voice_text?: string;
      voice?: string;
      caption_style_id?: number;
    },
  ) =>
    request<Run>(`/projects/${projectId}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  run: (runId: number) => request<Run>(`/runs/${runId}`),
  projectRuns: (projectId: number) =>
    request<Run[]>(`/projects/${projectId}/runs`),
  // --- Character Vault (Slice 4) ---
  listVault: () => request<VaultNicheSummary[]>("/vault"),
  getVault: (nicheId: number) =>
    request<VaultNicheDetail>(`/niches/${nicheId}/vault`),
  resolveVault: (nicheId: number) =>
    request<VaultNicheDetail["locked"]>(`/niches/${nicheId}/vault/resolve`),
  createVaultCharacter: (
    nicheId: number,
    body: {
      name: string;
      description: string;
      signature_prop: string;
      role: "main" | "secondary";
      poses?: VaultPose[];
      sheet_path?: string;
    },
  ) =>
    request<VaultCharacter>(`/niches/${nicheId}/vault/characters`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateVaultCharacter: (
    nicheId: number,
    charId: number,
    patch: {
      description?: string;
      signature_prop?: string;
      role?: "main" | "secondary";
      poses?: VaultPose[];
      sheet_path?: string;
    },
  ) =>
    request<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}`,
      { method: "PUT", body: JSON.stringify(patch) },
    ),
  uploadVaultSheet: (nicheId: number, charId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}/sheet`,
      form,
    );
  },
  approveVaultCharacter: (nicheId: number, charId: number) =>
    request<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}/approve`,
      { method: "POST" },
    ),
  lockVaultCharacter: (nicheId: number, charId: number) =>
    request<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}/lock`,
      { method: "POST" },
    ),
  deleteVaultCharacter: (nicheId: number, charId: number) =>
    request<{ deleted: boolean; id: number }>(
      `/niches/${nicheId}/vault/characters/${charId}`,
      { method: "DELETE" },
    ),
  // --- My Main Character (Release Packaging v0.14.0) ---
  getMainCharacter: () =>
    request<{ main_character: VaultCharacter | null }>("/vault/main"),
  createMyCharacter: (form: FormData) =>
    upload<VaultCharacter>("/vault/my-character", form),
  setMainCharacter: (nicheId: number, charId: number) =>
    request<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}/set-main`,
      { method: "POST" },
    ),
  unsetMainCharacter: (nicheId: number, charId: number) =>
    request<VaultCharacter>(
      `/niches/${nicheId}/vault/characters/${charId}/unset-main`,
      { method: "POST" },
    ),
  // --- Update via public GitHub Releases (v0.14.0) ---
  updateCheck: (force = false) =>
    request<UpdateCheck>(`/update/check${force ? "?force=true" : ""}`),
  updateStatus: () => request<UpdateStatus>("/update/status"),
  updateChangelog: () =>
    request<{ available: boolean; version: string; changelog: string }>(
      "/update/changelog",
    ),
  updateApply: (body: { asset_url?: string; dry_run?: boolean }) =>
    request<{ state: string; detail: string; status_url?: string }>(
      "/update/apply",
      { method: "POST", body: JSON.stringify(body) },
    ),
  // --- First-run Setup (v0.14.0) ---
  setupStatus: () => request<SetupStatus>("/setup/status"),
  setupRun: (body: { steps?: string[]; dry_run?: boolean }) =>
    request<SetupRun>("/setup/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setupRunStatus: (runId: string) =>
    request<SetupRun>(`/setup/run/${encodeURIComponent(runId)}`),
  desktopShortcut: () =>
    request<{ created: boolean; path: string }>("/setup/desktop-shortcut", {
      method: "POST",
    }),
  // --- Output folder (v0.14.0) ---
  outputInfo: () => request<OutputInfo>("/output/info"),
  outputOpen: () =>
    request<{ path: string }>("/output/open", { method: "POST" }),
  outputClean: (confirm: boolean) =>
    request<{ deleted_files: number; freed_bytes: number }>("/output/clean", {
      method: "POST",
      body: JSON.stringify({ confirm }),
    }),
  // --- Free keys (v0.14.0) ---
  freeKeys: () => request<FreeKey[]>("/free-keys"),
  testFreeKey: (provider: string) =>
    request<{ provider: string; ok: boolean; message: string }>(
      `/free-keys/${encodeURIComponent(provider)}/test`,
      { method: "POST" },
    ),
  pollinationsTest: (prompt: string) =>
    request<{ prompt: string; path: string; url: string; bytes: number }>(
      "/pollinations/test",
      { method: "POST", body: JSON.stringify({ prompt }) },
    ),
  // --- Magic Mode (Slice 3): topic + script in, finished MP4 out. ---
  getMagicOptions: (projectId: number, language?: string) =>
    request<MagicOptions>(
      `/projects/${projectId}/magic/options${
        language ? `?language=${encodeURIComponent(language)}` : ""
      }`,
    ),
  startMagic: (projectId: number, body: MagicStartBody) =>
    request<MagicRun>(`/projects/${projectId}/magic`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMagic: (projectId: number) =>
    request<MagicRun[]>(`/projects/${projectId}/magic`),
  getMagic: (magicId: number) => request<MagicRun>(`/magic/${magicId}`),
  // --- Per-scene regenerate + deliverables (Phase 3 slice 3) ---
  replaceClipImage: (timelineId: number, clipId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<Timeline>(
      `/timelines/${timelineId}/clips/${clipId}/replace-image`,
      form,
    );
  },
  rerenderTimeline: (timelineId: number, options?: RenderOptions) =>
    request<Job>(`/timelines/${timelineId}/rerender`, {
      method: "POST",
      body: JSON.stringify(options ?? {}),
    }),
  deliverables: (projectId: number) =>
    request<Deliverables>(`/projects/${projectId}/deliverables`),
  generateThumbnail: (projectId: number, timestampS?: number) =>
    request<Thumbnail>(`/projects/${projectId}/thumbnail`, {
      method: "POST",
      body: JSON.stringify(
        timestampS !== undefined ? { timestamp_s: timestampS } : {},
      ),
    }),
  metadata: (projectId: number) =>
    request<YoutubeMetadata>(`/projects/${projectId}/metadata`),
  updateMetadata: (
    projectId: number,
    patch: { title: string; description: string; tags: string },
  ) =>
    request<YoutubeMetadata>(`/projects/${projectId}/metadata`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  generateMetadata: (projectId: number) =>
    request<YoutubeMetadata>(`/projects/${projectId}/metadata/generate`, {
      method: "POST",
    }),
};
