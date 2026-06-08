import type { RunState } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function listRuns(): Promise<string[]> {
  const r = await fetch(`${BASE}/runs`, { cache: "no-store" });
  if (!r.ok) throw new Error("Failed to list runs");
  const data = await r.json();
  return data.run_ids as string[];
}

export async function getRun(id: string): Promise<RunState> {
  const r = await fetch(`${BASE}/runs/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to fetch run ${id}`);
  return r.json();
}

export async function createRun(objective: string, repo_path: string): Promise<{ run_id: string }> {
  const r = await fetch(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ objective, repo_path }),
  });
  if (!r.ok) throw new Error("Failed to create run");
  return r.json();
}
