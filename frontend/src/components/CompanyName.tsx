import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { CompanyInput } from "../api/types";

const empty: CompanyInput = { name: "", name_latin: "", operator_name: "", operator_name_latin: "" };

// Our own company, shown in the top-right corner. Used in every draft's signature and in the AI's instructions.
export function CompanyName() {
  const [company, setCompany] = useState<CompanyInput>(empty);
  const [draft, setDraft] = useState<CompanyInput | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    unwrap(api.GET("/api/company")).then(setCompany).catch(() => undefined);
  }, []);

  const save = async () => {
    if (!draft) return;
    setError(null);
    try {
      setCompany(await unwrap(api.PUT("/api/company", { body: draft })));
      setDraft(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (draft === null) {
    return (
      <div className="company-corner">
        <span className="muted">Company:</span> <strong>{company.name || "—"}</strong>{" "}
        <button onClick={() => setDraft(company)}>Edit</button>
      </div>
    );
  }

  const field = (key: keyof CompanyInput, label: string) => (
    <label>
      {label}
      <input value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
    </label>
  );

  return (
    <div className="company-corner editing">
      {field("name", "Company name")}
      {field("name_latin", "Latin name")}
      {field("operator_name", "Your name")}
      {field("operator_name_latin", "Your name (Latin)")}
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <button className="primary" onClick={save}>Save</button>
        <button onClick={() => setDraft(null)}>Cancel</button>
      </div>
    </div>
  );
}
