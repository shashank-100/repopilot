"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listRuns, getRun, createRun } from "@/lib/api";
import type { RunState, ToolCall } from "@/lib/types";

// ─── design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:         "#ffffff",
  bgSidebar:  "#f9f9fa",
  bgHover:    "#f2f2f4",
  bgActive:   "#ebebed",
  border:     "#e8e8eb",
  borderMid:  "#d4d4d8",
  text:       "#0f0f10",
  textMid:    "#52525b",
  textDim:    "#a1a1aa",
  blue:       "#2563eb",
  blueSoft:   "#eff6ff",
  green:      "#16a34a",
  greenBg:    "#f0fdf4",
  red:        "#dc2626",
  redBg:      "#fff1f2",
  orange:     "#ea580c",
  orangeBg:   "#fff7ed",
  purple:     "#7c3aed",
  purpleBg:   "#f5f3ff",
  yellow:     "#ca8a04",
  chip:       "#f1f1f3",
  chipText:   "#52525b",
  prOpen:     "#16a34a",
  prOpenBg:   "#dcfce7",
  shadow:     "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
  shadowMd:   "0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.04)",
  shadowLg:   "0 8px 24px rgba(0,0,0,0.09), 0 2px 8px rgba(0,0,0,0.05)",
};

// ─── demo data ────────────────────────────────────────────────────────────────
const DEMO_SESSIONS = [
  {
    id: "demo-1",
    title: "Migrate all gradient text to #317CFF",
    time: "1 hour ago",
    prs: 2,
    status: "open" as const,
  },
];

const DEMO_MESSAGES = [
  {
    id: "m1",
    type: "user" as const,
    text: "Migrate all gradient text to #317CFF in both repos, then test",
    avatar: "S",
  },
  {
    id: "m2",
    type: "agent" as const,
    steps: [
      { id: "s1", label: "Used playbook: Test", collapsed: true },
    ],
    text: "I'll migrate all gradient text to #317CFF in both cognition-website and devin-website repos, then test the changes. Starting now.",
  },
  {
    id: "m3",
    type: "worked" as const,
    duration: "4m 13s",
    adds: 25,
    removes: 131,
  },
  {
    id: "m4",
    type: "pr" as const,
    repo: "cognition/cognition-website",
    prNum: 167,
    status: "open" as const,
    hash: "devin/USA-938-1765942251",
    base: "main",
    files: 6,
    adds: 25,
    removes: 123,
  },
  {
    id: "m5",
    type: "pr" as const,
    repo: "cognition/devin-website",
    prNum: 357,
    status: "open" as const,
    hash: "devin/USA-938-1765942251",
    base: "main",
    files: 2,
    adds: 6,
    removes: 8,
  },
  {
    id: "m6",
    type: "worked" as const,
    duration: "5m 33s",
    adds: null,
    removes: null,
  },
  {
    id: "m7",
    type: "agent" as const,
    steps: [],
    text: "Done! All gradient text migrated to #317CFF and tested across both repos. Full report attached.",
    attachment: "test_gradient_migration.md",
  },
  {
    id: "m8",
    type: "status" as const,
    text: "Devin is ready for instructions",
  },
];

const DEMO_REPORT = {
  filename: "test_gradient_migration.md",
  title: "Test Report: Migrate Gradient Text",
  prs: [
    { repo: "devin-website", num: 167 },
    { repo: "cognition-website", num: 167 },
  ],
  summary: "All gradient text background: linear-gradient(...) replaced with solid color: #317CFF across both repos. Tested by comparing production sites (gradient) vs localhost dev servers (solid blue).",
  sections: [
    {
      title: "Homepage",
      items: [
        { label: "Before on Production", content: "Secure,\nPrivate", sub: "Gradient on text", gradient: true },
        { label: "After on Localhost", content: "Secure,\nPrivate", sub: "Uniform solid blue", gradient: false },
      ],
    },
    {
      title: "Footer",
      items: [
        { label: "Before on Production", content: "Secure,\nPrivate", sub: "Gradient on text", gradient: true },
        { label: "After on Localhost", content: "Secure,\nPrivate", sub: "Uniform solid blue", gradient: false },
      ],
    },
  ],
};

// ─── tiny helpers ─────────────────────────────────────────────────────────────

