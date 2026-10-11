import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { AudioLines, Check, Mic, Sparkles, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { api, unwrap } from "@/api/client";
import type { CallExtraction, CallRecording, ConfirmCallRequest } from "@/api/types";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/format";
import { cap } from "@/lib/useOps";

const ACCEPT = ".mp3,.m4a,.wav,.ogg";

// A file that is still on its way (or failed). Once the backend answers, the call comes from /api/calls instead.
type Pending = { key: string; name: string; progress: number; stage: "uploading" | "processing" | "failed"; error?: string; peaks?: number[] };

function uploadCall(file: File, onProgress: (fraction: number) => void): Promise<CallExtraction> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/calls/upload");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* the server did not answer with JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as CallExtraction);
      else reject(new Error((data as { detail?: string } | null)?.detail ?? `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Network error"));
    const body = new FormData();
    body.append("audio", file);
    xhr.send(body);
  });
}

// Loudness of the recording in `bars` slices, read from the audio file itself.
async function peaksOf(file: File, bars = 72): Promise<number[]> {
  const ctx = new AudioContext();
  try {
    const samples = (await ctx.decodeAudioData(await file.arrayBuffer())).getChannelData(0);
    const size = Math.max(1, Math.floor(samples.length / bars));
    const peaks: number[] = [];
    for (let i = 0; i < bars; i++) {
      let max = 0;
      for (let j = i * size; j < Math.min(samples.length, (i + 1) * size); j++) max = Math.max(max, Math.abs(samples[j] ?? 0));
      peaks.push(max);
    }
    const top = Math.max(...peaks, 1e-6);
    return peaks.map((p) => p / top);
  } finally {
    void ctx.close();
  }
}

const duration = (s?: number | null) => (s == null ? null : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`);

function Waveform({ peaks }: { peaks: number[] }) {
  return (
    <div className="flex h-16 items-center gap-[3px]" aria-hidden>
      {peaks.map((p, i) => (
        <span key={i} className="w-[3px] rounded-full bg-primary/40" style={{ height: `${Math.max(6, p * 100)}%` }} />
      ))}
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <label className="grid gap-1 text-[11px] text-muted-foreground">
      {label}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary"
      />
    </label>
  );
}

const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Math.round(Number(v)));

function ExtractedUpdate({ extraction, onConfirm, busy }: { extraction: CallExtraction; onConfirm: (changes: ConfirmCallRequest) => void; busy: boolean }) {
  const [f, setF] = useState({
    origin: extraction.origin ?? "",
    destination: extraction.destination ?? "",
    pickup_date: extraction.pickup_date ?? "",
    cargo: extraction.cargo ?? "",
    vehicle: extraction.vehicle ?? "",
    weight_kg: extraction.weight_kg?.toString() ?? "",
    price_eur: extraction.price_eur?.toString() ?? "",
  });
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  const review = extraction.status === "pending_review";
  const known: [string, string | number | null | undefined][] = [
    ["Client", extraction.client_name],
    ["Contact", extraction.contact_name],
    ["Delivery date", extraction.delivery_date],
    ["Pallets", extraction.pallets],
    ["Payment terms", extraction.payment_terms],
  ];

  return (
    <div className="grid gap-4 p-5">
      <p className="text-sm font-medium">{extraction.summary}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Origin" value={f.origin} onChange={set("origin")} />
        <Field label="Destination" value={f.destination} onChange={set("destination")} />
        <Field label="Pickup date" type="date" value={f.pickup_date} onChange={set("pickup_date")} />
        <Field label="Cargo" value={f.cargo} onChange={set("cargo")} />
        <Field label="Vehicle" value={f.vehicle} onChange={set("vehicle")} />
        <Field label="Weight (kg)" type="number" value={f.weight_kg} onChange={set("weight_kg")} />
        <Field label="Price (EUR)" type="number" value={f.price_eur} onChange={set("price_eur")} />
      </div>
      {known.some(([, v]) => v != null && v !== "") && (
        <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-xs">
          {known.map(([k, v]) => v != null && v !== "" && (
            <div key={k} className="contents">
              <dt className="subtle">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {extraction.requirements.length > 0 && <p className="text-xs"><span className="subtle">Requirements: </span>{extraction.requirements.join(", ")}</p>}
      {extraction.missing_fields.length > 0 && <p className="text-xs text-warning">Missing: {extraction.missing_fields.map(cap).join(", ")}</p>}
      <details className="text-xs">
        <summary className="cursor-pointer subtle">Transcript</summary>
        <p className="mt-2 whitespace-pre-wrap">{extraction.transcript}</p>
      </details>
      {review ? (
        <Button disabled={busy} onClick={() => onConfirm({ origin: f.origin || null, destination: f.destination || null, pickup_date: f.pickup_date || null, cargo: f.cargo || null, vehicle: f.vehicle || null, weight_kg: num(f.weight_kg), price_eur: num(f.price_eur) })}>
          <Check />Confirm and add load
        </Button>
      ) : (
        <p className="text-xs text-success">Confirmed{extraction.load_id ? ` · load ${extraction.load_id}` : ""}</p>
      )}
    </div>
  );
}

export function CallExtractionView() {
  const [calls, setCalls] = useState<CallRecording[]>([]);
  const [extractions, setExtractions] = useState<Record<string, CallExtraction>>({});
  const [pending, setPending] = useState<Pending[]>([]);
  const [peaks, setPeaks] = useState<Record<string, number[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const known = useRef(new Set<string>());

  const load = useCallback(async () => {
    const list = await unwrap(api.GET("/api/calls"));
    setCalls([...list].sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at)));
    for (const call of list) {
      if (known.current.has(call.id)) continue;
      known.current.add(call.id);
      unwrap(api.GET("/api/calls/{call_id}/extraction", { params: { path: { call_id: call.id } } }))
        .then((ex) => setExtractions((cur) => ({ ...cur, [call.id]: ex })))
        .catch(() => known.current.delete(call.id)); // no extraction yet: try again on the next load
    }
  }, []);

  useEffect(() => {
    load().catch((e: Error) => toast.error(e.message));
  }, [load]);

  const patch = (key: string, change: Partial<Pending>) => setPending((cur) => cur.map((p) => (p.key === key ? { ...p, ...change } : p)));

  const addFiles = (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const key = `${file.name}-${file.size}-${Date.now()}`;
      setPending((cur) => [{ key, name: file.name, progress: 0, stage: "uploading" }, ...cur]);
      setSelected(key);
      peaksOf(file).then((p) => patch(key, { peaks: p })).catch(() => undefined); // some formats cannot be decoded in the browser
      uploadCall(file, (fraction) => patch(key, { progress: fraction, stage: fraction >= 1 ? "processing" : "uploading" }))
        .then(async (ex) => {
          known.current.add(ex.call_id);
          setExtractions((cur) => ({ ...cur, [ex.call_id]: ex }));
          setPeaks((cur) => ({ ...cur, [ex.call_id]: pendingPeaks(key) }));
          await load();
          setPending((cur) => cur.filter((p) => p.key !== key));
          setSelected((cur) => (cur === key ? ex.call_id : cur));
        })
        .catch((err: Error) => patch(key, { stage: "failed", error: err.message }));
    }
  };

  // The peaks computed while uploading move over to the stored call.
  const pendingRef = useRef<Pending[]>([]);
  pendingRef.current = pending;
  const pendingPeaks = (key: string) => pendingRef.current.find((p) => p.key === key)?.peaks ?? [];

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    addFiles(e.dataTransfer.files);
  };

  const confirm = async (callId: string, changes: ConfirmCallRequest) => {
    setBusy(true);
    try {
      const ex = await unwrap(api.POST("/api/calls/{call_id}/confirm", { params: { path: { call_id: callId } }, body: changes }));
      setExtractions((cur) => ({ ...cur, [callId]: ex }));
      toast.success("Load confirmed and added to Loads");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const current = selected ? extractions[selected] : undefined;
  const selectedPending = pending.find((p) => p.key === selected);
  const status = selectedPending ? (selectedPending.stage === "failed" ? "Failed" : "Processing…") : current ? (current.status === "confirmed" ? "Confirmed" : "Ready for review") : "";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="panel p-5">
        <div
          role="button"
          tabIndex={0}
          onClick={() => input.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          className={`grid cursor-pointer place-items-center gap-3 rounded-lg border border-dashed py-10 text-xs text-muted-foreground transition-colors ${drag ? "border-primary bg-accent" : "border-border"}`}
        >
          <UploadCloud size={22} className="text-primary" />
          Drop audio files · .mp3 .m4a .wav .ogg
          <input ref={input} type="file" multiple hidden accept={ACCEPT} onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }} />
        </div>

        <div className="mt-5 grid gap-3">
          {pending.map((p) => (
            <button key={p.key} className={`grid gap-2 rounded-lg border p-3 text-left ${selected === p.key ? "border-primary" : "border-border"}`} onClick={() => setSelected(p.key)}>
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-md bg-accent text-primary"><Mic size={16} /></span>
                <div className="flex-1 text-xs font-medium">{p.name}</div>
                <span className={`text-[11px] font-medium ${p.stage === "failed" ? "text-danger" : "text-primary"}`}>
                  {p.stage === "uploading" ? `Uploading ${Math.round(p.progress * 100)}%` : p.stage === "processing" ? "Processing…" : "Failed"}
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-muted"><div className={`h-full ${p.stage === "failed" ? "bg-danger" : "bg-primary"} ${p.stage === "processing" ? "animate-pulse" : ""}`} style={{ width: `${p.stage === "uploading" ? p.progress * 100 : 100}%` }} /></div>
              {p.error && <div className="text-[11px] text-danger">{p.error}</div>}
              {p.peaks && <Waveform peaks={p.peaks} />}
            </button>
          ))}
          {calls.map((c) => (
            <button key={c.id} className={`grid gap-2 rounded-lg border p-3 text-left ${selected === c.id ? "border-primary" : "border-border"}`} onClick={() => setSelected(c.id)}>
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-md bg-accent text-primary"><Mic size={16} /></span>
                <div className="flex-1">
                  <div className="text-xs font-medium">{c.filename}</div>
                  <div className="subtle small">{[duration(c.duration_seconds), c.language, formatDateTime(c.uploaded_at)].filter(Boolean).join(" · ")}</div>
                </div>
                <span className="text-[11px] font-medium text-success">{c.transcription_status === "completed" ? "✓ Transcribed" : cap(c.transcription_status)}</span>
              </div>
              {peaks[c.id] && peaks[c.id]!.length > 0 && <Waveform peaks={peaks[c.id]!} />}
            </button>
          ))}
          {pending.length === 0 && calls.length === 0 && <p className="subtle text-xs">No recordings yet. Drop one above.</p>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="panel-title"><Sparkles />Extracted update</div>
          {status && <span className={`badge ${status === "Confirmed" ? "badge-low" : status === "Failed" ? "badge-high" : "badge-medium"}`}>{status}</span>}
        </div>
        {selectedPending ? (
          <p className="subtle p-5 text-xs">{selectedPending.stage === "failed" ? selectedPending.error : "Transcribing the call and extracting the shipment details. This takes a moment."}</p>
        ) : current && selected ? (
          <ExtractedUpdate key={selected} extraction={current} busy={busy} onConfirm={(changes) => confirm(selected, changes)} />
        ) : (
          <div className="grid place-items-center gap-2 p-10 text-xs text-muted-foreground"><AudioLines size={22} />Select a recording to see what was extracted.</div>
        )}
      </section>
    </div>
  );
}
