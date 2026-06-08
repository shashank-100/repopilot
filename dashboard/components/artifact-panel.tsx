"use client";

import { useState } from "react";
import type { RunState } from "@/lib/types";

type Tab = "pr" | "files" | "plan" | "validation";

const BORDER = "1px solid #30363d";
const BG_PANEL = "#161b22";
const BG_CARD = "#1c2128";
const TEXT = "#e6edf3";
const TEXT_DIM = "#8b949e";
const TEXT_FAINT = "#6e7681";

export function ArtifactPanel({ run }: { run: RunState }) {
  const [tab, setTab] = useState<Tab>("pr");

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "pr",         label: "PR" },
    { id: "files",      label: "Files",      count: run.modified_files.length },
    { id: "plan",       label: "Plan",       count: run.execution_plan?.steps.length },
    { id: "validation", label: "Validation" },
  ];

  return (
    <aside style={{
      width: 380, flexShrink: 0, display: "flex", flexDirection: "column",
      borderLeft: BORDER, background: BG_PANEL, height: "100%",
    }}>
      {/* tab bar */}
      <div style={{ display: "flex", borderBottom: BORDER, paddingLeft: 4 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "10px 12px",
            border: "none", borderBottom: tab === t.id ? "2px solid #3fb950" : "2px solid transparent",
            background: "transparent", cursor: "pointer", fontFamily: "inherit",
            color: tab === t.id ? "#f0f6fc" : TEXT_FAINT,
            fontSize: 12, fontWeight: tab === t.id ? 500 : 400,
            transition: "color 0.1s",
          }}>
            {t.label}
            {t.count != null && t.count > 0 && (
              <span style={{ background: "#21262d", color: TEXT_DIM, borderRadius: 10, padding: "0 6px", fontSize: 10 }}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* content */}
      <div style={{ flex: 1, overflowY: "auto", padding: 0 }}>
        {tab === "pr"         && <PRView run={run} />}
        {tab === "files"      && <FilesView run={run} />}
        {tab === "plan"       && <PlanView run={run} />}
        {tab === "validation" && <ValidationView run={run} />}
      </div>
    </aside>
  );
}

function Empty({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, gap: 10, color: TEXT_FAINT }}>
      <span style={{ fontSize: 28 }}>{icon}</span>
      <p style={{ fontSize: 12 }}>{text}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <p style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: TEXT_FAINT, marginBottom: 8 }}>{title}</p>
      {children}
    </div>
  );
}