function Avatar({ text, bg }: { text: string; bg: string }) {
  return (
    <div style={{
      width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
      background: bg, display: "flex", alignItems: "center",
      justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700,
    }}>{text}</div>
  );
}

function PrStatusBadge({ status }: { status: "open" | "merged" }) {
  const isOpen = status === "open";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: isOpen ? C.prOpenBg : C.purpleBg,
      color: isOpen ? C.prOpen : C.purple,
      borderRadius: 20, padding: "2px 9px", fontSize: 11, fontWeight: 600,
      border: `1px solid ${isOpen ? "rgba(22,163,74,0.25)" : "rgba(124,58,237,0.2)"}`,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
      {isOpen ? "Open" : "Merged"}
    </span>
  );
}

// ─── sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({ selectedSession, onSelect, onNew, liveRuns = [] }: {
  selectedSession: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  liveRuns?: RunState[];
}) {
  const navItems = ["Sessions", "Ask", "Wiki", "Review"];
  const [activeNav, setActiveNav] = useState("Sessions");

  return (
    <aside style={{
      width: 232, flexShrink: 0,
      borderRight: `1px solid ${C.border}`,
      background: C.bgSidebar,
      display: "flex", flexDirection: "column",
      height: "100%", overflow: "hidden",
    }}>
      {/* header */}
      <div style={{
        padding: "11px 14px 10px", borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 24, height: 24, borderRadius: 7,
            background: "linear-gradient(135deg,#1e1e2e,#383860)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
          }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="#fff" strokeWidth="1.4"/>
              <circle cx="6" cy="6" r="1.8" fill="#fff"/>
            </svg>
          </div>
          <span style={{ fontSize: 13, fontWeight: 650, color: C.text, letterSpacing: "-0.01em" }}>RepoPilot</span>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ marginTop: 1 }}>
            <path d="M2.5 4l2.5 2.5L7.5 4" stroke={C.textDim} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <button onClick={onNew} style={{
          border: `1px solid ${C.borderMid}`, background: C.bg,
          borderRadius: 7, padding: "3px 9px", fontSize: 11,
          cursor: "pointer", color: C.textMid, fontFamily: "inherit",
          boxShadow: C.shadow, fontWeight: 500,
          transition: "background 0.12s",
        }}
        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = C.bgHover}
        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = C.bg}
        >+ New</button>
      </div>

      {/* nav */}
      <div style={{ padding: "5px 7px 4px", borderBottom: `1px solid ${C.border}` }}>
        {navItems.map(item => (
          <button key={item} onClick={() => setActiveNav(item)} style={{
            width: "100%", textAlign: "left", padding: "5px 9px",
            border: "none", borderRadius: 7,
            background: activeNav === item ? C.bg : "transparent",
            boxShadow: activeNav === item ? C.shadow : "none",
            cursor: "pointer", fontFamily: "inherit",
            fontSize: 13, fontWeight: activeNav === item ? 500 : 400,
            color: activeNav === item ? C.text : C.textMid,
            transition: "all 0.1s",
          }}>
            {item}
          </button>
        ))}
      </div>

      {/* recent */}
      <div style={{ padding: "8px 7px 6px", flex: 1, overflowY: "auto" }}>
        <p style={{ fontSize: 10.5, color: C.textDim, fontWeight: 600, padding: "0 7px 5px", textTransform: "uppercase", letterSpacing: "0.07em" }}>Recent</p>

        {/* live runs from backend */}
        {liveRuns.slice().reverse().map(run => {
          const active = selectedSession === run.run_id;
          const isDone = run.current_phase === "pr_generation";
          const isError = run.current_phase === "error";
          return (
            <button key={run.run_id} onClick={() => onSelect(run.run_id)} style={{
              width: "100%", textAlign: "left", padding: "7px 9px",
              border: "none", borderRadius: 7,
              background: active ? C.bg : "transparent",
              boxShadow: active ? C.shadow : "none",
              cursor: "pointer", fontFamily: "inherit",
              transition: "all 0.12s", marginBottom: 1,
            }}
            onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = C.bgHover; }}
            onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <p style={{ fontSize: 12, fontWeight: active ? 500 : 400, color: active ? C.text : C.textMid, lineHeight: 1.35, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {run.objective}
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 10, borderRadius: 10, padding: "0 6px", fontWeight: 500,
                  background: isError ? C.redBg : isDone ? C.prOpenBg : C.blueSoft,
                  color: isError ? C.red : isDone ? C.prOpen : C.blue,
                }}>
                  {isError ? "error" : isDone ? "done" : run.current_phase.replace(/_/g," ")}
                </span>
                <span style={{ fontSize: 10, background: "#fef3c7", color: "#92400e", borderRadius: 10, padding: "0 5px", fontWeight: 500 }}>live</span>
              </div>
            </button>
          );
        })}

        {DEMO_SESSIONS.map(s => {
          const active = selectedSession === s.id;
          return (
            <button key={s.id} onClick={() => onSelect(s.id)} style={{
              width: "100%", textAlign: "left", padding: "7px 9px",
              border: "none", borderRadius: 7,
              background: active ? C.bg : "transparent",
              boxShadow: active ? C.shadow : "none",
              cursor: "pointer", fontFamily: "inherit",
              transition: "all 0.12s",
              marginBottom: 1,
            }}
            onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = C.bgHover; }}
            onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <p style={{ fontSize: 12, fontWeight: active ? 500 : 400, color: active ? C.text : C.textMid, lineHeight: 1.35, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {s.title}
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 10.5, color: C.textDim }}>{s.time}</span>
                <span style={{
                  fontSize: 10, borderRadius: 10, padding: "0 6px", fontWeight: 500,
                  background: (s.status as string) === "open" ? C.prOpenBg : C.chip,
                  color: (s.status as string) === "open" ? C.prOpen : C.textMid,
                }}>
                  {s.prs} {(s.status as string) === "merged" ? "merged" : "open"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* settings */}
      <div style={{ borderTop: `1px solid ${C.border}`, padding: "9px 14px" }}>
        <button style={{ display: "flex", alignItems: "center", gap: 7, border: "none", background: "none", cursor: "pointer", fontSize: 12, color: C.textMid, fontFamily: "inherit" }}
        onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = C.text}
        onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = C.textMid}
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
            <circle cx="8" cy="8" r="2.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
          </svg>
          Settings
        </button>
      </div>
    </aside>
  );
}

