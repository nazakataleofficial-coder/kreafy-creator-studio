import { useEffect, useRef, useState } from "react";
import {
  api,
  fileUrl,
  WATERMARK_CORNER_LABEL,
} from "./api";
import type {
  WatermarkImage,
  WatermarkJob,
  WatermarkStroke,
} from "./api";

/** Error text se backend ka plain Roman Urdu detail nikalna
 *  (api helpers "503 {\"detail\": \"...\"}" throw karte hain). */
function detailOf(e: unknown): string {
  if (!(e instanceof Error)) return "Kuch ghalat ho gaya — dobara try karein.";
  const m = e.message.match(/\{.*\}$/s);
  if (m) {
    try {
      const parsed = JSON.parse(m[0]) as { detail?: unknown };
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      /* fall through */
    }
  }
  return e.message;
}

function badgeText(img: WatermarkImage): string {
  if (!img.badge) return "Koi watermark nahi";
  const corner =
    WATERMARK_CORNER_LABEL[img.badge.corner] ?? img.badge.corner;
  return `Watermark mila — ${corner}`;
}

/** Manual paint: AFTER image par laal strokes. Canvas image ke upar
 *  overlay hai; pointer coords 0..1 me normalize hote hain. */
function PaintCanvas({
  src,
  strokes,
  onStrokes,
  disabled,
}: {
  src: string;
  strokes: WatermarkStroke[];
  onStrokes: (s: WatermarkStroke[]) => void;
  disabled: boolean;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const painting = useRef(false);

  function sizeCanvas() {
    const img = imgRef.current;
    const cv = canvasRef.current;
    if (!img || !cv) return;
    cv.width = img.clientWidth || 1;
    cv.height = img.clientHeight || 1;
    redraw();
  }

  function redraw() {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.strokeStyle = "rgba(255, 60, 60, 0.95)";
    ctx.fillStyle = "rgba(255, 60, 60, 0.35)";
    ctx.lineWidth = 2;
    for (const s of strokes) {
      const x = s.x * cv.width;
      const y = s.y * cv.height;
      const r = Math.max(4, s.r * cv.width);
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }

  useEffect(() => {
    redraw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strokes]);

  useEffect(() => {
    const onResize = () => sizeCanvas();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pointFromEvent(e: React.PointerEvent): WatermarkStroke | null {
    const cv = canvasRef.current;
    if (!cv) return null;
    const rect = cv.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
      r: 0.03,
    };
  }

  return (
    <div
      ref={wrapRef}
      style={{ position: "relative", lineHeight: 0 }}
      onPointerDown={(e) => {
        if (disabled) return;
        painting.current = true;
        (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
        const p = pointFromEvent(e);
        if (p) onStrokes([...strokes, p]);
      }}
      onPointerMove={(e) => {
        if (!painting.current || disabled) return;
        const p = pointFromEvent(e);
        if (p) onStrokes([...strokes, p]);
      }}
      onPointerUp={() => {
        painting.current = false;
      }}
      onPointerLeave={() => {
        painting.current = false;
      }}
    >
      {/* eslint-disable-next-line jsx-a11y/alt-text */}
      <img
        ref={imgRef}
        src={src}
        alt="Cleaned preview — paint par watermark bach gaya ho"
        style={{ width: "100%", display: "block", touchAction: "none" }}
        onLoad={sizeCanvas}
      />
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          cursor: disabled ? "default" : "crosshair",
          touchAction: "none",
        }}
      />
    </div>
  );
}

/** Slice 6 — Watermark Cleaner: ek tool = ek kaam. Sirf watermark
 *  saaf karna: upload, detect, clean, manual paint, ZIP download.
 *  Project-independent hai — koi project pick nahi mangta. */
export default function WatermarkCleanerView({
  onBack,
}: {
  onBack: () => void;
}) {
  const [job, setJob] = useState<WatermarkJob | null>(null);
  const [jobs, setJobs] = useState<WatermarkJob[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [manualBusy, setManualBusy] = useState<string | null>(null);
  const [intensity, setIntensity] = useState(1.0);
  const [showAfter, setShowAfter] = useState<Record<string, boolean>>({});
  const [strokes, setStrokes] = useState<Record<string, WatermarkStroke[]>>(
    {},
  );
  const [painting, setPainting] = useState<Record<string, boolean>>({});
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadJobs() {
    try {
      setJobs(await api.watermarkJobs());
      setJobsError(null);
    } catch (e) {
      setJobsError(detailOf(e));
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  async function onFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      for (const f of list) form.append("files", f);
      const created = await api.watermarkUpload(form);
      setJob(created);
      setShowAfter({});
      setStrokes({});
      setPainting({});
      void loadJobs();
    } catch (e) {
      setError(detailOf(e));
    } finally {
      setUploading(false);
    }
  }

  async function onClean() {
    if (!job) return;
    setError(null);
    setCleaning(true);
    try {
      const done = await api.watermarkClean(job.id, intensity);
      setJob(done);
      const after: Record<string, boolean> = {};
      for (const img of done.images) after[img.name] = true;
      setShowAfter(after);
      void loadJobs();
    } catch (e) {
      setError(detailOf(e));
    } finally {
      setCleaning(false);
    }
  }

  async function onManualRun(img: WatermarkImage) {
    if (!job) return;
    const list = strokes[img.name] ?? [];
    if (list.length === 0) return;
    setError(null);
    setManualBusy(img.name);
    try {
      const updated = await api.watermarkManual(job.id, {
        image: img.name,
        strokes: list,
        intensity,
      });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              images: prev.images.map((i) =>
                i.name === updated.name ? updated : i,
              ),
            }
          : prev,
      );
      setStrokes((prev) => ({ ...prev, [img.name]: [] }));
    } catch (e) {
      setError(detailOf(e));
    } finally {
      setManualBusy(null);
    }
  }

  async function openJob(id: string) {
    setError(null);
    try {
      const j = await api.watermarkJob(id);
      setJob(j);
      setShowAfter({});
      setStrokes({});
      setPainting({});
    } catch (e) {
      setError(detailOf(e));
    }
  }

  const foundCount = job?.images.filter((i) => i.badge)?.length ?? 0;

  return (
    <section>
      <h1>Watermark Cleaner</h1>
      <p>
        <button className="ghostbtn" onClick={onBack}>
          ← Back to All Tools
        </button>
      </p>
      <p className="muted">
        Gemini / Flow images ka chhota safed sparkle badge (corner star)
        saaf karein — free, local, koi API nahi. Upload karein, Clean
        dabayein, bacha hua ho to laal paint se dobara chalaiyein.
      </p>
      {error && <p className="error">{error}</p>}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void onFiles(e.dataTransfer.files);
        }}
        style={{
          border: dragOver
            ? "2px dashed #c8a96b"
            : "2px dashed var(--hatch-widget-border, #444)",
          borderRadius: 8,
          padding: 24,
          textAlign: "center",
        }}
      >
        <p>
          Tasveerein yahan drop karein (png / jpg / webp — max 20, har ek
          max 20 MB)
        </p>
        <button
          className="goldbtn"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
        >
          {uploading ? "Upload ho raha hai…" : "Files chunein"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".png,.jpg,.jpeg,.webp"
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) void onFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {job && (
        <>
          <h2>Job — {job.images.length} tasveerein</h2>
          <p className="muted">
            Status: {job.status}
            {job.status === "uploaded" &&
              ` · ${foundCount} me watermark mila, ${
                job.images.length - foundCount
              } me nahi`}
            {job.summary &&
              ` · ${job.summary.with_badge} me badge tha, ${job.summary.clean_ge_90} 90%+ clean, ${job.summary.remaining} baaqi`}
          </p>
          <div className="form-row">
            <label>
              Intensity — {intensity.toFixed(1)}
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.1}
                value={intensity}
                onChange={(e) => setIntensity(Number(e.target.value))}
                aria-label="Clean intensity"
                style={{ width: 180 }}
              />
            </label>
            <button
              className="goldbtn"
              onClick={() => void onClean()}
              disabled={cleaning || job.images.length === 0}
            >
              {cleaning ? "Clean ho raha hai…" : "Clean karein"}
            </button>
            {job.status === "done" && (
              <a
                className="goldbtn"
                href={api.watermarkZipUrl(job.id)}
                style={{ textDecoration: "none", display: "inline-block" }}
              >
                Download ZIP
              </a>
            )}
          </div>

          <div className="card-grid">
            {job.images.map((img) => {
              const after = showAfter[img.name] ?? false;
              const src =
                after && img.cleaned_url ? img.cleaned_url : img.orig_url;
              const imgStrokes = strokes[img.name] ?? [];
              const isPainting = painting[img.name] ?? false;
              return (
                <div key={img.name} className="card">
                  <strong>{img.name.replace(/^\d+_/, "")}</strong>
                  <p className="muted">{badgeText(img)}</p>
                  {img.report && (
                    <p className="muted">
                      {img.report.found
                        ? `Clean: ${img.report.clean_pct}% (contrast ${img.report.contrast_before} → ${img.report.contrast_after})`
                        : "Koi badge nahi tha — original jaisa hai"}
                      {img.report.note ? ` · ${img.report.note}` : ""}
                    </p>
                  )}
                  {img.cleaned_url ? (
                    <div className="form-row">
                      <button
                        className={after ? "ghostbtn" : ""}
                        onClick={() =>
                          setShowAfter((p) => ({ ...p, [img.name]: false }))
                        }
                      >
                        Before
                      </button>
                      <button
                        className={after ? "" : "ghostbtn"}
                        onClick={() =>
                          setShowAfter((p) => ({ ...p, [img.name]: true }))
                        }
                      >
                        After
                      </button>
                      <button
                        className={isPainting ? "" : "ghostbtn"}
                        onClick={() =>
                          setPainting((p) => ({
                            ...p,
                            [img.name]: !isPainting,
                          }))
                        }
                      >
                        {isPainting ? "Paint band karein" : "Manual paint"}
                      </button>
                    </div>
                  ) : (
                    <p className="muted">
                      Clean karne ke baad Before / After yahan dikhega.
                    </p>
                  )}
                  {img.cleaned_url && isPainting ? (
                    <>
                      <PaintCanvas
                        src={fileUrl(img.cleaned_url)}
                        strokes={imgStrokes}
                        onStrokes={(s) =>
                          setStrokes((p) => ({ ...p, [img.name]: s }))
                        }
                        disabled={manualBusy !== null}
                      />
                      <div className="form-row">
                        <button
                          className="goldbtn"
                          disabled={
                            imgStrokes.length === 0 || manualBusy !== null
                          }
                          onClick={() => void onManualRun(img)}
                        >
                          {manualBusy === img.name
                            ? "Dobara clean ho raha hai…"
                            : "Painted jagah dobara clean karein"}
                        </button>
                        <button
                          className="ghostbtn"
                          disabled={imgStrokes.length === 0}
                          onClick={() =>
                            setStrokes((p) => ({ ...p, [img.name]: [] }))
                          }
                        >
                          Strokes saaf karein
                        </button>
                      </div>
                      <p className="muted">
                        Laal rang se us jagah par paint karein jahan
                        watermark bach gaya ho, phir Re-run dabayein.
                      </p>
                    </>
                  ) : (
                    // eslint-disable-next-line jsx-a11y/alt-text
                    <img
                      src={fileUrl(src)}
                      alt={after ? "Cleaned image" : "Original image"}
                      style={{ width: "100%", display: "block" }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <h2>Recent jobs</h2>
      {jobsError ? (
        <p className="error">{jobsError}</p>
      ) : jobs.length === 0 ? (
        <p className="muted">
          Abhi koi job nahi — upar se tasveerein upload karein.
        </p>
      ) : (
        <ul className="list">
          {jobs.map((j) => (
            <li key={j.id}>
              {j.images.length} tasveerein · {j.status} · {j.created}{" "}
              <button className="ghostbtn" onClick={() => void openJob(j.id)}>
                Open
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
