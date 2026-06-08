"use client";

import { useState } from "react";
import type { RunState, ToolCall, ExecutionStep } from "@/lib/types";

const TEXT = "#e6edf3";
const TEXT_DIM = "#8b949e";
const TEXT_FAINT = "#6e7681";
const BORDER = "1px solid #30363d";
const BG_CARD = "#1c2128";

const PHASE_ORDER = [
  "discovery","knowledge","architecture","planning",
  "implementation","validation","reflection","documentation","pr_generation",
];

const NS_COLOR: Record<string, string> = {
  fs: "#79c0ff", git: "#ffa657", terminal: "#d2a8ff",
  analysis: "#56d3c8", research: "#48c78e", subagent: "#ff79c6",
};

function shortArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (!entries.length) return "{}";
  const [k, v] = entries[0];
  const val = typeof v === "string" ? (v.length > 45 ? v.slice(0, 45) + "…" : v) : JSON.stringify(v);
  return entries.length === 1 ? `${k}=${val}` : `${k}=${val} +${entries.length - 1}`;
}

function ToolRow({ tool }: { tool: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const [ns, ...rest] = tool.tool_name.split(".");
  const name = rest.join(".");

  return (
    <div onClick={() => setExpanded(e => !e)} style={{
      border: BORDER, borderRadius: 6, background: "#161b22",
      cursor: "pointer", overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px" }}>
        <span style={{ fontSize: 11, color: tool.success ? "#3fb950" : "#f85149", flexShrink: 0 }}>
          {tool.success ? "✓" : "✗"}
        </span>
        <span style={{ fontSize: 12, fontFamily: "monospace", color: NS_COLOR[ns] ?? TEXT_DIM, flexShrink: 0 }}>{ns}.</span>
        <span style={{ fontSize: 12, fontFamily: "monospace", color: TEXT }}>{name}</span>
        <span style={{ fontSize: 11, fontFamily: "monospace", color: TEXT_FAINT, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {shortArgs(tool.args)}
        </span>
        {tool.duration_ms != null && (
          <span style={{ fontSize: 10, color: TEXT_FAINT, flexShrink: 0 }}>{Math.round(tool.duration_ms)}ms</span>
        )}
        <span style={{ fontSize: 10, color: TEXT_FAINT, flexShrink: 0 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div style={{ borderTop: BORDER, padding: "8px 10px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, color: TEXT_FAINT, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Args</p>
          <pre style={{ fontSize: 11, color: TEXT_DIM, fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
            {JSON.stringify(tool.args, null, 2)}
          </pre>
          {!tool.success && (
            <>
              <p style={{ fontSize: 10, fontWeight: 600, color: "#f85149", margin: "8px 0 4px", textTransform: "uppercase" }}>Error</p>
              <pre style={{ fontSize: 11, color: "#f85149", fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {JSON.stringify((tool.result as Record<string,unknown>)?.error ?? tool.result, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function PhaseSection({ phase, tools, observations }: { phase: string; tools: ToolCall[]; observations: string[] }) {
  const [collapsed, setCollapsed] = useState(false);
  const phaseObs = observations.filter(o => o.toLowerCase().startsWith(phase.replace("_", " ") + ":") || o.toLowerCase().startsWith(phase + ":"));
  if (!tools.length && !phaseObs.length) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <button onClick={() => setCollapsed(c => !c)} style={{
        display: "flex", alignItems: "center", gap: 10, background: "none",
        border: "none", cursor: "pointer", padding: 0,
      }}>
        <div style={{ flex: 1, height: 1, background: "#21262d" }} />
        <span style={{
          border: "1px solid #30363d", background: "#161b22", color: TEXT_DIM,
          borderRadius: 20, padding: "2px 10px", fontSize: 10, fontWeight: 600,
          textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap",
        }}>
          {phase.replace("_", " ")} · {tools.length} tool{tools.length !== 1 ? "s" : ""}
        </span>
        <div style={{ flex: 1, height: 1, background: "#21262d" }} />
        <span style={{ fontSize: 10, color: TEXT_FAINT }}>{collapsed ? "▼" : "▲"}</span>
      </button>

      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 4 }}>
          {phaseObs.map((obs, i) => (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", paddingTop: 2 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#238636", flexShrink: 0, marginTop: 5 }} />
              <p style={{ fontSize: 12, color: TEXT_DIM, lineHeight: 1.5 }}>{obs}</p>
            </div>
          ))}
          {tools.map((t, i) => <ToolRow key={i} tool={t} />)}
        </div>
      )}
    </div>
  );
}

export function ActivityFeed({ run }: { run: RunState }) {
  const phaseTools: Record<string, ToolCall[]> = {};
  PHASE_ORDER.forEach(p => { phaseTools[p] = []; });

  const phaseForTool = (t: ToolCall): string => {
    const n = t.tool_name;
    if (n.startsWith("subagent"))           return "planning";
    if (n === "fs.list_directory" || n === "analysis.detect_framework") return "discovery";
    if (n.startsWith("analysis.build"))     return "knowledge";
    if (n.startsWith("analysis.find"))      return "architecture";
    if (n.startsWith("terminal.run_pytest") || n.startsWith("terminal.run_mypy") || n.startsWith("terminal.run_ruff")) return "validation";
    if (n.startsWith("fs.write") || n.startsWith("fs.read") || n.startsWith("fs.append") || n.startsWith("git")) return "implementation";
    if (n.startsWith("research"))           return "documentation";
    return "planning";
  };

  run.tool_history.forEach(t => {
    const p = phaseForTool(t);
    phaseTools[p].push(t);
  });

  const activeIdx = PHASE_ORDER.indexOf(run.current_phase as string);
  const phasesToShow = PHASE_ORDER.filter((p, i) => i <= Math.max(activeIdx, 0) || (phaseTools[p]?.length ?? 0) > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "16px 20px" }}>
      {/* run start card */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{
          width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
          background: "rgba(35,134,54,0.15)", border: "1px solid rgba(63,185,80,0.3)",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#3fb950", fontSize: 12,
        }}>▶</div>
        <div style={{ flex: 1, background: BG_CARD, border: BORDER, borderRadius: 8, padding: "10px 14px" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: TEXT }}>{run.objective}</p>
          <p style={{ fontSize: 11, color: TEXT_FAINT, marginTop: 3 }}>{run.repo_path}</p>
        </div>
      </div>

      {/* phase sections */}
      {phasesToShow.map(phase => (
        <PhaseSection key={phase} phase={phase} tools={phaseTools[phase] ?? []} observations={run.observations} />
      ))}

      {/* plan steps */}
      {(run.execution_plan?.steps?.length ?? 0) > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1, height: 1, background: "#21262d" }} />
            <span style={{ border: BORDER, background: "#161b22", color: TEXT_DIM, borderRadius: 20, padding: "2px 10px", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Plan · {run.execution_plan!.steps.length} steps
            </span>
            <div style={{ flex: 1, height: 1, background: "#21262d" }} />
          </div>
          {run.execution_plan!.steps.map((step, i) => (
            <div key={step.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "3px 4px" }}>
              <span style={{ fontSize: 12, color: step.status === "done" ? "#3fb950" : step.status === "failed" ? "#f85149" : TEXT_FAINT, flexShrink: 0, marginTop: 1 }}>
                {step.status === "done" ? "✓" : step.status === "failed" ? "✗" : `${i + 1}.`}
              </span>
              <div>
                <p style={{ fontSize: 12, color: step.status === "done" ? TEXT_FAINT : step.status === "failed" ? "#f85149" : TEXT, lineHeight: 1.4 }}>
                  {step.description}
                </p>
                {step.files_to_modify.length > 0 && (
                  <p style={{ fontSize: 11, color: TEXT_FAINT }}>{step.files_to_modify.join(", ")}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* validation */}
      {run.validation_results && (
        <div style={{
          borderRadius: 8, padding: "10px 14px",
          background: run.validation_results.passed ? "rgba(63,185,80,0.05)" : "rgba(248,81,73,0.05)",
          border: run.validation_results.passed ? "1px solid rgba(63,185,80,0.2)" : "1px solid rgba(248,81,73,0.2)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: run.validation_results.passed ? "#3fb950" : "#f85149" }}>
              {run.validation_results.passed ? "✓" : "✗"}
            </span>
            <p style={{ fontSize: 13, fontWeight: 500, color: run.validation_results.passed ? "#3fb950" : "#f85149" }}>
              Validation {run.validation_results.passed ? "passed" : "failed"}
            </p>
          </div>
          {run.validation_results.errors.map((e, i) => (
            <p key={i} style={{ fontSize: 12, color: "#f85149", marginTop: 4, paddingLeft: 20 }}>{e}</p>
          ))}
        </div>
      )}

      {/* reflection */}
      {run.reflection_report && (
        <div style={{ borderRadius: 8, padding: "10px 14px", background: "rgba(210,153,34,0.05)", border: "1px solid rgba(210,153,34,0.2)" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: "#e3b341" }}>↺ Reflection — repair attempt {run.repair_attempts}</p>
          <p style={{ fontSize: 12, color: TEXT_DIM, marginTop: 4 }}>{run.reflection_report.root_cause}</p>
          <p style={{ fontSize: 11, color: "#d29922", marginTop: 3 }}>{run.reflection_report.retry_strategy}</p>
        </div>
      )}

      {/* done */}
      {run.current_phase === "pr_generation" && run.generated_pr && (
        <div style={{ borderRadius: 8, padding: "10px 14px", background: "rgba(63,185,80,0.05)", border: "1px solid rgba(63,185,80,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#3fb950", fontSize: 16 }}>✦</span>
          <p style={{ fontSize: 13, color: "#3fb950", fontWeight: 500 }}>Done! {run.generated_pr.title}</p>
        </div>
      )}

      {/* error */}
      {run.current_phase === "error" && run.error && (
        <div style={{ borderRadius: 8, padding: "10px 14px", background: "rgba(248,81,73,0.05)", border: "1px solid rgba(248,81,73,0.2)" }}>
          <p style={{ fontSize: 13, color: "#f85149", fontWeight: 500 }}>Run failed</p>
          <pre style={{ fontSize: 11, color: "rgba(248,81,73,0.7)", marginTop: 4, whiteSpace: "pre-wrap", wordBreak: "break-all", fontFamily: "monospace" }}>{run.error}</pre>
        </div>
      )}
    </div>
  );
}