// ─── live run thread ──────────────────────────────────────────────────────────

const NS_COLOR: Record<string, string> = {
  fs: C.blue, git: "#ea580c", terminal: "#7c3aed",
  analysis: "#0891b2", research: "#16a34a", subagent: "#7c3aed",
};

function LiveThread({ run }: { run: RunState }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [run.observations.length, run.tool_history.length]);

  const isRunning = !["pr_generation", "error"].includes(run.current_phase);
  const done = run.current_phase === "pr_generation";

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 24px 12px" }}>
      {/* user message */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20, gap: 9, alignItems: "flex-end" }}>
        <div style={{ maxWidth: "68%", background: C.bgSidebar, border: `1px solid ${C.border}`, borderRadius: "16px 16px 4px 16px", padding: "10px 15px", fontSize: 13, color: C.text, lineHeight: 1.55, boxShadow: C.shadow }}>
          {run.objective}
          <p style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>{run.repo_path}</p>
        </div>
        <div style={{ width: 29, height: 29, borderRadius: "50%", background: "linear-gradient(135deg,#4f46e5,#7c3aed)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700, flexShrink: 0, boxShadow: "0 2px 6px rgba(79,70,229,0.35)" }}>U</div>
      </div>

      {/* agent response */}
      <div style={{ display: "flex", gap: 11, marginBottom: 16, alignItems: "flex-start" }}>
        <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: "linear-gradient(135deg,#18181b,#3f3f46)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700, boxShadow: "0 2px 5px rgba(0,0,0,0.18)" }}>R</div>
        <div style={{ flex: 1, paddingTop: 2 }}>
          {/* observations as collapsible steps */}
          {run.observations.slice(0, 6).map((obs, i) => (
            <CollapsibleStep key={i} label={obs} />
          ))}

          {/* tool calls */}
          {run.tool_history.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <CollapsibleStep label={`Used ${run.tool_history.length} tool${run.tool_history.length !== 1 ? "s" : ""} · ${run.current_phase.replace(/_/g, " ")}`} />
            </div>
          )}

          {/* plan */}
          {run.execution_plan?.steps && run.execution_plan.steps.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 13, color: C.text, lineHeight: 1.65, marginBottom: 6 }}>
                Execution plan: {run.execution_plan.goal}
              </p>
              {run.execution_plan.steps.map((s: any, i: number) => (
                <div key={s.id} style={{ display: "flex", gap: 8, padding: "2px 0", alignItems: "baseline" }}>
                  <span style={{ fontSize: 11, color: s.status === "done" ? C.green : s.status === "failed" ? C.red : C.textDim, width: 14, flexShrink: 0 }}>
                    {s.status === "done" ? "✓" : s.status === "failed" ? "✗" : `${i+1}.`}
                  </span>
                  <span style={{ fontSize: 12, color: s.status === "done" ? C.textDim : s.status === "failed" ? C.red : C.text }}>
                    {s.description}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* live indicator */}
          {isRunning && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
              <TypingDots />
              <span style={{ fontSize: 12, color: C.textDim }}>
                {run.current_phase.replace(/_/g, " ")}…
              </span>
            </div>
          )}

          {/* done */}
          {done && run.generated_pr && (
            <div>
              <p style={{ fontSize: 13, color: C.text, lineHeight: 1.65, marginBottom: 8 }}>
                Done! {run.generated_pr.title}
              </p>
              {run.generated_pr.url ? (
                <a href={run.generated_pr.url} target="_blank" rel="noopener noreferrer"
                  style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, color: "#fff", fontSize: 12, textDecoration: "none", background: "#2da44e", borderRadius: 7, padding: "6px 12px", fontWeight: 600 }}>
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="#fff"><path d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/></svg>
                  View Pull Request →
                </a>
              ) : (
                <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, color: C.blue, fontSize: 12, background: C.blueSoft, borderRadius: 7, padding: "5px 10px", border: `1px solid rgba(37,99,235,0.18)` }}>
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke={C.blue} strokeWidth="1.5"><path d="M4 2h6l4 4v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M10 2v4h4"/></svg>
                  <span style={{ fontWeight: 500 }}>PR summary generated</span>
                </div>
              )}
            </div>
          )}

          {/* error */}
          {run.current_phase === "error" && run.error && (
            <p style={{ fontSize: 12, color: C.red, marginTop: 4 }}>{run.error}</p>
          )}
        </div>
      </div>
      <div ref={bottomRef} />
    </div>
  );
}