function PRView({ run }: { run: RunState }) {
  const pr = run.generated_pr;
  if (!pr) return <Empty icon="◇" text="PR will appear when the run completes" />;
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
          <span style={{ background: "rgba(63,185,80,0.1)", color: "#3fb950", border: "1px solid rgba(63,185,80,0.3)", borderRadius: 4, padding: "1px 7px", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" }}>Ready</span>
          <h3 style={{ color: "#f0f6fc", fontSize: 14, fontWeight: 600, lineHeight: 1.4, margin: 0 }}>{pr.title}</h3>
        </div>
        <p style={{ color: TEXT_DIM, fontSize: 12, lineHeight: 1.7 }}>{pr.summary}</p>
      </div>

      <Section title="Changes">
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          {pr.changes.map((c, i) => (
            <li key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: TEXT_DIM }}>
              <span style={{ color: "#3fb950", flexShrink: 0 }}>+</span>{c}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Tests Executed">
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          {pr.tests_executed.map((t, i) => (
            <li key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: TEXT_DIM }}>
              <span style={{ color: "#3fb950", flexShrink: 0 }}>✓</span>{t}
            </li>
          ))}
        </ul>
      </Section>

      {pr.risks.length > 0 && (
        <Section title="Risks">
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            {pr.risks.map((r, i) => (
              <li key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: TEXT_DIM }}>
                <span style={{ color: "#d29922", flexShrink: 0 }}>⚠</span>{r}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <div style={{ background: "rgba(248,81,73,0.05)", border: "1px solid rgba(248,81,73,0.2)", borderRadius: 6, padding: 12 }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: "#f85149", marginBottom: 4 }}>ROLLBACK PLAN</p>
        <p style={{ fontSize: 12, color: TEXT_DIM, lineHeight: 1.6 }}>{pr.rollback_plan}</p>
      </div>
    </div>
  );
}

function FilesView({ run }: { run: RunState }) {
  if (!run.modified_files.length) return <Empty icon="◇" text="No files modified yet" />;
  return (
    <div style={{ padding: "8px 0" }}>
      {run.modified_files.map((f, i) => {
        const parts = f.split("/");
        const name = parts.pop() ?? f;
        const dir = parts.join("/");
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 16px" }}>
            <span style={{ color: "#79c0ff", fontSize: 12, flexShrink: 0 }}>◈</span>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 12, color: TEXT, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</p>
              {dir && <p style={{ fontSize: 11, color: TEXT_FAINT, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{dir}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PlanView({ run }: { run: RunState }) {
  const plan = run.execution_plan;
  if (!plan) return <Empty icon="◇" text="Plan not generated yet" />;

  const done = plan.steps.filter(s => s.status === "done").length;
  const failed = plan.steps.filter(s => s.status === "failed").length;
  const pct = plan.steps.length ? (done / plan.steps.length) * 100 : 0;

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ background: BG_CARD, border: BORDER, borderRadius: 6, padding: 12 }}>
        <p style={{ fontSize: 11, color: TEXT_FAINT, fontWeight: 600, marginBottom: 4 }}>GOAL</p>
        <p style={{ fontSize: 12, color: TEXT, lineHeight: 1.6 }}>{plan.goal}</p>
      </div>

      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: TEXT_FAINT }}>{done}/{plan.steps.length} steps done</span>
          {failed > 0 && <span style={{ fontSize: 11, color: "#f85149" }}>{failed} failed</span>}
        </div>
        <div style={{ height: 4, background: "#21262d", borderRadius: 4 }}>
          <div style={{ height: "100%", width: `${pct}%`, background: "#238636", borderRadius: 4, transition: "width 0.5s" }} />
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {plan.steps.map((step, i) => {
          const isDone = step.status === "done";
          const isFail = step.status === "failed";
          return (
            <div key={step.id} style={{
              border: isDone ? "1px solid rgba(63,185,80,0.2)" : isFail ? "1px solid rgba(248,81,73,0.2)" : BORDER,
              background: isDone ? "rgba(63,185,80,0.05)" : isFail ? "rgba(248,81,73,0.05)" : BG_CARD,
              borderRadius: 6, padding: "8px 12px",
              display: "flex", alignItems: "flex-start", gap: 8,
            }}>
              <span style={{ fontSize: 12, color: isDone ? "#3fb950" : isFail ? "#f85149" : TEXT_FAINT, flexShrink: 0, marginTop: 1 }}>
                {isDone ? "✓" : isFail ? "✗" : `${i + 1}.`}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, color: isDone ? TEXT_DIM : isFail ? "#f85149" : TEXT, lineHeight: 1.4 }}>
                  {step.description}
                </p>
                {step.tool_hints.length > 0 && (
                  <p style={{ fontSize: 11, color: TEXT_FAINT, marginTop: 2 }}>{step.tool_hints.join(" · ")}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ValidationView({ run }: { run: RunState }) {
  const val = run.validation_results;
  if (!val) return <Empty icon="◇" text="Validation not run yet" />;

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8, borderRadius: 6, padding: "8px 12px",
        background: val.passed ? "rgba(63,185,80,0.1)" : "rgba(248,81,73,0.1)",
        border: val.passed ? "1px solid rgba(63,185,80,0.3)" : "1px solid rgba(248,81,73,0.3)",
      }}>
        <span style={{ color: val.passed ? "#3fb950" : "#f85149", fontSize: 14 }}>{val.passed ? "✓" : "✗"}</span>
        <span style={{ color: val.passed ? "#3fb950" : "#f85149", fontSize: 13, fontWeight: 500 }}>
          {val.passed ? "All checks passed" : "Validation failed"}
        </span>
      </div>

      {val.errors.map((e, i) => (
        <p key={i} style={{ fontSize: 12, color: "#f85149", paddingLeft: 4 }}>{e}</p>
      ))}

      {[
        { label: "pytest", output: val.pytest_output },
        { label: "mypy",   output: val.mypy_output },
        { label: "ruff",   output: val.ruff_output },
      ].filter(x => x.output?.trim()).map(({ label, output }) => (
        <Section key={label} title={label}>
          <pre style={{
            background: "#0d1117", border: BORDER, borderRadius: 6,
            padding: 10, fontSize: 11, color: TEXT_DIM,
            fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all",
            maxHeight: 180, overflow: "auto",
          }}>
            {output.slice(-2000)}
          </pre>
        </Section>
      ))}
    </div>
  );
}
