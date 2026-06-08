import type { Phase } from "@/lib/types";

const CONFIG: Record<Phase, { label: string; bg: string; color: string; border: string }> = {
  created:        { label: "Created",        bg: "rgba(110,118,129,0.1)", color: "#8b949e", border: "rgba(110,118,129,0.3)" },
  discovery:      { label: "Discovery",      bg: "rgba(88,166,255,0.1)",  color: "#79c0ff", border: "rgba(88,166,255,0.3)" },
  knowledge:      { label: "Knowledge",      bg: "rgba(88,166,255,0.1)",  color: "#79c0ff", border: "rgba(88,166,255,0.3)" },
  architecture:   { label: "Architecture",   bg: "rgba(188,140,255,0.1)", color: "#d2a8ff", border: "rgba(188,140,255,0.3)" },
  planning:       { label: "Planning",       bg: "rgba(210,153,34,0.1)",  color: "#e3b341", border: "rgba(210,153,34,0.3)" },
  implementation: { label: "Implementing",   bg: "rgba(255,166,87,0.1)",  color: "#ffa657", border: "rgba(255,166,87,0.3)" },
  validation:     { label: "Validating",     bg: "rgba(86,211,200,0.1)",  color: "#56d3c8", border: "rgba(86,211,200,0.3)" },
  reflection:     { label: "Reflecting",     bg: "rgba(255,121,198,0.1)", color: "#ff79c6", border: "rgba(255,121,198,0.3)" },
  documentation:  { label: "Documenting",    bg: "rgba(72,199,142,0.1)",  color: "#48c78e", border: "rgba(72,199,142,0.3)" },
  pr_generation:  { label: "PR Ready",       bg: "rgba(63,185,80,0.1)",   color: "#3fb950", border: "rgba(63,185,80,0.3)" },
  error:          { label: "Error",          bg: "rgba(248,81,73,0.1)",   color: "#f85149", border: "rgba(248,81,73,0.3)" },
};

export function PhaseBadge({ phase }: { phase: Phase }) {
  const c = CONFIG[phase] ?? CONFIG.created;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      background: c.bg, color: c.color,
      border: `1px solid ${c.border}`,
      borderRadius: 4, padding: "1px 7px",
      fontSize: 11, fontWeight: 500, whiteSpace: "nowrap",
    }}>
      {c.label}
    </span>
  );
}