// ─── chat thread ──────────────────────────────────────────────────────────────

function ChatThread({ runState }: { runState: RunState | null }) {
  const title = runState ? runState.objective : "Migrate gradient text";
  const runId = runState ? runState.run_id.slice(0, 7) : "357";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: C.bg }}>
      {/* breadcrumb */}
      <div style={{ padding: "0 20px", height: 41, display: "flex", alignItems: "center", borderBottom: `1px solid ${C.border}`, gap: 5, flexShrink: 0, background: C.bgSidebar }}>
        <span style={{ fontSize: 12, color: C.textDim }}>Website</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M3.5 2.5L6 5l-2.5 2.5" stroke={C.textDim} strokeWidth="1.3" strokeLinecap="round"/></svg>
        <span style={{ fontSize: 12, color: C.text, fontWeight: 500, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, fontFamily: "ui-monospace,monospace", background: C.chip, color: C.chipText, padding: "2px 8px", borderRadius: 6, border: `1px solid ${C.border}` }}>
            #{runId} ▾
          </span>
          <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, fontSize: 16, padding: "0 2px" }}>⋯</button>
        </div>
      </div>

      {/* messages — live run vs demo */}
      {runState ? (
        <LiveThread run={runState} />
      ) : (
        <div style={{ flex: 1, overflowY: "auto", padding: "24px 24px 12px", background: C.bg }}>
          {DEMO_MESSAGES.map(msg => {
            if (msg.type === "user") return (
              <div key={msg.id} style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20, gap: 9, alignItems: "flex-end" }}>
                <div style={{ maxWidth: "68%", background: C.bgSidebar, border: `1px solid ${C.border}`, borderRadius: "16px 16px 4px 16px", padding: "10px 15px", fontSize: 13, color: C.text, lineHeight: 1.55, boxShadow: C.shadow }}>{msg.text}</div>
                <div style={{ width: 29, height: 29, borderRadius: "50%", background: "linear-gradient(135deg,#4f46e5,#7c3aed)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700, flexShrink: 0, boxShadow: "0 2px 6px rgba(79,70,229,0.35)" }}>{msg.avatar}</div>
              </div>
            );
            if (msg.type === "agent") return (
              <div key={msg.id} style={{ display: "flex", gap: 11, marginBottom: 18, alignItems: "flex-start" }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: "linear-gradient(135deg,#18181b,#3f3f46)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700, boxShadow: "0 2px 5px rgba(0,0,0,0.18)" }}>R</div>
                <div style={{ flex: 1, paddingTop: 2 }}>
                  {msg.steps?.map(step => <CollapsibleStep key={step.id} label={step.label} />)}
                  <p style={{ fontSize: 13, color: C.text, lineHeight: 1.65 }}>{msg.text}</p>
                  {msg.attachment && (
                    <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, color: C.blue, fontSize: 12, cursor: "pointer", background: C.blueSoft, borderRadius: 7, padding: "5px 10px", border: `1px solid rgba(37,99,235,0.18)` }}>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke={C.blue} strokeWidth="1.5"><path d="M4 2h6l4 4v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M10 2v4h4"/></svg>
                      <span style={{ fontWeight: 500 }}>{msg.attachment}</span>
                    </div>
                  )}
                </div>
              </div>
            );
            if (msg.type === "worked") return (
              <div key={msg.id} style={{ marginLeft: 36, marginBottom: 10 }}>
                <CollapsibleStep label={`Worked for ${msg.duration}${msg.adds != null ? ` · +${msg.adds}` : ""}${msg.removes != null ? ` · -${msg.removes}` : ""}`} adds={msg.adds ?? undefined} removes={msg.removes ?? undefined} />
              </div>
            );
            if (msg.type === "pr") return (
              <div key={msg.id} style={{ marginLeft: 36, marginBottom: 10 }}>
                <PrCard {...msg as any} />
              </div>
            );
            if (msg.type === "status") return (
              <div key={msg.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, marginLeft: 36 }}>
                <svg width="14" height="14" viewBox="0 0 16 16" fill={C.textDim}><circle cx="8" cy="8" r="6" stroke={C.textDim} strokeWidth="1.5" fill="none"/><path d="M8 5v3l2 2" stroke={C.textDim} strokeWidth="1.5" strokeLinecap="round"/></svg>
                <span style={{ fontSize: 12, color: C.textDim }}>{msg.text}</span>
              </div>
            );
            return null;
          })}
        </div>
      )}

      {/* input */}
      <div style={{ padding: "10px 16px 12px", borderTop: `1px solid ${C.border}`, flexShrink: 0, background: C.bg }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, border: `1px solid ${C.borderMid}`, borderRadius: 12, padding: "9px 14px", background: C.bg, boxShadow: "0 0 0 3px rgba(0,0,0,0.03), " + C.shadow }}>
          <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, fontSize: 17, lineHeight: 1, padding: 0 }}>+</button>
          <input readOnly placeholder="Ask RepoPilot to build features, fix bugs, or work on your code" style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: C.textDim, background: "transparent", fontFamily: "inherit" }} />
          <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, padding: 0, display: "flex", alignItems: "center" }}>
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke={C.textDim} strokeWidth="1.4"><path d="M8 1a3 3 0 013 3v4a3 3 0 01-6 0V4a3 3 0 013-3z"/><path d="M1 9s0 6 7 6 7-6 7-6"/><line x1="8" y1="15" x2="8" y2="12"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function CollapsibleStep({ label, adds, removes }: { label: string; adds?: number; removes?: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 5 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: "inline-flex", alignItems: "center", gap: 6, border: "none",
        background: C.chip, borderRadius: 6, cursor: "pointer",
        padding: "3px 9px 3px 7px", fontFamily: "inherit",
        transition: "background 0.1s",
      }}
      onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = C.bgHover}
      onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = C.chip}
      >
        <svg width="9" height="9" viewBox="0 0 9 9" fill="none" style={{ transition: "transform 0.15s", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          <path d="M2.5 1.5L6 4.5L2.5 7.5" stroke={C.textDim} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontSize: 11.5, color: C.textMid, fontWeight: 450 }}>{label}</span>
        {adds != null && <span style={{ fontSize: 11, color: C.green, fontFamily: "ui-monospace,monospace", fontWeight: 600 }}>+{adds}</span>}
        {removes != null && <span style={{ fontSize: 11, color: C.red, fontFamily: "ui-monospace,monospace", fontWeight: 600 }}>-{removes}</span>}
      </button>
    </div>
  );
}

