"use client";

import { PhaseBadge } from "./phase-badge";
import type { RunState } from "@/lib/types";

interface Props {
  runs: RunState[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function Sidebar({ runs, selectedId, onSelect }: Props) {
  return (
    <aside style={{ width: 260, flexShrink: 0, background: "#161b22", borderRight: "1px solid #30363d", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* header */}
      <div style={{ padding: "10px 16px", borderBottom: "1px solid #30363d" }}>
        <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "#8b949e" }}>Sessions</p>
      </div>

      {/* list */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {runs.length === 0 && (
          <p style={{ padding: "20px 16px", fontSize: 12, color: "#484f58" }}>No runs yet. Start one →</p>
        )}
        {runs.map(run => {
          const active = run.run_id === selectedId;
          return (
            <button
              key={run.run_id}
              onClick={() => onSelect(run.run_id)}
              style={{
                display: "flex", flexDirection: "column", gap: 3,
                width: "100%", textAlign: "left", padding: "10px 16px",
                cursor: "pointer", border: "none", outline: "none",
                borderLeft: active ? "2px solid #3fb950" : "2px solid transparent",
                background: active ? "#1c2128" : "transparent",
                transition: "background 0.1s",
              }}
              onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "#1c2128"; }}
              onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <p style={{
                fontSize: 13, fontWeight: 500, lineHeight: 1.3,
                color: active ? "#f0f6fc" : "#c9d1d9",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {run.objective}
              </p>

              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                <PhaseBadge phase={run.current_phase} />
                {run.repair_attempts > 0 && (
                  <span style={{ fontSize: 10, color: "#d29922" }}>↺ {run.repair_attempts}</span>
                )}
              </div>

              <div style={{ display: "flex", gap: 10, marginTop: 2 }}>
                <span style={{ fontSize: 11, color: "#6e7681" }}>{run.tool_history.length} tools</span>
                {run.modified_files.length > 0 && (
                  <span style={{ fontSize: 11, color: "#6e7681" }}>{run.modified_files.length} files</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
