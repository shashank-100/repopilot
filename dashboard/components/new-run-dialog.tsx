"use client";

import { useState } from "react";
import { createRun } from "@/lib/api";

interface Props { onCreated: (id: string) => void }

export function NewRunDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [objective, setObjective] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!objective.trim() || !repoPath.trim()) return;
    setLoading(true); setError("");
    try {
      const { run_id } = await createRun(objective.trim(), repoPath.trim());
      setOpen(false); setObjective(""); setRepoPath("");
      onCreated(run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally { setLoading(false); }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "#0d1117", border: "1px solid #30363d",
    borderRadius: 6, color: "#e6edf3", fontFamily: "inherit",
    fontSize: 13, padding: "7px 12px", outline: "none",
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{
        display: "flex", alignItems: "center", gap: 6,
        background: "#238636", border: "1px solid #2ea043",
        color: "#fff", borderRadius: 6, padding: "5px 14px",
        fontSize: 12, fontWeight: 500, cursor: "pointer",
        fontFamily: "inherit",
      }}>
        + New Run
      </button>
    );
  }

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 50,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(1,4,9,0.75)",
    }}>
      <form onSubmit={submit} style={{
        width: 480, background: "#161b22", border: "1px solid #30363d",
        borderRadius: 12, padding: 24, boxShadow: "0 16px 64px rgba(0,0,0,0.5)",
      }}>
        <h2 style={{ color: "#f0f6fc", fontSize: 16, fontWeight: 600, marginBottom: 20 }}>New Run</h2>

        <label style={{ display: "block", marginBottom: 14 }}>
          <span style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#8b949e", marginBottom: 6 }}>Objective</span>
          <input autoFocus value={objective} onChange={e => setObjective(e.target.value)}
            placeholder="e.g. add rate limiting middleware"
            style={inputStyle} />
        </label>

        <label style={{ display: "block", marginBottom: 20 }}>
          <span style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#8b949e", marginBottom: 6 }}>Repository Path</span>
          <input value={repoPath} onChange={e => setRepoPath(e.target.value)}
            placeholder="/absolute/path/to/repo"
            style={inputStyle} />
        </label>

        {error && <p style={{ color: "#f85149", fontSize: 12, marginBottom: 12 }}>{error}</p>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" onClick={() => setOpen(false)} style={{
            background: "transparent", border: "1px solid #30363d", color: "#8b949e",
            borderRadius: 6, padding: "6px 16px", fontSize: 12, cursor: "pointer", fontFamily: "inherit",
          }}>
            Cancel
          </button>
          <button type="submit" disabled={loading || !objective.trim() || !repoPath.trim()} style={{
            background: "#238636", border: "1px solid #2ea043", color: "#fff",
            borderRadius: 6, padding: "6px 16px", fontSize: 12, fontWeight: 500,
            cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
            fontFamily: "inherit",
          }}>
            {loading ? "Launching…" : "Launch →"}
          </button>
        </div>
      </form>
    </div>
  );
}
