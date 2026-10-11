import { useEffect, useState } from "react";

type Extraction = {
  call_id: string;
  status: string;
  summary: string;
  transcript: string;
  origin: string | null;
  destination: string | null;
  pickup_date: string | null;
  cargo: string | null;
  weight_kg: number | null;
  price_eur: number | null;
  missing_fields: string[];
  evidence: Record<string, string>;
  load_id: string | null;
};

export function CallExtractionPanel() {
  const [file, setFile] = useState<File>();
  const [extraction, setExtraction] = useState<Extraction>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>();
  const [fields, setFields] = useState({ origin: "", destination: "", pickup_date: "", cargo: "" });

  useEffect(() => {
    setMessage(undefined);
  }, [file]);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    setMessage(undefined);
    try {
      const body = new FormData();
      body.append("audio", file);
      const response = await fetch("/api/calls/upload", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Call processing failed");
      setExtraction(data);
      setFields({
        origin: data.origin ?? "",
        destination: data.destination ?? "",
        pickup_date: data.pickup_date ?? "",
        cargo: data.cargo ?? "",
      });
      setMessage("Extraction is ready for review.");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!extraction) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/calls/${extraction.call_id}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...fields, pickup_date: fields.pickup_date || null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Confirmation failed");
      setExtraction((current) => current && { ...current, status: "confirmed", load_id: data.load_id });
      setMessage("Load confirmed and added to the Loads section.");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>Call recording</h2>
      <p className="muted">Upload an MP3 recording to transcribe and extract load details for review.</p>
      <input type="file" accept=".mp3,.wav,.m4a,.ogg,audio/*" onChange={(event) => setFile(event.target.files?.[0])} />
      <button className="primary" disabled={!file || busy} onClick={upload}>{busy ? "Processing…" : "Process recording"}</button>
      {message && <p className={message.includes("failed") ? "error" : "muted"}>{message}</p>}
      {extraction && (
        <div className="call-review">
          <p><strong>{extraction.summary}</strong></p>
          <label>Origin <input value={fields.origin} onChange={(event) => setFields({ ...fields, origin: event.target.value })} /></label>
          <label>Destination <input value={fields.destination} onChange={(event) => setFields({ ...fields, destination: event.target.value })} /></label>
          <label>Pickup date <input type="date" value={fields.pickup_date} onChange={(event) => setFields({ ...fields, pickup_date: event.target.value })} /></label>
          <label>Cargo <input value={fields.cargo} onChange={(event) => setFields({ ...fields, cargo: event.target.value })} /></label>
          <p>Weight: {extraction.weight_kg ? `${extraction.weight_kg} kg` : "—"} · Price: {extraction.price_eur ? `€${extraction.price_eur}` : "—"}</p>
          {extraction.missing_fields.length > 0 && <p className="muted">Missing: {extraction.missing_fields.join(", ")}</p>}
          <details><summary>Transcript</summary><p>{extraction.transcript}</p></details>
          {extraction.status === "pending_review" && <button className="primary" disabled={busy} onClick={confirm}>Confirm and add load</button>}
        </div>
      )}
    </section>
  );
}
