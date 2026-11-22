import { useEffect, useRef, useState } from "react";
import {
  api,
  API_BASE,
  ATMOSPHERE_PRESETS,
  CAPTION_POSITIONS,
  CLIP_EFFECT_LABELS,
  CLIP_EFFECTS,
  MAGIC_STAGES,
  RENDER_QUALITIES,
  VERTICAL_ASPECTS,
  fileUrl,
  srtUrl,
  type Asset,
  type CanvasStatus,
  type CaptionStyle,
  type ChainResolveResult,
  type Character,
  type Clip,
  type Deliverables,
  type FinalClip,
  type FlowQueue,
  type FlowQueueState,
  type FlowStatus,
  type GenerationStatus,
  type GeminiKey,
  type GoogleStatus,
  type Health,
  type HeyGenStatus,
  type HeyGenVoice,
  type Job,
  type KeyRow,
  type KeyTestResult,
  type MagicOptions,
  type MagicRun,
  type MagicStageStatus,
  type MasterPrompt,
  type Moment,
  type Niche,
  type Project,
  type PromptsList,
  type OutputInfo,
  type Reframe,
  type RenderOptions,
  type ResearchNote,
  type Run,
  type Scene,
  type ScenePrompt,
  type Script,
  type ScriptImages,
  type Setting,
  type SetupRun,
  type SetupStatus,
  type SourceVideo,
  type StickmanPose,
  type StickmanPrompt,
  type StickmanPromptsList,
  type StorycraftOptions,
  type StyleDna,
  type Timeline,
  type Transcription,
  type TtsVoice,
  type UpdateCheck,
  type VaultCharacter,
  type VaultNicheDetail,
  type VaultNicheSummary,
  type VoiceProvider,
  type WhisperStatus,
} from "./api";

type Page =
  | "Dashboard"
  | "Projects"
  | "All Tools"
  | "Media Library"
  | "Templates"
  | "Settings";

const PAGES: Page[] = [
  "Dashboard",
  "Projects",
  "All Tools",
  "Media Library",
  "Templates",
  "Settings",
];

// Planned studios/tools. Status is honest: only the Phase 1 foundation
// (projects, assets, jobs, settings, Style DNA) is working; the rest is
// planned for later phases and is labelled as such, never faked as working.
const TOOLS: { name: string; description: string; status: string; color: string; subtitle: string }[] = [
  { name: "VoiceForge", description: "Voiceover, TTS and voice cloning.", status: "Phase 5 — voice library + transcription + HeyGen clone live", color: "#066a6d", subtitle: "Transcription · TTS · Dubbing" },
  { name: "CineCut", description: "Sync timeline: voiceover + images, captions, SRT, MP4 render.", status: "Phase 2 — sync timeline + render live", color: "#bb263e", subtitle: "Timeline · Captions · Effects" },
  { name: "ClipForge", description: "Long video to short clips, AI moments, approval gating.", status: "Phase 6 — complete: upload, transcribe, moments, 9:16 + approved final clips", color: "#b35f18", subtitle: "Auto Clips · Smart Reframing" },
  { name: "StickMan", description: "Stick-figure animation from a script.", status: "Phase 7 — stick-figure prompts + frames live", color: "#8a6d1f", subtitle: "Script → Stick Animation" },
  { name: "Documentary Director", description: "One-click topic to full documentary pipeline.", status: "Phase 3 — complete: one-click run + deliverables", color: "#712cb9", subtitle: "Topic → Finished Video" },
  { name: "VisualForge", description: "Bulk image generation with Style DNA.", status: "Canvas free images live (Gemini Pro quota) + API", color: "#145bd0", subtitle: "Batch Images · Consistency" },
  { name: "StoryCraft", description: "Research, scripts and master prompts.", status: "Deep Research + Thinking Levels live", color: "#5f1bac", subtitle: "Research · Scripts · Prompts" },
  { name: "Motion Studio", description: "Image-to-video and camera motion.", status: "Phase 7 — motion presets live", color: "#b52684", subtitle: "Animation · Image to Video" },
  { name: "Asset Vault", description: "Media library, brand kits, character references.", status: "Phase 1 — asset records live", color: "#286928", subtitle: "Media · References · Brand Kits" },
  { name: "Render Studio", description: "FFmpeg export queue and quality checks.", status: "Phase 7 — motion presets + asset tags + render queue live", color: "#a36f14", subtitle: "Export · Queue · Quality Checks" },
  { name: "Master Prompt Library", description: "Viral-short master prompts — copy ya script me lagayen.", status: "StoryCraft library — alag page", color: "#c9a6ff", subtitle: "Prompts · Reverse-engineer" },
];

// Caption styles the backend can really burn in (cross-check slice):
// the 14 keys of CAPTION_RENDER_SPECS in studio/backend/seed_data.py.
// A style outside this list gets a plain 400 from the render /
// reframe endpoint, so the picker only offers these.
const RENDERABLE_CAPTION_STYLES = [
  "Bold White",
  "Karaoke Yellow",
  "Minimal",
  "Cinema Subtitle",
  "Hormozi Green",
  "Beast Pop",
  "Hormozi Yellow",
  "Simple",
  "Bold Comic",
  "Boxed",
  "Comic Punch",
  "Green Word",
  "Urdu Modern Sans",
  "Urdu Nastaliq-style",
];

// ClipForge reframe / final styles: the 14 static styles PLUS the
// word-level "One Word Pop" (real Whisper word timestamps, one word
// at a time, big yellow, always centred — CineCut can't draw it,
// it has no word timestamps).
const VERTICAL_CAPTION_STYLES = [
  ...RENDERABLE_CAPTION_STYLES,
  "One Word Pop",
];

// ---- Approved-look helpers (copied from ui/ prototypes) ----
// Colours from design/dashboard-layout.svg + ui/00_App_Core/01_dashboard.html.
// Sidebar diamond colours from 01_dashboard.html nav.

const PAGE_ICONS: Record<Page, string> = {
  Dashboard: "⌂",
  Projects: "▤",
  "All Tools": "▦",
  "Media Library": "▧",
  Templates: "◇",
  Settings: "⚙",
};

const STUDIO_NAV: { name: string; color: string }[] = [
  { name: "VoiceForge", color: "#22d7b5" },
  { name: "CineCut", color: "#ff5c7b" },
  { name: "ClipForge", color: "#ff9b43" },
  { name: "StickMan", color: "#f6c45c" },
  { name: "Documentary Director", color: "#bc89ff" },
  { name: "VisualForge", color: "#4a9dff" },
  { name: "StoryCraft", color: "#b58bff" },
  { name: "Master Prompt Library", color: "#c9a6ff" },
  { name: "Motion Studio", color: "#f080ce" },
  { name: "Asset Vault", color: "#4ed79a" },
  { name: "Render Studio", color: "#efc568" },
];

// Dashboard studio grid order from design/dashboard-layout.svg (9 cards).
// v0.14.1: StickMan added as the 10th card — it is a live tool (sidebar
// + All Tools me tha) lekin dashboard par gayab tha; har live tool
// dashboard se khulna chahiye (Issue 3).
const STUDIO_GRID_ORDER = [
  "VoiceForge",
  "StoryCraft",
  "VisualForge",
  "CineCut",
  "ClipForge",
  "StickMan",
  "Documentary Director",
  "Motion Studio",
  "Asset Vault",
  "Render Studio",
];

const QUICK_TOOLS: { name: string; note: string; target: string }[] = [
  { name: "Transcribe", note: "In CineCut", target: "transcribe" },
  { name: "Text to Speech", note: "Try in CineCut", target: "voiceforge" },
  { name: "Generate Images", note: "In VisualForge", target: "visualforge" },
  { name: "Auto Captions", note: "In CineCut", target: "motion" },
  { name: "AI Clipper", note: "In ClipForge", target: "clipforge" },
  { name: "Video Generator", note: "In Documentary Director", target: "director" },
];

/** Settings keys jo API Keys section me hain — Advanced me nahi dikhte. */
const KEY_SETTINGS = new Set([
  "gemini_api_key",
  "openrouter_api_key",
  "groq_api_key",
  "huggingface_api_key",
  "openai_api_key",
  "deepgram_api_key",
  "pexels_api_key",
  "pixabay_api_key",
  "heygen_api_key",
  "elevenlabs_api_key",
]);

/** Har live tool ka CineCut section — Dashboard / sidebar / All Tools
 *  se kholne par isi section par scroll hota hai (v0.14.1). */
const TOOL_SECTIONS: Record<string, string> = {
  VoiceForge: "voiceforge",
  CineCut: "cinecut-top",
  ClipForge: "clipforge",
  StickMan: "stickman",
  "Documentary Director": "director",
  VisualForge: "visualforge",
  StoryCraft: "storycraft",
  "Motion Studio": "motion",
  "Render Studio": "render",
  "Master Prompt Library": "master-prompts",
};

type StageState = "done" | "running" | "failed" | "todo" | "planned";

interface PipelineState {
  script: StageState;
  voice: StageState;
  images: StageState;
  timeline: StageState;
  captions: StageState;
  render: StageState;
  doneCount: number;
}

/** Honest per-project pipeline state, derived only from real API data.
 *  The Script stage is done when the project has a saved script. */
function computePipeline(
  assets: Asset[],
  timeline: Timeline | null,
  jobs: Job[],
  projectId: number,
  hasScript: boolean,
): PipelineState {
  const hasVoice = assets.some((a) => a.kind === "voice");
  const hasImages = assets.some((a) => a.kind === "image");
  const hasTimeline = !!timeline && timeline.clips.length > 0;
  const hasCaptions =
    !!timeline &&
    (timeline.caption_style_id !== null ||
      timeline.clips.some((c) => c.caption_text.trim() !== ""));
  const renderJobs = jobs.filter(
    (j) => j.project_id === projectId && j.kind === "render",
  );
  let render: StageState = "todo";
  if (renderJobs.some((j) => j.status === "done")) render = "done";
  else if (
    renderJobs.some((j) => j.status === "running" || j.status === "queued")
  )
    render = "running";
  else if (renderJobs.some((j) => j.status === "failed")) render = "failed";
  const doneCount = [
    hasScript,
    hasVoice,
    hasImages,
    hasTimeline,
    hasCaptions,
    render === "done",
  ].filter(Boolean).length;
  return {
    script: hasScript ? "done" : "todo",
    voice: hasVoice ? "done" : "todo",
    images: hasImages ? "done" : "todo",
    timeline: hasTimeline ? "done" : "todo",
    captions: hasCaptions ? "done" : "todo",
    render,
    doneCount,
  };
}

function stageLabel(s: StageState): string {
  if (s === "done") return "Done";
  if (s === "running") return "Running";
  if (s === "failed") return "Failed";
  if (s === "planned") return "Planned";
  return "To do";
}

function PipelineBoard({ state }: { state: PipelineState }) {
  const pct = Math.round((state.doneCount / 6) * 100);
  const chips: { label: string; state: StageState }[] = [
    { label: "Script", state: state.script },
    { label: "Voice", state: state.voice },
    { label: "Images", state: state.images },
    { label: "Timeline", state: state.timeline },
    { label: "Captions", state: state.captions },
    { label: "Render", state: state.render },
  ];
  return (
    <div className="pipeline">
      <div className="pipeline-stages">
        {chips.map((c) => (
          <span key={c.label} className={`stage-chip ${c.state}`}>
            {c.label} · {stageLabel(c.state)}
          </span>
        ))}
      </div>
      <div className="meter">
        <i style={{ width: `${pct}%` }} />
      </div>
      <div className="pipeline-note">
        {state.doneCount} of 6 stages done · {pct}%
      </div>
    </div>
  );
}

function ProjectTile({
  project,
  thumb,
  state,
  character,
  onOpen,
}: {
  project: Project;
  thumb: string | null;
  state: PipelineState | null;
  character?: Character | null;
  onOpen: () => void;
}) {
  return (
    <div className="project-tile">
      {thumb ? (
        <img src={thumb} alt={project.name} />
      ) : (
        <div className="tile-thumb">{project.name.charAt(0).toUpperCase()}</div>
      )}
      <div className="project-tile-body">
        <strong>{project.name}</strong>
        <small>Created {project.created_at}</small>
        {character && (
          <small style={{ display: "block", marginTop: 4 }}>
            Main character: {character.name}{" "}
            <img
              src={fileUrl(character.image_path)}
              alt={character.name}
              style={{ width: 28, height: 28, objectFit: "cover", verticalAlign: "middle", borderRadius: 4 }}
            />
          </small>
        )}
        {state && <PipelineBoard state={state} />}
        <div className="form-row" style={{ marginTop: 10, marginBottom: 0 }}>
          <button onClick={onOpen}>Open in CineCut</button>
        </div>
      </div>
    </div>
  );
}
function useLoad<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loader()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

const FREE_VOICES = [
  "en-US-AriaNeural",
  "en-GB-SoniaNeural",
  "hi-IN-MadhurNeural",
  "ur-PK-AsadNeural",
];

/** Magic Mode (Slice 3) stage names + status labels, Roman Urdu. */
const MAGIC_STAGE_NAMES: Record<string, string> = {
  script: "Script",
  images: "Images",
  voice: "Voice",
  timeline: "Timeline",
  captions: "Captions",
  render: "Render",
};

const MAGIC_STATUS_LABELS: Record<MagicStageStatus, string> = {
  queued: "Intezar",
  running: "Chal raha hai",
  done: "Ho gaya",
  failed: "Fail",
  blocked: "Ruka hua",
};

/** Backend error detail (Roman Urdu) out of api.ts's
 *  `400 {"detail": "..."}` error text; plain text passes through. */
function apiErrorDetail(e: unknown): string | null {
  if (!(e instanceof Error)) return null;
  const m = e.message.match(/\{.*\}$/s);
  if (!m) return e.message || null;
  try {
    const parsed = JSON.parse(m[0]) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : e.message;
  } catch {
    return e.message;
  }
}

/** One-click run step names (Phase 3 slice 2). */
const RUN_STEP_NAMES: Record<string, string> = {
  run_script: "Script",
  run_voice: "Voice",
  run_images: "Images",
  run_timeline: "Timeline",
  run_captions: "Captions",
  render: "Render",
};

/** CineCut — Phase 2: voiceover + images, auto-sync timeline, captions,
 *  Style DNA, SRT export and MP4 render. Free-first: the default
 *  voiceover source is an uploaded audio file; the Edge-TTS try is
 *  best-effort and may return a plain 503 on blocked networks. */
