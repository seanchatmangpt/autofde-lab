"use client";

import { useState } from "react";
import { TriageResponseSchema } from "../lib/contracts/wd-fa.js";

const CASES = ["known_a", "known_b_misleading", "incomplete_a", "novel_x"];

export default function FailureWorkbench() {
  const [caseName, setCaseName] = useState("known_a");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function runTriage() {
    setError("");
    const base = process.env.NEXT_PUBLIC_WD_FA_API_BASE_URL || "http://localhost:8000";
    try {
      const response = await fetch(base + "/triage", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ case_name: caseName }),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      setResult(TriageResponseSchema.parse(await response.json()));
    } catch (cause) {
      setResult(null);
      setError(String(cause));
    }
  }

  return (
    <section className="workbench">
      <div className="controls">
        <label htmlFor="case">Synthetic failure subject</label>
        <select id="case" value={caseName} onChange={(event) => setCaseName(event.target.value)}>
          {CASES.map((name) => <option key={name}>{name}</option>)}
        </select>
        <button type="button" onClick={runTriage}>Run bounded triage</button>
      </div>
      <div className="result" aria-live="polite">
        {error && <p className="error">{error}</p>}
        {!error && !result && <p>No candidate result yet.</p>}
        {result && (
          <dl>
            <div><dt>Case</dt><dd>{result.case_id}</dd></div>
            <div><dt>Standing</dt><dd>{result.standing}</dd></div>
            <div><dt>Admitted mode</dt><dd>{result.admitted_mode || "—"}</dd></div>
            <div><dt>Next action</dt><dd>{result.next_action}</dd></div>
            <div><dt>Authority</dt><dd>{result.authority}</dd></div>
          </dl>
        )}
      </div>
    </section>
  );
}