function PrCard({ repo, prNum, status, hash, base, files, adds, removes }: any) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        border: `1px solid ${hovered ? C.borderMid : C.border}`,
        borderRadius: 10, background: C.bg, overflow: "hidden", marginBottom: 7,
        boxShadow: hovered ? C.shadowMd : C.shadow,
        transition: "box-shadow 0.15s, border-color 0.15s",
        cursor: "pointer",
      }}>
      <div style={{ padding: "8px 13px", display: "flex", alignItems: "center", gap: 8, borderBottom: `1px solid ${C.border}`, background: C.bgSidebar }}>
        <PrStatusBadge status={status} />
        <span style={{ fontSize: 12.5, fontWeight: 560, color: C.text, flex: 1 }}>{repo}</span>
        <span style={{ fontSize: 12, color: C.blue, fontWeight: 500 }}>#{prNum}</span>
        <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, fontSize: 13, padding: "0 2px", lineHeight: 1 }}>↗</button>
        <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, fontSize: 13, padding: "0 2px", lineHeight: 1 }}>✕</button>
      </div>
      <div style={{ padding: "7px 13px 9px", display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
        <code style={{ fontSize: 11, fontFamily: "ui-monospace,monospace", color: C.textDim, background: C.chip, padding: "1px 5px", borderRadius: 4 }}>{hash}</code>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6h8M7 3l3 3-3 3" stroke={C.textDim} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
        <code style={{ fontSize: 11, fontFamily: "ui-monospace,monospace", color: C.blue, background: C.blueSoft, padding: "1px 5px", borderRadius: 4, fontWeight: 500 }}>{base}</code>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: C.textDim }}>{files} files</span>
          <span style={{ fontSize: 11, fontFamily: "ui-monospace,monospace", color: C.green, fontWeight: 600, background: C.greenBg, padding: "1px 5px", borderRadius: 4 }}>+{adds}</span>
          <span style={{ fontSize: 11, fontFamily: "ui-monospace,monospace", color: C.red, fontWeight: 600, background: C.redBg, padding: "1px 5px", borderRadius: 4 }}>-{removes}</span>
        </div>
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
      {[0,1,2].map(i => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: "50%", background: C.textDim,
          display: "inline-block",
          animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-3px)}}`}</style>
    </span>
  );
}

// ─── right panel ──────────────────────────────────────────────────────────────

function ReportPanel({ runState, onClose }: { runState: RunState | null; onClose: () => void }) {
  const report = DEMO_REPORT;
  const pr = runState?.generated_pr;

  return (
    <aside style={{
      width: 390, flexShrink: 0,
      borderLeft: `1px solid ${C.border}`,
      background: C.bg,
      display: "flex", flexDirection: "column",
      height: "100%", overflow: "hidden",
    }}>
      {/* file header */}
      <div style={{
        height: 41, padding: "0 10px 0 14px", borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", gap: 8, flexShrink: 0,
        background: C.bgSidebar,
      }}>
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke={C.textDim} strokeWidth="1.4"><path d="M4 2h6l4 4v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M10 2v4h4"/></svg>
        <span style={{ fontSize: 12, fontWeight: 500, color: C.text, flex: 1, fontFamily: "ui-monospace,monospace" }}>
          {pr ? "generated_pr.md" : report.filename}
        </span>
        <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, padding: "2px 3px", borderRadius: 4, fontSize: 12 }}>⧉</button>
        <button style={{ border: "none", background: "none", cursor: "pointer", color: C.textDim, padding: "2px 3px", borderRadius: 4, fontSize: 12 }}>↓</button>
        {/* close button */}
        <button
          onClick={onClose}
          title="Close panel"
          style={{
            border: "none", background: "none", cursor: "pointer",
            color: C.textDim, padding: "4px 5px", borderRadius: 5,
            fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center",
            transition: "background 0.1s, color 0.1s",
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = C.bgHover; (e.currentTarget as HTMLElement).style.color = C.text; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "none"; (e.currentTarget as HTMLElement).style.color = C.textDim; }}
        >
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <path d="M1 1l12 12M13 1L1 13"/>
          </svg>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "20px 20px 20px" }}>
        {pr ? (
          // Live PR from run
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <p style={{ fontSize: 10, color: C.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>Test Report</p>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: C.text, lineHeight: 1.3 }}>{pr.title}</h2>
            </div>
            <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.7 }}>{pr.summary}</p>
            <div>
              {pr.changes.map((c, i) => (
                <div key={i} style={{ display: "flex", gap: 8, padding: "3px 0", fontSize: 13, color: C.text }}>
                  <span style={{ color: C.green }}>+</span>{c}
                </div>
              ))}
            </div>
            {pr.risks.length > 0 && (
              <div style={{ background: "#fffbea", border: `1px solid #fde68a`, borderRadius: 8, padding: 12 }}>
                <p style={{ fontSize: 11, fontWeight: 600, color: C.yellow, marginBottom: 6 }}>RISKS</p>
                {pr.risks.map((r, i) => <p key={i} style={{ fontSize: 12, color: C.textMid }}>{r}</p>)}
              </div>
            )}
          </div>
        ) : (
          // Demo report
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div>
              <p style={{ fontSize: 10, color: C.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Test Report</p>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: C.text, lineHeight: 1.3, marginBottom: 8 }}>{report.title}</h2>
              <p style={{ fontSize: 13, color: C.textMid }}>
                PRs:{" "}
                {report.prs.map((p, i) => (
                  <span key={i}>
                    <span style={{ color: C.blue, textDecoration: "underline", cursor: "pointer" }}>{p.repo} #{p.num}</span>
                    {i < report.prs.length - 1 ? " | " : ""}
                  </span>
                ))}
              </p>
            </div>

            <p style={{ fontSize: 13, color: C.text, lineHeight: 1.7 }}>{report.summary}</p>

            {report.sections.map(section => (
              <div key={section.title}>
                <p style={{ fontSize: 13.5, fontWeight: 600, color: C.text, marginBottom: 10 }}>{section.title}</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  {section.items.map((item, i) => (
                    <div key={i} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                      <p style={{ fontSize: 10.5, color: C.textDim, fontWeight: 500 }}>{item.label}</p>
                      <div style={{
                        border: `1px solid ${C.border}`, borderRadius: 10,
                        padding: "22px 14px", textAlign: "center",
                        background: item.gradient
                          ? "linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%)"
                          : "#317CFF",
                        minHeight: 84,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        boxShadow: item.gradient
                          ? "0 4px 14px rgba(99,102,241,0.3)"
                          : "0 4px 14px rgba(49,124,255,0.3)",
                        transition: "transform 0.15s, box-shadow 0.15s",
                      }}>
                        <span style={{
                          fontSize: 18, fontWeight: 750, color: "#fff",
                          lineHeight: 1.2, whiteSpace: "pre-line",
                          textShadow: "0 1px 3px rgba(0,0,0,0.15)",
                          letterSpacing: "-0.02em",
                        }}>
                          {item.content}
                        </span>
                      </div>
                      <p style={{ fontSize: 10.5, color: C.textDim, textAlign: "center" }}>{item.sub}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

// ─── new run modal ────────────────────────────────────────────────────────────

function NewRunModal({ onCreated, onClose }: { onCreated: (id: string) => void; onClose: () => void }) {
  const [obj, setObj] = useState("");
  // Pre-fill a public GitHub repo so the hosted demo works out of the box.
  const [repo, setRepo] = useState("https://github.com/tiangolo/fastapi");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!obj.trim()) { setErr("Objective is required."); return; }
    if (!repo.trim()) { setErr("Repository is required."); return; }
    setLoading(true); setErr("");
    try {
      const { run_id } = await createRun(obj.trim(), repo.trim());
      onCreated(run_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to start run — is the API reachable?");
    } finally {
      setLoading(false);
    }
  }

  const inp: React.CSSProperties = {
    width: "100%", padding: "7px 10px", fontSize: 13,
    border: `1px solid ${C.border}`, borderRadius: 6,
    color: C.text, fontFamily: "inherit", outline: "none", background: C.bg,
  };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(15,15,20,0.45)", backdropFilter: "blur(4px)" }}>
      <form onSubmit={submit} style={{ width: 440, background: C.bg, border: `1px solid ${C.borderMid}`, borderRadius: 16, padding: 28, boxShadow: C.shadowLg }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 18 }}>New Run</h2>
        <label style={{ display: "block", marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: C.textMid, display: "block", marginBottom: 5 }}>Objective</span>
          <input value={obj} onChange={e => setObj(e.target.value)} placeholder="e.g. migrate gradient text to #317CFF" style={inp} autoFocus />
        </label>
        <label style={{ display: "block", marginBottom: 18 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: C.textMid, display: "block", marginBottom: 5 }}>GitHub Repo or Path</span>
          <input value={repo} onChange={e => setRepo(e.target.value)} placeholder="https://github.com/owner/repo" style={inp} />
          <span style={{ fontSize: 11, color: C.textDim, display: "block", marginTop: 4 }}>Paste a public GitHub URL — it'll be cloned automatically.</span>
        </label>
        {err && <p style={{ color: C.red, fontSize: 12, marginBottom: 10 }}>{err}</p>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" onClick={onClose} style={{ padding: "6px 14px", border: `1px solid ${C.border}`, borderRadius: 6, background: C.bg, cursor: "pointer", fontSize: 12, fontFamily: "inherit", color: C.textMid }}>Cancel</button>
          <button type="submit" disabled={loading} style={{ padding: "6px 14px", border: "none", borderRadius: 6, background: "#2da44e", color: "#fff", cursor: loading ? "default" : "pointer", fontSize: 12, fontWeight: 500, fontFamily: "inherit", opacity: loading ? 0.6 : 1 }}>
            {loading ? "Launching…" : "Launch →"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── main ─────────────────────────────────────────────────────────────────────

const TERMINAL = new Set(["pr_generation", "error"]);

export function DashboardClient() {
  const [runs, setRuns] = useState<RunState[]>([]);
  const [selectedSession, setSelectedSession] = useState("demo-1");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [reportOpen, setReportOpen] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedRun = runs.find(r => r.run_id === selectedRunId) ?? null;

  const refresh = useCallback(async (id: string) => {
    try {
      const s = await getRun(id);
      setRuns(prev => { const i = prev.findIndex(r => r.run_id === id); if (i === -1) return [...prev, s]; const n = [...prev]; n[i] = s; return n; });
      return s;
    } catch { return null; }
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const ids = await listRuns();
      await Promise.all(ids.map(refresh));
      setRuns(prev => prev.filter(r => ids.includes(r.run_id)));
    } catch {}
  }, [refresh]);

  useEffect(() => { refreshAll(); }, [refreshAll]);
  useEffect(() => { const t = setInterval(refreshAll, 5000); return () => clearInterval(t); }, [refreshAll]);

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!selectedRunId) return;
    const tick = async () => { const s = await refresh(selectedRunId); if (s && TERMINAL.has(s.current_phase)) clearInterval(pollRef.current!); };
    tick();
    pollRef.current = setInterval(tick, 2500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selectedRunId, refresh]);

  const handleCreated = useCallback(async (id: string) => {
    await refresh(id);
    setSelectedRunId(id);
    setSelectedSession(id);
    setShowModal(false);
  }, [refresh]);

  // when a real run session is selected, show that run; otherwise demo
  const isRealSession = selectedSession !== "demo-1" || selectedRunId !== null;

  return (
    <div style={{ display: "flex", height: "100vh", background: C.bg, overflow: "hidden", fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" }}>
      <Sidebar
        selectedSession={selectedSession}
        onSelect={id => {
          const realRun = runs.find(r => r.run_id === id);
          if (realRun) {
            setSelectedRunId(id);
            setSelectedSession(id);
            setReportOpen(true);
          } else {
            setSelectedSession(id);
            setSelectedRunId(null);
            setReportOpen(true);
          }
        }}
        onNew={() => setShowModal(true)}
        liveRuns={runs}
      />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <ChatThread runState={selectedRun} />
      </div>

      {reportOpen && <ReportPanel runState={selectedRun} onClose={() => setReportOpen(false)} />}

      {showModal && <NewRunModal onCreated={handleCreated} onClose={() => setShowModal(false)} />}
    </div>
  );
}