function CineCut({
  project,
  projects,
  onPickProject,
  onBack,
  toolTarget,
  onToolTargetShown,
  activeTool,
  onActiveTool,
}: {
  project: Project | null;
  projects: Project[];
  onPickProject: (id: number) => void;
  onBack: () => void;
  /** v0.14.1: Dashboard/sidebar se khola gaya tool (pehle us ke section
   *  par scroll hota tha; fix round 2 se us ka focused view khulta hai). */
  toolTarget: string | null;
  onToolTargetShown: () => void;
  /** v0.14.1 fix round 2: kaunsa tool dikh raha hai — ek waqt par ek. */
  activeTool: string;
  onActiveTool: (t: string) => void;
}) {
  // v0.14.1 fix round 2: focused views — Dashboard/sidebar se khola
  // gaya tool ab scroll nahi karta, us ka focused view khulta hai.
  // Scroll ki zaroorat hi nahi: ek waqt par sirf ek tool render hota hai.
  useEffect(() => {
    if (!project || !toolTarget) return;
    onActiveTool(toolTarget);
    onToolTargetShown();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, toolTarget]);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  // v0.14.1 fix round 2 — focused views ke andar sub-tabs: VoiceForge
  // aur StoryCraft ke stacked sections ab tabs hain, ek waqt par ek.
  const [voiceTab, setVoiceTab] = useState("generate");
  const [storyTab, setStoryTab] = useState("script");
  // Edge-TTS ka EK verdict (list + synthesis probe) — list aur Generate
  // kabhi alag nahi bolenge.
  const [ttsStatus, setTtsStatus] = useState<{
    synthesis_ok: boolean;
    list_source: string;
    reason: string;
  } | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [styles, setStyles] = useState<StyleDna[]>([]);
  const [captionStyles, setCaptionStyles] = useState<CaptionStyle[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<
    Record<number, { start_s: string; end_s: string; caption_text: string }>
  >({});
  const [styleId, setStyleId] = useState("");
  const [captionId, setCaptionId] = useState("");
  const [ttsText, setTtsText] = useState("");
  const [ttsVoice, setTtsVoice] = useState(FREE_VOICES[0]);
  const [renderJob, setRenderJob] = useState<Job | null>(null);
  // Phase 7 slice 2: Motion Studio + Render Studio — quality +
  // atmosphere per render, and the honest render queue (real job
  // rows: status + elapsed time, never a fake progress bar).
  const [renderQuality, setRenderQuality] = useState("1080p");
  const [atmosphere, setAtmosphere] = useState({
    vignette: false,
    grain: false,
    warm: false,
  });
  // Cross-check slice: named atmosphere preset + caption size /
  // position / on-off for the render (AutoCut / ClipNova parity).
  const [atmospherePreset, setAtmospherePreset] = useState("");
  const [captionSizePct, setCaptionSizePct] = useState(100);
  const [captionPosition, setCaptionPosition] = useState("bottom");
  const [captionsOn, setCaptionsOn] = useState(true);
  const [renderQueue, setRenderQueue] = useState<Job[]>([]);
  const [queueNow, setQueueNow] = useState(() => Date.now());
  const [playTime, setPlayTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Phase 3 slice 2: one-click run — script -> voice -> images ->
  // timeline -> captions -> render, with per-step progress.
  const [oneClickRun, setOneClickRun] = useState<Run | null>(null);
  const [runVoiceSource, setRunVoiceSource] = useState<"upload" | "tts">(
    "upload",
  );
  const [runCaptionId, setRunCaptionId] = useState("");
  // Magic Mode (Slice 3): topic + script in, finished MP4 out.
  // Voice select value is "upload:<assetId>" | "edge:<voiceId>" |
  // "heygen:<voiceId>" — one select, three real groups, no fake voice.
  const [magicOptions, setMagicOptions] = useState<MagicOptions | null>(null);
  const [magicOptionsError, setMagicOptionsError] = useState<string | null>(null);
  const [magicRun, setMagicRun] = useState<MagicRun | null>(null);
  const [magicTopic, setMagicTopic] = useState("");
  const [magicScript, setMagicScript] = useState("");
  const [magicVoiceSel, setMagicVoiceSel] = useState("");
  const [magicCaptionId, setMagicCaptionId] = useState("");
  const [magicStyleDnaId, setMagicStyleDnaId] = useState("");
  const [magicAspect, setMagicAspect] = useState("16:9");
  const [magicLanguage, setMagicLanguage] = useState("en");
  const [magicError, setMagicError] = useState<string | null>(null);
  const [magicStarting, setMagicStarting] = useState(false);
  // Phase 2 slice 2: main character + per-image scene texts (script beats)
  // + the live Edge-TTS voice list when it is actually reachable.
  const [character, setCharacter] = useState<Character | null>(null);
  const [charName, setCharName] = useState("");
  const [charFile, setCharFile] = useState<File | null>(null);
  const [sceneTexts, setSceneTexts] = useState<Record<number, string>>({});
  const [ttsVoices, setTtsVoices] = useState<TtsVoice[]>([]);
  // Phase 7 slice 3: VoiceForge provider registry — built-ins plus
  // separately-added providers (e.g. A123 Pro later).
  const [voiceProviders, setVoiceProviders] = useState<VoiceProvider[]>([]);
  const [voicesLive, setVoicesLive] = useState(false);
  // Phase 5 slice 1: VoiceForge library — filter, sample preview,
  // favourite default voice.
  const [defaultVoice, setDefaultVoice] = useState("en-US-AriaNeural");
  const [voiceFilter, setVoiceFilter] = useState("All");
  const [previewVoice, setPreviewVoice] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  // Phase 5 slice 2: local Whisper transcription — cached models only,
  // never a download.
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([]);
  const [transcription, setTranscription] = useState<Transcription | null>(
    null,
  );
  const [trFile, setTrFile] = useState<File | null>(null);
  const [trModel, setTrModel] = useState("tiny");
  const [trBusy, setTrBusy] = useState(false);
  const [trError, setTrError] = useState<string | null>(null);
  const [trUseAsScriptBusy, setTrUseAsScriptBusy] = useState(false);
  // Cross-check slice: edit the transcript text (ClipNova Library parity).
  // Only full_text changes — word timings and SRT/VTT keep the original
  // Whisper segments, so captions never drift from the audio.
  const [trEditing, setTrEditing] = useState(false);
  const [trEditText, setTrEditText] = useState("");
  const [trEditBusy, setTrEditBusy] = useState(false);
  const [whisperStatus, setWhisperStatus] = useState<WhisperStatus | null>(
    null,
  );
  // Phase 5 slice 3: HeyGen clone voice — Ale's own voice. No live
  // call without his say-so each time; the key lives in Settings.
  const [heygenVoices, setHeygenVoices] = useState<HeyGenVoice[]>([]);
  const [heygenStatus, setHeygenStatus] = useState<HeyGenStatus | null>(null);
  const [heygenText, setHeygenText] = useState("");
  const [heygenLang, setHeygenLang] = useState("en");
  const [heygenBusy, setHeygenBusy] = useState(false);
  const [heygenError, setHeygenError] = useState<string | null>(null);
  const [heygenJobId, setHeygenJobId] = useState<number | null>(null);
  // Phase 6 slice 1: ClipForge — long video upload + local Whisper
  // transcription (cached models only, never a download).
  const [sourceVideos, setSourceVideos] = useState<SourceVideo[]>([]);
  const [sourceVideo, setSourceVideo] = useState<SourceVideo | null>(null);
  const [svFile, setSvFile] = useState<File | null>(null);
  const [svBusy, setSvBusy] = useState(false);
  const [svError, setSvError] = useState<string | null>(null);
  // Phase 6 slice 2: ClipForge moments — scored from the real word
  // timestamps (density / keywords / silence / length). No approval
  // gating or rendering here — that is slice 4.
  const [moments, setMoments] = useState<Moment[]>([]);
  const [momentsBusy, setMomentsBusy] = useState(false);
  const [momentsError, setMomentsError] = useState<string | null>(null);
  const [momentsNote, setMomentsNote] = useState<string | null>(null);
  // Phase 6 slice 3: ClipForge 9:16 reframe + captions — one vertical
  // preview per moment, centre-cropped to 1080x1920 with the moment's
  // real segments burned in. Face tracking comes later; this slice
  // never claims it. Keyed by moment id; style per moment, default
  // Bold White.
  const [reframesByMoment, setReframesByMoment] = useState<
    Record<number, Reframe[]>
  >({});
  const [reframeStyleByMoment, setReframeStyleByMoment] = useState<
    Record<number, string>
  >({});
  // Cross-check slice: aspect / size / position / captions per
  // moment (ClipNova parity — 9:16 / 1:1 / 4:5 / 3:4, size %,
  // position, captions on/off). Defaults match the old behaviour.
  const [reframeAspectByMoment, setReframeAspectByMoment] = useState<
    Record<number, string>
  >({});
  const [reframeSizeByMoment, setReframeSizeByMoment] = useState<
    Record<number, number>
  >({});
  const [reframePositionByMoment, setReframePositionByMoment] = useState<
    Record<number, string>
  >({});
  const [reframeCaptionsByMoment, setReframeCaptionsByMoment] = useState<
    Record<number, boolean>
  >({});
  // Cross-check slice: moment controls (ClipNova parity — clips
  // count Auto/1/3/5/10/15, length Auto/15/25/30/40/60/90).
  const [momentsMax, setMomentsMax] = useState(5);
  const [momentsTargetLength, setMomentsTargetLength] = useState("");
  const [reframeBusyByMoment, setReframeBusyByMoment] = useState<
    Record<number, boolean>
  >({});
  const [reframeErrorByMoment, setReframeErrorByMoment] = useState<
    Record<number, string | null>
  >({});
  // Phase 6 slice 4: ClipForge approval gating + final render — only
  // APPROVED moments render as final clips. One final clip per
  // moment; a re-render reuses the row. Final clips for the selected
  // source video, with rename drafts keyed by clip id.
  const [finalClips, setFinalClips] = useState<FinalClip[]>([]);
  const [finalBusyByMoment, setFinalBusyByMoment] = useState<
    Record<number, boolean>
  >({});
  const [finalErrorByMoment, setFinalErrorByMoment] = useState<
    Record<number, string | null>
  >({});
  const [renameDraftByClip, setRenameDraftByClip] = useState<
    Record<number, string>
  >({});
  const svVideoRef = useRef<HTMLVideoElement | null>(null);
  // Phase 3 slice 1: script + scene breakdown (Documentary Director)
  const [scripts, setScripts] = useState<Script[]>([]);
  const [script, setScript] = useState<Script | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [scriptTopic, setScriptTopic] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [sceneDrafts, setSceneDrafts] = useState<
    Record<number, { text: string; image_prompt: string; duration_s: string }>
  >({});
  // Phase 3 slice 3: per-scene regenerate + deliverables (MP4,
  // thumbnail from the real render, YouTube title/description/tags).
  const [deliverables, setDeliverables] = useState<Deliverables | null>(null);
  const [prompts, setPrompts] = useState<PromptsList | null>(null);
  // Phase 4 slice 2: bulk image generation — per-scene status + quota.
  const [genStatus, setGenStatus] = useState<GenerationStatus | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  // VisualForge provider: 'api' (Gemini API — reliable, billing),
  // 'canvas' (Gemini Canvas — free, user's Gemini Pro quota) or
  // 'flow' (Google Flow — free, same Gemini Pro quota, same Google
  // login; fails on a scene → Canvas fallback). Canvas stays the
  // default free provider.
  const [imageProvider, setImageProvider] = useState<
    "api" | "canvas" | "flow"
  >("canvas");
  const [canvasStatus, setCanvasStatus] = useState<CanvasStatus | null>(
    null,
  );
  const [canvasLoginBusy, setCanvasLoginBusy] = useState(false);
  // Connect Google: one sign-in for Canvas + Flow (Settings section
  // and the VisualForge Flow status line share this).
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(
    null,
  );
  const [googleLoginBusy, setGoogleLoginBusy] = useState(false);
  const [googleDisconnectBusy, setGoogleDisconnectBusy] = useState(false);
  // Slice 5: Flow provider hardening — per-account status, Fast
  // mode, queue pause/resume + history, #/@ chaining preview.
  const [flowStatus, setFlowStatus] = useState<FlowStatus | null>(null);
  const [flowBusy, setFlowBusy] = useState(false);
  const [flowQueues, setFlowQueues] = useState<FlowQueue[]>([]);
  const [flowQueueState, setFlowQueueState] = useState<FlowQueueState | null>(
    null,
  );
  const [chainPrompt, setChainPrompt] = useState("");
  const [chainPreview, setChainPreview] = useState<ChainResolveResult | null>(
    null,
  );
  const flowReadyAccount =
    flowStatus?.accounts.find((a) => a.ready) ?? null;
  // Cross-check slice: StickFilm character/style-match toggles — off
  // means the prompt drops the character words (and reference image)
  // or the style words, so a scene can be generated free of them.
  const [characterMatch, setCharacterMatch] = useState(true);
  const [styleMatch, setStyleMatch] = useState(true);
  // Phase 4 slice 3: image verification — candidate images per scene
  // with Ale's verdict; only approved images go into a timeline.
  const [scriptImages, setScriptImages] = useState<ScriptImages | null>(null);
  const [vfBusy, setVfBusy] = useState(false);
  const [useApprovedSummary, setUseApprovedSummary] = useState<string | null>(
    null,
  );
  const [rejectReasons, setRejectReasons] = useState<Record<number, string>>(
    {},
  );
  const [attachAssetIds, setAttachAssetIds] = useState<Record<number, string>>(
    {},
  );
  const [copiedPromptId, setCopiedPromptId] = useState<number | null>(null);
  const [thumbTs, setThumbTs] = useState("");
  const [metaDraft, setMetaDraft] = useState({
    title: "",
    description: "",
    tags: "",
  });
  // Phase 7 slice 1: StickMan — template-built stick-figure prompts
  // per scene (no AI call, no key) + real rendered PNG frames.
  // Frames are plain project images: approve in VisualForge and
  // "Use approved in timeline" puts them in the CineCut timeline.
  // Stickman is a tool, never the default video style.
  const [stickmanPoses, setStickmanPoses] = useState<StickmanPose[]>([]);
  const [stickman, setStickman] = useState<StickmanPromptsList | null>(null);
  const [stickmanBusy, setStickmanBusy] = useState(false);
  const [frameBusyByScene, setFrameBusyByScene] = useState<
    Record<number, boolean>
  >({});
  const [framePoseByScene, setFramePoseByScene] = useState<
    Record<number, string>
  >({});
  const [stickmanPromptDrafts, setStickmanPromptDrafts] = useState<
    Record<number, StickmanPrompt>
  >({});
  const [editingPoseId, setEditingPoseId] = useState<number | null>(null);
  const [poseDescDraft, setPoseDescDraft] = useState("");
  // Phase 7 slice 1: StoryCraft — Master Prompt library (seeded from
  // the real inspiration-video patterns) + research notes per project.
  const [masterPrompts, setMasterPrompts] = useState<MasterPrompt[]>([]);
  const [copiedMasterId, setCopiedMasterId] = useState<number | null>(null);
  const [newMaster, setNewMaster] = useState({
    name: "",
    category: "hook",
    template: "",
    source: "",
  });
  const [masterBusy, setMasterBusy] = useState(false);
  // Cross-check slice: Niches (AutoCut Writer / Video 7 parity) +
  // Style DNA from description (StickFilm "New category") +
  // reverse-engineer (WAPCut Master Prompt Studio) + import.
  const [niches, setNiches] = useState<Niche[]>([]);
  const [newNiche, setNewNiche] = useState({
    name: "",
    description: "",
    main_characters: "",
  });
  const [nicheBusy, setNicheBusy] = useState(false);
  const [topicsByNiche, setTopicsByNiche] = useState<
    Record<number, string[]>
  >({});
  const [topicsBusyByNiche, setTopicsBusyByNiche] = useState<
    Record<number, boolean>
  >({});
  const [styleBuilder, setStyleBuilder] = useState({
    name: "",
    description: "",
  });
  const [styleBuilderBusy, setStyleBuilderBusy] = useState(false);
  const [reverseNotes, setReverseNotes] = useState("");
  const [reverseName, setReverseName] = useState("");
  const [reverseBusy, setReverseBusy] = useState(false);
  const [researchNotes, setResearchNotes] = useState<ResearchNote[]>([]);
  const [newNoteTitle, setNewNoteTitle] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");
  const [noteDrafts, setNoteDrafts] = useState<
    Record<number, { title: string; content: string }>
  >({});
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [researchBusy, setResearchBusy] = useState(false);
  // Slice 2: Deep Research + Thinking Levels + Model picker. One
  // shared pair of pickers drives both topic scripts (Script
  // section) and write-script-from-research; the options come from
  // the backend so the UI never offers a level/model it does not know.
  const [thinkingLevel, setThinkingLevel] = useState("medium");
  const [scriptModel, setScriptModel] = useState("fast");
  const [storycraftOptions, setStorycraftOptions] =
    useState<StorycraftOptions | null>(null);
  const [deepResearchTopic, setDeepResearchTopic] = useState("");
  const [deepResearchBusy, setDeepResearchBusy] = useState(false);
  // Slice 4: Character Vault — per-niche locked character sheets.
  // List + one expanded niche's detail; every mutation reloads both.
  const [vaultList, setVaultList] = useState<VaultNicheSummary[]>([]);
  const [vaultError, setVaultError] = useState<string | null>(null);
  const [expandedVaultId, setExpandedVaultId] = useState<number | null>(
    null,
  );
  const [vaultDetailByNiche, setVaultDetailByNiche] = useState<
    Record<number, VaultNicheDetail>
  >({});
  const [vaultBusy, setVaultBusy] = useState(false);
  const [newVaultChar, setNewVaultChar] = useState({
    name: "",
    description: "",
    signature_prop: "",
    role: "main" as "main" | "secondary",
  });
  const [editingVaultCharId, setEditingVaultCharId] = useState<number | null>(
    null,
  );
  const [vaultEditDraft, setVaultEditDraft] = useState({
    description: "",
    signature_prop: "",
    role: "main" as "main" | "secondary",
  });
  // Release Packaging (v0.14.0): my main character (Vault section).
  // Update / setup / output / free keys ka state App() me hai —
  // Dashboard aur Settings wahan render hote hain.
  const [mainCharacter, setMainCharacter] = useState<VaultCharacter | null>(
    null,
  );
  const [showMyCharForm, setShowMyCharForm] = useState(false);
  const [myCharForm, setMyCharForm] = useState({
    name: "",
    description: "",
    niche_id: "",
    signature_prop: "",
  });
  const [myCharFile, setMyCharFile] = useState<File | null>(null);
  const [myCharBusy, setMyCharBusy] = useState(false);
  const [myChars, setMyChars] = useState<VaultCharacter[]>([]);
  const [myCharsBusy, setMyCharsBusy] = useState(false);
  const [myCharsLoaded, setMyCharsLoaded] = useState(false);
  // Magic Mode + VisualForge niche picks (Slice 4): "" = no Vault.
  const [magicNicheId, setMagicNicheId] = useState("");
  const [vfNicheId, setVfNicheId] = useState("");

  async function reload() {
    if (!project) return;
    try {
      const [tl, as, st, cs, ch, vv, sc, dl] = await Promise.all([
        api.projectTimeline(project.id).catch(() => null),
        api.assets(project.id),
        api.styleDna(),
        api.captionStyles(),
        api.character(project.id).catch(() => null),
        api.ttsVoices().catch(() => null),
        api.scripts(project.id).catch(() => [] as Script[]),
        api.deliverables(project.id).catch(() => null),
      ]);
      setTimeline(tl);
      setAssets(as);
      setStyles(st);
      setCaptionStyles(cs);
      setCharacter(ch);
      setDeliverables(dl);
      if (dl?.metadata) {
        setMetaDraft({
          title: dl.metadata.title,
          description: dl.metadata.description,
          tags: dl.metadata.tags,
        });
      }
      if (ch) setCharName(ch.name);
      if (vv && vv.voices.length > 0) {
        setTtsVoices(vv.voices);
        setVoicesLive(vv.available);
        setTtsStatus({
          synthesis_ok: vv.synthesis_ok,
          list_source: vv.list_source,
          reason: vv.reason,
        });
        if (vv.default_voice) setDefaultVoice(vv.default_voice);
      } else {
        setTtsVoices([]);
        setVoicesLive(false);
        setTtsStatus(null);
      }
      setVoiceProviders(vv?.providers ?? []);
      if (tl) {
        setStyleId(tl.style_dna_id ? String(tl.style_dna_id) : "");
        setCaptionId(tl.caption_style_id ? String(tl.caption_style_id) : "");
      }
      setScripts(sc);
      // Phase 5 slice 2: transcription list + Whisper status (cached
      // models only). The status probe is cached server-side, so this
      // costs ~1 s only on the first load of the session.
      void api
        .listTranscriptions(project.id)
        .then((trs) => {
          setTranscriptions(trs);
          setTranscription(null);
        })
        .catch(() => undefined);
      void api
        .whisperStatus()
        .then((w) => {
          setWhisperStatus(w);
          setTrModel((cur) =>
            w.models_cached.includes(cur)
              ? cur
              : (w.models_cached[0] ?? cur),
          );
        })
        .catch(() => undefined);
      // Phase 5 slice 3: HeyGen clone status + finished clone VOs.
      void api
        .heygenStatus()
        .then(setHeygenStatus)
        .catch(() => undefined);
      void api
        .heygenVoices(project.id)
        .then(setHeygenVoices)
        .catch(() => undefined);
      // Phase 6 slice 1: ClipForge source videos for this project.
      void api
        .listSourceVideos(project.id)
        .then((svs) => {
          setSourceVideos(svs);
          setSourceVideo(null);
          setMoments([]);
          setMomentsNote(null);
          setMomentsError(null);
          setReframesByMoment({});
          setFinalClips([]);
          setFinalErrorByMoment({});
          setRenameDraftByClip({});
        })
        .catch(() => undefined);
      // Phase 7 slice 1: StoryCraft — master prompt library (shared)
      // + research notes for this project. Cross-check slice: niches.
      void api
        .masterPrompts()
        .then(setMasterPrompts)
        .catch(() => undefined);
      void api.niches().then(setNiches).catch(() => undefined);
      // Slice 4: Character Vault summary — live guard status per niche.
      void api
        .listVault()
        .then((v) => {
          setVaultList(v);
          setVaultError(null);
        })
        .catch((e) => setVaultError(apiErrorDetail(e) ?? "Vault load nahi hua."));
      void api
        .researchNotes(project.id)
        .then(setResearchNotes)
        .catch(() => undefined);
      // Slice 2: Thinking Levels + model picker options (backend).
      void api
        .storycraftOptions()
        .then(setStorycraftOptions)
        .catch(() => undefined);
      void api.stickmanPoses().then(setStickmanPoses).catch(() => undefined);
      const latest = sc[0] ?? null;
      setScript(latest);
      if (latest) {
        const ss = await api
          .scriptScenes(latest.id)
          .catch(() => [] as Scene[]);
        setScenes(ss);
        setScriptTopic(latest.topic);
        setScriptText(latest.full_text);
        void loadPrompts(latest.id);
        void loadStickmanPrompts(latest.id);
      } else {
        setScenes([]);
        setPrompts(null);
        setScriptImages(null);
        setGenStatus(null);
        setStickman(null);
        setStickmanPromptDrafts({});
      }
      setSceneDrafts({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load CineCut");
    }
  }

  useEffect(() => {
    void reload();
    setRenderJob(null);
    setOneClickRun(null);
    setGenStatus(null);
    setScriptImages(null);
    setUseApprovedSummary(null);
    setRunCaptionId("");
    setMagicOptions(null);
    setMagicOptionsError(null);
    setMagicRun(null);
    setMagicTopic("");
    setMagicScript("");
    setMagicVoiceSel("");
    setMagicCaptionId("");
    setMagicStyleDnaId("");
    setMagicAspect("16:9");
    setMagicLanguage("en");
    setMagicError(null);
    setDrafts({});
    setNotice(null);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  useEffect(() => {
    if (!renderJob || renderJob.status === "done" || renderJob.status === "failed") {
      return;
    }
    const id = setInterval(() => {
      api
        .job(renderJob.id)
        .then(setRenderJob)
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
  }, [renderJob]);

  // Phase 7 slice 2: render queue — real render-job rows for this
  // project, reloaded with the page and polled while any job is
  // queued/running. Elapsed time is (updated - created) for finished
  // jobs and (now - created) for active ones — never invented.
  async function loadRenderQueue() {
    if (!project) return;
    try {
      const all = await api.jobs("render");
      setRenderQueue(
        all.filter((j) => j.project_id === project.id).slice(0, 20),
      );
    } catch {
      // The queue is a view, not a gate — a failed load leaves the
      // last list in place and the render button still works.
    }
  }

  useEffect(() => {
    void loadRenderQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  useEffect(() => {
    const active = renderQueue.some(
      (j) => j.status === "queued" || j.status === "running",
    );
    if (!active) return;
    const id = setInterval(() => {
      setQueueNow(Date.now());
      void loadRenderQueue();
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderQueue]);

  // One-click run progress: poll the run until it finishes or fails.
  useEffect(() => {
    if (
      !oneClickRun ||
      oneClickRun.status === "done" ||
      oneClickRun.status === "failed"
    ) {
      return;
    }
    const id = setInterval(() => {
      api
        .run(oneClickRun.id)
        .then((r) => {
          setOneClickRun(r);
          if (r.status === "done") void reload();
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oneClickRun?.id, oneClickRun?.status]);

  // Magic Mode (Slice 3): form options + latest run when the project
  // opens; the Edge-TTS voice list follows the picked language.
  function magicDefaultVoiceSel(opts: MagicOptions): string {
    const d = opts.defaults;
    if (d.voice_kind === "upload" && d.vo_asset_id != null) {
      return `upload:${d.vo_asset_id}`;
    }
    if (
      d.voice_kind === "heygen" &&
      opts.voices.heygen.available &&
      opts.voices.heygen.voice_id
    ) {
      return `heygen:${opts.voices.heygen.voice_id}`;
    }
    return `edge:${d.voice_id}`;
  }

  async function loadMagicOptions(language: string) {
    if (!project) return;
    try {
      const opts = await api.getMagicOptions(project.id, language);
      setMagicOptions(opts);
      setMagicOptionsError(null);
      // Smart defaults from the backend — user kuch na chune to bhi
      // Start chal jaye. A pick already made is kept when still valid.
      const valid = new Set<string>([
        ...opts.voices.uploaded.map((v) => `upload:${v.id}`),
        ...opts.voices.edge.list.map((v) => `edge:${v.id}`),
        ...(opts.voices.heygen.available && opts.voices.heygen.voice_id
          ? [`heygen:${opts.voices.heygen.voice_id}`]
          : []),
      ]);
      setMagicVoiceSel((prev) =>
        prev && valid.has(prev) ? prev : magicDefaultVoiceSel(opts),
      );
      setMagicCaptionId((prev) =>
        prev ||
        (opts.defaults.caption_style_id != null
          ? String(opts.defaults.caption_style_id)
          : ""),
      );
      setMagicStyleDnaId((prev) =>
        prev ||
        (opts.defaults.style_dna_id != null
          ? String(opts.defaults.style_dna_id)
          : ""),
      );
      setMagicAspect((prev) => prev || opts.defaults.aspect || "16:9");
    } catch (e) {
      setMagicOptions(null);
      // A network/CORS failure ("Failed to fetch") carries no backend
      // detail — show a plain Roman Urdu message instead of raw text.
      const detail = apiErrorDetail(e);
      setMagicOptionsError(
        detail && !/failed to fetch/i.test(detail)
          ? detail
          : "Magic options load nahi hue — backend se options nahi mile. Page reload karein ya backend check karein.",
      );
    }
  }

  async function loadLatestMagic() {
    if (!project) return;
    try {
      const list = await api.listMagic(project.id);
      setMagicRun(list[0] ?? null);
    } catch {
      // The latest run is a view, not a gate — a failed load leaves
      // the form usable and Start still works.
    }
  }

  useEffect(() => {
    if (!project) return;
    void loadMagicOptions("en");
    void loadLatestMagic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  // Magic Mode progress: poll the run until it finishes or fails.
  useEffect(() => {
    if (
      !magicRun ||
      magicRun.status === "done" ||
      magicRun.status === "failed"
    ) {
      return;
    }
    const id = setInterval(() => {
      api
        .getMagic(magicRun.id)
        .then((r) => {
          setMagicRun(r);
          if (r.status === "done") void reload();
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [magicRun?.id, magicRun?.status]);

  // Transcription progress: poll the selected transcription until its
  // job finishes or fails.
  useEffect(() => {
    if (
      !transcription ||
      transcription.job_status === "done" ||
      transcription.job_status === "failed"
    ) {
      return;
    }
    const id = setInterval(() => {
      api
        .getTranscription(transcription.id)
        .then((t) => {
          setTranscription(t);
          if (t.job_status === "done" || t.job_status === "failed") {
            if (project) {
              void api
                .listTranscriptions(project.id)
                .then(setTranscriptions)
                .catch(() => undefined);
            }
          }
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcription?.id, transcription?.job_status]);

  // ClipForge source video progress: poll the selected source video
  // until its transcription finishes or fails.
  useEffect(() => {
    if (
      !sourceVideo ||
      sourceVideo.job_status === "done" ||
      sourceVideo.job_status === "failed"
    ) {
      return;
    }
    const id = setInterval(() => {
      api
        .getSourceVideo(sourceVideo.id)
        .then((sv) => {
          setSourceVideo(sv);
          if (sv.job_status === "done" || sv.job_status === "failed") {
            if (project) {
              void api
                .listSourceVideos(project.id)
                .then(setSourceVideos)
                .catch(() => undefined);
            }
          }
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceVideo?.id, sourceVideo?.job_status]);

  // Phase 6 slice 3: poll 9:16 reframes while any is queued/running.
  const reframePollKey = moments
    .map((m) =>
      (reframesByMoment[m.id] ?? []).map((r) => r.job_status).join("/"),
    )
    .join("|");
  useEffect(() => {
    const busy = moments.some((m) =>
      (reframesByMoment[m.id] ?? []).some(
        (r) => r.job_status === "queued" || r.job_status === "running",
      ),
    );
    if (!busy) return;
    const id = setInterval(() => {
      void Promise.all(
        moments.map((m) =>
          api
            .listReframes(m.id)
            .then((rs) =>
              setReframesByMoment((prev) => ({ ...prev, [m.id]: rs })),
            )
            .catch(() => undefined),
        ),
      );
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reframePollKey]);

  // Phase 6 slice 4: poll final clips while any render is
  // queued/running.
  const finalClipPollKey = finalClips.map((c) => c.job_status).join("/");
  useEffect(() => {
    const busy = finalClips.some(
      (c) => c.job_status === "queued" || c.job_status === "running",
    );
    if (!busy || !sourceVideo) return;
    const id = setInterval(() => {
      void api
        .listFinalClipsBySourceVideo(sourceVideo.id)
        .then(setFinalClips)
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finalClipPollKey]);

  // VisualForge bulk generation progress: poll while any scene is
  // queued or generating.
  useEffect(() => {
    if (
      !genStatus ||
      !genStatus.scenes.some(
        (s) => s.status === "queued" || s.status === "running",
      )
    ) {
      return;
    }
    const id = setInterval(() => {
      api
        .generationStatus(genStatus.script_id)
        .then(setGenStatus)
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genStatus?.script_id, genStatus?.scenes.map((s) => s.status).join(",")]);

  const voice = [...assets].reverse().find((a) => a.kind === "voice");
  // Placeholder title cards are real image files, but they are not
  // uploads — keep them out of the scene-text / auto-sync image list.
  const images = assets.filter(
    (a) => a.kind === "image" && !a.placeholder,
  );
  // Phase 4 slice 3: candidate images per scene (verification list),
  // keyed by scene id, plus the verdict counts for the summary line.
  const vfImagesByScene = new Map<
    number,
    ScriptImages["scenes"][number]["images"]
  >();
  scriptImages?.scenes.forEach((s) => vfImagesByScene.set(s.scene_id, s.images));
  const vfAllImages = [...vfImagesByScene.values()].flat();
  const vfApprovedCount = vfAllImages.filter(
    (im) => im.verdict === "approved",
  ).length;
  const vfPendingCount = vfAllImages.filter(
    (im) => im.verdict === "pending",
  ).length;
  const vfRejectedCount = vfAllImages.filter(
    (im) => im.verdict === "rejected",
  ).length;
  const currentClip: Clip | undefined =
    timeline?.clips.find((c) => playTime >= c.start_s && playTime < c.end_s) ??
    timeline?.clips[timeline.clips.length - 1];

  async function run<T>(fn: () => Promise<T>, okMsg?: string): Promise<T | null> {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const out = await fn();
      if (okMsg) setNotice(okMsg);
      return out;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onVoiceFile(file: File | undefined) {
    if (!project || !file) return;
    const res = await run(() => api.uploadVoice(project.id, file));
    if (res) {
      setNotice(`Voiceover uploaded (${res.duration_s}s). Now auto-sync.`);
      await reload();
    }
  }

  async function onImageFiles(files: FileList | null) {
    if (!project || !files || files.length === 0) return;
    const res = await run(() => api.uploadImages(project.id, [...files]));
    if (res) {
      setNotice(`${res.length} image(s) uploaded. Now auto-sync.`);
      await reload();
    }
  }

  async function onTts() {
    if (!project || !ttsText.trim()) return;
    const res = await run(() => api.tts(project.id, ttsText.trim(), ttsVoice));
    if (res) {
      setNotice(`Voice generated (${res.duration_s}s). Now auto-sync.`);
      await reload();
    }
  }

  // Phase 5 slice 1: play a short sample of one library voice. The
  // sample is generated once by the backend and cached; where Edge-TTS
  // is blocked the backend answers 503 and the error is shown plainly.
  async function onPreviewVoice(voiceId: string) {
    setPreviewVoice(voiceId);
    setPreviewError(null);
    try {
      const res = await api.ttsPreview(voiceId);
      setPlayingUrl(`http://127.0.0.1:8000${res.url}`);
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setPreviewVoice(null);
    }
  }

  async function onSetDefaultVoice(voiceId: string) {
    const res = await run(() =>
      api.updateSetting("default_tts_voice", voiceId),
    );
    if (res) {
      setDefaultVoice(voiceId);
      setNotice(`Default voice set to ${voiceId}.`);
    }
  }

  // --- Local Whisper transcription (Phase 5 slice 2) ---
  async function onTranscribe() {
    if (!project || !trFile) return;
    setTrError(null);
    setTrBusy(true);
    try {
      const res = await api.transcribe(project.id, trFile, trModel);
      setNotice(
        `Transcription queued (job #${res.job_id}) — ${trModel} model, free offline.`,
      );
      const trs = await api.listTranscriptions(project.id);
      setTranscriptions(trs);
      setTranscription(
        trs.find((t) => t.id === res.transcription_id) ?? null,
      );
    } catch (e) {
      setTrError(e instanceof Error ? e.message : "Transcription failed");
    } finally {
      setTrBusy(false);
    }
  }

  async function onSelectTranscription(id: number) {
    if (!id) return;
    try {
      setTranscription(await api.getTranscription(id));
    } catch (e) {
      setTrError(
        e instanceof Error ? e.message : "Failed to load transcription",
      );
    }
  }

  // --- ClipForge long video (Phase 6 slice 1) ---
  async function onUploadSourceVideo() {
    if (!project || !svFile) return;
    setSvError(null);
    setSvBusy(true);
    try {
      const res = await api.uploadSourceVideo(project.id, svFile, trModel);
      setNotice(
        `Long video queued (job #${res.job_id}) — ${res.duration_s}s, ${trModel} model, free offline.`,
      );
      const svs = await api.listSourceVideos(project.id);
      setSourceVideos(svs);
      setSourceVideo(
        svs.find((s) => s.id === res.source_video_id) ?? null,
      );
    } catch (e) {
      setSvError(e instanceof Error ? e.message : "Source video upload failed");
    } finally {
      setSvBusy(false);
    }
  }

  async function onSelectSourceVideo(id: number) {
    if (!id) return;
    try {
      setSourceVideo(await api.getSourceVideo(id));
      const ms = await api.listMoments(id);
      setMoments(ms);
      setMomentsNote(null);
      setMomentsError(null);
      void loadReframesForMoments(ms);
      void api
        .listFinalClipsBySourceVideo(id)
        .then(setFinalClips)
        .catch(() => undefined);
    } catch (e) {
      setSvError(
        e instanceof Error ? e.message : "Failed to load source video",
      );
    }
  }

  // --- ClipForge moments (Phase 6 slice 2) ---
  async function onDetectMoments() {
    if (!sourceVideo) return;
    setMomentsError(null);
    setMomentsNote(null);
    setMomentsBusy(true);
    try {
      const res = await api.detectMoments(sourceVideo.id, {
        max_moments: momentsMax,
        target_length_s: momentsTargetLength
          ? Number(momentsTargetLength)
          : null,
      });
      setMoments(res.moments);
      setMomentsNote(res.note);
      void loadReframesForMoments(res.moments);
      void api
        .listFinalClipsBySourceVideo(sourceVideo.id)
        .then(setFinalClips)
        .catch(() => undefined);
      setNotice(
        res.count > 0
          ? `${res.count} moment(s) mil gaye — best score ${Math.max(
              ...res.moments.map((m) => m.score),
            )}.`
          : "Koi moment nahi bana.",
      );
    } catch (e) {
      setMomentsError(
        e instanceof Error ? e.message : "Moment detection failed",
      );
    } finally {
      setMomentsBusy(false);
    }
  }

  function onPreviewMoment(start_s: number) {
    const video = svVideoRef.current;
    if (!video) return;
    video.currentTime = start_s;
    void video.play();
  }

  // --- ClipForge 9:16 reframe + captions (Phase 6 slice 3) ---
  async function loadReframesForMoments(ms: Moment[]) {
    const entries = await Promise.all(
      ms.map(async (m): Promise<[number, Reframe[]]> => {
        try {
          return [m.id, await api.listReframes(m.id)];
        } catch {
          return [m.id, []];
        }
      }),
    );
    setReframesByMoment((prev) => {
      const next = { ...prev };
      for (const [id, rs] of entries) next[id] = rs;
      return next;
    });
  }

  async function onReframeMoment(m: Moment) {
    const style = reframeStyleByMoment[m.id] || "Bold White";
    const aspect = reframeAspectByMoment[m.id] || "9:16";
    const sizePct = reframeSizeByMoment[m.id] ?? 100;
    const position = reframePositionByMoment[m.id] || "bottom";
    const captions = reframeCaptionsByMoment[m.id] ?? true;
    setReframeErrorByMoment((prev) => ({ ...prev, [m.id]: null }));
    setReframeBusyByMoment((prev) => ({ ...prev, [m.id]: true }));
    try {
      const rf = await api.reframeMoment(m.id, {
        caption_style: style,
        aspect,
        caption_size_pct: sizePct,
        caption_position: position,
        captions,
      });
      setReframesByMoment((prev) => ({
        ...prev,
        [m.id]: [rf, ...(prev[m.id] ?? [])],
      }));
      setNotice(
        `${aspect} preview queued (job #${rf.job_id}) — ${style} captions.`,
      );
    } catch (e) {
      setReframeErrorByMoment((prev) => ({
        ...prev,
        [m.id]: e instanceof Error ? e.message : "Reframe failed",
      }));
    } finally {
      setReframeBusyByMoment((prev) => ({ ...prev, [m.id]: false }));
    }
  }

  // --- ClipForge approval gating + final render (Phase 6 slice 4) ---
  function applyMomentUpdate(updated: Moment) {
    setMoments((prev) =>
      prev.map((m) => (m.id === updated.id ? updated : m)),
    );
  }

  async function onApproveMoment(m: Moment) {
    try {
      applyMomentUpdate(await api.approveMoment(m.id));
      setNotice(`Moment approved — ab final clip render ho sakta hai.`);
    } catch (e) {
      setMomentsError(e instanceof Error ? e.message : "Approve failed");
    }
  }

  async function onRejectMoment(m: Moment) {
    try {
      applyMomentUpdate(await api.rejectMoment(m.id));
      setNotice(`Moment rejected — ye final clip nahi banega.`);
    } catch (e) {
      setMomentsError(e instanceof Error ? e.message : "Reject failed");
    }
  }

  async function onRenderFinalClip(m: Moment) {
    const style = reframeStyleByMoment[m.id] || "Bold White";
    const aspect = reframeAspectByMoment[m.id] || "9:16";
    const sizePct = reframeSizeByMoment[m.id] ?? 100;
    const position = reframePositionByMoment[m.id] || "bottom";
    const captions = reframeCaptionsByMoment[m.id] ?? true;
    setFinalErrorByMoment((prev) => ({ ...prev, [m.id]: null }));
    setFinalBusyByMoment((prev) => ({ ...prev, [m.id]: true }));
    try {
      const fc = await api.renderFinalClip(m.id, {
        caption_style: style,
        aspect,
        caption_size_pct: sizePct,
        caption_position: position,
        captions,
      });
      setFinalClips((prev) => {
        const rest = prev.filter((c) => c.id !== fc.id);
        return [fc, ...rest];
      });
      setNotice(
        `Final clip queued (job #${fc.job_id}) — ${style} captions, ${aspect}, approved moment only.`,
      );
    } catch (e) {
      setFinalErrorByMoment((prev) => ({
        ...prev,
        [m.id]: e instanceof Error ? e.message : "Final render failed",
      }));
    } finally {
      setFinalBusyByMoment((prev) => ({ ...prev, [m.id]: false }));
    }
  }

  async function onRenameFinalClip(fc: FinalClip) {
    const title = (renameDraftByClip[fc.id] ?? "").trim();
    if (!title) return;
    try {
      const updated = await api.renameFinalClip(fc.id, title);
      setFinalClips((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c)),
      );
      setNotice(`Final clip renamed — "${updated.title}".`);
    } catch (e) {
      setMomentsError(e instanceof Error ? e.message : "Rename failed");
    }
  }

  async function onDeleteFinalClip(fc: FinalClip) {
    try {
      await api.deleteFinalClip(fc.id);
      setFinalClips((prev) => prev.filter((c) => c.id !== fc.id));
      setNotice(
        `Final clip deleted — moment abhi bhi approved hai, dobara render ho sakta hai.`,
      );
    } catch (e) {
      setMomentsError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  // Cross-check slice: Copy link + Reuse (ClipNova Library parity).
  // Copy puts the clip's file URL on the clipboard; Reuse copies
  // the clip file into the current project as a real asset.
  async function onCopyFinalLink(fc: FinalClip) {
    if (!fc.asset_path) return;
    const url = `${window.location.origin}${fileUrl(fc.asset_path)}`;
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Clip link copied — share karein ya kahin paste karein.");
    } catch {
      setMomentsError("Clipboard nahi khula — link manually copy karein: " + url);
    }
  }

  async function onReuseFinalClip(fc: FinalClip) {
    if (!project) return;
    try {
      const asset = await api.reuseFinalClip(fc.id, project.id);
      setNotice(
        `Clip reused — ${asset.path} is project ki Media Library me aa gaya.`,
      );
      void reload();
    } catch (e) {
      setMomentsError(e instanceof Error ? e.message : "Reuse failed");
    }
  }

  async function onSaveTranscriptionEdit() {
    if (!transcription || !trEditText.trim()) return;
    setTrEditBusy(true);
    try {
      const updated = await api.updateTranscription(
        transcription.id,
        trEditText.trim(),
      );
      setTranscription(updated);
      setTranscriptions((prev) =>
        prev.map((t) => (t.id === updated.id ? updated : t)),
      );
      setTrEditing(false);
      setNotice(
        "Transcript text save ho gaya — SRT/VTT abhi bhi original word timings use karte hain.",
      );
    } catch (e) {
      setTrError(e instanceof Error ? e.message : "Edit save failed");
    } finally {
      setTrEditBusy(false);
    }
  }

  async function onUseTranscriptionAsScript() {
    if (!project || !transcription) return;
    setTrUseAsScriptBusy(true);
    try {
      const sc = await api.useTranscriptionAsScript(transcription.id);
      setNotice(
        `Script ban gaya transcription se (${sc.scenes?.length ?? 0} scenes).`,
      );
      void reload();
    } catch (e) {
      setTrError(e instanceof Error ? e.message : "Use as script failed");
    } finally {
      setTrUseAsScriptBusy(false);
    }
  }

  // --- HeyGen clone voice (Phase 5 slice 3) ---
  async function onHeygenSpeak() {
    if (!project || !heygenText.trim()) return;
    setHeygenError(null);
    setHeygenBusy(true);
    try {
      const res = await api.heygenSpeak(
        project.id,
        heygenText.trim(),
        heygenLang,
      );
      setHeygenJobId(res.job_id);
      setNotice(
        `HeyGen clone voice queued (job #${res.job_id}) — ${heygenLang === "hi" ? "Urdu/Hindi, 106 Hz pitch lock" : "English, as-is"}.`,
      );
    } catch (e) {
      setHeygenError(e instanceof Error ? e.message : "HeyGen speak failed");
    } finally {
      setHeygenBusy(false);
    }
  }

  // HeyGen job progress: poll the queued job until it is done/failed,
  // then refresh the clone VO list.
  useEffect(() => {
    if (heygenJobId === null || !project) return;
    const timer = setInterval(() => {
      void api
        .job(heygenJobId)
        .then((j) => {
          if (j.status === "done" || j.status === "failed") {
            clearInterval(timer);
            setHeygenJobId(null);
            if (j.status === "failed" && j.error) setHeygenError(j.error);
            void api
              .heygenVoices(project.id)
              .then(setHeygenVoices)
              .catch(() => undefined);
          }
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(timer);
  }, [heygenJobId, project]);

  async function onAutoSync() {
    if (!project) return;
    // Script-beat sync: pass the per-image scene texts when any are
    // written, so clip lengths follow word counts. With no scene texts
    // the backend keeps the previous captions (or falls back to equal
    // splits when there are no words at all).
    const captions = images.map((img) => sceneTexts[img.id] ?? "");
    const tl = await run(
      () =>
        api.autoSync(
          project.id,
          captions.some((c) => c.trim() !== "") ? captions : undefined,
        ),
      "Timeline synced to the script beats.",
    );
    if (tl) setTimeline(tl);
  }

  async function onSaveCharacter() {
    if (!project || !charFile || !charName.trim()) return;
    const ch = await run(
      () => api.uploadCharacter(project.id, charName.trim(), charFile),
      `Main character "${charName.trim()}" saved.`,
    );
    if (ch) {
      setCharacter(ch);
      setCharFile(null);
    }
  }

  // --- Script (Phase 3 slice 1) ---
  async function onSaveScript() {
    if (!project) return;
    if (!scriptText.trim() && !scriptTopic.trim()) {
      setError("Script text ya topic likhein — ek to chahiye.");
      return;
    }
    const saved = await run(() =>
      api.createScript(
        project.id,
        scriptTopic.trim(),
        scriptText.trim(),
        thinkingLevel,
        scriptModel,
      ),
    );
    if (saved) {
      setScript(saved);
      setScenes(saved.scenes ?? []);
      setScripts((prev) => [saved, ...prev.filter((s) => s.id !== saved.id)]);
      setScriptTopic(saved.topic);
      setScriptText(saved.full_text);
      setSceneDrafts({});
      void loadPrompts(saved.id);
      setNotice(
        `Script saved — ${(saved.scenes ?? []).length} scenes${
          saved.source === "gemini"
            ? ` (Gemini free tier, ${thinkingLevel} / ${scriptModel})`
            : ""
        }.`,
      );
    }
  }

  async function onDeleteScript() {
    if (!project || !script) return;
    const res = await run(() => api.deleteScript(script.id));
    if (res) {
      setScript(null);
      setScenes([]);
      setPrompts(null);
      setScripts((prev) => prev.filter((s) => s.id !== script.id));
      setSceneDrafts({});
      setNotice("Script deleted.");
    }
  }

  // --- Sentence-level visuals: re-split the script into one scene
  // per sentence, so the visual changes on every sentence. ---
  async function onResplitSentences() {
    if (!project || !script) return;
    const saved = await run(() => api.resplitSentences(script.id));
    if (saved) {
      setScript(saved);
      setScenes(saved.scenes ?? []);
      setSceneDrafts({});
      void loadPrompts(saved.id);
      setNotice(
        `Script re-split — ${(saved.scenes ?? []).length} sentence scenes. Har sentence par naya visual.`,
      );
    }
  }

  // --- VisualForge prompt list (Phase 4 slice 1) ---
  async function loadPrompts(scriptId: number) {
    const p = await api.scriptPrompts(scriptId).catch(() => null);
    setPrompts(p);
    await loadGenStatus(scriptId);
    await loadScriptImages(scriptId);
    void loadCanvasStatus();
    void loadGoogleStatus();
    void loadFlowStatus();
    void loadFlowQueues();
    await loadFlowQueueState(scriptId);
  }

  // --- Gemini Canvas provider status (free image route) ---
  async function loadCanvasStatus() {
    const c = await api.canvasStatus().catch(() => null);
    setCanvasStatus(c);
  }

  async function onOpenCanvasLogin() {
    setCanvasLoginBusy(true);
    setError(null);
    try {
      const res = await api.openCanvasLogin();
      setNotice(res.message);
      await loadCanvasStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Canvas login nahi khul saka");
    } finally {
      setCanvasLoginBusy(false);
    }
  }

  // --- Connect Google (one sign-in for Canvas + Flow) ---
  async function loadGoogleStatus() {
    const g = await api.googleStatus().catch(() => null);
    setGoogleStatus(g);
  }

  async function onOpenGoogleLogin() {
    setGoogleLoginBusy(true);
    setError(null);
    try {
      const res = await api.openGoogleLogin();
      setNotice(res.message);
      await loadGoogleStatus();
      await loadCanvasStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google login nahi khul saka");
    } finally {
      setGoogleLoginBusy(false);
    }
  }

  async function onDisconnectGoogle() {
    setGoogleDisconnectBusy(true);
    setError(null);
    try {
      await api.disconnectGoogle();
      setNotice(
        "Google disconnect ho gaya — Canvas aur Flow dono ke liye dobara sign-in karna hoga.",
      );
      await loadGoogleStatus();
      await loadCanvasStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Disconnect nahi hua");
    } finally {
      setGoogleDisconnectBusy(false);
    }
  }

  // --- Flow provider hardening (Slice 5) ---
  async function loadFlowStatus() {
    const f = await api.flowStatus().catch(() => null);
    setFlowStatus(f);
  }

  async function loadFlowQueues() {
    const q = await api.flowQueues().catch(() => null);
    setFlowQueues(q ? q.queues : []);
  }

  async function loadFlowQueueState(scriptId: number) {
    const s = await api.flowQueueState(scriptId).catch(() => null);
    setFlowQueueState(s);
  }

  async function onFlowSetFast(v: number) {
    setFlowBusy(true);
    setError(null);
    try {
      await api.flowSetSettings(v);
      await loadFlowStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fast mode set nahi hua");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowAddAccount() {
    setFlowBusy(true);
    setError(null);
    try {
      const a = await api.flowAddAccount();
      setNotice(`Account ${a.name} bana — Connect karein.`);
      await loadFlowStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Account nahi bana");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowRemoveAccount(accountId: number) {
    setFlowBusy(true);
    setError(null);
    try {
      await api.flowRemoveAccount(accountId);
      setNotice("Account hata diya.");
      await loadFlowStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Account nahi hata");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowOpenAccountLogin(accountId: number) {
    setFlowBusy(true);
    setError(null);
    try {
      const res = await api.flowOpenAccountLogin(accountId);
      setNotice(res.message);
      await loadFlowStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login window nahi khula");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowRecoverAccount(accountId: number) {
    setFlowBusy(true);
    setError(null);
    try {
      const res = await api.flowRecoverAccount(accountId);
      setNotice(res.detail);
      await loadFlowStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recovery nahi hui");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowPauseQueue() {
    if (!script) return;
    setFlowBusy(true);
    setError(null);
    try {
      const s = await api.flowPauseQueue(script.id);
      setFlowQueueState(s);
      setNotice("Queue pause ho gayi — bache hue scenes ruke hain.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Queue pause nahi hui");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onFlowResumeQueue() {
    if (!script) return;
    setFlowBusy(true);
    setError(null);
    try {
      const r = await api.flowResumeQueue(script.id);
      setFlowQueueState({ script_id: r.script_id, paused: r.paused });
      setNotice(
        r.resumed
          ? "Queue dobara chal padi."
          : "Queue resume ho gayi — koi bacha hua kaam nahi tha.",
      );
      await loadGenStatus(script.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Queue resume nahi hui");
    } finally {
      setFlowBusy(false);
    }
  }

  async function onChainPreview() {
    if (!chainPrompt.trim()) return;
    setFlowBusy(true);
    setError(null);
    try {
      const r = await api.flowResolveChain(
        chainPrompt,
        vfNicheId ? Number(vfNicheId) : null,
      );
      setChainPreview(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chain preview nahi bana");
    } finally {
      setFlowBusy(false);
    }
  }

  // --- VisualForge image verification (Phase 4 slice 3) ---
  async function loadScriptImages(scriptId: number) {
    const v = await api.scriptImages(scriptId).catch(() => null);
    setScriptImages(v);
  }

  // --- StickMan prompts + frames (Phase 7 slice 1) ---
  async function loadStickmanPrompts(scriptId: number) {
    const s = await api.stickmanPrompts(scriptId).catch(() => null);
    setStickman(s);
    if (s) {
      setStickmanPromptDrafts((prev) => {
        const next = { ...prev };
        for (const row of s.prompts) {
          if (row.prompt && next[row.prompt.id] === undefined) {
            next[row.prompt.id] = row.prompt;
          }
        }
        return next;
      });
    }
  }

  async function onGenerateStickmanPrompts() {
    if (!script) return;
    setStickmanBusy(true);
    setError(null);
    try {
      const res = await api.generateStickmanPrompts(script.id);
      setNotice(`${res.count} stickman prompts ban gaye — har scene ke liye.`);
      await loadStickmanPrompts(script.id);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Stickman prompts failed",
      );
    } finally {
      setStickmanBusy(false);
    }
  }

  async function onSaveStickmanPrompt(promptId: number) {
    const draft = stickmanPromptDrafts[promptId];
    if (!draft) return;
    await run(async () => {
      await api.updateStickmanPrompt(promptId, {
        pose: draft.pose,
        action: draft.action,
        expression: draft.expression,
        props: draft.props,
        background: draft.background,
        prompt: draft.prompt,
      });
      if (script) await loadStickmanPrompts(script.id);
    }, "Stickman prompt save ho gaya.");
  }

  async function onRenderStickmanFrame(sceneId: number) {
    setFrameBusyByScene((prev) => ({ ...prev, [sceneId]: true }));
    setError(null);
    try {
      const pose = framePoseByScene[sceneId] || undefined;
      const frame = await api.renderStickmanFrame(sceneId, pose);
      setNotice(
        `Stickman frame ban gaya (${frame.pose}) — VisualForge me approve karein, phir timeline me aayega.`,
      );
      if (script) {
        await loadStickmanPrompts(script.id);
        await loadScriptImages(script.id);
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Stickman frame failed",
      );
    } finally {
      setFrameBusyByScene((prev) => ({ ...prev, [sceneId]: false }));
    }
  }

  async function onSavePoseDescription(poseId: number) {
    const description = poseDescDraft.trim();
    if (!description) return;
    await run(async () => {
      const updated = await api.updateStickmanPose(poseId, description);
      setStickmanPoses((prev) =>
        prev.map((p) => (p.id === poseId ? updated : p)),
      );
      setEditingPoseId(null);
      setPoseDescDraft("");
    }, "Pose description save ho gayi.");
  }

  // --- StoryCraft master prompts + research notes (Phase 7 slice 1) ---
  async function copyMasterPrompt(prompt: MasterPrompt) {
    try {
      await navigator.clipboard.writeText(prompt.template);
      setCopiedMasterId(prompt.id);
      setTimeout(() => setCopiedMasterId((cur) => (cur === prompt.id ? null : cur)), 2000);
    } catch {
      setError("Copy nahi hua — browser ne clipboard block kiya.");
    }
  }

  function useMasterPromptInScript(prompt: MasterPrompt) {
    setScriptText((cur) =>
      cur ? `${cur}\n\n${prompt.template}` : prompt.template,
    );
    setNotice(
      `"${prompt.name}" script me lag gaya — Script tab me ja kar edit karein.`,
    );
    // v0.14.1 fix round 2: Library ab apna view hai — apply karte hi
    // StoryCraft ke Script tab par wapas jao, phir scroll karo.
    onActiveTool("storycraft");
    setStoryTab("script");
    setTimeout(() => {
      document
        .getElementById("script-section")
        ?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }

  async function onAddMasterPrompt() {
    if (!newMaster.name.trim() || !newMaster.template.trim()) {
      setError("Master prompt ka naam aur template dono likhein.");
      return;
    }
    setMasterBusy(true);
    setError(null);
    try {
      const created = await api.createMasterPrompt({
        name: newMaster.name.trim(),
        category: newMaster.category,
        template: newMaster.template.trim(),
        source: newMaster.source.trim(),
      });
      setMasterPrompts((prev) => [...prev, created]);
      setNewMaster({ name: "", category: "hook", template: "", source: "" });
      setNotice("Master prompt add ho gaya.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Master prompt add failed",
      );
    } finally {
      setMasterBusy(false);
    }
  }

  async function onDeleteMasterPrompt(promptId: number) {
    await run(async () => {
      await api.deleteMasterPrompt(promptId);
      setMasterPrompts((prev) => prev.filter((p) => p.id !== promptId));
    }, "Master prompt delete ho gaya.");
  }

  // --- Cross-check slice: niches + Style DNA builder + import ---
  async function onAddNiche() {
    if (!newNiche.name.trim()) {
      setError("Niche ka naam likhein.");
      return;
    }
    setNicheBusy(true);
    setError(null);
    try {
      const created = await api.createNiche({
        name: newNiche.name.trim(),
        description: newNiche.description.trim(),
        main_characters: newNiche.main_characters.trim(),
      });
      setNiches((prev) => [...prev, created]);
      setNewNiche({ name: "", description: "", main_characters: "" });
      setNotice("Niche add ho gaya.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Niche add failed");
    } finally {
      setNicheBusy(false);
    }
  }

  async function onDeleteNiche(nicheId: number) {
    await run(async () => {
      await api.deleteNiche(nicheId);
      setNiches((prev) => prev.filter((n) => n.id !== nicheId));
    }, "Niche delete ho gaya.");
  }

  async function onSuggestTopics(niche: Niche) {
    setTopicsBusyByNiche((prev) => ({ ...prev, [niche.id]: true }));
    try {
      const res = await api.suggestTopics(niche.id);
      setTopicsByNiche((prev) => ({ ...prev, [niche.id]: res.topics }));
      setNotice(`${res.topics.length} topic ideas mil gaye — kisi par click karein to script topic bhar jaye.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Topic ideas failed");
    } finally {
      setTopicsBusyByNiche((prev) => ({ ...prev, [niche.id]: false }));
    }
  }

  function useTopicAsScriptTopic(topic: string) {
    setScriptTopic(topic);
    setNotice(`Topic script me lag gaya — Script section me Generate karein.`);
    document
      .getElementById("script-section")
      ?.scrollIntoView({ behavior: "smooth" });
  }

  // --- Slice 4: Character Vault ---
  async function loadVaultList() {
    try {
      const v = await api.listVault();
      setVaultList(v);
      setVaultError(null);
    } catch (e) {
      setVaultError(apiErrorDetail(e) ?? "Vault load nahi hua.");
    }
    // Release Packaging (v0.14.0): main character bhi yahin se.
    void api
      .getMainCharacter()
      .then((r) => setMainCharacter(r.main_character))
      .catch(() => undefined);
  }

  async function loadVaultDetail(nicheId: number) {
    const d = await api.getVault(nicheId);
    setVaultDetailByNiche((prev) => ({ ...prev, [nicheId]: d }));
    return d;
  }

  async function onToggleVault(nicheId: number) {
    if (expandedVaultId === nicheId) {
      setExpandedVaultId(null);
      return;
    }
    setExpandedVaultId(nicheId);
    if (!vaultDetailByNiche[nicheId]) {
      setVaultBusy(true);
      setError(null);
      try {
        await loadVaultDetail(nicheId);
      } catch (e) {
        setError(apiErrorDetail(e) ?? "Vault detail load nahi hua.");
      } finally {
        setVaultBusy(false);
      }
    }
  }

  async function reloadVault(nicheId: number) {
    await loadVaultList();
    await loadVaultDetail(nicheId);
  }

  async function loadMyChars() {
    setMyCharsBusy(true);
    try {
      const niches = await api.listVault();
      const all: VaultCharacter[] = [];
      for (const n of niches) {
        const d = await api.getVault(n.niche_id);
        for (const c of d.characters) {
          if (c.source === "user") all.push(c);
        }
      }
      setMyChars(all);
      setMyCharsLoaded(true);
    } catch (e) {
      setError(apiErrorDetail(e) ?? "My characters load nahi hue.");
    } finally {
      setMyCharsBusy(false);
    }
  }

  async function onCreateMyCharacter() {
    if (!myCharForm.name.trim()) {
      setError("Character ka naam likhein.");
      return;
    }
    if (!myCharForm.description.trim()) {
      setError("Description likhein — poora paragraph.");
      return;
    }
    if (!myCharForm.niche_id) {
      setError("Niche chunein.");
      return;
    }
    if (!myCharFile) {
      setError("Character sheet image chunein.");
      return;
    }
    setMyCharBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", myCharFile);
      form.append("name", myCharForm.name.trim());
      form.append("description", myCharForm.description.trim());
      form.append("niche_id", myCharForm.niche_id);
      form.append("signature_prop", myCharForm.signature_prop.trim());
      await api.createMyCharacter(form);
      setMyCharForm({ name: "", description: "", niche_id: "", signature_prop: "" });
      setMyCharFile(null);
      setShowMyCharForm(false);
      await loadMyChars();
      await loadVaultList();
      setNotice(
        "Apna character draft ban gaya — approve karein, phir lock karein, phir 'Set as my main character'.",
      );
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Character add nahi ho saka.");
    } finally {
      setMyCharBusy(false);
    }
  }

  async function onSetMainCharacter(c: VaultCharacter) {
    setVaultBusy(true);
    setError(null);
    try {
      await api.setMainCharacter(c.niche_id, c.id);
      const r = await api.getMainCharacter();
      setMainCharacter(r.main_character);
      await loadMyChars();
      setNotice(`"${c.name}" ab aapka main character hai — har scene me wahi aayega.`);
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Main character set nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onUnsetMainCharacter(c: VaultCharacter) {
    setVaultBusy(true);
    setError(null);
    try {
      await api.unsetMainCharacter(c.niche_id, c.id);
      setMainCharacter(null);
      await loadMyChars();
      setNotice("Main character hata diya gaya.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Main character nahi hata.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onDeleteMyCharacter(c: VaultCharacter) {
    if (!window.confirm(`"${c.name}" delete karein? Ye wapas nahi aayega.`)) return;
    setVaultBusy(true);
    setError(null);
    try {
      await api.deleteVaultCharacter(c.niche_id, c.id);
      if (mainCharacter?.id === c.id) setMainCharacter(null);
      await loadMyChars();
      await loadVaultList();
      setNotice("Character delete ho gaya.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Character delete nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onAddVaultCharacter(nicheId: number) {
    if (!newVaultChar.name.trim()) {
      setError("Character ka naam likhein.");
      return;
    }
    setVaultBusy(true);
    setError(null);
    try {
      await api.createVaultCharacter(nicheId, {
        name: newVaultChar.name.trim(),
        description: newVaultChar.description.trim(),
        signature_prop: newVaultChar.signature_prop.trim(),
        role: newVaultChar.role,
      });
      setNewVaultChar({
        name: "",
        description: "",
        signature_prop: "",
        role: "main",
      });
      await reloadVault(nicheId);
      setNotice("Character draft ban gaya — approve karein, phir lock karein.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Character add nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  function startEditVaultCharacter(c: VaultCharacter) {
    setEditingVaultCharId(c.id);
    setVaultEditDraft({
      description: c.description,
      signature_prop: c.signature_prop,
      role: c.role,
    });
  }

  async function onSaveVaultCharacter(nicheId: number, charId: number) {
    setVaultBusy(true);
    setError(null);
    try {
      // Edit kabhi locked version ko in-place nahi badalta — backend
      // naya draft version banata hai, purana locked rehta hai.
      await api.updateVaultCharacter(nicheId, charId, {
        description: vaultEditDraft.description.trim(),
        signature_prop: vaultEditDraft.signature_prop.trim(),
        role: vaultEditDraft.role,
      });
      setEditingVaultCharId(null);
      await reloadVault(nicheId);
      setNotice("Naya draft version ban gaya — approve karein, phir lock karein.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Character update nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onUploadVaultSheet(
    nicheId: number,
    charId: number,
    file: File | undefined,
  ) {
    if (!file) return;
    setVaultBusy(true);
    setError(null);
    try {
      await api.uploadVaultSheet(nicheId, charId, file);
      await reloadVault(nicheId);
      setNotice("Sheet upload ho gayi — naya draft version ban gaya.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Sheet upload nahi ho saki.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onApproveVaultCharacter(nicheId: number, charId: number) {
    setVaultBusy(true);
    setError(null);
    try {
      await api.approveVaultCharacter(nicheId, charId);
      await reloadVault(nicheId);
      if (myCharsLoaded) await loadMyChars();
      setNotice("Character approve ho gaya — ab lock karein.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Approve nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onLockVaultCharacter(nicheId: number, charId: number) {
    setVaultBusy(true);
    setError(null);
    try {
      await api.lockVaultCharacter(nicheId, charId);
      await reloadVault(nicheId);
      if (myCharsLoaded) await loadMyChars();
      setNotice("Character lock ho gaya — ab yehi version har scene me aayega.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Lock nahi ho saka.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onDeleteVaultCharacter(nicheId: number, charId: number) {
    setVaultBusy(true);
    setError(null);
    try {
      await api.deleteVaultCharacter(nicheId, charId);
      await reloadVault(nicheId);
      setNotice("Draft delete ho gaya.");
    } catch (e) {
      setError(apiErrorDetail(e) ?? "Delete nahi ho saka — sirf draft delete hota hai.");
    } finally {
      setVaultBusy(false);
    }
  }

  async function onStyleFromDescription() {
    if (!styleBuilder.name.trim() || !styleBuilder.description.trim()) {
      setError("Style ka naam aur description dono likhein.");
      return;
    }
    setStyleBuilderBusy(true);
    setError(null);
    try {
      const created = await api.createStyleDnaFromDescription(
        styleBuilder.name.trim(),
        styleBuilder.description.trim(),
      );
      setStyleBuilder({ name: "", description: "" });
      setNotice(`Style DNA "${created.name}" ban gaya — ab scripts me use ho sakta hai.`);
      void reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Style DNA failed");
    } finally {
      setStyleBuilderBusy(false);
    }
  }

  async function onReverseEngineer() {
    if (!reverseNotes.trim()) {
      setError("Viral short ke notes likhein — hook, visual style, pacing, captions, CTA.");
      return;
    }
    setReverseBusy(true);
    setError(null);
    try {
      const created = await api.reverseEngineerMasterPrompt(
        reverseName.trim() || "Reverse-Engineered Master Prompt",
        reverseNotes.trim(),
      );
      setMasterPrompts((prev) => [...prev, created]);
      setReverseNotes("");
      setReverseName("");
      setNotice("Master prompt ban gaya — library me aa gaya.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reverse-engineer failed");
    } finally {
      setReverseBusy(false);
    }
  }

  async function onImportMasterPrompt(file: File | undefined) {
    if (!file) return;
    try {
      const created = await api.importMasterPrompt(file);
      setMasterPrompts((prev) => [...prev, created]);
      setNotice(`Master prompt import ho gaya — "${created.name}".`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    }
  }

  async function onAddResearchNote() {
    if (!project || !newNoteContent.trim()) {
      setError("Research note khaali nahi ho sakta.");
      return;
    }
    setResearchBusy(true);
    setError(null);
    try {
      const created = await api.createResearchNote(
        project.id,
        newNoteTitle.trim(),
        newNoteContent.trim(),
      );
      setResearchNotes((prev) => [created, ...prev]);
      setNewNoteTitle("");
      setNewNoteContent("");
      setNotice("Research note save ho gaya.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Research note save failed",
      );
    } finally {
      setResearchBusy(false);
    }
  }

  // Slice 2: Deep Research — topic ki tehqeeq, script se pehle.
  async function onDeepResearch() {
    if (!project || !deepResearchTopic.trim()) {
      setError("Research ke liye topic likhein.");
      return;
    }
    setDeepResearchBusy(true);
    setError(null);
    try {
      const created = await api.deepResearch(
        project.id,
        deepResearchTopic.trim(),
      );
      setResearchNotes((prev) => [created, ...prev]);
      setDeepResearchTopic("");
      setNotice(
        `Research tayyar — ${created.facts.length} facts + sources. ` +
          `Ab is se script likhwayein.`,
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Deep Research failed",
      );
    } finally {
      setDeepResearchBusy(false);
    }
  }

  async function onSaveResearchNote(noteId: number) {
    const draft = noteDrafts[noteId];
    if (!draft || !draft.content.trim()) {
      setError("Research note khaali nahi ho sakta.");
      return;
    }
    await run(async () => {
      const updated = await api.updateResearchNote(
        noteId,
        draft.title,
        draft.content,
      );
      setResearchNotes((prev) =>
        prev.map((n) => (n.id === noteId ? updated : n)),
      );
      setEditingNoteId(null);
    }, "Research note save ho gaya.");
  }

  async function onDeleteResearchNote(noteId: number) {
    await run(async () => {
      await api.deleteResearchNote(noteId);
      setResearchNotes((prev) => prev.filter((n) => n.id !== noteId));
    }, "Research note delete ho gaya.");
  }

  async function onWriteScriptFromResearch(noteId: number) {
    await run(async () => {
      const created = await api.writeScriptFromResearch(
        noteId,
        thinkingLevel,
        scriptModel,
      );
      setScript(created);
      setScripts((prev) => [created, ...prev]);
      setScriptTopic(created.topic);
      setScriptText(created.full_text);
      const ss = await api.scriptScenes(created.id).catch(() => [] as Scene[]);
      setScenes(ss);
      setSceneDrafts({});
      setPrompts(null);
      setScriptImages(null);
      setGenStatus(null);
      setStickman(null);
      void loadPrompts(created.id);
      void loadStickmanPrompts(created.id);
    }, `Script ban gaya (${thinkingLevel} / ${scriptModel}) — Script section me dekh lein.`);
  }

  async function onApproveImage(assetId: number) {
    await run(async () => {
      await api.approveImage(assetId);
      if (script) await loadScriptImages(script.id);
    }, "Image approved — ab ye timeline me ja sakti hai.");
  }

  async function onRejectImage(assetId: number) {
    const reason = (rejectReasons[assetId] ?? "").trim();
    await run(async () => {
      await api.rejectImage(assetId, reason || undefined);
      if (script) await loadScriptImages(script.id);
    }, "Image rejected — timeline me nahi jayegi.");
  }

  async function onRegenerateImage(assetId: number) {
    setVfBusy(true);
    setError(null);
    try {
      const res = await api.regenerateImage(assetId);
      setNotice(
        res.outcome === "limit_blocked"
          ? "Daily limit khatam — kal dobara."
          : "Dobara generate ke liye queue me hai.",
      );
      if (script) {
        await loadScriptImages(script.id);
        await loadGenStatus(script.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Regenerate failed");
    } finally {
      setVfBusy(false);
    }
  }

  async function onAttachImage(sceneId: number) {
    const assetId = Number(attachAssetIds[sceneId] ?? "");
    if (!assetId) return;
    await run(async () => {
      await api.attachImageToScene(sceneId, assetId);
      if (script) await loadScriptImages(script.id);
    }, "Image scene se jud gayi — ab approve/reject karein.");
  }

  async function onUseApproved() {
    if (!script) return;
    await run(async () => {
      const res = await api.useApproved(script.id);
      setTimeline(res.timeline);
      setUseApprovedSummary(res.summary);
      await loadScriptImages(script.id);
    }, "Approved images timeline me lag gayi.");
  }

  // --- VisualForge bulk generation (Phase 4 slice 2) ---
  async function loadGenStatus(scriptId: number) {
    const g = await api.generationStatus(scriptId).catch(() => null);
    setGenStatus(g);
  }

  async function onGenerateImages() {
    if (!script) return;
    setGenBusy(true);
    setError(null);
    try {
      const res = await api.generateImages(script.id, imageProvider, {
        character_match: characterMatch,
        style_match: styleMatch,
        niche_id: vfNicheId ? Number(vfNicheId) : null,
      });
      const parts: string[] = [];
      if (res.queued_job_ids.length > 0)
        parts.push(
          `${res.queued_job_ids.length} image(s) queued (${res.provider === "canvas" ? "Canvas — free" : "Gemini API"})`,
        );
      if (res.skipped_done_scene_ids.length > 0)
        parts.push(`${res.skipped_done_scene_ids.length} already done`);
      if (res.limit_blocked_job_ids.length > 0)
        parts.push(
          `${res.limit_blocked_job_ids.length} blocked — daily limit reached`,
        );
      setNotice(parts.join(" · ") || "Nothing to generate.");
      await loadGenStatus(script.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generate failed");
    } finally {
      setGenBusy(false);
    }
  }

  function exportPromptsTxt() {
    if (!prompts || !project) return;
    const lines: string[] = [
      "Kreafy Creator Studio — VisualForge image prompts",
      `Project: ${project.name}`,
      `Script: ${prompts.topic || "(no topic)"}`,
      `Style DNA: ${prompts.style_dna_name ?? "—"}`,
      `Main character: ${prompts.character_name ?? "—"}`,
      "",
    ];
    prompts.prompts.forEach((p, i) => {
      lines.push(`Scene ${i + 1} (~${p.duration_s}s) — ${p.status}`);
      lines.push(p.image_prompt);
      lines.push("");
    });
    const blob = new Blob([lines.join("\n")], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `visualforge-prompts-script-${prompts.script_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    setNotice(`Exported ${prompts.prompts.length} prompt(s) as .txt.`);
  }

  async function copyPrompt(p: ScenePrompt) {
    try {
      await navigator.clipboard.writeText(p.image_prompt);
    } catch {
      // Clipboard unavailable: fall back to a temporary textarea.
      const ta = document.createElement("textarea");
      ta.value = p.image_prompt;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopiedPromptId(p.scene_id);
    window.setTimeout(
      () =>
        setCopiedPromptId((cur) => (cur === p.scene_id ? null : cur)),
      1500,
    );
  }

  function sceneDraft(scene: Scene) {
    return (
      sceneDrafts[scene.id] ?? {
        text: scene.text,
        image_prompt: scene.image_prompt,
        duration_s: String(scene.duration_s),
      }
    );
  }

  async function saveScene(scene: Scene) {
    const d = sceneDraft(scene);
    const updated = await run(() =>
      api.updateScene(scene.id, {
        text: d.text,
        image_prompt: d.image_prompt,
        duration_s: Number(d.duration_s),
      }),
    );
    if (updated) {
      setScenes((prev) => prev.map((s) => (s.id === scene.id ? updated : s)));
      setSceneDrafts((prev) => {
        const next = { ...prev };
        delete next[scene.id];
        return next;
      });
      setNotice(`Scene ${scene.position + 1} saved.`);
      if (script) void loadPrompts(script.id);
    }
  }

  async function onRegeneratePrompt(scene: Scene) {
    const updated = await run(() => api.regenerateScenePrompt(scene.id));
    if (updated) {
      setScenes((prev) => prev.map((s) => (s.id === scene.id ? updated : s)));
      setSceneDrafts((prev) => {
        const next = { ...prev };
        delete next[scene.id];
        return next;
      });
      setNotice(`Scene ${scene.position + 1} prompt rebuilt.`);
      if (script) void loadPrompts(script.id);
    }
  }

  function useScenesInTimeline() {
    // Load each scene's text as the matching image's caption, so
    // auto-sync splits the voiceover on the script beats.
    if (scenes.length === 0) return;
    const next: Record<number, string> = {};
    images.forEach((img, i) => {
      if (scenes[i]) next[img.id] = scenes[i].text;
    });
    setSceneTexts(next);
    setNotice("Scene texts loaded into the timeline — now Auto-sync.");
  }

  function draftFor(clip: Clip) {
    return (
      drafts[clip.id] ?? {
        start_s: String(clip.start_s),
        end_s: String(clip.end_s),
        caption_text: clip.caption_text,
      }
    );
  }

  async function saveClip(clip: Clip) {
    if (!timeline) return;
    const d = draftFor(clip);
    const tl = await run(() =>
      api.updateClip(timeline.id, clip.id, {
        start_s: Number(d.start_s),
        end_s: Number(d.end_s),
        caption_text: d.caption_text,
      }),
    );
    if (tl) {
      setTimeline(tl);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[clip.id];
        return next;
      });
    }
  }

  async function onSetClipEffect(clip: Clip, effect: string) {
    if (!timeline) return;
    const tl = await run(() =>
      api.updateClip(timeline.id, clip.id, { effect }),
    );
    if (tl) setTimeline(tl);
  }

  async function moveClip(clip: Clip, dir: -1 | 1) {
    if (!timeline) return;
    const sorted = [...timeline.clips].sort((a, b) => a.position - b.position);
    const idx = sorted.findIndex((c) => c.id === clip.id);
    const other = sorted[idx + dir];
    if (!other) return;
    // One PUT: the backend swaps the two clips' positions and re-lays
    // the times end to end (a second PUT would swap them back).
    const tl = await run(() =>
      api.updateClip(timeline.id, clip.id, { position: other.position }),
    );
    if (tl) setTimeline(tl);
  }

  async function onApplyStyle() {
    if (!timeline) return;
    const tl = await run(
      () =>
        api.applyStyle(timeline.id, {
          style_dna_id: styleId ? Number(styleId) : undefined,
          caption_style_id: captionId ? Number(captionId) : undefined,
        }),
      "Style applied.",
    );
    if (tl) setTimeline(tl);
  }

  async function onRender() {
    if (!timeline) return;
    const job = await run(() =>
      api.renderTimeline(timeline.id, {
        quality: renderQuality,
        ...atmosphere,
        atmosphere_preset: atmospherePreset,
        caption_size_pct: captionSizePct,
        caption_position: captionPosition,
        captions: captionsOn,
      }),
    );
    if (job) {
      setRenderJob(job);
      void loadRenderQueue();
    }
  }

  // --- Per-scene regenerate + deliverables (Phase 3 slice 3) ---
  async function onReplaceClipImage(clip: Clip, file: File | undefined) {
    if (!timeline || !file) return;
    const tl = await run(
      () => api.replaceClipImage(timeline.id, clip.id, file),
      "Clip image replaced — ab Re-render karein.",
    );
    if (tl) setTimeline(tl);
  }

  async function onRerender() {
    if (!timeline) return;
    const job = await run(
      () =>
        api.rerenderTimeline(timeline.id, {
          quality: renderQuality,
          ...atmosphere,
          atmosphere_preset: atmospherePreset,
          caption_size_pct: captionSizePct,
          caption_position: captionPosition,
          captions: captionsOn,
        }),
      "Re-render started — purani MP4 tab tak available hai jab tak nayi tayyar na ho.",
    );
    if (job) {
      setRenderJob(job);
      void loadRenderQueue();
    }
  }

  async function onGenerateThumbnail() {
    if (!project) return;
    const thumb = await run(
      () =>
        api.generateThumbnail(
          project.id,
          thumbTs.trim() ? Number(thumbTs) : undefined,
        ),
      "Thumbnail ban gaya — ye rendered video ka asal frame hai.",
    );
    if (thumb) await reload();
  }

  async function onGenerateMetadata() {
    if (!project) return;
    const meta = await run(
      () => api.generateMetadata(project.id),
      "YouTube pack script se draft ho gaya — edit karke Save karein.",
    );
    if (meta) {
      setMetaDraft({
        title: meta.title,
        description: meta.description,
        tags: meta.tags,
      });
      await reload();
    }
  }

  async function onSaveMetadata() {
    if (!project) return;
    const meta = await run(
      () => api.updateMetadata(project.id, metaDraft),
      "YouTube metadata saved.",
    );
    if (meta) {
      setMetaDraft({
        title: meta.title,
        description: meta.description,
        tags: meta.tags,
      });
    }
  }

  function copyText(text: string, label: string) {
    void navigator.clipboard
      ?.writeText(text)
      .then(() => setNotice(`${label} copied.`))
      .catch(() => setError("Copy nahi ho saka — text select karke copy karein."));
  }

  // --- One-click run (Phase 3 slice 2) ---
  async function onStartRun() {
    if (!project || !script) return;
    const started = await run(() =>
      api.startRun(project.id, {
        script_id: script.id,
        ...(runVoiceSource === "upload" && voice
          ? { voiceover_asset_id: voice.id }
          : {}),
        ...(runVoiceSource === "tts"
          ? { voice_text: script.full_text, voice: ttsVoice }
          : {}),
        ...(runCaptionId ? { caption_style_id: Number(runCaptionId) } : {}),
      }),
    );
    if (started) {
      setOneClickRun(started);
      setNotice("One-click run started — steps below.");
    }
  }

  // --- Magic Mode (Slice 3) ---
  async function onStartMagic() {
    if (!project || magicStarting) return;
    const topic = magicTopic.trim();
    if (!topic) {
      setMagicError("Topic likhein — Magic Mode ko topic chahiye.");
      return;
    }
    const [kind, ...rest] = magicVoiceSel.split(":");
    const voiceValue = rest.join(":");
    let voiceKind: "upload" | "edge" | "heygen" = "edge";
    let voiceId = "";
    let voAssetId: number | null = null;
    if (kind === "upload") {
      voiceKind = "upload";
      voAssetId = Number(voiceValue) || null;
    } else if (kind === "heygen") {
      voiceKind = "heygen";
      voiceId = voiceValue;
    } else {
      voiceKind = "edge";
      voiceId = voiceValue;
    }
    if (voiceKind === "upload" && voAssetId == null) {
      setMagicError(
        "Voiceover upload karein ya Edge-TTS chunein — bina voice ke video nahi ban sakti.",
      );
      return;
    }
    if (voiceKind === "edge" && !voiceId) {
      setMagicError(
        "Edge-TTS voice chunein — bina voice ke video nahi ban sakti.",
      );
      return;
    }
    setMagicError(null);
    setMagicStarting(true);
    try {
      const started = await api.startMagic(project.id, {
        topic,
        script_text: magicScript.trim(),
        voice_kind: voiceKind,
        voice_id: voiceId,
        vo_asset_id: voAssetId,
        caption_style_id: magicCaptionId ? Number(magicCaptionId) : null,
        style_dna_id: magicStyleDnaId ? Number(magicStyleDnaId) : null,
        aspect: magicAspect,
        language: magicLanguage,
        niche_id: magicNicheId ? Number(magicNicheId) : null,
      });
      setMagicRun(started);
      setNotice("Magic Mode chal raha hai — stages neeche dekhein.");
    } catch (e) {
      setMagicError(
        apiErrorDetail(e) ??
          "Magic Mode start nahi ho saka — dobara koshish karein.",
      );
    } finally {
      setMagicStarting(false);
    }
  }

  if (!project) {
    return (
      <section>
        <h1>CineCut</h1>
        <p className="muted">Pick a project to open its sync timeline.</p>
        {toolTarget && (
          <p>
            <span className="badge gold">
              {toolTarget === "cinecut-top"
                ? "CineCut"
                : Object.keys(TOOL_SECTIONS).find(
                    (k) => TOOL_SECTIONS[k] === toolTarget,
                  ) ?? "Tool"}{" "}
              kholne ke liye project chunein
            </span>
          </p>
        )}
        {projects.length === 0 ? (
          <p>No projects yet. Create one on the Projects page first.</p>
        ) : (
          <ul className="list">
            {projects.map((p) => (
              <li key={p.id}>
                {p.name}{" "}
                <button onClick={() => onPickProject(p.id)}>Open</button>
              </li>
            ))}
          </ul>
        )}
        <p>
          <button onClick={onBack}>Back</button>
        </p>
      </section>
    );
  }

  return (
    <section>
      <h1>CineCut — {project.name}</h1>
      <p>
        <button onClick={onBack}>← Back to All Tools</button>
      </p>
      {notice && <p>{notice}</p>}
      {error && <p className="error">{error}</p>}
      {/* v0.14.1 fix round 2 — tool switcher: ek waqt par ek tool
       * (Ali ka rule: ek tool = ek kaam, har cheez apni sahi jagah). */}
      <div className="form-row" role="tablist" aria-label="Tools">
        {(
          [
            ["CineCut", "cinecut-top"],
            ["VoiceForge", "voiceforge"],
            ["StoryCraft", "storycraft"],
            ["VisualForge", "visualforge"],
            ["ClipForge", "clipforge"],
            ["StickMan", "stickman"],
            ["Documentary Director", "director"],
            ["Motion Studio", "motion"],
            ["Render Studio", "render"],
            ["Master Prompts", "master-prompts"],
          ] as [string, string][]
        ).map(([label, id]) => (
          <button
            key={id}
            className={activeTool === id ? "" : "ghostbtn"}
            onClick={() => onActiveTool(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {activeTool === "cinecut-top" && (
        <>
      <h2 id="tool-cinecut-top">1. Voiceover + images</h2>
      <p className="muted">
        Upload a voiceover file (mp3/wav) — the reliable path — or try free
        Edge-TTS in VoiceForge. Images: png/jpg, several at once.
      </p>
      <div className="form-row">
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) void onVoiceFile(f);
          }}
          title="Ya voiceover file yahan drop karein"
          style={{ border: "1px dashed var(--hatch-widget-border)", padding: 8, borderRadius: 8 }}
        >
          Voiceover (drop bhi kar sakte hain){" "}
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac"
            onChange={(e) => void onVoiceFile(e.target.files?.[0])}
            disabled={busy}
          />
        </label>
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files?.length)
              void onImageFiles(e.dataTransfer.files);
          }}
          title="Ya images yahan drop karein"
          style={{ border: "1px dashed var(--hatch-widget-border)", padding: 8, borderRadius: 8 }}
        >
          Images (drop bhi kar sakte hain){" "}
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            multiple
            onChange={(e) => void onImageFiles(e.target.files)}
            disabled={busy}
          />
        </label>
      </div>
      <p className="muted">
        {voice ? `Voiceover: ${voice.path}` : "No voiceover yet."} ·{" "}
        {images.length} image(s)
      </p>
      {images.length > 0 && (
        <>
          <h3>Scene texts (optional — script beats)</h3>
          <p className="muted">
            Write one line per image. Auto-sync splits the voiceover by word
            count, so each visual lands on its dialogue beat. These lines
            become the clip captions (and the burned-in captions on render).
          </p>
          {images.map((img, i) => (
            <div className="form-row" key={img.id}>
              <img
                src={fileUrl(img.path)}
                alt={`Scene ${i + 1}`}
                style={{ width: 64, height: 40, objectFit: "cover", borderRadius: 4 }}
              />
              <input
                value={sceneTexts[img.id] ?? ""}
                onChange={(e) =>
                  setSceneTexts((prev) => ({ ...prev, [img.id]: e.target.value }))
                }
                placeholder={`Scene ${i + 1} text…`}
                aria-label={`Scene ${i + 1} text`}
                style={{ flex: 1 }}
              />
            </div>
          ))}
        </>
      )}
      <div className="form-row">
        <button className="ghostbtn" onClick={() => onActiveTool("voiceforge")}>
          Awaaz banani hai? VoiceForge me Edge-TTS →
        </button>
      </div>
        </>
      )}
      {activeTool === "voiceforge" && (
        <>
      <div className="form-row" role="tablist" aria-label="VoiceForge sections">
        {(
          [
            ["Generate voice", "generate"],
            ["Voice Library", "library"],
            ["Transcription", "transcribe"],
            ["HeyGen Clone", "heygen"],
          ] as [string, string][]
        ).map(([label, id]) => (
          <button
            key={id}
            className={voiceTab === id ? "" : "ghostbtn"}
            onClick={() => setVoiceTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {voiceTab === "generate" && (
        <>
      <h2 id="tool-voiceforge-generate">VoiceForge — Generate voice</h2>
      <p className="muted">
        Free Edge-TTS se voiceover banayen — ya voiceover file upload
        karein (CineCut me). Neeche status ek hi hai: list aur
        Generate kabhi alag nahi bolenge.
      </p>
      <div className="form-row">
        <input
          value={ttsText}
          onChange={(e) => setTtsText(e.target.value)}
          placeholder="Or type narration for free TTS (best-effort)"
          aria-label="Narration text for TTS"
          style={{ flex: 1 }}
        />
        <select
          value={ttsVoice}
          onChange={(e) => setTtsVoice(e.target.value)}
          aria-label="TTS voice"
        >
          {(ttsVoices.length > 0
            ? ttsVoices
            : FREE_VOICES.map((id) => ({
                voice_id: id,
                name: id
                  .replace(/^[a-z]{2}-[A-Z]{2}-/, "")
                  .replace(/Neural$/, ""),
                locale: id.slice(0, 5),
                language: "",
                gender: "",
                verified_here: false,
              }))
          ).map((v) => (
            <option key={v.voice_id} value={v.voice_id}>
              {v.name} ({v.locale}
              {v.gender ? `, ${v.gender}` : ""})
              {v.voice_id === defaultVoice ? " ★ Default" : ""}
              {voicesLive || v.verified_here ? "" : " (unverified here)"}
            </option>
          ))}
        </select>
        <button onClick={() => void onTts()} disabled={busy || !ttsText.trim()}>
          Generate voice
        </button>
      </div>
      {ttsStatus ? (
        ttsStatus.synthesis_ok ? (
          <p className="muted">
            Edge-TTS chal raha hai — live list ({ttsVoices.length} voices),
            Generate bhi chalega.
          </p>
        ) : (
          <p className="error">{ttsStatus.reason}</p>
        )
      ) : (
        <p className="muted">Edge-TTS status check ho raha hai…</p>
      )}
        </>
      )}
      {voiceTab === "library" && (
        <>
      <h2 id="tool-voiceforge">VoiceForge — Voice Library</h2>
      <p className="muted">
        Free Microsoft voices (Edge-TTS, no key). Play a sample, then set
        your favourite as the default — the one-click run and TTS use it
        when no voice is picked.
        {ttsStatus?.list_source === "live"
          ? ` Live list from this PC (${ttsVoices.length} voices).`
          : " Curated list — live list is PC par nahi mili, is liye samples 503 de sakte hain."}
        {ttsStatus && !ttsStatus.synthesis_ok
          ? " Awaaz banana (synthesis) yahan blocked hai — Generate bhi nahi chalega."
          : ""}
      </p>
      <div className="form-row">
        {["All", "English", "Hindi", "Urdu"].map((f) => (
          <button
            key={f}
            className={voiceFilter === f ? "" : "ghostbtn"}
            onClick={() => setVoiceFilter(f)}
          >
            {f}
          </button>
        ))}
        <span className="muted">
          {
            ttsVoices.filter(
              (v) => voiceFilter === "All" || v.language === voiceFilter,
            ).length
          }{" "}
          voices · Default: {defaultVoice}
        </span>
      </div>
      {playingUrl && (
        <div className="form-row">
          <audio src={playingUrl} controls autoPlay style={{ flex: 1 }} />
          <button className="ghostbtn" onClick={() => setPlayingUrl(null)}>
            Close player
          </button>
        </div>
      )}
      {previewError && <p className="error">{previewError}</p>}
      <div className="voice-grid">
        {ttsVoices
          .filter((v) => voiceFilter === "All" || v.language === voiceFilter)
          .map((v) => (
            <div key={v.voice_id} className="voice-card">
              <strong>{v.name}</strong>
              <span className="muted">
                {v.locale} · {v.language} · {v.gender}
              </span>
              {v.voice_id === defaultVoice && (
                <span className="badge gold">★ Default</span>
              )}
              {!voicesLive && !v.verified_here && (
                <span className="muted">unverified here</span>
              )}
              <div className="form-row">
                <button
                  className="ghostbtn"
                  onClick={() => void onPreviewVoice(v.voice_id)}
                  disabled={previewVoice === v.voice_id}
                >
                  {previewVoice === v.voice_id ? "Loading…" : "▶ Play sample"}
                </button>
                {v.voice_id !== defaultVoice && (
                  <button
                    className="ghostbtn"
                    onClick={() => void onSetDefaultVoice(v.voice_id)}
                  >
                    Set as default
                  </button>
                )}
              </div>
            </div>
          ))}
        {ttsVoices.length === 0 && (
          <p className="muted">
            Voice library could not be loaded — reload the page.
          </p>
        )}
      </div>

      <h2>VoiceForge — Voice providers</h2>
      <p className="muted">
        Edge-TTS free aur HeyGen clone pehle se hain. A123 Pro ya koi bhi
        aur provider Settings me alag se add hota hai — Test sirf base URL
        ki reachability check karta hai, voice generation is se verify
        nahi hoti.
      </p>
      <ul className="list">
        {voiceProviders.map((p) => (
          <li key={String(p.id)}>
            <strong>{p.name}</strong> · {p.kind}
            {p.base_url ? ` · ${p.base_url}` : ""} ·{" "}
            {p.key_set ? "key set hai" : "no key"} · test: {p.test_status}
            {p.test_message ? ` — ${p.test_message}` : ""}
          </li>
        ))}
        {voiceProviders.length === 0 && (
          <li>
            <em>Providers load nahi hue — reload the page.</em>
          </li>
        )}
      </ul>

        </>
      )}
      {voiceTab === "transcribe" && (
        <>
      <h2 id="tool-transcribe">VoiceForge — Transcription</h2>
      <p className="muted">
        Local Whisper (free, offline, no key). Audio/video file dein —
        likhai milegi, har lafz ke time ke saath. Sirf wo models jo is PC
        par cached hain — kuch download nahi hota.
        {whisperStatus
          ? whisperStatus.transcribe_ready
            ? ` Ready — cached models: ${whisperStatus.models_cached.join(", ")}.`
            : ` ${whisperStatus.note}`
          : " Checking Whisper status…"}
      </p>
      <div className="form-row">
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) setTrFile(f);
          }}
          title="Ya audio/video file yahan drop karein"
          style={{ border: "1px dashed var(--hatch-widget-border)", padding: 8, borderRadius: 8 }}
        >
          Audio/video file (drop bhi kar sakte hain){" "}
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac,.mp4,.mov,.webm"
            onChange={(e) => setTrFile(e.target.files?.[0] ?? null)}
            aria-label="Audio or video file to transcribe"
          />
        </label>
        <select
          value={trModel}
          onChange={(e) => setTrModel(e.target.value)}
          aria-label="Whisper model"
        >
          {(whisperStatus?.models_cached ?? ["tiny"]).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button
          onClick={() => void onTranscribe()}
          disabled={!trFile || trBusy || !whisperStatus?.transcribe_ready}
        >
          {trBusy ? "Transcribing…" : "Transcribe"}
        </button>
      </div>
      {trError && <p className="error">{trError}</p>}
      {transcriptions.length > 0 && (
        <div className="form-row">
          <select
            value={transcription?.id ?? ""}
            onChange={(e) => void onSelectTranscription(Number(e.target.value))}
            aria-label="Transcription"
            style={{ flex: 1 }}
          >
            {transcriptions.map((t) => (
              <option key={t.id} value={t.id}>
                #{t.id} · {t.source_filename} · {t.model} ·{" "}
                {t.job_status ?? "queued"}
              </option>
            ))}
          </select>
        </div>
      )}
      {transcription && transcription.job_status !== "done" && (
        <p className="muted">
          Status: {transcription.job_status}
          {transcription.job_error ? ` — ${transcription.job_error}` : ""}
        </p>
      )}
      {transcription && transcription.job_status === "done" && (
        <>
          <p>
            <strong>
              {transcription.word_count ?? transcription.words?.length ?? 0}{" "}
              words
            </strong>{" "}
            · {transcription.language} · {transcription.duration_s}s · model{" "}
            {transcription.model}
          </p>
          <p>{transcription.full_text}</p>
          {trEditing ? (
            <>
              <textarea
                value={trEditText}
                onChange={(e) => setTrEditText(e.target.value)}
                rows={6}
                aria-label="Edit transcript text"
              />
              <p className="muted">
                Sirf text badlega — word timings aur SRT/VTT original
                rehte hain, is liye captions audio se nahi hatenge.
              </p>
              <div className="form-row">
                <button
                  onClick={() => void onSaveTranscriptionEdit()}
                  disabled={trEditBusy}
                >
                  {trEditBusy ? "Saving…" : "Save text"}
                </button>
                <button
                  className="ghostbtn"
                  onClick={() => setTrEditing(false)}
                >
                  Cancel
                </button>
              </div>
            </>
          ) : null}
          <div className="form-row">
            <a
              className="ghostbtn"
              href={api.transcriptionSrtUrl(transcription.id)}
              download
            >
              Download SRT
            </a>
            <button
              className="ghostbtn"
              onClick={async () => {
                try {
                  const res = await fetch(
                    api.transcriptionSrtUrl(transcription.id),
                  );
                  if (!res.ok) throw new Error("SRT nahi mili");
                  await navigator.clipboard.writeText(await res.text());
                  setNotice("SRT copy ho gayi — paste karein.");
                } catch (e) {
                  setTrError(
                    e instanceof Error ? e.message : "Copy SRT failed",
                  );
                }
              }}
            >
              Copy SRT
            </button>
            <a
              className="ghostbtn"
              href={api.transcriptionVttUrl(transcription.id)}
              download
            >
              Download VTT
            </a>
            <a
              className="ghostbtn"
              href={api.transcriptionTxtUrl(transcription.id)}
              download
            >
              Download TXT
            </a>
            <button
              className="ghostbtn"
              onClick={() => {
                setTrEditText(transcription.full_text);
                setTrEditing(true);
              }}
            >
              Edit text
            </button>
            <button
              className="ghostbtn"
              onClick={() => void onUseTranscriptionAsScript()}
              disabled={trUseAsScriptBusy}
            >
              Use as script
            </button>
          </div>
          <div className="word-list">
            {transcription.words?.map((w, i) => (
              <span key={i} className="word-chip" title={`${w.start}s – ${w.end}s`}>
                {w.word} <span className="muted">{w.start}s</span>
              </span>
            ))}
          </div>
        </>
      )}

        </>
      )}
      {voiceTab === "heygen" && (
        <>
      <h2>VoiceForge — HeyGen clone (apni awaz)</h2>
      <p className="muted">
        Ye awaz aapki apni HeyGen clone awaz hai — apni key aur apni
        clone voice_id Settings me lagayen. HeyGen free-tier default
        NAHI hai — Turbo paid hai, Turbo Free 30 Nov 2026 tak free hai.
        {heygenStatus
          ? heygenStatus.key_configured
            ? heygenStatus.voice_name
              ? ` Key set hai · Voice: ${heygenStatus.voice_name} · Model: ${heygenStatus.model}.`
              : " Key set hai · Clone voice_id set nahi hai — Settings me lagayen."
            : " Key set nahi hai."
          : " Checking HeyGen status…"}
      </p>
      <textarea
        value={heygenText}
        onChange={(e) => setHeygenText(e.target.value)}
        placeholder="Text likhein — English ya Urdu/Hindi (max 5000 characters)…"
        aria-label="HeyGen clone text"
        rows={4}
      />
      <div className="form-row" style={{ marginTop: 8 }}>
        <select
          value={heygenLang}
          onChange={(e) => setHeygenLang(e.target.value)}
          aria-label="HeyGen language"
        >
          <option value="en">English — as-is (no pitch change)</option>
          <option value="hi">Urdu/Hindi — 106 Hz pitch lock</option>
        </select>
        <button
          onClick={() => void onHeygenSpeak()}
          disabled={
            !heygenText.trim() ||
            heygenBusy ||
            !heygenStatus?.key_configured
          }
        >
          {heygenBusy ? "Generating…" : "Generate in my voice"}
        </button>
        {!heygenStatus?.key_configured && (
          <span className="muted">
            HeyGen key + apni clone voice_id Settings me lagayen — bina
            dono ke awaz nahi ban sakti.
          </span>
        )}
      </div>
      {heygenJobId !== null && (
        <p className="muted">Job #{heygenJobId} — generating…</p>
      )}
      {heygenError && <p className="error">{heygenError}</p>}
      {heygenVoices.length > 0 && (
        <>
          <h3>Clone voiceovers</h3>
          {heygenVoices.map((hv) => (
            <div key={hv.id} className="scene-card">
              <strong>
                #{hv.id} · {hv.language === "hi" ? "Urdu/Hindi" : "English"} ·{" "}
                {hv.duration_s}s · {hv.job_status ?? "queued"}
              </strong>
              <span className="muted">
                {hv.pitch_applied
                  ? "106 Hz pitch lock applied (×1.0495, tempo unchanged)"
                  : hv.language === "hi"
                    ? "⚠ pitch lock nahi laga (is PC par rubberband nahi mila)"
                    : "as-is — English par pitch change nahi hota"}
              </span>
              {hv.job_error && <p className="error">{hv.job_error}</p>}
              {hv.asset_path && (
                <audio src={fileUrl(hv.asset_path)} controls style={{ width: "100%" }} />
              )}
            </div>
          ))}
        </>
      )}

        </>
      )}
        </>
      )}
      {activeTool === "clipforge" && (
        <>
      <h2 id="tool-clipforge">ClipForge — Long video</h2>
      <p className="muted">
        Lambi video upload karein — iski audio local Whisper se likhi
        jayegi (free, offline, no key), har lafz ke time ke saath.
        Transcription tayyar hote hi "Find moments" se 15–60 s ke best
        moments niklein ge — score ke saath; Preview dabate hi video usi
        jagah se chalega. Sirf wo models jo is PC par cached hain — kuch
        download nahi hota.
        {whisperStatus
          ? whisperStatus.transcribe_ready
            ? ` Ready — cached models: ${whisperStatus.models_cached.join(", ")}.`
            : ` ${whisperStatus.note}`
          : " Checking Whisper status…"}
      </p>
      <div className="form-row">
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) setSvFile(f);
          }}
          title="Ya long video yahan drop karein"
          style={{ border: "1px dashed var(--hatch-widget-border)", padding: 8, borderRadius: 8 }}
        >
          Long video (drop bhi kar sakte hain){" "}
          <input
            type="file"
            accept=".mp4,.mov,.webm"
            onChange={(e) => setSvFile(e.target.files?.[0] ?? null)}
            aria-label="Long video to clip"
          />
        </label>
        <select
          value={trModel}
          onChange={(e) => setTrModel(e.target.value)}
          aria-label="Whisper model"
        >
          {(whisperStatus?.models_cached ?? ["tiny"]).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button
          onClick={() => void onUploadSourceVideo()}
          disabled={!svFile || svBusy || !whisperStatus?.transcribe_ready}
        >
          {svBusy ? "Uploading…" : "Upload + transcribe"}
        </button>
      </div>
      {svError && <p className="error">{svError}</p>}
      {sourceVideos.length > 0 && (
        <div className="form-row">
          <select
            value={sourceVideo?.id ?? ""}
            onChange={(e) => void onSelectSourceVideo(Number(e.target.value))}
            aria-label="Source video"
            style={{ flex: 1 }}
          >
            {sourceVideos.map((sv) => (
              <option key={sv.id} value={sv.id}>
                #{sv.id} · {sv.source_filename} · {sv.duration_s}s ·{" "}
                {sv.job_status ?? "queued"}
              </option>
            ))}
          </select>
        </div>
      )}
      {sourceVideo && sourceVideo.job_status !== "done" && (
        <p className="muted">
          Status: {sourceVideo.job_status}
          {sourceVideo.job_error ? ` — ${sourceVideo.job_error}` : ""}
        </p>
      )}
      {sourceVideo && sourceVideo.job_status === "done" && (
        <>
          {sourceVideo.asset_path && (
            <video
              ref={svVideoRef}
              src={fileUrl(sourceVideo.asset_path)}
              controls
              style={{ width: "100%", maxHeight: 360 }}
            />
          )}
          <p>
            <strong>{sourceVideo.word_count} words</strong> ·{" "}
            {sourceVideo.language} · {sourceVideo.duration_s}s video · model{" "}
            {sourceVideo.model}
          </p>
          <p>{sourceVideo.full_text}</p>
          <div className="form-row">
            <a
              className="ghostbtn"
              href={api.transcriptionSrtUrl(sourceVideo.transcription_id ?? 0)}
              download
            >
              Download SRT
            </a>
            <a
              className="ghostbtn"
              href={api.transcriptionVttUrl(sourceVideo.transcription_id ?? 0)}
              download
            >
              Download VTT
            </a>
          </div>
          <div className="word-list">
            {sourceVideo.words?.map((w, i) => (
              <span key={i} className="word-chip" title={`${w.start}s – ${w.end}s`}>
                {w.word} <span className="muted">{w.start}s</span>
              </span>
            ))}
          </div>
          <h3>Moments — best clips (Phase 6 slice 2)</h3>
          <p className="muted">
            Har moment 15–60 s ka hai, likhai ke asal time se nikla hua.
            Score 4 cheezon se banta hai — density (alfaz per second),
            keywords (sawal / number / zor wale lafz), silence (aage-peeche
            khamoshi), length (20–45 s behtareen). Audio energy score me
            nahi hai — wo naapi nahi gayi, is liye banayi bhi nahi gayi.
            Har moment ka vertical preview yahin banta hai (chosen
            aspect — 9:16 / 1:1 / 4:5 / 3:4 — centre crop, captions ke
            saath — face tracking baad me). Approve karein to hi final
            clip banta hai — bina approval ke render nahi hota. Approved
            clips neeche "Approved clips" me milte hain (Download, SRT,
            Copy link, Reuse, Rename, Delete).
          </p>
          <div className="form-row">
            <button
              onClick={() => void onDetectMoments()}
              disabled={momentsBusy}
            >
              {momentsBusy ? "Finding moments…" : "Find moments"}
            </button>
            <label>
              Clips{" "}
              <select
                value={momentsMax}
                onChange={(e) => setMomentsMax(Number(e.target.value))}
                disabled={momentsBusy}
              >
                {[1, 3, 5, 10].map((n) => (
                  <option key={n} value={n}>
                    {n === 5 ? "Auto (up to 5)" : `Up to ${n}`}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Length{" "}
              <select
                value={momentsTargetLength}
                onChange={(e) => setMomentsTargetLength(e.target.value)}
                disabled={momentsBusy}
              >
                <option value="">Auto</option>
                {[15, 25, 30, 40, 60, 90].map((n) => (
                  <option key={n} value={n}>
                    {n}s
                  </option>
                ))}
              </select>
            </label>
            {moments.length > 0 && (
              <span className="muted">
                {moments.length} moment(s) · best score{" "}
                {Math.max(...moments.map((m) => m.score))}
              </span>
            )}
          </div>
          {momentsError && <p className="error">{momentsError}</p>}
          {momentsNote && <p className="muted">{momentsNote}</p>}
          {moments.map((m, i) => (
            <div className="scene-card" key={m.id}>
              <strong>
                Moment {i + 1} · score {m.score} · {m.start_s}s – {m.end_s}
                s · {(m.end_s - m.start_s).toFixed(1)}s · {m.word_count}{" "}
                words
              </strong>
              <p>{m.title}</p>
              <p className="muted">{m.excerpt}</p>
              <p className="muted">
                density {m.score_breakdown.density} · keywords{" "}
                {m.score_breakdown.keywords} ({m.score_breakdown.hook_hits}{" "}
                hits) · silence {m.score_breakdown.silence} (gap{" "}
                {m.score_breakdown.gap_before_s}s /{" "}
                {m.score_breakdown.gap_after_s}s) · length{" "}
                {m.score_breakdown.length} ·{" "}
                {m.score_breakdown.words_per_second} words/s
              </p>
              <div className="form-row">
                <button
                  className="ghostbtn"
                  onClick={() => onPreviewMoment(m.start_s)}
                >
                  Preview from {m.start_s}s
                </button>
              </div>
              <div className="form-row">
                <span className="muted">
                  Approval:{" "}
                  {m.approval === "approved"
                    ? "✓ Approved"
                    : m.approval === "rejected"
                      ? "✕ Rejected"
                      : "Pending"}
                </span>
                <button
                  className="ghostbtn"
                  onClick={() => void onApproveMoment(m)}
                  disabled={m.approval === "approved"}
                >
                  Approve
                </button>
                <button
                  className="ghostbtn"
                  onClick={() => void onRejectMoment(m)}
                  disabled={m.approval === "rejected"}
                >
                  Reject
                </button>
                {m.approval === "approved" && (
                  <button
                    onClick={() => void onRenderFinalClip(m)}
                    disabled={!!finalBusyByMoment[m.id]}
                    title="Sirf approved moments ka final 9:16 clip banta hai — wahi caption style jo preview me chuna tha"
                  >
                    {finalBusyByMoment[m.id]
                      ? "Rendering final…"
                      : "Render final clip"}
                  </button>
                )}
              </div>
              {finalErrorByMoment[m.id] && (
                <p className="error">{finalErrorByMoment[m.id]}</p>
              )}
              <div className="form-row">
                <select
                  value={reframeStyleByMoment[m.id] || "Bold White"}
                  onChange={(e) =>
                    setReframeStyleByMoment((prev) => ({
                      ...prev,
                      [m.id]: e.target.value,
                    }))
                  }
                  aria-label={`Caption style for moment ${i + 1}`}
                >
                  {captionStyles
                    .filter((c) => RENDERABLE_CAPTION_STYLES.includes(c.name))
                    .map((c) => (
                      <option key={c.id} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  <option value="One Word Pop">
                    One Word Pop (one word at a time)
                  </option>
                </select>
                <select
                  value={reframeAspectByMoment[m.id] || "9:16"}
                  onChange={(e) =>
                    setReframeAspectByMoment((prev) => ({
                      ...prev,
                      [m.id]: e.target.value,
                    }))
                  }
                  aria-label={`Aspect for moment ${i + 1}`}
                >
                  {VERTICAL_ASPECTS.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                <select
                  value={reframeSizeByMoment[m.id] ?? 100}
                  onChange={(e) =>
                    setReframeSizeByMoment((prev) => ({
                      ...prev,
                      [m.id]: Number(e.target.value),
                    }))
                  }
                  aria-label={`Caption size for moment ${i + 1}`}
                >
                  {[50, 75, 100, 125, 150].map((p) => (
                    <option key={p} value={p}>
                      {p}%
                    </option>
                  ))}
                </select>
                <select
                  value={reframePositionByMoment[m.id] || "bottom"}
                  onChange={(e) =>
                    setReframePositionByMoment((prev) => ({
                      ...prev,
                      [m.id]: e.target.value,
                    }))
                  }
                  aria-label={`Caption position for moment ${i + 1}`}
                >
                  {CAPTION_POSITIONS.map((p) => (
                    <option key={p} value={p}>
                      {p === "bottom"
                        ? "Bottom"
                        : p === "center"
                          ? "Center"
                          : "Top"}
                    </option>
                  ))}
                </select>
                <label>
                  <input
                    type="checkbox"
                    checked={reframeCaptionsByMoment[m.id] ?? true}
                    onChange={(e) =>
                      setReframeCaptionsByMoment((prev) => ({
                        ...prev,
                        [m.id]: e.target.checked,
                      }))
                    }
                  />{" "}
                  Captions
                </label>
                <button
                  onClick={() => void onReframeMoment(m)}
                  disabled={!!reframeBusyByMoment[m.id]}
                  title="Centre-cropped vertical clip with burned-in captions (preview only — final render needs approval)"
                >
                  {reframeBusyByMoment[m.id]
                    ? "Making preview…"
                    : "Make preview"}
                </button>
              </div>
              {reframeErrorByMoment[m.id] && (
                <p className="error">{reframeErrorByMoment[m.id]}</p>
              )}
              {(reframesByMoment[m.id] ?? []).map((rf) => (
                <div key={rf.id}>
                  <p className="muted">
                    {rf.aspect || "9:16"} · {rf.width}x{rf.height} ·{" "}
                    {rf.duration_s}s · {rf.caption_style} · {rf.job_status}
                    {rf.job_error ? ` — ${rf.job_error}` : ""}
                  </p>
                  {rf.job_status === "done" && rf.asset_path && (
                    <>
                      <video
                        src={fileUrl(rf.asset_path)}
                        controls
                        style={{
                          width: 270,
                          maxWidth: "100%",
                          aspectRatio: (rf.aspect || "9:16").replace(
                            ":",
                            " / ",
                          ),
                        }}
                      />
                      <div className="form-row">
                        <a
                          className="ghostbtn"
                          href={fileUrl(rf.asset_path)}
                          download
                        >
                          Download {rf.aspect || "9:16"} clip
                        </a>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          ))}
          {finalClips.length > 0 && (
            <>
              <h3>Approved clips — final (Phase 6 slice 4)</h3>
              <p className="muted">
                Sirf approved moments yahan aate hain — bina approval ke
                koi final clip nahi banta. Har clip: chosen aspect,
                captions ke saath, Download + SRT + Copy link + Reuse +
                Rename + Delete.
              </p>
              {finalClips.map((fc) => (
                <div className="scene-card" key={fc.id}>
                  <strong>
                    {fc.title || fc.moment_title || `Clip #${fc.id}`} ·{" "}
                    {fc.aspect || "9:16"} · {fc.width}x{fc.height} ·{" "}
                    {fc.duration_s}s · {fc.caption_style} · {fc.job_status}
                    {fc.job_error ? ` — ${fc.job_error}` : ""}
                  </strong>
                  {fc.job_status === "done" && fc.asset_path && (
                    <>
                      <video
                        src={fileUrl(fc.asset_path)}
                        controls
                        style={{
                          width: 270,
                          maxWidth: "100%",
                          aspectRatio: (fc.aspect || "9:16").replace(
                            ":",
                            " / ",
                          ),
                        }}
                      />
                      <div className="form-row">
                        <a
                          className="ghostbtn"
                          href={fileUrl(fc.asset_path)}
                          download
                        >
                          Download final clip
                        </a>
                        <a
                          className="ghostbtn"
                          href={api.finalClipSrtUrl(fc.id)}
                          download
                        >
                          Download SRT
                        </a>
                        <button
                          className="ghostbtn"
                          onClick={() => void onCopyFinalLink(fc)}
                        >
                          Copy link
                        </button>
                        <button
                          className="ghostbtn"
                          onClick={() => void onReuseFinalClip(fc)}
                          title="Is clip ki copy is project ki Media Library me daalein"
                        >
                          Reuse in this project
                        </button>
                      </div>
                    </>
                  )}
                  <div className="form-row">
                    <input
                      value={renameDraftByClip[fc.id] ?? fc.title}
                      onChange={(e) =>
                        setRenameDraftByClip((prev) => ({
                          ...prev,
                          [fc.id]: e.target.value,
                        }))
                      }
                      aria-label={`Rename final clip ${fc.id}`}
                      style={{ flex: 1 }}
                    />
                    <button
                      className="ghostbtn"
                      onClick={() => void onRenameFinalClip(fc)}
                      disabled={
                        !(renameDraftByClip[fc.id] ?? "").trim() ||
                        (renameDraftByClip[fc.id] ?? "").trim() === fc.title
                      }
                    >
                      Rename
                    </button>
                    <button
                      className="ghostbtn"
                      onClick={() => void onDeleteFinalClip(fc)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}

        </>
      )}
      {activeTool === "storycraft" && (
        <>
      <div className="form-row" role="tablist" aria-label="StoryCraft sections">
        {(
          [
            ["Script", "script"],
            ["Niches", "niches"],
            ["Character Vault", "vault"],
            ["Research Notes", "research"],
          ] as [string, string][]
        ).map(([label, id]) => (
          <button
            key={id}
            className={storyTab === id ? "" : "ghostbtn"}
            onClick={() => setStoryTab(id)}
          >
            {label}
          </button>
        ))}
        <button className="ghostbtn" onClick={() => onActiveTool("master-prompts")}>
          Master Prompt Library →
        </button>
      </div>
      {storyTab === "script" && (
        <>
      <h2 id="script-section">Script</h2>
      <p className="muted">
        Paste or type the narration — no key needed. Or write only a topic
        and let Gemini (free tier, key in Settings) write the script. The
        script splits into one scene per sentence — har sentence par
        visual badlega; each scene gets an image prompt from the
        Style DNA + main character.
      </p>
      <div className="form-row">
        <input
          value={scriptTopic}
          onChange={(e) => setScriptTopic(e.target.value)}
          placeholder="Topic (e.g. The Man Who Sold the Eiffel Tower)"
          aria-label="Script topic"
          style={{ flex: 1 }}
        />
      </div>
      <textarea
        value={scriptText}
        onChange={(e) => setScriptText(e.target.value)}
        placeholder="Paste or type the full script here — one beat per paragraph…"
        aria-label="Script text"
        rows={6}
      />
      <div className="form-row" style={{ marginTop: 8 }}>
        <label>
          Thinking level{" "}
          <select
            value={thinkingLevel}
            onChange={(e) => setThinkingLevel(e.target.value)}
            aria-label="Thinking level"
          >
            {(
              storycraftOptions?.thinking_levels ?? [
                { id: "low", label: "Low — tez draft", words: "80-100" },
                {
                  id: "medium",
                  label: "Medium — balanced",
                  words: "140-160",
                },
                {
                  id: "high",
                  label: "High — gehri script",
                  words: "200-260",
                },
              ]
            ).map((l) => (
              <option key={l.id} value={l.id}>
                {l.label} ({l.words} words)
              </option>
            ))}
          </select>
        </label>
        <label>
          Model{" "}
          <select
            value={scriptModel}
            onChange={(e) => setScriptModel(e.target.value)}
            aria-label="Script model"
          >
            {(
              storycraftOptions?.models ?? [
                { id: "fast", label: "Fast — tez draft", model: "" },
                { id: "deep", label: "Deep — gehri, slow", model: "" },
                {
                  id: "code",
                  label: "Code — structured, precise",
                  model: "",
                },
              ]
            ).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">
          Sirf topic se script likhwane par lagoo — pasted text par nahi.
          Research notes se script par bhi yehi lagte hain.
        </span>
      </div>
      <div className="form-row" style={{ marginTop: 8 }}>
        <button
          onClick={() => void onSaveScript()}
          disabled={busy || (!scriptText.trim() && !scriptTopic.trim())}
        >
          Save script
        </button>
        {script && (
          <button
            className="ghostbtn"
            onClick={() => void onDeleteScript()}
            disabled={busy}
          >
            Delete script
          </button>
        )}
        {script && (
          <button
            className="ghostbtn"
            onClick={() => void onResplitSentences()}
            disabled={busy}
            title="One scene per sentence — har sentence par naya visual"
          >
            Re-split into sentences
          </button>
        )}
        <span className="muted">
          {script
            ? `${scenes.length} scene(s) · source: ${script.source}`
            : "No script saved yet."}
        </span>
      </div>
      {scenes.length > 0 && (
        <>
          <h3>Scenes</h3>
          {scenes.map((sc, i) => {
            const d = sceneDraft(sc);
            return (
              <div className="scene-card" key={sc.id}>
                <strong>
                  Scene {i + 1} · ~{sc.duration_s}s
                </strong>
                <label>
                  Text
                  <textarea
                    value={d.text}
                    onChange={(e) =>
                      setSceneDrafts((prev) => ({
                        ...prev,
                        [sc.id]: { ...sceneDraft(sc), text: e.target.value },
                      }))
                    }
                    aria-label={`Scene ${i + 1} text`}
                    rows={2}
                  />
                </label>
                <label>
                  Image prompt
                  <textarea
                    value={d.image_prompt}
                    onChange={(e) =>
                      setSceneDrafts((prev) => ({
                        ...prev,
                        [sc.id]: {
                          ...sceneDraft(sc),
                          image_prompt: e.target.value,
                        },
                      }))
                    }
                    aria-label={`Scene ${i + 1} image prompt`}
                    rows={2}
                  />
                </label>
                <div className="form-row">
                  <label>
                    Duration (s){" "}
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={d.duration_s}
                      onChange={(e) =>
                        setSceneDrafts((prev) => ({
                          ...prev,
                          [sc.id]: {
                            ...sceneDraft(sc),
                            duration_s: e.target.value,
                          },
                        }))
                      }
                      aria-label={`Scene ${i + 1} duration`}
                    />
                  </label>
                  <button onClick={() => void saveScene(sc)}>Save scene</button>
                  <button
                    className="ghostbtn"
                    onClick={() => void onRegeneratePrompt(sc)}
                  >
                    Regenerate prompt
                  </button>
                </div>
              </div>
            );
          })}
          <div className="form-row">
            <button
              onClick={useScenesInTimeline}
              disabled={busy || scenes.length === 0 || images.length === 0}
            >
              Use scene texts in timeline
            </button>
            <span className="muted">
              Loads each scene&apos;s text as the matching image&apos;s caption
              for auto-sync.
            </span>
          </div>
        </>
      )}

        </>
      )}
      {storyTab === "niches" && (
        <>
      <h2 id="tool-storycraft">StoryCraft — Niches</h2>
      <p className="muted">
        Topic families — har niche ke liye Gemini se 10 fresh topic ideas
        (key Settings me ho to). Kisi topic par click karein to wo script
        topic ban jata hai.
      </p>
      {niches.length > 0 ? (
        <div className="card-grid">
          {niches.map((n) => (
            <div key={n.id} className="card">
              <strong>{n.name}</strong>
              {n.default_style_dna_name && (
                <span className="muted"> · Style: {n.default_style_dna_name}</span>
              )}
              {n.description && <p className="muted">{n.description}</p>}
              {n.main_characters && (
                <p>
                  <span className="muted">Main characters: </span>
                  {n.main_characters
                    .split("\n")
                    .filter((c) => c.trim())
                    .join(" · ")}
                </p>
              )}
              <div className="form-row">
                <button
                  className="ghostbtn"
                  onClick={() => void onSuggestTopics(n)}
                  disabled={!!topicsBusyByNiche[n.id]}
                >
                  {topicsBusyByNiche[n.id] ? "Thinking…" : "Suggest topics"}
                </button>
                <button
                  className="ghostbtn"
                  onClick={() => void onDeleteNiche(n.id)}
                  disabled={busy}
                >
                  Delete
                </button>
              </div>
              {(topicsByNiche[n.id] ?? []).length > 0 && (
                <ul>
                  {topicsByNiche[n.id].map((t, i) => (
                    <li key={i}>
                      <button
                        className="ghostbtn"
                        onClick={() => useTopicAsScriptTopic(t)}
                      >
                        {t}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">Abhi koi niche nahi — neeche se add karein.</p>
      )}
      <div className="form-row">
        <input
          value={newNiche.name}
          onChange={(e) =>
            setNewNiche((prev) => ({ ...prev, name: e.target.value }))
          }
          placeholder="Niche ka naam — jaise Faceless History"
          aria-label="New niche name"
          style={{ flex: 1 }}
        />
        <input
          value={newNiche.description}
          onChange={(e) =>
            setNewNiche((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Description (optional)"
          aria-label="New niche description"
          style={{ flex: 1 }}
        />
        <input
          value={newNiche.main_characters}
          onChange={(e) =>
            setNewNiche((prev) => ({
              ...prev,
              main_characters: e.target.value,
            }))
          }
          placeholder="Main characters — one per line (optional)"
          aria-label="New niche main characters"
          style={{ flex: 1 }}
        />
        <button onClick={() => void onAddNiche()} disabled={busy || nicheBusy}>
          {nicheBusy ? "Adding…" : "Add niche"}
        </button>
      </div>

        </>
      )}
      {storyTab === "vault" && (
        <>
      <h2>StoryCraft — Character Vault</h2>
      <p className="muted">
        Har niche ke locked characters — ek dafa approve + lock ho jaye to
        har scene me wahi chehra, wahi kapde, wahi prop aayega. Edit
        kabhi locked version ko nahi badalta — naya draft version banta
        hai, phir approve + lock karein. Magic Mode aur VisualForge me
        niche chunein to sirf locked characters use hote hain.
      </p>
      {/* Release Packaging (v0.14.0): Apna Main Character */}
      {mainCharacter && (
        <p>
          <span className="badge green">
            ★ My Main Character: {mainCharacter.name}
          </span>{" "}
          <span className="muted">
            — har Magic/bulk run me har scene me wahi aayega (poori
            description verbatim + sheet reference image).
          </span>
        </p>
      )}
      <div className="form-row">
        <button
          className="goldbtn"
          onClick={() => setShowMyCharForm((v) => !v)}
        >
          {showMyCharForm ? "Form band karein" : "＋ Apna Main Character Add Karo"}
        </button>
        <button
          className="ghostbtn"
          onClick={() => void loadMyChars()}
          disabled={myCharsBusy}
        >
          {myCharsBusy ? "Load ho raha…" : "My Characters dekhein"}
        </button>
      </div>
      {showMyCharForm && (
        <div className="scene-card">
          <p className="muted">
            Apni character sheet image upload karein (ek sheet, ya
            front/side/back), naam + description likhein, niche chunein.
            Entry draft banegi — phir Approve → Lock → “Set as my main
            character”. Sheet sirf is PC par rehti hai, kabhi ZIP/repo
            me nahi jati.
          </p>
          <div className="form-row">
            <input
              type="text"
              placeholder="Character ka naam"
              aria-label="Character name"
              value={myCharForm.name}
              onChange={(e) =>
                setMyCharForm((f) => ({ ...f, name: e.target.value }))
              }
            />
            <select
              value={myCharForm.niche_id}
              onChange={(e) =>
                setMyCharForm((f) => ({ ...f, niche_id: e.target.value }))
              }
              aria-label="Niche"
            >
              <option value="">Niche chunein…</option>
              {vaultList.map((v) => (
                <option key={v.niche_id} value={String(v.niche_id)}>
                  {v.niche_name}
                </option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Signature prop (optional)"
              aria-label="Signature prop"
              value={myCharForm.signature_prop}
              onChange={(e) =>
                setMyCharForm((f) => ({
                  ...f,
                  signature_prop: e.target.value,
                }))
              }
            />
          </div>
          <textarea
            value={myCharForm.description}
            onChange={(e) =>
              setMyCharForm((f) => ({ ...f, description: e.target.value }))
            }
            placeholder="Description — poora paragraph: chehra, kapde, rang, style… (yehi har image prompt me jayega)"
            aria-label="Character description"
            rows={4}
          />
          <div className="form-row" style={{ marginTop: 8 }}>
            <input
              type="file"
              accept="image/*"
              aria-label="Character sheet image"
              onChange={(e) => setMyCharFile(e.target.files?.[0] ?? null)}
            />
            <button
              onClick={() => void onCreateMyCharacter()}
              disabled={myCharBusy}
            >
              {myCharBusy ? "Save ho raha…" : "Save as draft"}
            </button>
          </div>
        </div>
      )}
      {myCharsLoaded && (
        <div>
          <h3>My Characters ({myChars.length})</h3>
          {myChars.length === 0 ? (
            <p className="muted">
              Abhi koi apna character nahi hai — upar wale button se
              add karein. Built-in 70 characters neeche niches me hain.
            </p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Character</th>
                  <th>Niche</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {myChars.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.name}</strong>
                      {c.is_main && (
                        <span className="badge green"> ★ my main</span>
                      )}
                      {c.sheet_url && (
                        <>
                          <br />
                          <img
                            src={fileUrl(
                              c.sheet_url.replace(/^\/files\//, ""),
                            )}
                            alt={`${c.name} sheet`}
                            style={{ maxWidth: 120, borderRadius: 6 }}
                          />
                        </>
                      )}
                    </td>
                    <td>
                      {vaultList.find((v) => v.niche_id === c.niche_id)
                        ?.niche_name ?? c.niche_id}
                    </td>
                    <td>v{c.version}</td>
                    <td>
                      <span
                        className={
                          c.status === "locked"
                            ? "badge green"
                            : c.status === "approved"
                              ? "badge"
                              : "badge gold"
                        }
                      >
                        {c.status}
                      </span>
                    </td>
                    <td>
                      <div className="form-row">
                        {c.status === "draft" && (
                          <button
                            className="ghostbtn"
                            onClick={() =>
                              void onApproveVaultCharacter(c.niche_id, c.id)
                            }
                            disabled={vaultBusy}
                          >
                            Approve
                          </button>
                        )}
                        {c.status === "approved" && (
                          <button
                            className="ghostbtn"
                            onClick={() =>
                              void onLockVaultCharacter(c.niche_id, c.id)
                            }
                            disabled={vaultBusy}
                          >
                            Lock
                          </button>
                        )}
                        {c.status === "locked" && !c.is_main && (
                          <button
                            className="goldbtn"
                            onClick={() => void onSetMainCharacter(c)}
                            disabled={vaultBusy}
                          >
                            Set as my main character
                          </button>
                        )}
                        {c.is_main && (
                          <button
                            className="ghostbtn"
                            onClick={() => void onUnsetMainCharacter(c)}
                            disabled={vaultBusy}
                          >
                            Main hatayen
                          </button>
                        )}
                        <button
                          className="ghostbtn"
                          onClick={() => void onDeleteMyCharacter(c)}
                          disabled={vaultBusy}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {vaultError && <p className="error">{vaultError}</p>}
      {vaultList.length > 0 ? (
        <div className="card-grid">
          {vaultList.map((v) => {
            const detail = vaultDetailByNiche[v.niche_id];
            const expanded = expandedVaultId === v.niche_id;
            return (
              <div key={v.niche_id} className="card">
                <strong>{v.niche_name}</strong>{" "}
                {v.guard_ok ? (
                  <span className="badge green">Locked ✓</span>
                ) : (
                  <span className="badge gold">
                    Sheet baaki — {v.missing_mains.length} mains lock nahi
                  </span>
                )}
                <p className="muted">
                  {v.character_count} characters · {v.mains_locked}/
                  {v.mains_expected} mains locked
                  {!v.guard_ok && v.missing_mains.length > 0 && (
                    <> · baaki: {v.missing_mains.join(", ")}</>
                  )}
                </p>
                {v.mains && v.mains.length > 0 && (
                  <div className="form-row">
                    {v.mains.map((m) => (
                      <span key={m.name} title={m.name} style={{ textAlign: "center" }}>
                        {m.thumb_url ? (
                          <img
                            src={fileUrl(
                              m.thumb_url.replace(/^\/files\//, ""),
                            )}
                            alt={m.name}
                            style={{
                              width: 56,
                              height: 100,
                              objectFit: "cover",
                              objectPosition: "top",
                              borderRadius: 6,
                            }}
                          />
                        ) : (
                          <span className="muted">{m.name}</span>
                        )}
                        <br />
                        <small>{m.name}</small>
                      </span>
                    ))}
                  </div>
                )}
                {v.sheet_url && (
                  <p>
                    <img
                      src={fileUrl(
                        v.sheet_url.replace(/^\/files\//, ""),
                      )}
                      alt={`${v.niche_name} cast sheet`}
                      style={{ maxWidth: "100%", borderRadius: 8 }}
                    />
                  </p>
                )}
                {detail && (
                  <p className="muted">
                    Mains: {detail.locked.main_characters.join(" · ")}
                  </p>
                )}
                <div className="form-row">
                  <button
                    className="ghostbtn"
                    onClick={() => void onToggleVault(v.niche_id)}
                    disabled={vaultBusy}
                  >
                    {expanded ? "Band karein" : "Characters dekhein"}
                  </button>
                </div>
                {expanded && (
                  <>
                    {!detail && vaultBusy && (
                      <p className="muted">Characters load ho rahe hain…</p>
                    )}
                    {detail && (
                      <table>
                        <thead>
                          <tr>
                            <th>Character</th>
                            <th>Role</th>
                            <th>Version</th>
                            <th>Status</th>
                            <th>Prop</th>
                            <th>Poses</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.characters.map((c) => (
                            <tr key={c.id}>
                              <td>
                                <strong>{c.name}</strong>
                                {c.is_active && (
                                  <span className="badge gold"> ★ active</span>
                                )}
                                {c.sheet_url && (
                                  <>
                                    <br />
                                    <img
                                      src={fileUrl(
                                        c.sheet_url.replace(
                                          /^\/files\//,
                                          "",
                                        ),
                                      )}
                                      alt={`${c.name} sheet`}
                                      style={{
                                        maxWidth: 120,
                                        borderRadius: 6,
                                      }}
                                    />
                                  </>
                                )}
                              </td>
                              <td>{c.role === "main" ? "Main" : "Secondary"}</td>
                              <td>v{c.version}</td>
                              <td>
                                <span
                                  className={
                                    c.status === "locked"
                                      ? "badge green"
                                      : c.status === "approved"
                                        ? "badge"
                                        : "badge gold"
                                  }
                                >
                                  {c.status}
                                </span>
                              </td>
                              <td>{c.signature_prop || "—"}</td>
                              <td>{c.poses.length}</td>
                              <td>
                                <div className="form-row">
                                  {c.status === "draft" && (
                                    <button
                                      className="ghostbtn"
                                      onClick={() =>
                                        void onApproveVaultCharacter(
                                          v.niche_id,
                                          c.id,
                                        )
                                      }
                                      disabled={vaultBusy}
                                    >
                                      Approve
                                    </button>
                                  )}
                                  {c.status === "approved" && (
                                    <button
                                      className="ghostbtn"
                                      onClick={() =>
                                        void onLockVaultCharacter(
                                          v.niche_id,
                                          c.id,
                                        )
                                      }
                                      disabled={vaultBusy}
                                    >
                                      Lock
                                    </button>
                                  )}
                                  <button
                                    className="ghostbtn"
                                    onClick={() =>
                                      editingVaultCharId === c.id
                                        ? setEditingVaultCharId(null)
                                        : startEditVaultCharacter(c)
                                    }
                                    disabled={vaultBusy}
                                  >
                                    Edit
                                  </button>
                                  <label className="ghostbtn">
                                    Sheet upload
                                    <input
                                      type="file"
                                      accept="image/*"
                                      style={{ display: "none" }}
                                      onChange={(e) => {
                                        void onUploadVaultSheet(
                                          v.niche_id,
                                          c.id,
                                          e.target.files?.[0],
                                        );
                                        e.target.value = "";
                                      }}
                                    />
                                  </label>
                                  {c.status === "draft" && (
                                    <button
                                      className="ghostbtn"
                                      onClick={() =>
                                        void onDeleteVaultCharacter(
                                          v.niche_id,
                                          c.id,
                                        )
                                      }
                                      disabled={vaultBusy}
                                    >
                                      Delete
                                    </button>
                                  )}
                                </div>
                                {editingVaultCharId === c.id && (
                                  <div className="form-row">
                                    <input
                                      value={vaultEditDraft.description}
                                      onChange={(e) =>
                                        setVaultEditDraft((prev) => ({
                                          ...prev,
                                          description: e.target.value,
                                        }))
                                      }
                                      placeholder="Description"
                                      aria-label="Edit character description"
                                      style={{ flex: 1 }}
                                    />
                                    <input
                                      value={vaultEditDraft.signature_prop}
                                      onChange={(e) =>
                                        setVaultEditDraft((prev) => ({
                                          ...prev,
                                          signature_prop: e.target.value,
                                        }))
                                      }
                                      placeholder="Signature prop"
                                      aria-label="Edit signature prop"
                                      style={{ flex: 1 }}
                                    />
                                    <select
                                      value={vaultEditDraft.role}
                                      onChange={(e) =>
                                        setVaultEditDraft((prev) => ({
                                          ...prev,
                                          role: e.target.value as
                                            | "main"
                                            | "secondary",
                                        }))
                                      }
                                      aria-label="Edit character role"
                                    >
                                      <option value="main">Main</option>
                                      <option value="secondary">
                                        Secondary
                                      </option>
                                    </select>
                                    <button
                                      onClick={() =>
                                        void onSaveVaultCharacter(
                                          v.niche_id,
                                          c.id,
                                        )
                                      }
                                      disabled={vaultBusy}
                                    >
                                      Save naya version
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <div className="form-row">
                      <input
                        value={newVaultChar.name}
                        onChange={(e) =>
                          setNewVaultChar((prev) => ({
                            ...prev,
                            name: e.target.value,
                          }))
                        }
                        placeholder="Naya character — naam"
                        aria-label="New vault character name"
                        style={{ flex: 1 }}
                      />
                      <input
                        value={newVaultChar.description}
                        onChange={(e) =>
                          setNewVaultChar((prev) => ({
                            ...prev,
                            description: e.target.value,
                          }))
                        }
                        placeholder="Description"
                        aria-label="New vault character description"
                        style={{ flex: 1 }}
                      />
                      <input
                        value={newVaultChar.signature_prop}
                        onChange={(e) =>
                          setNewVaultChar((prev) => ({
                            ...prev,
                            signature_prop: e.target.value,
                          }))
                        }
                        placeholder="Signature prop"
                        aria-label="New vault character prop"
                        style={{ flex: 1 }}
                      />
                      <select
                        value={newVaultChar.role}
                        onChange={(e) =>
                          setNewVaultChar((prev) => ({
                            ...prev,
                            role: e.target.value as "main" | "secondary",
                          }))
                        }
                        aria-label="New vault character role"
                      >
                        <option value="main">Main</option>
                        <option value="secondary">Secondary</option>
                      </select>
                      <button
                        onClick={() => void onAddVaultCharacter(v.niche_id)}
                        disabled={vaultBusy}
                      >
                        Add character
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        !vaultError && <p className="muted">Vault load ho raha hai…</p>
      )}

      <h2>Main character</h2>
      <p className="muted">
        One main character per project. Image prompts reference them by name,
        so the same person stays consistent in every scene.
      </p>
      {character ? (
        <p>
          <img
            src={fileUrl(character.image_path)}
            alt={character.name}
            style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 6, verticalAlign: "middle" }}
          />{" "}
          <strong>{character.name}</strong> — reference saved. Upload again to
          replace.
        </p>
      ) : (
        <p className="muted">No main character set yet.</p>
      )}
      <div className="form-row">
        <input
          value={charName}
          onChange={(e) => setCharName(e.target.value)}
          placeholder="Character name (e.g. Victor Lustig)"
          aria-label="Character name"
          style={{ flex: 1 }}
        />
        <label>
          Reference image{" "}
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={(e) => setCharFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>
        <button
          onClick={() => void onSaveCharacter()}
          disabled={busy || !charName.trim() || !charFile}
        >
          Save character
        </button>
      </div>

        </>
      )}
      {storyTab === "research" && (
        <>
      <h2>StoryCraft — Research notes</h2>
      <p className="muted">
        Research yahan paste karein — har note se Gemini se script likhwayi
        ja sakti hai (key Settings me ho to; key nahi to saaf error, koi
        fake script nahi). Script likhwate waqt Script section wale
        Thinking Level + Model lagte hain.
      </p>
      <h3>Deep Research — script se pehle tehqeeq</h3>
      <p className="muted">
        Topic likhein — Gemini (free tier) 4-6 key facts + sources jama
        karega, phir unhi facts se script banegi. Pehle tehqeeq, phir
        script.
      </p>
      <div className="form-row">
        <input
          value={deepResearchTopic}
          onChange={(e) => setDeepResearchTopic(e.target.value)}
          placeholder="Topic (e.g. The Man Who Sold the Eiffel Tower)"
          aria-label="Deep Research topic"
          style={{ flex: 1 }}
        />
        <button
          onClick={() => void onDeepResearch()}
          disabled={busy || deepResearchBusy || !deepResearchTopic.trim()}
        >
          {deepResearchBusy ? "Tehqeeq ho rahi hai…" : "Research karo"}
        </button>
      </div>
      <label>
        Title
        <input
          value={newNoteTitle}
          onChange={(e) => setNewNoteTitle(e.target.value)}
          aria-label="New research note title"
        />
      </label>
      <label>
        Note
        <textarea
          value={newNoteContent}
          onChange={(e) => setNewNoteContent(e.target.value)}
          rows={4}
          aria-label="New research note content"
        />
      </label>
      <div className="form-row">
        <button
          onClick={() => void onAddResearchNote()}
          disabled={busy || researchBusy}
        >
          {researchBusy ? "Saving…" : "Add research note"}
        </button>
      </div>
      {researchNotes.length > 0 ? (
        <div className="card-grid">
          {researchNotes.map((note) => {
            const draft = noteDrafts[note.id];
            const editing = editingNoteId === note.id;
            return (
              <div key={note.id} className="card">
                {editing && draft ? (
                  <>
                    <label>
                      Title
                      <input
                        value={draft.title}
                        onChange={(e) =>
                          setNoteDrafts((prev) => ({
                            ...prev,
                            [note.id]: { ...draft, title: e.target.value },
                          }))
                        }
                        aria-label={`Research note ${note.id} title`}
                      />
                    </label>
                    <label>
                      Note
                      <textarea
                        value={draft.content}
                        onChange={(e) =>
                          setNoteDrafts((prev) => ({
                            ...prev,
                            [note.id]: { ...draft, content: e.target.value },
                          }))
                        }
                        rows={4}
                        aria-label={`Research note ${note.id} content`}
                      />
                    </label>
                    <div className="form-row">
                      <button
                        onClick={() => void onSaveResearchNote(note.id)}
                        disabled={busy}
                      >
                        Save
                      </button>
                      <button
                        className="ghostbtn"
                        onClick={() => setEditingNoteId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <strong>
                      {note.title}
                      {note.kind === "deep-research" && (
                        <span className="muted"> · Deep Research</span>
                      )}
                    </strong>
                    {note.kind === "deep-research" &&
                    note.facts.length > 0 ? (
                      <ul>
                        {note.facts.map((f, i) => (
                          <li key={i}>
                            {f.fact}
                            <br />
                            <span className="muted">
                              Source: {f.source || "—"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p style={{ whiteSpace: "pre-wrap" }}>
                        {note.content}
                      </p>
                    )}
                    <div className="form-row">
                      <button
                        className="ghostbtn"
                        onClick={() => void onWriteScriptFromResearch(note.id)}
                        disabled={busy}
                      >
                        Write script from research
                      </button>
                      <button
                        className="ghostbtn"
                        onClick={() => {
                          setEditingNoteId(note.id);
                          setNoteDrafts((prev) => ({
                            ...prev,
                            [note.id]: {
                              title: note.title,
                              content: note.content,
                            },
                          }));
                        }}
                      >
                        Edit
                      </button>
                      <button
                        className="ghostbtn"
                        onClick={() => void onDeleteResearchNote(note.id)}
                        disabled={busy}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted">Is project me abhi koi research note nahi.</p>
      )}

        </>
      )}
        </>
      )}
      {activeTool === "visualforge" && (
        <>
      <h2 id="tool-visualforge">VisualForge — Image Prompts</h2>
      <p className="muted">
        Every scene&apos;s image prompt, built from the Style DNA + main
        character. “Generate all images” sends each prompt to the
        chosen provider — Gemini API (reliable, billing lagti hai, 20
        free per day hard limit), Gemini Canvas (free, aapki Gemini
        Pro quota se — ek dafa Google login chahiye) ya Google Flow
        (free, Imagen se — wahi Google login; Flow fail ho to Canvas
        par fallback) — with the
        character reference attached, so the same face stays in every
        scene. Without a Gemini key in Settings, API generation fails
        with a plain message; without a Google login, Canvas/Flow jobs
        stop at “Blocked — login chahiye”. Prompts and uploads still
        work either way. Har image use hone se pehle check hoti hai:
        Approve karein to hi timeline me jati hai, Reject karein to
        dobara generate hoti hai.
      </p>
      {prompts ? (
        <>
          <p className="muted">
            Style: {prompts.style_dna_name ?? "—"} · Character:{" "}
            {prompts.character_name ?? "—"} · Gemini free tier:{" "}
            {prompts.quota.used_today}/{prompts.quota.daily_limit} used today
            ({prompts.quota.remaining} left) · {prompts.quota.note}
          </p>
          {genStatus && genStatus.quota.daily_limit > 0 && (
            <div
              className="quota-bar"
              role="progressbar"
              aria-valuenow={genStatus.quota.used_today}
              aria-valuemax={genStatus.quota.daily_limit}
              aria-label="Images generated today"
            >
              <div
                className="quota-bar-fill"
                style={{
                  width: `${Math.min(
                    100,
                    (genStatus.quota.used_today /
                      genStatus.quota.daily_limit) *
                      100,
                  )}%`,
                }}
              />
            </div>
          )}
          <div className="form-row">
            <label>
              <input
                type="radio"
                name="image-provider"
                checked={imageProvider === "canvas"}
                onChange={() => setImageProvider("canvas")}
              />{" "}
              Gemini Canvas (free — Gemini Pro quota)
            </label>
            <label>
              <input
                type="radio"
                name="image-provider"
                checked={imageProvider === "flow"}
                onChange={() => setImageProvider("flow")}
              />{" "}
              Google Flow (free — Gemini Pro quota, Imagen)
            </label>
            <label>
              <input
                type="radio"
                name="image-provider"
                checked={imageProvider === "api"}
                onChange={() => setImageProvider("api")}
              />{" "}
              Gemini API (reliable — billing)
            </label>
            <span className="muted">
              {imageProvider === "canvas"
                ? (prompts.providers?.canvas.note ??
                  "Gemini Canvas — free, aapki Gemini Pro quota se")
                : imageProvider === "flow"
                  ? (prompts.providers?.flow?.note ??
                    "Google Flow — free, aapki Gemini Pro quota se")
                  : (prompts.providers?.api.note ?? "Gemini API")}
            </span>
          </div>
          {imageProvider === "canvas" && (
            <>
              <div className="form-row">
                <span className="muted">
                  {canvasStatus
                    ? canvasStatus.logged_in
                      ? "✓ Canvas ready — free images, aapki Gemini Pro quota se."
                      : `Canvas: ${canvasStatus.message}`
                    : "Canvas status loading…"}
                </span>
                {canvasStatus?.needs_login && (
                  <button
                    onClick={() => void onOpenCanvasLogin()}
                    disabled={canvasLoginBusy}
                  >
                    {canvasLoginBusy ? "Opening…" : "Canvas login kholein"}
                  </button>
                )}
                <button onClick={() => void loadCanvasStatus()}>
                  Refresh status
                </button>
              </div>
              {canvasStatus?.needs_login && (
                <ol className="muted">
                  {canvasStatus.setup_steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              )}
            </>
          )}
          {imageProvider === "flow" && (
            <>
              <div className="form-row">
                <span className="muted">
                  {googleStatus
                    ? googleStatus.flow.logged_in
                      ? "✓ Flow ready — free images, aapki Gemini Pro quota se."
                      : googleStatus.logged_in
                        ? `Flow: ${googleStatus.flow.message || "Flow login check karein"}`
                        : `Flow: ${googleStatus.message}`
                    : "Flow status loading…"}
                </span>
                {googleStatus?.needs_login && (
                  <button
                    onClick={() => void onOpenGoogleLogin()}
                    disabled={googleLoginBusy}
                  >
                    {googleLoginBusy ? "Opening…" : "Connect Google"}
                  </button>
                )}
                <button onClick={() => void loadGoogleStatus()}>
                  Refresh status
                </button>
              </div>
              {googleStatus?.needs_login && (
                <ol className="muted">
                  {googleStatus.setup_steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              )}
              <p className="muted">
                Flow fail ho to scene Canvas par dobara banta hai — image
                phir bhi aati hai, sirf provider badalta hai.
              </p>
              {/* Slice 5: Flow hardening — ready indicator, accounts,
                  Fast mode, recovery, queue, #/@ chaining. */}
              <div className="form-row">
                <span className="muted">
                  {flowStatus
                    ? flowStatus.ready
                      ? `✓ Flow ready${flowReadyAccount?.project_id_fragment ? ` — project ${flowReadyAccount.project_id_fragment}…` : ""}`
                      : `Flow: ${flowStatus.message}`
                    : "Flow status loading…"}
                </span>
                <button onClick={() => void loadFlowStatus()}>
                  Refresh Flow status
                </button>
              </div>
              {flowStatus && (
                <>
                  <div className="form-row">
                    <label>
                      Fast mode (ek saath){" "}
                      <select
                        value={flowStatus.fast_concurrency}
                        disabled={flowBusy}
                        onChange={(e) =>
                          void onFlowSetFast(Number(e.target.value))
                        }
                      >
                        {[1, 2, 3, 4].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </label>
                    <span className="muted">
                      Asal speed: {flowStatus.effective_concurrency} ek saath
                      {flowStatus.accounts.filter((a) => a.ready).length <
                        2 &&
                        " — 1 account se zyada ek saath nahi chal sakte, account add karein"}
                    </span>
                  </div>
                  {flowStatus.accounts.map((a) => (
                    <div className="form-row" key={a.id}>
                      <span className="muted">
                        {a.ready ? "✓" : "○"} {a.name} — {a.status}
                        {a.project_id_fragment
                          ? ` — project ${a.project_id_fragment}…`
                          : ""}
                        {!a.ready && a.detail ? ` — ${a.detail}` : ""}
                        {a.status === "limited" && a.limited_until
                          ? ` — ${a.limited_until} tak araam`
                          : ""}
                      </span>
                      {!a.logged_in && a.status !== "limited" && (
                        <button
                          onClick={() => void onFlowOpenAccountLogin(a.id)}
                          disabled={flowBusy}
                        >
                          Connect
                        </button>
                      )}
                      {a.unusual_activity && (
                        <button
                          onClick={() => void onFlowRecoverAccount(a.id)}
                          disabled={flowBusy}
                        >
                          Recover karein (1 min)
                        </button>
                      )}
                      {a.id !== 1 && (
                        <button
                          onClick={() => void onFlowRemoveAccount(a.id)}
                          disabled={flowBusy}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                  {flowStatus.accounts.length < 3 && (
                    <button
                      onClick={() => void onFlowAddAccount()}
                      disabled={flowBusy}
                    >
                      Account add karein (max 3)
                    </button>
                  )}
                  {flowStatus.recovery_steps.length > 0 && (
                    <div>
                      <p className="muted">
                        <b>Unusual Activity — 1 minute recovery:</b>
                      </p>
                      <ol className="muted">
                        {flowStatus.recovery_steps.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ol>
                      <p className="muted">{flowStatus.recovery_tip}</p>
                    </div>
                  )}
                  <div className="form-row">
                    <button
                      onClick={() => void onFlowPauseQueue()}
                      disabled={
                        flowBusy || !script || flowQueueState?.paused === true
                      }
                    >
                      Queue pause karein
                    </button>
                    <button
                      onClick={() => void onFlowResumeQueue()}
                      disabled={
                        flowBusy || !script || !flowQueueState?.paused
                      }
                    >
                      Queue resume karein
                    </button>
                    <span className="muted">
                      {flowQueueState?.paused ? "Queue paused hai." : ""}
                    </span>
                  </div>
                  {flowQueues.length > 0 && (
                    <div>
                      <p className="muted">
                        <b>Queue history:</b>
                      </p>
                      <ul className="muted">
                        {flowQueues.map((q) => (
                          <li key={q.batch_id}>
                            {q.topic || "Script"} — {q.done}/{q.total} done
                            {q.failed > 0 ? `, ${q.failed} failed` : ""}
                            {q.blocked > 0 ? `, ${q.blocked} blocked` : ""}{" "}
                            <a
                              href={`${API_BASE}/flow/queues/${q.batch_id}/images.zip`}
                            >
                              ZIP download
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="form-row">
                    <input
                      value={chainPrompt}
                      onChange={(e) => setChainPrompt(e.target.value)}
                      placeholder="#Captain define karein, @Captain se wahi character layein"
                    />
                    <button
                      onClick={() => void onChainPreview()}
                      disabled={flowBusy || !chainPrompt.trim()}
                    >
                      Chain preview
                    </button>
                  </div>
                  {chainPreview && (
                    <p className="muted">
                      {chainPreview.prompt}
                      {chainPreview.unknown.length > 0 &&
                        ` — nahi mile: ${chainPreview.unknown.join(", ")}`}
                    </p>
                  )}
                  <p className="muted">
                    #name se character define karein, @name se har scene me
                    wahi character layein — Vault ke locked characters se
                    linked hai.
                  </p>
                </>
              )}
            </>
          )}
          <div className="form-row">
            <button
              onClick={() => void onGenerateImages()}
              disabled={
                genBusy ||
                prompts.prompts.length === 0 ||
                (imageProvider === "api"
                  ? !prompts.quota.generation_available
                  : imageProvider === "flow"
                    ? googleStatus !== null &&
                      (!googleStatus.available || googleStatus.needs_login)
                    : canvasStatus !== null &&
                      (!canvasStatus.available || canvasStatus.needs_login))
              }
            >
              {genBusy
                ? "Queueing…"
                : imageProvider === "canvas"
                  ? "Generate all images (Canvas — free)"
                  : imageProvider === "flow"
                    ? "Generate all images (Flow — free)"
                    : "Generate all images"}
            </button>
            <label title="Off karein to prompt se character ke lafz aur reference image hat jayenge">
              <input
                type="checkbox"
                checked={characterMatch}
                onChange={(e) => setCharacterMatch(e.target.checked)}
              />{" "}
              Character Match
            </label>
            <label>
              Character Vault niche{" "}
              <select
                value={vfNicheId}
                onChange={(e) => setVfNicheId(e.target.value)}
                aria-label="VisualForge Character Vault niche"
              >
                <option value="">Koi niche nahi (Vault band)</option>
                {vaultList.map((n) => (
                  <option
                    key={n.niche_id}
                    value={n.niche_id}
                    disabled={!n.guard_ok}
                  >
                    {n.niche_name} — {n.character_count} characters
                    {n.guard_ok
                      ? " (locked ✓)"
                      : ` (lock baaki: ${n.missing_mains.join(", ") || "sheet baaki"})`}
                  </option>
                ))}
              </select>
            </label>
            <label title="Off karein to prompt se style ke lafz hat jayenge">
              <input
                type="checkbox"
                checked={styleMatch}
                onChange={(e) => setStyleMatch(e.target.checked)}
              />{" "}
              Style Match
            </label>
            <button
              onClick={exportPromptsTxt}
              disabled={prompts.prompts.length === 0}
            >
              Export prompts (.txt)
            </button>
            <span className="muted">
              {prompts.prompts.length} prompt(s) ·{" "}
              {imageProvider === "api" && !prompts.quota.generation_available
                ? "Gemini key Settings me lagayen — bina key ke image nahi ban sakti."
                : genStatus
                  ? `${genStatus.scenes.filter((s) => s.status === "done").length} done · ${genStatus.scenes.filter((s) => s.status === "failed").length} failed · ${genStatus.scenes.filter((s) => s.status === "blocked").length} blocked · ${genStatus.scenes.filter((s) => s.status === "queued" || s.status === "running").length} in queue`
                  : "status loading…"}
            </span>
          </div>
          <div className="form-row">
            <button
              onClick={() => void onUseApproved()}
              disabled={busy || vfApprovedCount === 0}
            >
              Use approved in timeline
            </button>
            <button
              onClick={() => {
                if (script) {
                  window.open(
                    api.approvedImagesZipUrl(script.id),
                    "_blank",
                  );
                }
              }}
              disabled={vfApprovedCount === 0}
            >
              Download approved (.zip)
            </button>
            <span className="muted">
              {useApprovedSummary ??
                `${vfApprovedCount} approved · ${vfPendingCount} pending · ${vfRejectedCount} rejected — sirf approved images timeline me jati hain.`}
            </span>
          </div>
          {prompts.prompts.map((p, i) => {
            const sc = scenes.find((s) => s.id === p.scene_id);
            if (!sc) return null;
            const d = sceneDraft(sc);
            const gs = genStatus?.scenes.find(
              (s) => s.scene_id === p.scene_id,
            );
            const status = gs?.status ?? p.status;
            const statusLabel =
              status === "done"
                ? "Done — image ready"
                : status === "running"
                  ? "Generating…"
                  : status === "queued"
                    ? "Queued"
                    : status === "failed"
                      ? "Failed"
                      : status === "blocked"
                        ? "Blocked — login chahiye"
                        : "Pending — not generated yet";
            return (
              <div className="scene-card" key={p.scene_id}>
                <strong>
                  Scene {i + 1} · ~{p.duration_s}s · {statusLabel}
                </strong>
                <p className="muted">{p.text}</p>
                {gs?.error && <p className="error">{gs.error}</p>}
                {gs?.fallback_used && (
                  <p className="muted">
                    Fallback image — padosi shot se (alag crop/zoom)
                  </p>
                )}
                {gs?.retry_fixed_by &&
                  gs.retry_fixed_by !== "fallback" && (
                    <p className="muted">
                      Retry ({gs.retry_fixed_by}) se bani
                    </p>
                  )}
                {gs?.precheck_reworded && !gs?.retry_fixed_by && (
                  <p className="muted">Pre-check: prompt reword hua</p>
                )}
                {(vfImagesByScene.get(p.scene_id) ?? []).map((im) => (
                  <div key={im.asset_id}>
                    <img
                      src={fileUrl(im.path)}
                      alt={`Scene ${i + 1} image (${im.source})`}
                      style={{ maxWidth: "320px", borderRadius: "8px" }}
                    />
                    <div className="form-row">
                      <span
                        className={
                          im.verdict === "approved"
                            ? "badge green"
                            : im.verdict === "rejected"
                              ? "badge"
                              : "badge gold"
                        }
                      >
                        {im.verdict === "approved"
                          ? "✓ Approved"
                          : im.verdict === "rejected"
                            ? "✕ Rejected"
                            : "Pending — check karein"}
                      </span>
                      <span className="muted">
                        {im.source === "generated" ? "Generated" : "Uploaded"}
                        {im.reason ? ` · ${im.reason}` : ""}
                      </span>
                    </div>
                    <div className="form-row">
                      <button
                        onClick={() => void onApproveImage(im.asset_id)}
                        disabled={busy || im.verdict === "approved"}
                      >
                        Approve
                      </button>
                      <input
                        value={rejectReasons[im.asset_id] ?? ""}
                        onChange={(e) =>
                          setRejectReasons((prev) => ({
                            ...prev,
                            [im.asset_id]: e.target.value,
                          }))
                        }
                        placeholder="Reject reason (optional)"
                        aria-label={`Reject reason for scene ${i + 1} image`}
                      />
                      <button
                        className="ghostbtn"
                        onClick={() => void onRejectImage(im.asset_id)}
                        disabled={busy || im.verdict === "rejected"}
                      >
                        Reject
                      </button>
                      <a
                        className="ghostbtn"
                        href={fileUrl(im.path)}
                        download
                      >
                        Download
                      </a>
                      {im.verdict === "rejected" && (
                        <button
                          className="ghostbtn"
                          onClick={() => void onRegenerateImage(im.asset_id)}
                          disabled={vfBusy}
                        >
                          Regenerate
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <div className="form-row">
                  <label>
                    Attach uploaded image{" "}
                    <select
                      value={attachAssetIds[sc.id] ?? ""}
                      onChange={(e) =>
                        setAttachAssetIds((prev) => ({
                          ...prev,
                          [sc.id]: e.target.value,
                        }))
                      }
                      aria-label={`Attach image to scene ${i + 1}`}
                    >
                      <option value="">— choose image —</option>
                      {images.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.path}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="ghostbtn"
                    onClick={() => void onAttachImage(sc.id)}
                    disabled={busy || !attachAssetIds[sc.id]}
                  >
                    Attach to scene
                  </button>
                </div>
                <label>
                  Image prompt
                  <textarea
                    value={d.image_prompt}
                    onChange={(e) =>
                      setSceneDrafts((prev) => ({
                        ...prev,
                        [sc.id]: {
                          ...sceneDraft(sc),
                          image_prompt: e.target.value,
                        },
                      }))
                    }
                    aria-label={`Scene ${i + 1} VisualForge prompt`}
                    rows={3}
                  />
                </label>
                <div className="form-row">
                  <button onClick={() => void saveScene(sc)}>
                    Save prompt
                  </button>
                  <button
                    className="ghostbtn"
                    onClick={() => void onRegeneratePrompt(sc)}
                  >
                    Regenerate prompt
                  </button>
                  <button
                    className="ghostbtn"
                    onClick={() => void copyPrompt(p)}
                  >
                    {copiedPromptId === p.scene_id ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            );
          })}
        </>
      ) : (
        <p className="muted">
          {script
            ? "Prompts loading…"
            : "Save a script first — prompts are built from its scenes."}
        </p>
      )}

        </>
      )}
      {activeTool === "stickman" && (
        <>
      <h2 id="tool-stickman">StickMan — Stick-figure prompts</h2>
      <p className="muted">
        Har scene ke liye stick-figure animation prompt — scene ke apne
        alfaz se banta hai, koi AI call nahi, koi key nahi. Frame bhi
        yahin render hota hai (asal PNG) — VisualForge me approve karein,
        phir &ldquo;Use approved in timeline&rdquo; se timeline me aayega.
        Stickman sirf ek tool hai, video ka default style nahi.
      </p>
      <div className="form-row">
        <button
          onClick={() => void onGenerateStickmanPrompts()}
          disabled={busy || stickmanBusy || !script}
        >
          {stickmanBusy ? "Ban raha hai…" : "Generate stickman prompts"}
        </button>
        <span className="muted">
          {stickman
            ? `${stickman.prompts.length} scenes`
            : "Script save karein pehle."}
        </span>
      </div>
      {stickmanPoses.length > 0 && (
        <details>
          <summary>
            Pose library ({stickmanPoses.length} poses — description edit
            kar sakte hain)
          </summary>
          <div className="card-grid" style={{ marginTop: 8 }}>
            {stickmanPoses.map((p) => (
              <div key={p.id} className="card">
                <strong>{p.name}</strong>
                {editingPoseId === p.id ? (
                  <>
                    <textarea
                      value={poseDescDraft}
                      onChange={(e) => setPoseDescDraft(e.target.value)}
                      rows={2}
                      aria-label={`Pose ${p.name} description`}
                    />
                    <div className="form-row">
                      <button
                        onClick={() => void onSavePoseDescription(p.id)}
                        disabled={busy}
                      >
                        Save
                      </button>
                      <button
                        className="ghostbtn"
                        onClick={() => setEditingPoseId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="muted">{p.description}</p>
                    <button
                      className="ghostbtn"
                      onClick={() => {
                        setEditingPoseId(p.id);
                        setPoseDescDraft(p.description);
                      }}
                    >
                      Edit description
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        </details>
      )}
      {stickman ? (
        <div className="card-grid">
          {stickman.prompts.map((row, i) => {
            const pr = row.prompt;
            const draft = pr ? stickmanPromptDrafts[pr.id] : undefined;
            const frame = row.frame;
            return (
              <div key={row.scene_id} className="card">
                <strong>
                  Scene {i + 1} — {pr ? pr.pose : "no prompt yet"}
                </strong>
                <p className="muted">{row.text}</p>
                {pr && draft ? (
                  <>
                    <label>
                      Pose
                      <select
                        value={draft.pose}
                        onChange={(e) =>
                          setStickmanPromptDrafts((prev) => ({
                            ...prev,
                            [pr.id]: { ...draft, pose: e.target.value },
                          }))
                        }
                        aria-label={`Scene ${i + 1} stickman pose`}
                      >
                        {stickmanPoses.map((p) => (
                          <option key={p.id} value={p.name}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Prompt
                      <textarea
                        value={draft.prompt}
                        onChange={(e) =>
                          setStickmanPromptDrafts((prev) => ({
                            ...prev,
                            [pr.id]: { ...draft, prompt: e.target.value },
                          }))
                        }
                        rows={4}
                        aria-label={`Scene ${i + 1} stickman prompt`}
                      />
                    </label>
                    {frame && (
                      <div>
                        <img
                          src={fileUrl(frame.path)}
                          alt={`Stickman frame, scene ${i + 1}`}
                          style={{ maxWidth: "100%", borderRadius: 8 }}
                        />
                        <p className="muted">
                          Frame verdict: {frame.verdict} — approve VisualForge
                          me karein.
                        </p>
                      </div>
                    )}
                    <div className="form-row">
                      <button
                        onClick={() => void onSaveStickmanPrompt(pr.id)}
                        disabled={busy}
                      >
                        Save prompt
                      </button>
                      <button
                        className="ghostbtn"
                        onClick={() => void onRenderStickmanFrame(row.scene_id)}
                        disabled={busy || frameBusyByScene[row.scene_id]}
                      >
                        {frameBusyByScene[row.scene_id]
                          ? "Rendering…"
                          : "Render frame"}
                      </button>
                      <select
                        value={framePoseByScene[row.scene_id] ?? ""}
                        onChange={(e) =>
                          setFramePoseByScene((prev) => ({
                            ...prev,
                            [row.scene_id]: e.target.value,
                          }))
                        }
                        aria-label={`Scene ${i + 1} frame pose override`}
                      >
                        <option value="">— prompt pose —</option>
                        {stickmanPoses.map((p) => (
                          <option key={p.id} value={p.name}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </>
                ) : (
                  <p className="muted">
                    Prompt nahi bana — upar &ldquo;Generate stickman
                    prompts&rdquo; dabayein.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted">
          {script
            ? "Stickman prompts abhi nahi bane."
            : "Save a script first — stickman prompts are built from its scenes."}
        </p>
      )}

        </>
      )}
      {activeTool === "master-prompts" && (
        <>
      <h2>Master Prompt Library</h2>
      <p className="muted">
        Inspiration videos se reverse-engineered master prompts — hook,
        story, style DNA aur viral short. &ldquo;Use in script&rdquo; se
        template script me lag jata hai; copy se clipboard me.
      </p>
      {masterPrompts.length > 0 ? (
        <div className="card-grid">
          {masterPrompts.map((mp) => (
            <div key={mp.id} className="card">
              <strong>{mp.name}</strong>{" "}
              <span className="muted">[{mp.category}]</span>
              {mp.style_dna_name && (
                <span className="muted"> · Style: {mp.style_dna_name}</span>
              )}
              {mp.source && <p className="muted">Source: {mp.source}</p>}
              <p style={{ whiteSpace: "pre-wrap" }}>{mp.template}</p>
              <div className="form-row">
                <button
                  className="ghostbtn"
                  onClick={() => void copyMasterPrompt(mp)}
                >
                  {copiedMasterId === mp.id ? "Copied!" : "Copy"}
                </button>
                <button
                  className="ghostbtn"
                  onClick={() => useMasterPromptInScript(mp)}
                >
                  Use in script
                </button>
                <button
                  className="ghostbtn"
                  onClick={() => void onDeleteMasterPrompt(mp.id)}
                  disabled={busy}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">Master prompts loading…</p>
      )}
      <h3>Add a master prompt</h3>
      <label>
        Name
        <input
          value={newMaster.name}
          onChange={(e) =>
            setNewMaster((prev) => ({ ...prev, name: e.target.value }))
          }
          aria-label="New master prompt name"
        />
      </label>
      <label>
        Category
        <select
          value={newMaster.category}
          onChange={(e) =>
            setNewMaster((prev) => ({ ...prev, category: e.target.value }))
          }
          aria-label="New master prompt category"
        >
          <option value="hook">hook</option>
          <option value="story">story</option>
          <option value="style-dna">style-dna</option>
          <option value="viral-short">viral-short</option>
        </select>
      </label>
      <label>
        Template
        <textarea
          value={newMaster.template}
          onChange={(e) =>
            setNewMaster((prev) => ({ ...prev, template: e.target.value }))
          }
          rows={4}
          aria-label="New master prompt template"
        />
      </label>
      <label>
        Source (optional — video ya creator ka naam)
        <input
          value={newMaster.source}
          onChange={(e) =>
            setNewMaster((prev) => ({ ...prev, source: e.target.value }))
          }
          aria-label="New master prompt source"
        />
      </label>
      <div className="form-row">
        <button
          onClick={() => void onAddMasterPrompt()}
          disabled={busy || masterBusy}
        >
          {masterBusy ? "Adding…" : "Add master prompt"}
        </button>
        <label className="ghostbtn">
          Import .txt / .md
          <input
            type="file"
            accept=".txt,.md"
            style={{ display: "none" }}
            onChange={(e) => {
              void onImportMasterPrompt(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <h3>Reverse-engineer a viral short</h3>
      <p className="muted">
        Koi viral short dekha? Uske notes likhein — hook (pehle 3 second),
        visual style, pacing, captions, CTA — aur Gemini uska locked master
        prompt bana dega (key Settings me ho to).
      </p>
      <label>
        Name (optional)
        <input
          value={reverseName}
          onChange={(e) => setReverseName(e.target.value)}
          placeholder="Reverse-Engineered Master Prompt"
          aria-label="Reverse-engineered master prompt name"
        />
      </label>
      <label>
        Notes — what you saw in the viral short
        <textarea
          value={reverseNotes}
          onChange={(e) => setReverseNotes(e.target.value)}
          rows={4}
          aria-label="Viral short notes"
        />
      </label>
      <div className="form-row">
        <button
          onClick={() => void onReverseEngineer()}
          disabled={busy || reverseBusy}
        >
          {reverseBusy ? "Writing…" : "Write master prompt from notes"}
        </button>
      </div>
      <h3>New style from a description</h3>
      <p className="muted">
        Look ko lafzon me likhein — Gemini Style DNA + master prompt likh
        dega (key Settings me ho to). Samples VisualForge se bante hain.
      </p>
      <label>
        Style name
        <input
          value={styleBuilder.name}
          onChange={(e) =>
            setStyleBuilder((prev) => ({ ...prev, name: e.target.value }))
          }
          placeholder="Jaise: Flat Paper Cutout"
          aria-label="New style name"
        />
      </label>
      <label>
        Description — the look, in plain words
        <textarea
          value={styleBuilder.description}
          onChange={(e) =>
            setStyleBuilder((prev) => ({
              ...prev,
              description: e.target.value,
            }))
          }
          rows={3}
          aria-label="New style description"
        />
      </label>
      <div className="form-row">
        <button
          onClick={() => void onStyleFromDescription()}
          disabled={busy || styleBuilderBusy}
        >
          {styleBuilderBusy ? "Writing…" : "Create Style DNA"}
        </button>
      </div>

        </>
      )}
      {activeTool === "director" && (
        <>
      <h2>Magic Mode — Topic se tayyar video</h2>
      <p className="muted">
        Sirf topic likhein — script, images, voice, timeline, captions aur
        render, sab khud hoga. Script khali chhoren to Deep Research se
        script khud banega. Kuch na chunein to bhi chal jayega — smart
        defaults pehle se lage hain.
      </p>
      {magicOptionsError && <p className="error">{magicOptionsError}</p>}
      {magicError && <p className="error">{magicError}</p>}
      <div className="form-row">
        <label style={{ display: "flex", flex: 1, gap: 8, alignItems: "center" }}>
          Topic{" "}
          <input
            value={magicTopic}
            onChange={(e) => setMagicTopic(e.target.value)}
            placeholder="Misal: Portugal ki kahani"
            aria-label="Magic topic"
            style={{ flex: 1, minWidth: 240 }}
          />
        </label>
      </div>
      <label>
        Script — khali chhoren to Deep Research se script khud banega{" "}
        <textarea
          value={magicScript}
          onChange={(e) => setMagicScript(e.target.value)}
          placeholder="Apni script yahan likhein, ya khali chhor dein"
          rows={4}
          aria-label="Magic script"
        />
      </label>
      <div className="form-row">
        <label>
          Voice character{" "}
          <select
            value={magicVoiceSel}
            onChange={(e) => setMagicVoiceSel(e.target.value)}
            aria-label="Magic voice character"
            disabled={!magicOptions}
          >
            {magicOptions && (
              <>
                {magicOptions.voices.uploaded.length > 0 && (
                  <optgroup label="Uploaded voiceover">
                    {magicOptions.voices.uploaded.map((v) => (
                      <option key={v.id} value={`upload:${v.id}`}>
                        Uploaded voiceover — {v.path} ({v.duration_s}s)
                      </option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="Edge-TTS (free)">
                  {magicOptions.voices.edge.list.map((v) => (
                    <option key={v.id} value={`edge:${v.id}`}>
                      {v.label} ({v.locale})
                    </option>
                  ))}
                </optgroup>
                <optgroup label="HeyGen clone">
                  {magicOptions.voices.heygen.available &&
                  magicOptions.voices.heygen.voice_id ? (
                    <option
                      value={`heygen:${magicOptions.voices.heygen.voice_id}`}
                    >
                      {magicOptions.voices.heygen.voice_name} (
                      {magicOptions.voices.heygen.model})
                    </option>
                  ) : (
                    <option value="" disabled>
                      HeyGen clone — quota/key nahi hai (band hai)
                    </option>
                  )}
                </optgroup>
              </>
            )}
            {!magicOptions && <option value="">Options load nahi hue</option>}
          </select>
        </label>
        <label>
          Caption style{" "}
          <select
            value={magicCaptionId}
            onChange={(e) => setMagicCaptionId(e.target.value)}
            aria-label="Magic caption style"
            disabled={!magicOptions}
          >
            {magicOptions?.caption_styles.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
            {!magicOptions && <option value="">Options load nahi hue</option>}
          </select>
        </label>
        <label>
          Aspect{" "}
          <select
            value={magicAspect}
            onChange={(e) => setMagicAspect(e.target.value)}
            aria-label="Magic aspect ratio"
            disabled={!magicOptions}
          >
            {(magicOptions?.aspects ?? [
              { value: "16:9", label: "16:9 (YouTube)" },
              { value: "9:16", label: "9:16 (Shorts/Reels)" },
              { value: "1:1", label: "1:1 (Square)" },
            ]).map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Style DNA preset{" "}
          <select
            value={magicStyleDnaId}
            onChange={(e) => setMagicStyleDnaId(e.target.value)}
            aria-label="Magic Style DNA preset"
            disabled={!magicOptions}
          >
            <option value="">Koi preset nahi (last used)</option>
            {magicOptions?.style_dna.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Language{" "}
          <select
            value={magicLanguage}
            onChange={(e) => {
              setMagicLanguage(e.target.value);
              void loadMagicOptions(e.target.value);
            }}
            aria-label="Magic language"
            disabled={!magicOptions}
          >
            {(magicOptions?.languages ?? [
              { value: "en", label: "English" },
              { value: "ur", label: "Roman Urdu" },
            ]).map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Character Vault niche{" "}
          <select
            value={magicNicheId}
            onChange={(e) => setMagicNicheId(e.target.value)}
            aria-label="Magic Character Vault niche"
            disabled={!magicOptions}
          >
            <option value="">Koi niche nahi (Vault band)</option>
            {(magicOptions?.niches ?? []).map((n) => (
              <option
                key={n.id}
                value={n.id}
                disabled={!n.guard_ok}
              >
                {n.name} — {n.character_count} characters
                {n.guard_ok
                  ? " (locked ✓)"
                  : ` (lock baaki: ${n.missing_mains.join(", ") || "sheet baaki"})`}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={() => void onStartMagic()}
          disabled={
            busy ||
            magicStarting ||
            (magicRun !== null &&
              magicRun.status !== "done" &&
              magicRun.status !== "failed")
          }
        >
          Magic Mode chalao
        </button>
      </div>
      {magicOptions && !magicOptions.voices.heygen.available && (
        <p className="muted">
          HeyGen clone band hai —{" "}
          {magicOptions.voices.heygen.note ||
            "key ya quota nahi hai, is liye voice list me nahi."}
        </p>
      )}
      {magicOptions && !magicOptions.voices.edge.available && (
        <p className="muted">
          Edge-TTS live list load nahi hui — curated list dikha raha hoon.
        </p>
      )}
      {magicOptions?.voices.edge.note && (
        <p className="muted">{magicOptions.voices.edge.note}</p>
      )}
      {magicRun && (
        <>
          <h3>
            Magic #{magicRun.id} — {magicRun.topic} — {magicRun.status}
          </h3>
          {magicRun.error && (
            <>
              <p className="error">{magicRun.error}</p>
              <p className="muted">
                Dobara chalane ke liye upar se “Magic Mode chalao” dabayein —
                ya script ya voice badal kar dobara koshish karein. Agar koi
                stage fail hua to us ki detail upar stages me hai.
              </p>
            </>
          )}
          <ul className="list">
            {MAGIC_STAGES.map((stage) => {
              const s = magicRun.stages?.[stage];
              const status = (s?.status ?? "queued") as MagicStageStatus;
              return (
                <li key={stage}>
                  {MAGIC_STAGE_NAMES[stage]}: {MAGIC_STATUS_LABELS[status]}
                  {s?.detail ? ` — ${s.detail}` : ""}
                </li>
              );
            })}
          </ul>
          {magicRun.status === "done" && (
            <>
              <h3>Summary</h3>
              <ul className="list">
                <li>
                  Images bani: {magicRun.summary.images_generated ?? "—"} ·
                  pehle se thi: {magicRun.summary.images_skipped_done ?? "—"}{" "}
                  · fail: {magicRun.summary.images_failed ?? "—"} · ruki hui:{" "}
                  {magicRun.summary.images_blocked ?? "—"} · dobara bani:{" "}
                  {magicRun.summary.images_retried ?? "—"}
                </li>
                <li>
                  Scenes: {magicRun.summary.scenes ?? "—"} · Words:{" "}
                  {magicRun.summary.words ?? "—"} · Video duration:{" "}
                  {magicRun.summary.duration_s != null
                    ? `${magicRun.summary.duration_s}s`
                    : "—"}
                </li>
                <li>
                  Placeholders: {magicRun.summary.placeholders_used ?? "—"} ·
                  Uploaded images: {magicRun.summary.uploaded_images ?? "—"}
                </li>
                {magicRun.summary.vault_niche && (
                  <li>Character Vault niche: {magicRun.summary.vault_niche}</li>
                )}
                {(magicRun.summary.images_qc_checked ?? 0) > 0 && (
                  <li>
                    QC: {magicRun.summary.images_qc_checked} check,{" "}
                    {magicRun.summary.images_qc_regenerated ?? 0} dobara bani
                  </li>
                )}
                {(magicRun.summary.images_retried ?? 0) > 0 && (
                  <li>
                    Retry Ladder: {magicRun.summary.images_retried} retry ·{" "}
                    {magicRun.summary.images_retry_fixed ?? 0} retry se bani ·{" "}
                    {magicRun.summary.images_fallback_used ?? 0} fallback
                    {(magicRun.summary.images_precheck_reworded ?? 0) > 0 && (
                      <>
                        {" "}
                        · {magicRun.summary.images_precheck_reworded} pre-check
                        reword
                      </>
                    )}
                  </li>
                )}
                {(magicRun.summary.images_retry_log ?? []).length > 0 && (
                  <li>
                    Retry log:
                    <ul className="list">
                      {(magicRun.summary.images_retry_log ?? []).map((r) => (
                        <li key={r.job_id}>
                          Scene {(r.scene_position ?? 0) + 1}:{" "}
                          {r.fixed_by === "fallback"
                            ? "fallback image (padosi shot se)"
                            : r.fixed_by
                              ? `retry (${r.fixed_by}) se bani`
                              : "fail — retry ladder bhi fail"}
                          {" — "}
                          {r.error}
                        </li>
                      ))}
                    </ul>
                  </li>
                )}
                {magicRun.summary.output_path && (
                  <li>
                    <a href={fileUrl(magicRun.summary.output_path)} download>
                      Download MP4
                    </a>
                  </li>
                )}
                {magicRun.summary.thumbnail_path && (
                  <li>
                    <a
                      href={fileUrl(magicRun.summary.thumbnail_path)}
                      download
                    >
                      Download thumbnail
                    </a>
                  </li>
                )}
              </ul>
              {(magicRun.summary.warnings ?? []).length > 0 && (
                <ul className="list">
                  {magicRun.summary.warnings!.map((w, i) => (
                    <li key={i}>Warning: {w}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </>
      )}

      <h2 id="tool-director">One-click video — Documentary Director</h2>
      <p className="muted">
        Script → voice → images → timeline → captions → render, one click.
        One clip per sentence — har sentence par visual badlega, har clip
        ka effect alag (zoom in / zoom out / pan left / pan right) aur
        har cut par 0.5 s crossfade.
        {images.length > 0 && script && scenes.length > images.length
          ? ` ${images.length} images, ${scenes.length} sentences — images cycle hoti hain, har dafa alag effect.`
          : ""}
        {images.length === 0
          ? " A scene with no uploaded image gets a title card marked “Placeholder — real image needed” (VisualForge will replace it with a generated image)."
          : ""}
      </p>
      <div className="form-row">
        <label>
          Voice{" "}
          <select
            value={runVoiceSource}
            onChange={(e) =>
              setRunVoiceSource(e.target.value as "upload" | "tts")
            }
            aria-label="Run voice source"
          >
            <option value="upload">
              {voice
                ? `Uploaded voiceover (${voice.path})`
                : "Uploaded voiceover — none yet"}
            </option>
            <option value="tts">
              Free Edge-TTS from the script text (best-effort)
            </option>
          </select>
        </label>
        <label>
          Caption style{" "}
          <select
            value={runCaptionId}
            onChange={(e) => setRunCaptionId(e.target.value)}
            aria-label="Run caption style"
          >
            <option value="">Keep current</option>
            {captionStyles.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.language})
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={() => void onStartRun()}
          disabled={
            busy ||
            !script ||
            (runVoiceSource === "upload" && !voice) ||
            (oneClickRun !== null &&
              oneClickRun.status !== "done" &&
              oneClickRun.status !== "failed")
          }
        >
          Start Video
        </button>
      </div>
      {!script && (
        <p className="muted">
          Pehle script save karein — phir Start Video.
        </p>
      )}
      {script && runVoiceSource === "upload" && !voice && (
        <p className="muted">
          No voiceover uploaded yet — upload one above, or pick Edge-TTS.
        </p>
      )}
      {oneClickRun && (
        <>
          <h3>
            Run #{oneClickRun.id} — {oneClickRun.status}
          </h3>
          {oneClickRun.error && <p className="error">{oneClickRun.error}</p>}
          <ul className="list">
            {oneClickRun.steps.map((s) => (
              <li key={s.id}>
                {RUN_STEP_NAMES[s.kind] ?? s.kind}: {s.status}
                {s.error ? ` — ${s.error}` : ""}
              </li>
            ))}
          </ul>
          {oneClickRun.status === "done" && oneClickRun.output_path && (
            <p>
              <a href={fileUrl(oneClickRun.output_path)} download>
                Download MP4
              </a>
              {oneClickRun.timeline_id && (
                <>
                  {" · "}
                  <a
                    href={srtUrl(oneClickRun.timeline_id)}
                    download={`run-${oneClickRun.id}.srt`}
                  >
                    Download SRT
                  </a>
                </>
              )}
            </p>
          )}
        </>
      )}

        </>
      )}
      {["cinecut-top", "motion", "render"].includes(activeTool) && (
        <>
      {activeTool === "cinecut-top" && (
        <>
      <h2>2. Timeline</h2>
      <button onClick={() => void onAutoSync()} disabled={busy || images.length === 0}>
        Auto-sync images to voiceover
      </button>
        </>
      )}
      {!timeline ? (
        <p className="muted">
          {activeTool === "motion"
            ? "Style + captions ke liye pehle CineCut me timeline banayen (voiceover + images, phir Auto-sync)."
            : activeTool === "render"
              ? "Render ke liye pehle CineCut me timeline banayen (voiceover + images, phir Auto-sync)."
              : "No timeline yet. Upload a voiceover and images, then auto-sync."}
        </p>
      ) : (
        <>
      {activeTool === "cinecut-top" && (
        <>
          <p className="muted">
            Voiceover length: {timeline.vo_duration_s}s · {timeline.clips.length}{" "}
            clip(s)
            {timeline.style_dna_id
              ? ` · Style: ${styles.find((s) => s.id === timeline.style_dna_id)?.name ?? ""}`
              : ""}
            {timeline.character_name
              ? ` · Main character: ${timeline.character_name}`
              : ""}
          </p>
          {voice && (
            <div className="preview">
              <audio
                ref={audioRef}
                controls
                src={fileUrl(voice.path)}
                onTimeUpdate={(e) => setPlayTime(e.currentTarget.currentTime)}
              />
              {currentClip && (
                <img
                  src={fileUrl(currentClip.asset_path)}
                  alt={`Clip at ${currentClip.start_s}s`}
                  className="preview-img"
                />
              )}
            </div>
          )}
          <div className="timeline">
            {timeline.clips.map((clip) => {
              const d = draftFor(clip);
              return (
                <div className="clip-card" key={clip.id}>
                  <img
                    src={fileUrl(clip.asset_path)}
                    alt={`Clip ${clip.position + 1}`}
                    className="clip-thumb"
                  />
                  {clip.asset_placeholder ? (
                    <p className="error">
                      Placeholder — real image needed
                    </p>
                  ) : null}
                  {clip.asset_approved ? (
                    <p>
                      <span className="badge green">
                        ✓ Approved VisualForge image
                      </span>
                    </p>
                  ) : null}
                  {clip.image_replaced ? (
                    <p className="muted">
                      Image replaced — ye scene dobara banaya gaya
                    </p>
                  ) : null}
                  {clip.effect ? (
                    <p>
                      <span className="badge">
                        🎥 {CLIP_EFFECT_LABELS[clip.effect] ?? clip.effect}
                      </span>
                    </p>
                  ) : null}
                  {clip.asset_reused ? (
                    <p className="muted">
                      Reused image — same picture, different effect
                    </p>
                  ) : null}
                  <div className="clip-fields">
                    <label>
                      Replace image{" "}
                      <input
                        type="file"
                        accept=".png,.jpg,.jpeg,.webp"
                        onChange={(e) =>
                          void onReplaceClipImage(clip, e.target.files?.[0])
                        }
                        disabled={busy}
                      />
                    </label>
                    <label>
                      Start (s){" "}
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={d.start_s}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [clip.id]: { ...draftFor(clip), start_s: e.target.value },
                          }))
                        }
                      />
                    </label>
                    <label>
                      End (s){" "}
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={d.end_s}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [clip.id]: { ...draftFor(clip), end_s: e.target.value },
                          }))
                        }
                      />
                    </label>
                    <label>
                      Caption{" "}
                      <input
                        value={d.caption_text}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [clip.id]: { ...draftFor(clip), caption_text: e.target.value },
                          }))
                        }
                        placeholder="Caption text (optional)"
                      />
                    </label>
                    <label>
                      Motion{" "}
                      <select
                        value={clip.effect ?? ""}
                        onChange={(e) =>
                          void onSetClipEffect(clip, e.target.value)
                        }
                        disabled={busy}
                      >
                        <option value="">Auto (by position)</option>
                        {CLIP_EFFECTS.map((fx) => (
                          <option key={fx} value={fx}>
                            {CLIP_EFFECT_LABELS[fx] ?? fx}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="form-row">
                      <button onClick={() => void saveClip(clip)}>Save clip</button>
                      <button onClick={() => void moveClip(clip, -1)}>↑</button>
                      <button onClick={() => void moveClip(clip, 1)}>↓</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
      {activeTool === "motion" && (
        <>
          <h2 id="tool-motion">3. Style + captions</h2>
          <div className="form-row">
            <select
              value={styleId}
              onChange={(e) => setStyleId(e.target.value)}
              aria-label="Style DNA"
            >
              <option value="">Style DNA — none</option>
              {styles.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <select
              value={captionId}
              onChange={(e) => setCaptionId(e.target.value)}
              aria-label="Caption style"
            >
              <option value="">Caption style — none</option>
              {captionStyles.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.language})
                </option>
              ))}
            </select>
            <button onClick={() => void onApplyStyle()} disabled={busy}>
              Apply style
            </button>
            <a href={srtUrl(timeline.id)} download={`timeline-${timeline.id}.srt`}>
              <button type="button">Download SRT</button>
            </a>
          </div>
        </>
      )}
      {activeTool === "render" && (
        <>
          <h2 id="tool-render">4. Render</h2>
          <p className="muted">
            Ken Burns motion (per-clip preset, dropdown on each clip
            card), 0.5 s crossfades between clips, captions burned in
            with the chosen caption style — 30 fps, MP4 with your
            voiceover.
          </p>
          <div className="form-row">
            <label>
              Quality{" "}
              <select
                value={renderQuality}
                onChange={(e) => setRenderQuality(e.target.value)}
                disabled={busy}
              >
                {RENDER_QUALITIES.map((q) => (
                  <option key={q} value={q}>
                    {q === "720p"
                      ? "720p (1280×720)"
                      : q === "1080p"
                        ? "1080p (1920×1080)"
                        : "4K (3840×2160 — upscale)"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={atmosphere.vignette}
                onChange={(e) =>
                  setAtmosphere((prev) => ({
                    ...prev,
                    vignette: e.target.checked,
                  }))
                }
                disabled={busy}
              />{" "}
              Vignette
            </label>
            <label>
              <input
                type="checkbox"
                checked={atmosphere.grain}
                onChange={(e) =>
                  setAtmosphere((prev) => ({
                    ...prev,
                    grain: e.target.checked,
                  }))
                }
                disabled={busy}
              />{" "}
              Film grain
            </label>
            <label>
              <input
                type="checkbox"
                checked={atmosphere.warm}
                onChange={(e) =>
                  setAtmosphere((prev) => ({
                    ...prev,
                    warm: e.target.checked,
                  }))
                }
                disabled={busy}
              />{" "}
              Warm grade
            </label>
            <label>
              Atmosphere preset{" "}
              <select
                value={atmospherePreset}
                onChange={(e) => setAtmospherePreset(e.target.value)}
                disabled={busy}
              >
                <option value="">None (bools only)</option>
                {ATMOSPHERE_PRESETS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Caption size{" "}
              <select
                value={captionSizePct}
                onChange={(e) => setCaptionSizePct(Number(e.target.value))}
                disabled={busy}
              >
                {[50, 75, 100, 125, 150].map((p) => (
                  <option key={p} value={p}>
                    {p}%
                  </option>
                ))}
              </select>
            </label>
            <label>
              Caption position{" "}
              <select
                value={captionPosition}
                onChange={(e) => setCaptionPosition(e.target.value)}
                disabled={busy}
              >
                {CAPTION_POSITIONS.map((p) => (
                  <option key={p} value={p}>
                    {p === "bottom"
                      ? "Bottom"
                      : p === "center"
                        ? "Center"
                        : "Top"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={captionsOn}
                onChange={(e) => setCaptionsOn(e.target.checked)}
                disabled={busy}
              />{" "}
              Burn captions (off = no captions)
            </label>
          </div>
          <p className="muted">
            4K upscales the 1080p sources — picture bara hota hai, nayi
            detail nahi banti. Vignette, grain aur warm grade asal
            ffmpeg filters hain, poori video par lagte hain. Atmosphere
            preset (jaise Noir black &amp; white ya Vintage Sepia) bhi
            asal filter hai — preset aur bools dono lag sakte hain.
          </p>
          <button onClick={() => void onRender()} disabled={busy}>
            Render MP4
          </button>{" "}
          <button onClick={() => void onRerender()} disabled={busy}>
            Re-render (same timeline)
          </button>
          <p className="muted">
            Re-render purani MP4 ko delete nahi karta — nayi video alag file
            mein banti hai, purani tab tak chalti rehti hai jab tak nayi
            tayyar na ho jaye.
          </p>
          {renderJob && (
            <p>
              Render job #{renderJob.id}: {renderJob.status}
              {renderJob.error ? ` — ${renderJob.error}` : ""}
              {renderJob.status === "done" && renderJob.output_path && (
                <>
                  {" "}
                  <a href={fileUrl(renderJob.output_path)} download>
                    Download MP4
                  </a>
                </>
              )}
            </p>
          )}
          <h3>Render queue</h3>
          {renderQueue.length === 0 ? (
            <p className="muted">
              Is project ki koi render job nahi hai — pehle Render karein.
            </p>
          ) : (
            <ul className="list">
              {renderQueue.map((j) => {
                const started = new Date(j.created_at).getTime();
                const ended =
                  j.status === "done" || j.status === "failed"
                    ? new Date(j.updated_at).getTime()
                    : queueNow;
                const elapsed = Math.max(
                  0,
                  Math.round((ended - started) / 1000),
                );
                let opts = "";
                try {
                  const o = JSON.parse(j.options_json ?? "{}") as {
                    quality?: string;
                    vignette?: boolean;
                    grain?: boolean;
                    warm?: boolean;
                  };
                  const bits = [o.quality ?? "1080p"];
                  if (o.vignette) bits.push("vignette");
                  if (o.grain) bits.push("grain");
                  if (o.warm) bits.push("warm");
                  opts = bits.join(" · ");
                } catch {
                  opts = "1080p";
                }
                return (
                  <li key={j.id}>
                    #{j.id} · {j.status} · {opts} · {elapsed}s
                    {j.error ? ` — ${j.error}` : ""}
                    {j.status === "done" && j.output_path && (
                      <>
                        {" "}
                        <a href={fileUrl(j.output_path)} download>
                          Download MP4
                        </a>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
        </>
      )}
        </>
      )}
      {activeTool === "render" && (
        <>
      <h2>5. Deliverables</h2>
      <p className="muted">
        Publish karne ke liye sab kuch ek jagah: MP4, thumbnail (rendered
        video ka asal frame), aur YouTube title / description / tags
        (script se draft, haath se edit karein).
      </p>
      {!deliverables?.video && (
        <p className="muted">
          Abhi koi finished video nahi hai — pehle Render ya one-click run
          se video banayein.
        </p>
      )}
      {deliverables?.video && (
        <p>
          <strong>Video:</strong>{" "}
          <a href={fileUrl(deliverables.video.output_path)} download>
            Download MP4
          </a>{" "}
          ({deliverables.video.duration_s}s, render job #
          {deliverables.video.job_id})
        </p>
      )}
      <h3>Thumbnail</h3>
      {deliverables?.thumbnail && (
        <p>
          <img
            src={fileUrl(deliverables.thumbnail.path)}
            alt="Video thumbnail"
            style={{ width: 320, height: 180, objectFit: "cover", borderRadius: 6 }}
          />
          <br />
          <span className="muted">
            Frame at {deliverables.thumbnail.timestamp_s}s ·{" "}
            <a href={fileUrl(deliverables.thumbnail.path)} download>
              Download JPG
            </a>
          </span>
        </p>
      )}
      <div className="form-row">
        <label>
          Frame time (s) — khaali = pehle clip ka beech{" "}
          <input
            type="number"
            step="0.1"
            min="0"
            value={thumbTs}
            onChange={(e) => setThumbTs(e.target.value)}
            placeholder="e.g. 2.4"
            aria-label="Thumbnail frame time in seconds"
          />
        </label>
        <button
          onClick={() => void onGenerateThumbnail()}
          disabled={busy || !deliverables?.video}
        >
          {deliverables?.thumbnail ? "Regenerate thumbnail" : "Generate thumbnail"}
        </button>
      </div>
      {!deliverables?.video && (
        <p className="muted">
          Thumbnail ke liye pehle video render honi chahiye.
        </p>
      )}
      <h3>YouTube title / description / tags</h3>
      <div className="form-row">
        <button
          onClick={() => void onGenerateMetadata()}
          disabled={busy || !script}
        >
          Generate YouTube pack (script se)
        </button>
        {!script && (
          <span className="muted">
            Pehle script save karein — metadata script se banta hai.
          </span>
        )}
      </div>
      <label>
        Title{" "}
        <input
          value={metaDraft.title}
          onChange={(e) =>
            setMetaDraft((prev) => ({ ...prev, title: e.target.value }))
          }
          placeholder="YouTube title"
          aria-label="YouTube title"
          style={{ width: "100%" }}
          maxLength={100}
        />
      </label>
      <label>
        Description{" "}
        <textarea
          value={metaDraft.description}
          onChange={(e) =>
            setMetaDraft((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="YouTube description"
          aria-label="YouTube description"
          style={{ width: "100%", minHeight: 120 }}
        />
      </label>
      <label>
        Tags (comma separated){" "}
        <input
          value={metaDraft.tags}
          onChange={(e) =>
            setMetaDraft((prev) => ({ ...prev, tags: e.target.value }))
          }
          placeholder="documentary, history, true story"
          aria-label="YouTube tags"
          style={{ width: "100%" }}
        />
      </label>
      <div className="form-row">
        <button onClick={() => void onSaveMetadata()} disabled={busy}>
          Save metadata
        </button>
        <button
          onClick={() => copyText(metaDraft.title, "Title")}
          disabled={!metaDraft.title}
        >
          Copy title
        </button>
        <button
          onClick={() => copyText(metaDraft.description, "Description")}
          disabled={!metaDraft.description}
        >
          Copy description
        </button>
        <button
          onClick={() => copyText(metaDraft.tags, "Tags")}
          disabled={!metaDraft.tags}
        >
          Copy tags
        </button>
      </div>
        </>
      )}
    </section>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [refresh, setRefresh] = useState(0);
  const health = useLoad<Health>(api.health);
  const projects = useLoad<Project[]>(api.projects, [refresh]);
  const jobs = useLoad<Job[]>(api.jobs, [refresh]);
  const assets = useLoad<Asset[]>(api.assets, [refresh]);
  const settings = useLoad<Setting[]>(api.settings, [refresh]);
  const styles = useLoad<StyleDna[]>(api.styleDna, [refresh]);
  const captionStyles = useLoad<CaptionStyle[]>(api.captionStyles, [refresh]);

  const [newProjectName, setNewProjectName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  // CineCut view: a project id opens that project's timeline, "pick"
  // opens the project picker, null means the normal 6 pages.
  const [cineCut, setCineCut] = useState<number | "pick" | null>(null);
  // v0.14.1 (Issue 3 fix): har tool ka apna section hai CineCut ke
  // project view ke andar — Dashboard / sidebar / All Tools se tool
  // kholne par pehle project picker khulta hai, phir project chunte
  // hi us tool ke section par scroll hota hai. Pehle sirf CineCut
  // ka button tha; baaki 8 live tools All Tools par dead cards the.
  const [toolTarget, setToolTarget] = useState<string | null>(null);
  // v0.14.1 fix round 2 — focused tool views: project view me ek waqt
  // par SIRF ek tool dikhta hai (Ali ka rule: ek tool = ek kaam).
  const [activeTool, setActiveTool] = useState("cinecut-top");
  function openTool(name: string) {
    if (name === "Asset Vault") {
      setToolTarget(null);
      setCineCut(null);
      setPage("Media Library");
      return;
    }
    setToolTarget(TOOL_SECTIONS[name] ?? null);
    setActiveTool(TOOL_SECTIONS[name] ?? "cinecut-top");
    setCineCut("pick");
  }
  const cineCutProject =
    typeof cineCut === "number"
      ? (projects.data?.find((p) => p.id === cineCut) ?? null)
      : null;
  const [search, setSearch] = useState("");
  // Phase 7 slice 2: Asset Vault — server-side search + tag filter
  // for the Media Library (the library loader below re-queries on
  // every change; the global assets list stays untouched).
  const [libQ, setLibQ] = useState("");
  const [libTag, setLibTag] = useState("");
  const [libTagDraft, setLibTagDraft] = useState<Record<number, string>>({});
  const libAssets = useLoad<Asset[]>(
    () => api.assets(undefined, libQ || undefined, libTag || undefined),
    [libQ, libTag, refresh],
  );
  const allTags = useLoad<{ tag: string; count: number }[]>(
    api.assetTags,
    [refresh],
  );
  const [pipeline, setPipeline] = useState<Record<number, PipelineState>>({});
  const [characters, setCharacters] = useState<Record<number, Character | null>>({});
  const [whisper, setWhisper] = useState<WhisperStatus | null>(null);
  // v0.14.1 unified API Keys: EK grouped section (AI Text / Images /
  // Voice / Stock) — purana raw dump + alag rotation + alag Free keys
  // table hata diye gaye hain.
  const keysList = useLoad<KeyRow[]>(api.keys, [refresh]);
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [keyAddLabel, setKeyAddLabel] = useState("");
  const [keyBusy, setKeyBusy] = useState<string | null>(null);
  const [keyTest, setKeyTest] = useState<Record<string, KeyTestResult>>({});
  // Cross-check slice: per-key test result (rotation sub-rows).
  const [keyTestResult, setKeyTestResult] = useState<Record<number, string>>(
    {},
  );
  const [keyTestBusy, setKeyTestBusy] = useState<number | null>(null);
  const voiceProviders = useLoad<VoiceProvider[]>(
    api.voiceProviders,
    [refresh],
  );
  // Connect Google: one sign-in for Canvas + Flow (Settings section).
  // CineCut keeps its own copy for the VisualForge Flow status line.
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(
    null,
  );
  const [googleLoginBusy, setGoogleLoginBusy] = useState(false);
  const [googleDisconnectBusy, setGoogleDisconnectBusy] = useState(false);
  const [googleNote, setGoogleNote] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);

  async function loadGoogleStatus() {
    const g = await api.googleStatus().catch(() => null);
    setGoogleStatus(g);
  }

  async function onOpenGoogleLogin() {
    setGoogleLoginBusy(true);
    setGoogleError(null);
    try {
      const res = await api.openGoogleLogin();
      setGoogleNote(res.message);
      await loadGoogleStatus();
    } catch (e) {
      setGoogleError(
        e instanceof Error ? e.message : "Google login nahi khul saka",
      );
    } finally {
      setGoogleLoginBusy(false);
    }
  }

  async function onDisconnectGoogle() {
    setGoogleDisconnectBusy(true);
    setGoogleError(null);
    try {
      await api.disconnectGoogle();
      setGoogleNote(
        "Google disconnect ho gaya — Canvas aur Flow dono ke liye dobara sign-in karna hoga.",
      );
      await loadGoogleStatus();
    } catch (e) {
      setGoogleError(e instanceof Error ? e.message : "Disconnect nahi hua");
    } finally {
      setGoogleDisconnectBusy(false);
    }
  }

  useEffect(() => {
    if (page === "Settings") {
      void loadGoogleStatus();
      void loadReleaseSections();
    }
    if (page === "Dashboard") {
      void loadReleaseSections();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);
  const [newProviderName, setNewProviderName] = useState("");
  const [newProviderUrl, setNewProviderUrl] = useState("");
  const [newProviderKey, setNewProviderKey] = useState("");
  const [providerError, setProviderError] = useState<string | null>(null);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreResult, setRestoreResult] = useState<string | null>(null);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [resumeBusy, setResumeBusy] = useState<number | null>(null);
  const [resumeNote, setResumeNote] = useState<string | null>(null);
  // Release Packaging (v0.14.0): update / setup / output / free keys /
  // main character — Dashboard + Settings. Sab live API data se.
  const [updateCheck, setUpdateCheck] = useState<UpdateCheck | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updateApplying, setUpdateApplying] = useState(false);
  const [changelog, setChangelog] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupRun, setSetupRun] = useState<SetupRun | null>(null);
  const [setupMsg, setSetupMsg] = useState<string | null>(null);
  const [outputInfo, setOutputInfo] = useState<OutputInfo | null>(null);
  const [outputMsg, setOutputMsg] = useState<string | null>(null);
  const [pollinationsImg, setPollinationsImg] = useState<string | null>(null);
  const [pollinationsBusy, setPollinationsBusy] = useState(false);
  const [mainCharacter, setMainCharacter] = useState<VaultCharacter | null>(
    null,
  );

  async function loadReleaseSections() {
    // Dashboard + Settings dono par — fail ho to page nahi toot-ta,
    // sections khaali rehte hain aur button dobara try kar sakta hai.
    try {
      setUpdateCheck(await api.updateCheck());
    } catch {
      /* ignore — Check button dobara try karega */
    }
    try {
      setSetupStatus(await api.setupStatus());
    } catch {
      /* ignore */
    }
    try {
      setOutputInfo(await api.outputInfo());
    } catch {
      /* ignore */
    }
    try {
      const r = await api.getMainCharacter();
      setMainCharacter(r.main_character);
    } catch {
      /* ignore */
    }
  }

  // Per-project pipeline state, derived from real API data only.
  useEffect(() => {
    const list = projects.data ?? [];
    if (list.length === 0) {
      setPipeline({});
      setCharacters({});
      return;
    }
    let cancelled = false;
    Promise.all(
      list.map(async (p) => {
        const [as, tl, ch, sc] = await Promise.all([
          api.assets(p.id).catch(() => [] as Asset[]),
          api.projectTimeline(p.id).catch(() => null),
          api.character(p.id).catch(() => null),
          api.scripts(p.id).catch(() => [] as Script[]),
        ]);
        return [
          p.id,
          computePipeline(as, tl, jobs.data ?? [], p.id, sc.length > 0),
          ch,
        ] as const;
      }),
    )
      .then((entries) => {
        if (!cancelled) {
          setPipeline(Object.fromEntries(entries.map(([id, s]) => [id, s])));
          setCharacters(
            Object.fromEntries(entries.map(([id, , ch]) => [id, ch])),
          );
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects.data, jobs.data]);

  // First uploaded image of a project, for its card thumbnail.
  // Placeholder title cards are not uploads — never a thumbnail.
  function firstImage(projectId: number): string | null {
    const img = (assets.data ?? []).find(
      (a) =>
        a.project_id === projectId && a.kind === "image" && !a.placeholder,
    );
    return img ? fileUrl(img.path) : null;
  }

  const filteredProjects = (projects.data ?? []).filter((p) =>
    p.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  async function createProject() {
    const name = newProjectName.trim();
    if (!name) {
      setCreateError("Pehle project ka naam likhein.");
      return;
    }
    setCreateError(null);
    try {
      await api.createProject(name);
      setNewProjectName("");
      setRefresh((r) => r + 1);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create project");
    }
  }

  // Phase 7 slice 2: Asset Vault tag actions — the library reloads
  // from the server after each change, so the chips always show the
  // real stored tags.
  async function onAddTag(asset: Asset) {
    const draft = (libTagDraft[asset.id] ?? "").trim();
    if (!draft) {
      alert("Pehle tag likhein.");
      return;
    }
    try {
      await api.addAssetTag(asset.id, draft);
      setLibTagDraft((prev) => ({ ...prev, [asset.id]: "" }));
      setRefresh((r) => r + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Tag add nahi hua");
    }
  }

  async function onRemoveTag(asset: Asset, tag: string) {
    try {
      await api.removeAssetTag(asset.id, tag);
      setRefresh((r) => r + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Tag remove nahi hua");
    }
  }

  async function saveSetting(key: string) {
    await api.updateSetting(key, editingValue);
    setEditingKey(null);
    setRefresh((r) => r + 1);
  }

  // Phase 7 slice 3: add a Gemini key to the rotation list.
  // v0.14.1: unified API Keys handlers (grouped section).
  async function onAddKey(provider: string) {
    const value = (keyDraft[provider] ?? "").trim();
    if (!value) {
      setKeyTest((p) => ({
        ...p,
        [provider]: {
          provider,
          ok: false,
          message: "Pehle key likhein.",
        },
      }));
      return;
    }
    setKeyBusy(provider);
    try {
      if (provider === "gemini") {
        await api.addGeminiKey(keyAddLabel.trim(), value);
        setKeyAddLabel("");
      } else {
        await api.setKey(provider, value);
      }
      setKeyDraft((p) => ({ ...p, [provider]: "" }));
      setKeyTest((p) => ({
        ...p,
        [provider]: { provider, ok: true, message: "✓ Key save ho gayi." },
      }));
      setRefresh((r) => r + 1);
    } catch (e) {
      setKeyTest((p) => ({
        ...p,
        [provider]: {
          provider,
          ok: false,
          message: apiErrorDetail(e) ?? "Key save nahi hui.",
        },
      }));
    } finally {
      setKeyBusy(null);
    }
  }

  async function onTestKey(provider: string) {
    setKeyBusy(provider);
    try {
      const r = await api.testKey(provider);
      setKeyTest((p) => ({ ...p, [provider]: r }));
    } catch (e) {
      setKeyTest((p) => ({
        ...p,
        [provider]: {
          provider,
          ok: false,
          message: apiErrorDetail(e) ?? "Test nahi ho saka.",
        },
      }));
    } finally {
      setKeyBusy(null);
    }
  }

  async function onDeleteKey(provider: string) {
    if (!window.confirm("Ye key delete karein?")) return;
    setKeyBusy(provider);
    try {
      await api.deleteKey(provider);
      setKeyTest((p) => {
        const next = { ...p };
        delete next[provider];
        return next;
      });
      setRefresh((r) => r + 1);
    } catch (e) {
      setKeyTest((p) => ({
        ...p,
        [provider]: {
          provider,
          ok: false,
          message: apiErrorDetail(e) ?? "Delete nahi hua.",
        },
      }));
    } finally {
      setKeyBusy(null);
    }
  }

  const [setupElapsed, setSetupElapsed] = useState(0);

  /** v0.14.1: Setup polling — 10-min cap hata diya (Chromium ~150 MB +
   *  FFmpeg ~80 MB downloads us se zyada le sakte hain); poll error ya
   *  backend restart par run kho nahi jata — wahi run_id ki disk
   *  record se status dobara milta hai aur polling jari rehti hai. */
  async function pollSetupRun(runId: string) {
    const started = Date.now();
    for (let i = 0; i < 2400; i++) {
      await new Promise((res) => setTimeout(res, 3000));
      setSetupElapsed(Math.floor((Date.now() - started) / 1000));
      try {
        const s = await api.setupRunStatus(runId);
        setSetupRun(s);
        if (s.state === "done" || s.state === "failed") {
          setSetupMsg(
            s.state === "done"
              ? (s.note ?? "Setup mukammal — sab kuch tayyar hai.")
              : (s.note ??
                "Setup fail ho gaya — neeche step ka error dekhein aur Retry dabayen."),
          );
          return s;
        }
      } catch {
        // Poll fail — run shayad backend restart se kho gaya; disk
        // record se status dobara lo, polling jari rakho.
        try {
          const st = await api.setupStatus();
          setSetupStatus(st);
          if (st.last_run?.run_id === runId) {
            const finished: SetupRun = {
              run_id: st.last_run.run_id,
              state: st.last_run.ok ? "done" : "failed",
              steps: Object.keys(st.last_run.steps ?? {}),
              steps_done: st.last_run.steps,
            };
            setSetupRun(finished);
            setSetupMsg(
              st.last_run.ok
                ? "Setup mukammal — sab kuch tayyar hai."
                : "Setup fail ho gaya — neeche step ka error dekhein aur Retry dabayen.",
            );
            return finished;
          }
        } catch {
          /* ignore — agle poll me dobara try */
        }
      }
    }
    setSetupMsg(
      "Setup abhi bhi chal raha hai (bohat bara download) — thodi der baad dobara check karein.",
    );
    return null;
  }

  /** v0.14.1: ek fail step ko akela dobara chalao — poora Setup nahi. */
  async function retrySetupStep(step: string) {
    setSetupBusy(true);
    setSetupMsg(null);
    setSetupElapsed(0);
    try {
      const r = await api.setupRun({ steps: [step] });
      setSetupRun(r);
      if (r.state !== "done") await pollSetupRun(r.run_id);
    } catch (e) {
      setSetupMsg(apiErrorDetail(e) ?? "Retry nahi chala.");
    } finally {
      try {
        setSetupStatus(await api.setupStatus());
      } catch {
        /* ignore */
      }
      setSetupBusy(false);
    }
  }

  /** v0.14.1: update source badlo (GitHub Releases / Drive mirror) —
   *  setting save hoti hai aur foran dobara check hota hai. */
  async function changeUpdateSource(v: string) {
    setUpdateBusy(true);
    setUpdateMsg(null);
    try {
      await api.updateSetting("update_source", v);
      setRefresh((r) => r + 1);
      const c = await api.updateCheck(true);
      setUpdateCheck(c);
      setUpdateMsg(
        c.update_available
          ? `Naya version hai: ${c.latest} — neeche Apply dabayen.`
          : c.reachable
            ? "Aap latest version par hain."
            : c.error || "Koi update nahi mila.",
      );
    } catch (e) {
      setUpdateMsg(apiErrorDetail(e) ?? "Update source nahi badla.");
    } finally {
      setUpdateBusy(false);
    }
  }

  // Phase 7 slice 3: resume an interrupted/failed job (render, image
  // or transcribe) — it restarts from the beginning, honestly.
  async function onResumeJob(job: Job) {
    setResumeBusy(job.id);
    setResumeNote(null);
    try {
      const res = await api.resumeJob(job.id);
      setResumeNote(`Job #${res.job_id} dobara shuru — ${res.note}`);
      setRefresh((r) => r + 1);
    } catch (e) {
      setResumeNote(e instanceof Error ? e.message : "Resume nahi hua");
    } finally {
      setResumeBusy(null);
    }
  }

  // Cross-check slice: Stop a queued/running job (cancel).
  async function onCancelJob(job: Job) {
    setResumeBusy(job.id);
    setResumeNote(null);
    try {
      const res = await api.cancelJob(job.id);
      setResumeNote(
        `Job #${res.id} ${res.status} — ${
          res.status === "cancelled"
            ? "ab start nahi hoga / render ruk gaya."
            : "status dekh lein."
        }`,
      );
      setRefresh((r) => r + 1);
    } catch (e) {
      setResumeNote(e instanceof Error ? e.message : "Cancel nahi hua");
    } finally {
      setResumeBusy(null);
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">K</div>
          <div>
            <div className="brand-b">Kreafy</div>
            <div className="brand-small">Creator Studio</div>
          </div>
        </div>
        <nav>
          {PAGES.map((p) => (
            <button
              key={p}
              className={page === p && cineCut === null ? "nav-item active" : "nav-item"}
              onClick={() => {
                setCineCut(null);
                setPage(p);
              }}
            >
              <span className="nav-icon">{PAGE_ICONS[p]}</span>
              {p}
            </button>
          ))}
        </nav>
        <div className="nav-heading">Production Studios</div>
        <nav>
          {STUDIO_NAV.map((s) => (
            <button
              key={s.name}
              className="nav-item"
              onClick={() => openTool(s.name)}
            >
              <span className="studio-dot" style={{ color: s.color }}>
                ◆
              </span>
              {s.name}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <strong>
            Localhost · {health.data?.phase ?? "Phase 7 — Hardening"}
          </strong>
          <br />
          {health.loading
            ? "Checking backend…"
            : health.error
              ? `Backend offline: ${health.error}`
              : `Backend: ${health.data?.status} · FFmpeg ${
                  health.data?.ffmpeg.available ? "available" : "not found"
                }`}
        </div>
      </aside>

      <main className="content">
        <div className="topbar">
          <div className="app-title">
            <span className="app-symbol">✦</span>
            <div>
              <div className="app-name">Kreafy Creator Studio</div>
              <p>
                Local-first AI video production ·{" "}
                {health.data?.phase ?? "Phase 7 — Hardening"}
              </p>
            </div>
          </div>
          <input
            className="topsearch"
            placeholder="⌕ Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search projects"
          />
          <button
            className="goldbtn"
            onClick={() => {
              setCineCut(null);
              setPage("Projects");
            }}
          >
            ＋ New Project
          </button>
        </div>
        {cineCut !== null ? (
          <CineCut
            project={cineCutProject}
            projects={projects.data ?? []}
            onPickProject={(id) => setCineCut(id)}
            onBack={() => {
              setToolTarget(null);
              setActiveTool("cinecut-top");
              setCineCut(null);
              setPage("All Tools");
            }}
            toolTarget={toolTarget}
            onToolTargetShown={() => setToolTarget(null)}
            activeTool={activeTool}
            onActiveTool={setActiveTool}
          />
        ) : (
          <>
                {page === "Dashboard" && (
          <section>
            {health.error && (
              <p className="error">
                Backend is not reachable at http://127.0.0.1:8000. Start it with
                `python -m uvicorn main:app --host 127.0.0.1 --port 8000` in
                studio/backend.
              </p>
            )}
            <div className="hero">
              <div className="hero-text">
                <h1>Build. Create. Grow.</h1>
                <p>
                  From idea to professional video — all your tools in one
                  local-first studio.
                </p>
              </div>
              <button
                className="goldbtn"
                onClick={() => {
                  setCineCut(null);
                  setPage("Projects");
                }}
              >
                ＋ New Project
              </button>
            </div>
            {/* Release Packaging (v0.14.0): update badge + setup banner */}
            {updateCheck?.update_available && (
              <p>
                <span className="badge gold">
                  Update available: {updateCheck.latest}
                </span>{" "}
                <button
                  className="ghostbtn"
                  onClick={() => setPage("Settings")}
                >
                  Settings me update karein
                </button>
              </p>
            )}
            {setupStatus && !setupStatus.ready && (
              <p>
                <span className="badge gold">Setup baaki hai</span>{" "}
                <span className="muted">
                  Kuch requirements missing hain —{" "}
                </span>
                <button
                  className="ghostbtn"
                  onClick={() => setPage("Settings")}
                >
                  Setup — Install Requirements
                </button>
              </p>
            )}
            {mainCharacter && (
              <p>
                <span className="badge green">
                  ★ My Main Character: {mainCharacter.name}
                </span>
              </p>
            )}
            <div className="cards">
              <div className="card">
                <div className="card-num">{projects.data?.length ?? "—"}</div>
                <div className="card-label">Projects</div>
              </div>
              <div className="card">
                <div className="card-num">{jobs.data?.length ?? "—"}</div>
                <div className="card-label">Jobs</div>
              </div>
              <div className="card">
                <div className="card-num">{assets.data?.length ?? "—"}</div>
                <div className="card-label">Assets</div>
              </div>
              <div className="card">
                <div className="card-num">{styles.data?.length ?? "—"}</div>
                <div className="card-label">Style DNA entries</div>
              </div>
            </div>

            <h2 className="section-title">AI Production Studios</h2>
            <div className="studio-grid">
              {STUDIO_GRID_ORDER.map((name) => {
                const t = TOOLS.find((x) => x.name === name);
                if (!t) return null;
                return (
                  <button
                    key={t.name}
                    className="studio-card"
                    style={{ background: t.color }}
                    onClick={() => openTool(t.name)}
                  >
                    <h3>{t.name}</h3>
                    <p className="studio-sub">{t.subtitle}</p>
                    <p className="studio-status">{t.status}</p>
                  </button>
                );
              })}
            </div>

            <h2 className="section-title">Quick Tools</h2>
            <div className="quick-grid">
              {QUICK_TOOLS.map((q) => (
                <button
                  key={q.name}
                  className="quick-card"
                  onClick={() => {
                    setToolTarget(q.target);
                    setCineCut("pick");
                  }}
                >
                  {q.name}
                  <small>{q.note}</small>
                </button>
              ))}
            </div>

            <div className="panels">
              <div className="panel">
                <div className="panel-h">
                  <b>Recent Projects</b>
                  <span className="sub">
                    {filteredProjects.length} shown · {projects.data?.length ?? 0}{" "}
                    total
                  </span>
                </div>
                <div className="panel-body">
                  {projects.loading ? (
                    <p>Loading…</p>
                  ) : projects.error ? (
                    <p className="error">{projects.error}</p>
                  ) : filteredProjects.length === 0 ? (
                    <p className="muted">
                      No projects yet. Create your first project on the
                      Projects page.
                    </p>
                  ) : (
                    <div className="project-tiles cols2">
                      {filteredProjects.slice(0, 6).map((p) => (
                        <ProjectTile
                          key={p.id}
                          project={p}
                          thumb={firstImage(p.id)}
                          state={pipeline[p.id] ?? null}
                          character={characters[p.id] ?? null}
                          onOpen={() => setCineCut(p.id)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="panel">
                <div className="panel-h">
                  <b>Jobs</b>
                  <span className="sub">Notifications · System Status</span>
                </div>
                <div className="panel-body">
                  {jobs.loading ? (
                    <p>Loading…</p>
                  ) : jobs.error ? (
                    <p className="error">{jobs.error}</p>
                  ) : jobs.data && jobs.data.length === 0 ? (
                    <p className="muted">
                      No jobs yet. Jobs appear here when a pipeline step is
                      queued.
                    </p>
                  ) : (
                    <ul className="list">
                      {jobs.data?.map((j) => (
                        <li key={j.id}>
                          #{j.id} · {j.kind} · {j.status} · project{" "}
                          {j.project_id} · {j.created_at}
                          {j.error ? (
                            <>
                              <br />
                              <span className="error">{j.error}</span>
                            </>
                          ) : null}
                          {(j.status === "interrupted" ||
                            j.status === "failed") &&
                          (j.kind === "render" ||
                            j.kind === "image-generate" ||
                            j.kind === "transcribe") ? (
                            <>
                              {" "}
                              <button
                                disabled={resumeBusy === j.id}
                                onClick={() => void onResumeJob(j)}
                              >
                                Resume
                              </button>
                            </>
                          ) : null}
                          {(j.status === "queued" ||
                            j.status === "running") && (
                            <>
                              {" "}
                              <button
                                disabled={resumeBusy === j.id}
                                onClick={() => void onCancelJob(j)}
                                title="Queued job start nahi hoga; running render/transcribe turant ruk jayega"
                              >
                                Cancel
                              </button>
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {resumeNote && <p className="muted">{resumeNote}</p>}
                  {health.data?.ffmpeg.version && (
                    <p className="muted">{health.data.ffmpeg.version}</p>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {page === "Projects" && (
          <section>
            <h1>Projects</h1>
            <div className="form-row">
              <input
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void createProject();
                }}
                placeholder="New project name"
                aria-label="New project name"
              />
              <button onClick={() => void createProject()}>Create project</button>
            </div>
            {createError && <p className="error">{createError}</p>}
            {projects.loading ? (
              <p>Loading…</p>
            ) : projects.error ? (
              <p className="error">{projects.error}</p>
            ) : projects.data && projects.data.length === 0 ? (
              <p>No projects yet. Create your first project above.</p>
            ) : (
              <div className="project-tiles">
                {projects.data?.map((p) => (
                  <ProjectTile
                    key={p.id}
                    project={p}
                    thumb={firstImage(p.id)}
                    state={pipeline[p.id] ?? null}
                    character={characters[p.id] ?? null}
                    onOpen={() => setCineCut(p.id)}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {page === "All Tools" && (
          <section>
            <h1>All Tools</h1>
            <p className="muted">
              Har tool apna kaam karta hai — card par click karein, us tool ka
              apna page khulega. All Tools sirf menu hai.
            </p>
            <div className="tool-grid">
              {TOOLS.map((t) => (
                <div
                  className="tool-card coloured"
                  key={t.name}
                  style={{
                    background: `linear-gradient(120deg, ${t.color}bb, #152337)`,
                    borderColor: t.color,
                  }}
                >
                  <h3>{t.name}</h3>
                  <p>{t.description}</p>
                  <p className="muted">{t.status}</p>
                  <button onClick={() => openTool(t.name)}>
                    Open {t.name}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {page === "Media Library" && (
          <section>
            <h1>Media Library</h1>
            <p className="muted">
              Asset Vault — naam se dhoondhein ya tag se filter karein.
              Search aur tag filter server par chalte hain, asal assets
              par.
            </p>
            <div className="form-row">
              <label>
                Search{" "}
                <input
                  value={libQ}
                  onChange={(e) => setLibQ(e.target.value)}
                  placeholder="Naam ya kind likhein…"
                />
              </label>
              <label>
                Tag filter{" "}
                <select
                  value={libTag}
                  onChange={(e) => setLibTag(e.target.value)}
                >
                  <option value="">All tags</option>
                  {(allTags.data ?? []).map((t) => (
                    <option key={t.tag} value={t.tag}>
                      {t.tag} ({t.count})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {libAssets.loading ? (
              <p>Loading…</p>
            ) : libAssets.error ? (
              <p className="error">{libAssets.error}</p>
            ) : libAssets.data && libAssets.data.length === 0 ? (
              <p>
                {libQ || libTag
                  ? "Is search / tag se koi asset nahi mila."
                  : "No assets recorded yet. Upload a voiceover or images from a project's CineCut page."}
              </p>
            ) : (
              <>
                {(() => {
                  const images = (libAssets.data ?? []).filter(
                    (a) => a.kind === "image",
                  );
                  const other = (libAssets.data ?? []).filter(
                    (a) => a.kind !== "image",
                  );
                  const tagBlock = (a: Asset) => (
                    <div>
                      {(a.tags ?? []).map((t) => (
                        <span key={t} className="badge">
                          {t}{" "}
                          <button
                            type="button"
                            onClick={() => void onRemoveTag(a, t)}
                            title={`Remove tag ${t}`}
                          >
                            ×
                          </button>
                        </span>
                      ))}{" "}
                      <input
                        value={libTagDraft[a.id] ?? ""}
                        onChange={(e) =>
                          setLibTagDraft((prev) => ({
                            ...prev,
                            [a.id]: e.target.value,
                          }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void onAddTag(a);
                        }}
                        placeholder="Naya tag…"
                      />{" "}
                      <button
                        type="button"
                        onClick={() => void onAddTag(a)}
                      >
                        Add tag
                      </button>
                    </div>
                  );
                  return (
                    <>
                      {images.length > 0 && (
                        <div className="media-grid">
                          {images.map((a) => (
                            <div className="picturecard" key={a.id}>
                              <img src={fileUrl(a.path)} alt={`Asset ${a.id}`} />
                              <div className="detail">
                                <strong>Image #{a.id}</strong>
                                <div className="muted">
                                  Project {a.project_id} · {a.created_at}
                                </div>
                                {tagBlock(a)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {other.length > 0 && (
                        <>
                          <h2>Other assets</h2>
                          <ul className="list">
                            {other.map((a) => (
                              <li key={a.id}>
                                #{a.id} · {a.kind} · {a.path} · project{" "}
                                {a.project_id}
                                {tagBlock(a)}
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                    </>
                  );
                })()}
              </>
            )}
          </section>
        )}

{page === "Templates" && (
          <section>
            <h1>Templates</h1>
            <h2>Style DNA library</h2>
            <p className="muted">
              Locked visual styles from the inspiration-video review. Pick one
              style per project and every image prompt follows it.
            </p>
            {styles.loading ? (
              <p>Loading…</p>
            ) : styles.error ? (
              <p className="error">{styles.error}</p>
            ) : (
              <div className="tool-grid">
                {styles.data?.map((s) => (
                  <div className="tool-card" key={s.id}>
                    <h3>{s.name}</h3>
                    <p>{s.description}</p>
                    <details>
                      <summary>Master prompt</summary>
                      <p>{s.master_prompt}</p>
                    </details>
                  </div>
                ))}
              </div>
            )}
            <h2>Caption styles</h2>
            {captionStyles.loading ? (
              <p>Loading…</p>
            ) : captionStyles.error ? (
              <p className="error">{captionStyles.error}</p>
            ) : (
              <ul className="list">
                {captionStyles.data?.map((c) => (
                  <li key={c.id}>
                    {c.name} ({c.language}) — {c.description}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {page === "Settings" && (
          <section>
            <h1>Settings</h1>
            <p className="muted">
              API keys are stored on this PC only. Secret values are never
              shown back in full. Transcription defaults to local Whisper — a
              Groq key is never required.
            </p>
            <h2>Free-tier limits</h2>
            <ul className="list">
              <li>
                <strong>Gemini API (free tier):</strong>{" "}
                {settings.data?.find((s) => s.key === "gemini_free_limit_per_day")
                  ?.value || "20"}{" "}
                requests per model per day.{" "}
                <span className="muted">
                  Free AI Studio key — nothing in this app needs a paid key.
                </span>
              </li>
              <li>
                <strong>Transcription:</strong> local Whisper (free, on this
                PC). Groq is optional and never required
                {settings.data?.find((s) => s.key === "groq_required")?.value ===
                "false"
                  ? " — groq_required is false"
                  : ""}
                .
              </li>
              <li>
                <strong>Voice:</strong> free Edge-TTS (Microsoft voices, no
                key). Voice cloning / HeyGen is not used without your say-so.
              </li>
              <li>
                <strong>Render:</strong> local FFmpeg (free, on this PC). No
                cloud render, no watermark.
              </li>
            </ul>
            <h2>Local Whisper status</h2>
            <p className="muted">
              Checked live — no model is ever downloaded by this check.{" "}
              <button
                onClick={() =>
                  api
                    .whisperStatus()
                    .then(setWhisper)
                    .catch(() => setWhisper(null))
                }
              >
                Check now
              </button>
            </p>
            {whisper ? (
              <ul className="list">
                <li>
                  <strong>
                    {whisper.transcribe_ready
                      ? "Ready — offline transcription can run free"
                      : whisper.available
                        ? "Installed, but not ready to transcribe"
                        : "Not installed"}
                  </strong>
                  <br />
                  <span className="muted">{whisper.note}</span>
                </li>
                <li>
                  Engines:{" "}
                  {whisper.engines.length > 0
                    ? whisper.engines.join(", ")
                    : "none"}
                  {whisper.version ? ` (v${whisper.version})` : ""}
                </li>
                <li>
                  Models already on this PC:{" "}
                  {whisper.models_cached.length > 0
                    ? whisper.models_cached.join(", ")
                    : "none cached"}
                </li>
              </ul>
            ) : (
              <p className="muted">
                Not checked yet in this session — press “Check now”.
              </p>
            )}
            {/* v0.14.1: EK grouped "API Keys" section — purana raw dump
                (~20 technical rows), alag Gemini rotation section aur
                alag Free keys table hata diye gaye. Gemini rotation
                AI Text group ke andar hai; keys sirf aakhri 4 chars
                dikhti hain; test par friendly error + help link. */}
            <h2>API Keys</h2>
            <p className="muted">
              Har banda APNI key lagata hai — keys sirf is PC par rehti
              hain, kabhi ZIP, repo ya update me nahi jatin. App bina key
              ke bhi chalti hai; jis feature ko key chahiye wo saaf
              kahega. Key kabhi poori nahi dikhti — sirf aakhri 4
              characters.
            </p>
            {keysList.loading ? (
              <p>Loading…</p>
            ) : keysList.error ? (
              <p className="error">{keysList.error}</p>
            ) : (
              ["AI Text", "Images", "Voice", "Stock"].map((group) => (
                <div key={group}>
                  <h3>{group}</h3>
                  <ul className="list">
                    {(keysList.data ?? [])
                      .filter((k) => k.group === group)
                      .map((row) => (
                        <li key={row.id}>
                          <strong>{row.name}</strong>{" "}
                          <span
                            className={
                              row.badge === "FREE"
                                ? "badge green"
                                : row.badge === "TRIAL"
                                  ? "badge"
                                  : "badge gold"
                            }
                          >
                            {row.badge}
                          </span>{" "}
                          {row.configured ? "✓ set hai" : "— set nahi hai"}
                          {row.preview ? <> · {row.preview}</> : null}
                          <br />
                          <span className="muted">
                            {row.used_by} — {row.note}
                          </span>{" "}
                          <a href={row.get_url} target="_blank" rel="noreferrer">
                            Get key ↗
                          </a>
                          {row.kind === "rotation" ? (
                            <>
                              <ul className="list">
                                {row.keys.length === 0 && (
                                  <li>
                                    <em>Koi key nahi — neeche add karein.</em>
                                  </li>
                                )}
                                {row.keys.map((k) => (
                                  <li key={k.id}>
                                    <strong>{k.label}</strong> · {k.preview} ·
                                    position {k.position}{" "}
                                    <button
                                      onClick={() => {
                                        setKeyTestBusy(k.id);
                                        api
                                          .testGeminiKey(k.id)
                                          .then((res) =>
                                            setKeyTestResult((p) => ({
                                              ...p,
                                              [k.id]: `✓ ${res.message}`,
                                            })),
                                          )
                                          .catch((e) =>
                                            setKeyTestResult((p) => ({
                                              ...p,
                                              [k.id]: `✕ ${
                                                apiErrorDetail(e) ??
                                                "Test nahi ho saka."
                                              }`,
                                            })),
                                          )
                                          .finally(() => setKeyTestBusy(null));
                                      }}
                                      disabled={keyTestBusy === k.id}
                                    >
                                      {keyTestBusy === k.id
                                        ? "Testing…"
                                        : "Test"}
                                    </button>{" "}
                                    <button
                                      onClick={() =>
                                        api
                                          .moveGeminiKey(k.id, "up")
                                          .then(() => setRefresh((r) => r + 1))
                                          .catch(() => undefined)
                                      }
                                    >
                                      ↑
                                    </button>{" "}
                                    <button
                                      onClick={() =>
                                        api
                                          .moveGeminiKey(k.id, "down")
                                          .then(() => setRefresh((r) => r + 1))
                                          .catch(() => undefined)
                                      }
                                    >
                                      ↓
                                    </button>{" "}
                                    <button
                                      onClick={() =>
                                        api
                                          .deleteGeminiKey(k.id)
                                          .then(() => setRefresh((r) => r + 1))
                                          .catch(() => undefined)
                                      }
                                    >
                                      Delete
                                    </button>
                                    {keyTestResult[k.id] && (
                                      <span className="muted">
                                        {" "}
                                        · {keyTestResult[k.id]}
                                      </span>
                                    )}
                                  </li>
                                ))}
                              </ul>
                              <div className="form-row">
                                <input
                                  value={keyAddLabel}
                                  onChange={(e) =>
                                    setKeyAddLabel(e.target.value)
                                  }
                                  placeholder="Label (e.g. Key 2)"
                                  aria-label="New Gemini key label"
                                />
                                <input
                                  type="password"
                                  value={keyDraft["gemini"] ?? ""}
                                  onChange={(e) =>
                                    setKeyDraft((p) => ({
                                      ...p,
                                      gemini: e.target.value,
                                    }))
                                  }
                                  placeholder="Gemini API key"
                                  aria-label="New Gemini API key"
                                />
                                <button
                                  disabled={keyBusy === "gemini"}
                                  onClick={() => void onAddKey("gemini")}
                                >
                                  Add key
                                </button>
                              </div>
                            </>
                          ) : row.kind === "no-key" ? (
                            <>
                              <span className="muted">
                                {" "}
                                — key nahi chahiye
                              </span>{" "}
                              <button
                                disabled={pollinationsBusy}
                                onClick={() => {
                                  setPollinationsBusy(true);
                                  api
                                    .pollinationsTest(
                                      "a lighthouse at sunset, cinematic, detailed",
                                    )
                                    .then((r) => {
                                      setPollinationsImg(fileUrl(r.path));
                                      setKeyTest((p) => ({
                                        ...p,
                                        pollinations: {
                                          provider: "pollinations",
                                          ok: true,
                                          message: `Pollinations: image ban gayi (${(
                                            r.bytes / 1024
                                          ).toFixed(0)} KB) — bina key ke.`,
                                        },
                                      }));
                                    })
                                    .catch((e) =>
                                      setKeyTest((p) => ({
                                        ...p,
                                        pollinations: {
                                          provider: "pollinations",
                                          ok: false,
                                          message:
                                            apiErrorDetail(e) ??
                                            "Pollinations test nahi ho saka.",
                                        },
                                      })),
                                    )
                                    .finally(() => setPollinationsBusy(false));
                                }}
                              >
                                {pollinationsBusy
                                  ? "Image ban rahi…"
                                  : "Pollinations test image"}
                              </button>
                              {pollinationsImg && (
                                <p>
                                  <img
                                    src={pollinationsImg}
                                    alt="Pollinations test"
                                    style={{
                                      maxWidth: "100%",
                                      borderRadius: 8,
                                    }}
                                  />
                                </p>
                              )}
                            </>
                          ) : (
                            <div className="form-row">
                              <input
                                type="password"
                                value={keyDraft[row.id] ?? ""}
                                onChange={(e) =>
                                  setKeyDraft((p) => ({
                                    ...p,
                                    [row.id]: e.target.value,
                                  }))
                                }
                                placeholder={`${row.name} key (blank = no change)`}
                                aria-label={`${row.name} key`}
                              />
                              <button
                                disabled={keyBusy === row.id}
                                onClick={() => void onAddKey(row.id)}
                              >
                                Save key
                              </button>{" "}
                              <button
                                disabled={
                                  !row.configured || keyBusy === row.id
                                }
                                onClick={() => void onDeleteKey(row.id)}
                              >
                                Delete
                              </button>{" "}
                              <button
                                disabled={
                                  !row.configured || keyBusy === row.id
                                }
                                onClick={() => void onTestKey(row.id)}
                              >
                                Test
                              </button>
                            </div>
                          )}
                          {keyTest[row.id] && (
                            <p className="muted">
                              {keyTest[row.id]!.ok ? "✓ " : "✕ "}
                              {keyTest[row.id]!.message}
                              {keyTest[row.id]!.help_url ? (
                                <>
                                  {" · "}
                                  <a
                                    href={keyTest[row.id]!.help_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Key lein ↗
                                  </a>
                                </>
                              ) : null}
                            </p>
                          )}
                        </li>
                      ))}
                  </ul>
                </div>
              ))
            )}
            <details>
              <summary>Advanced settings</summary>
              <p className="muted">
                Engine aur update ki advanced settings — aam tor par
                chherne ki zaroorat nahi. Keys upar wale API Keys section
                me hain.
              </p>
              {settings.loading ? (
                <p>Loading…</p>
              ) : settings.error ? (
                <p className="error">{settings.error}</p>
              ) : (
                <ul className="list">
                  {settings.data
                    ?.filter((s) => !KEY_SETTINGS.has(s.key))
                    .map((s) => (
                      <li key={s.key}>
                        <strong>{s.key}</strong>:{" "}
                        {editingKey === s.key ? (
                          <>
                            <input
                              value={editingValue}
                              onChange={(e) =>
                                setEditingValue(e.target.value)
                              }
                              aria-label={`Value for ${s.key}`}
                              placeholder={
                                s.value.includes("•")
                                  ? "New value (blank keeps current)"
                                  : undefined
                              }
                            />{" "}
                            <button onClick={() => void saveSetting(s.key)}>
                              Save
                            </button>{" "}
                            <button onClick={() => setEditingKey(null)}>
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            {s.value === "" ? (
                              <em>(not set)</em>
                            ) : (
                              s.value
                            )}{" "}
                            <button
                              onClick={() => {
                                setEditingKey(s.key);
                                // Prefill the current value so saving without
                                // typing cannot wipe the key. Secret keys show
                                // masked (••••), so they start blank — and the
                                // backend leaves a secret untouched on a blank
                                // save.
                                setEditingValue(
                                  s.value.includes("•") ? "" : s.value,
                                );
                              }}
                            >
                              Edit
                            </button>
                          </>
                        )}
                        <br />
                        <span className="muted">{s.note}</span>
                      </li>
                    ))}
                </ul>
              )}
            </details>
            <h2>Connect Google (Canvas + Flow)</h2>
            <p className="muted">
              Ek dafa Google sign-in karein — wahi login VisualForge ke
              dono free providers (Gemini Canvas aur Google Flow) ke
              liye kaam karta hai, dobara sign-in nahi. Images aapki
              Gemini Pro quota se free banti hain. Login sirf is PC
              par save hota hai, koi password ya key yahan nahi
              likhi jati.
            </p>
            <div className="form-row">
              <span className="muted">
                {googleStatus
                  ? googleStatus.logged_in
                    ? "✓ Google connected — Canvas aur Flow dono ke liye login hai."
                    : `Google: ${googleStatus.message}`
                  : "Google status loading…"}
              </span>
              {googleStatus?.needs_login && (
                <button
                  onClick={() => void onOpenGoogleLogin()}
                  disabled={googleLoginBusy}
                >
                  {googleLoginBusy ? "Opening…" : "Connect Google"}
                </button>
              )}
              {googleStatus?.logged_in && (
                <button
                  onClick={() => void onDisconnectGoogle()}
                  disabled={googleDisconnectBusy}
                >
                  {googleDisconnectBusy ? "Disconnecting…" : "Disconnect"}
                </button>
              )}
              <button onClick={() => void loadGoogleStatus()}>
                Refresh status
              </button>
            </div>
            {googleNote && <p className="muted">{googleNote}</p>}
            {googleError && <p className="error">{googleError}</p>}
            {googleStatus && (
              <ul className="list">
                <li>
                  Canvas:{" "}
                  {googleStatus.canvas.logged_in
                    ? "✓ ready"
                    : googleStatus.canvas.message || "login chahiye"}
                </li>
                <li>
                  Flow:{" "}
                  {googleStatus.flow.logged_in
                    ? "✓ ready"
                    : googleStatus.flow.message || "login chahiye"}
                </li>
              </ul>
            )}
            {googleStatus?.needs_login && (
              <ol className="muted">
                {googleStatus.setup_steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
            )}
            <h2>Custom voice providers (advanced)</h2>
            <p className="muted">
              Apne TTS endpoints yahan add karein. API keys upar wale
              API Keys section me hain.
            </p>
            <p className="muted">
              Edge-TTS free aur HeyGen clone pehle se hain. A123 Pro ya koi
              bhi aur provider yahan add karein — Test sirf base URL ki
              reachability check karta hai; voice generation is se verify
              nahi hoti.
            </p>
            {voiceProviders.loading ? (
              <p>Loading…</p>
            ) : voiceProviders.error ? (
              <p className="error">{voiceProviders.error}</p>
            ) : (
              <ul className="list">
                {voiceProviders.data?.map((p) => (
                  <li key={String(p.id)}>
                    <strong>{p.name}</strong> · {p.kind}
                    {p.base_url ? ` · ${p.base_url}` : ""} ·{" "}
                    {p.key_set ? "key set hai" : "no key"} · test:{" "}
                    {p.test_status}
                    {p.test_message ? ` — ${p.test_message}` : ""}
                    {p.kind === "custom" && (
                      <>
                        {" "}
                        <button
                          onClick={() =>
                            api
                              .testVoiceProvider(p.id)
                              .then(() => setRefresh((r) => r + 1))
                              .catch((e) =>
                                setProviderError(
                                  e instanceof Error
                                    ? e.message
                                    : "Test nahi hua",
                                ),
                              )
                          }
                        >
                          Test
                        </button>{" "}
                        <button
                          onClick={() =>
                            api
                              .deleteVoiceProvider(p.id)
                              .then(() => setRefresh((r) => r + 1))
                              .catch(() => undefined)
                          }
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <div className="form-row">
              <input
                value={newProviderName}
                onChange={(e) => setNewProviderName(e.target.value)}
                placeholder="Provider name (e.g. A123 Pro)"
                aria-label="New provider name"
              />
              <input
                value={newProviderUrl}
                onChange={(e) => setNewProviderUrl(e.target.value)}
                placeholder="Base URL (https://…)"
                aria-label="New provider base URL"
              />
              <input
                value={newProviderKey}
                onChange={(e) => setNewProviderKey(e.target.value)}
                placeholder="API key (optional)"
                aria-label="New provider API key"
              />
              <button
                onClick={() => {
                  setProviderError(null);
                  api
                    .addVoiceProvider(
                      newProviderName.trim(),
                      newProviderUrl.trim(),
                      newProviderKey.trim(),
                    )
                    .then(() => {
                      setNewProviderName("");
                      setNewProviderUrl("");
                      setNewProviderKey("");
                      setRefresh((r) => r + 1);
                    })
                    .catch((e) =>
                      setProviderError(
                        e instanceof Error
                          ? e.message
                          : "Provider add nahi hua",
                      ),
                    );
                }}
              >
                Add provider
              </button>
            </div>
            {providerError && <p className="error">{providerError}</p>}
            {/* Release Packaging (v0.14.0): Update / Setup / Output / Free keys */}
            <h2>Update</h2>
            <p className="muted">
              Version: <strong>{health.data?.version ?? "—"}</strong>
              {updateCheck && (
                <>
                  {" · "}Update source:{" "}
                  {updateCheck.source === "drive"
                    ? "Google Drive mirror (link-shared ZIP)"
                    : `${updateCheck.repo} (public GitHub Releases — bina login)`}
                </>
              )}
            </p>
            <div className="form-row">
              <span className="muted">Source:</span>{" "}
              <button
                className={
                  updateCheck?.source !== "drive" ? "" : "ghostbtn"
                }
                disabled={updateBusy}
                onClick={() => void changeUpdateSource("github")}
              >
                GitHub Releases
              </button>{" "}
              <button
                className={
                  updateCheck?.source === "drive" ? "" : "ghostbtn"
                }
                disabled={updateBusy}
                onClick={() => void changeUpdateSource("drive")}
              >
                Google Drive mirror
              </button>
            </div>
            <div className="form-row">
              <button
                onClick={() => {
                  setUpdateBusy(true);
                  setUpdateMsg(null);
                  api
                    .updateCheck(true)
                    .then((c) => {
                      setUpdateCheck(c);
                      setUpdateMsg(
                        c.update_available
                          ? `Naya version hai: ${c.latest} — neeche Apply dabayen.`
                          : c.reachable
                            ? "Aap latest version par hain."
                            : c.error || "Koi public Release nahi mili.",
                      );
                    })
                    .catch((e) =>
                      setUpdateMsg(
                        apiErrorDetail(e) ?? "Update check nahi ho saka.",
                      ),
                    )
                    .finally(() => setUpdateBusy(false));
                }}
                disabled={updateBusy}
              >
                {updateBusy ? "Check ho raha…" : "Check for Update"}
              </button>
              {updateCheck?.update_available && updateCheck.asset && (
                <button
                  onClick={() => {
                    if (
                      !window.confirm(
                        "Update apply karein? Pehle backup banta hai; videos, settings aur keys kabhi delete nahi hotin.",
                      )
                    )
                      return;
                    setUpdateApplying(true);
                    setUpdateMsg(null);
                    api
                      .updateApply({})
                      .then(async () => {
                        for (let i = 0; i < 120; i++) {
                          await new Promise((res) =>
                            setTimeout(res, 5000),
                          );
                          const s = await api.updateStatus();
                          setUpdateMsg(
                            `Update: ${s.state} — ${s.detail}`,
                          );
                          if (
                            s.state === "done" ||
                            s.state === "failed" ||
                            s.last?.state === "done" ||
                            s.last?.state === "failed"
                          )
                            break;
                        }
                        setUpdateApplying(false);
                        try {
                          const c = await api.updateChangelog();
                          setChangelog(c.changelog);
                        } catch {
                          /* ignore */
                        }
                        try {
                          setUpdateCheck(await api.updateCheck(true));
                        } catch {
                          /* ignore */
                        }
                      })
                      .catch((e) => {
                        setUpdateMsg(
                          apiErrorDetail(e) ??
                            "Update apply nahi ho saka.",
                        );
                        setUpdateApplying(false);
                      });
                  }}
                  disabled={updateApplying}
                >
                  {updateApplying
                    ? "Update chal raha…"
                    : `Apply update ${updateCheck.latest ?? ""}`}
                </button>
              )}
            </div>
            {updateMsg && <p className="muted">{updateMsg}</p>}
            {changelog && (
              <details>
                <summary>Changelog</summary>
                <pre className="muted">{changelog}</pre>
              </details>
            )}
            <h2>Setup — Install Requirements</h2>
            <p className="muted">
              Pehli dafa ya kuch missing ho to Setup dabayen — backend
              packages, Chromium browser (Canvas free images) aur FFmpeg
              khud install ho jate hain. Har step green tick se verify
              hota hai — tick SIRF tab jab cheez asal me maujood ho.
            </p>
            {setupStatus ? (
              <ul className="list">
                <li>
                  <strong>
                    {setupStatus.ready ? "Ready ✓" : "Setup baaki hai"}
                  </strong>{" "}
                  · Python {setupStatus.python.version} · FFmpeg{" "}
                  {setupStatus.ffmpeg.ok ? "✓" : "✗ missing"} · Chromium{" "}
                  {setupStatus.chromium.ok ? "✓" : "✗ missing (recommended)"}
                </li>
                {setupStatus.backend_deps.map((d) => (
                  <li key={d.module}>
                    {d.ok ? "✓" : "✗"} {d.module}
                    {d.required ? " (required)" : " (optional)"}
                  </li>
                ))}
                {/* v0.14.1: last_run ke steps bhi dikhte hain — refresh
                    ke baad bhi fail step ka asal error + Retry milta hai. */}
                {Object.entries(
                  setupRun?.steps_done ?? setupStatus.last_run?.steps ?? {},
                ).map(([step, r]) => (
                  <li key={step}>
                    {r.ok ? "✓" : "✗"} {step} — {r.detail}
                    {!r.ok && !setupBusy && (
                      <>
                        {" "}
                        <button onClick={() => void retrySetupStep(step)}>
                          Retry
                        </button>
                      </>
                    )}
                  </li>
                ))}
                {setupBusy && setupRun?.current && (
                  <li>
                    … {setupRun.current} chal raha hai ({setupElapsed}s)
                  </li>
                )}
              </ul>
            ) : (
              <p className="muted">Setup status load nahi hua — dobara try karein.</p>
            )}
            <div className="form-row">
              <button
                onClick={() => {
                  setSetupBusy(true);
                  setSetupMsg(null);
                  setSetupElapsed(0);
                  api
                    .setupRun({})
                    .then(async (r) => {
                      setSetupRun(r);
                      if (r.state === "done") {
                        setSetupMsg(
                          r.note ?? "Sab kuch pehle se tayyar hai.",
                        );
                        return;
                      }
                      await pollSetupRun(r.run_id);
                    })
                    .catch((e) => {
                      setSetupMsg(
                        apiErrorDetail(e) ?? "Setup nahi chala.",
                      );
                    })
                    .finally(async () => {
                      try {
                        setSetupStatus(await api.setupStatus());
                      } catch {
                        /* ignore */
                      }
                      setSetupBusy(false);
                    });
                }}
                disabled={setupBusy}
              >
                {setupBusy
                  ? `Setup chal raha… (${setupElapsed}s)`
                  : "Setup — Install Requirements"}
              </button>
              <button
                onClick={() => {
                  api
                    .desktopShortcut()
                    .then((r) =>
                      setSetupMsg(`Desktop shortcut ban gaya: ${r.path}`),
                    )
                    .catch((e) =>
                      setSetupMsg(
                        apiErrorDetail(e) ??
                          "Desktop shortcut nahi bana.",
                      ),
                    );
                }}
              >
                Desktop shortcut banao
              </button>
            </div>
            {setupMsg && <p className="muted">{setupMsg}</p>}
            <h2>Output folder</h2>
            <p className="muted">
              Aapki final videos yahin hain — date-wise folders me.
              Update inhe kabhi touch nahi karta.
            </p>
            {outputInfo && (
              <ul className="list">
                <li>
                  <strong>Path:</strong> {outputInfo.path}
                </li>
                <li>
                  <strong>Videos:</strong> {outputInfo.files} files ·{" "}
                  {(outputInfo.size_bytes / 1048576).toFixed(1)} MB
                </li>
                {outputInfo.by_date.slice(0, 7).map((d) => (
                  <li key={d.date}>
                    {d.date}: {d.files} files ·{" "}
                    {(d.size_bytes / 1048576).toFixed(1)} MB
                  </li>
                ))}
              </ul>
            )}
            <div className="form-row">
              <button
                onClick={() => {
                  api
                    .outputOpen()
                    .then((r) => setOutputMsg(`Folder khul gaya: ${r.path}`))
                    .catch((e) =>
                      setOutputMsg(
                        apiErrorDetail(e) ?? "Folder nahi khula.",
                      ),
                    );
                }}
              >
                Open output folder
              </button>
              <button
                onClick={() => {
                  if (
                    !window.confirm(
                      "30 din se purane renders delete karein? Aaj ki videos kabhi delete nahi hotin.",
                    )
                  )
                    return;
                  api
                    .outputClean(true)
                    .then((r) => {
                      setOutputMsg(
                        `${r.deleted_files} purani files delete hui — ${(r.freed_bytes / 1048576).toFixed(1)} MB khaali hua.`,
                      );
                      return api.outputInfo().then(setOutputInfo);
                    })
                    .catch((e) =>
                      setOutputMsg(
                        apiErrorDetail(e) ?? "Clean nahi ho saka.",
                      ),
                    );
                }}
              >
                Clean old renders (30+ days)
              </button>
            </div>
            {outputMsg && <p className="muted">{outputMsg}</p>}
            <h2>Backup &amp; restore</h2>
            <p className="muted">
              Backup me poori database + studio/data ki files hoti hain —
              renders/ nahi (wo dobara render ho jate hain). Restore karne
              se pehle chalti jobs khatam hone dein.
            </p>
            <div className="form-row">
              <a href={`${API_BASE}/backup`}>
                <button type="button">Download backup (.zip)</button>
              </a>
            </div>
            <div className="form-row">
              <input
                type="file"
                accept=".zip"
                aria-label="Backup ZIP file"
                onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
              />
              <button
                disabled={!restoreFile || restoreBusy}
                onClick={() => {
                  if (!restoreFile) return;
                  setRestoreBusy(true);
                  setRestoreResult(null);
                  api
                    .restoreBackup(restoreFile)
                    .then((r) =>
                      setRestoreResult(
                        `Restore ho gaya — ${r.projects} projects, ${r.assets} assets, ${r.jobs} jobs, ${r.files} files. ${r.note}`,
                      ),
                    )
                    .catch((e) =>
                      setRestoreResult(
                        e instanceof Error ? e.message : "Restore nahi hua",
                      ),
                    )
                    .finally(() => {
                      setRestoreBusy(false);
                      setRefresh((r) => r + 1);
                    });
                }}
              >
                Restore backup
              </button>
            </div>
            {restoreResult && <p className="muted">{restoreResult}</p>}
          </section>
        )}
          </>
        )}
        <footer className="muted" style={{ marginTop: 24 }}>
          Kreafy Creator Studio {health.data?.version ?? ""} · Localhost
          only — aapka data is PC par rehta hai.
        </footer>
      </main>
    </div>
  );
}
