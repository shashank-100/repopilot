export type Phase =
  | "created"
  | "cloning"
  | "discovery"
  | "knowledge"
  | "architecture"
  | "planning"
  | "implementation"
  | "validation"
  | "reflection"
  | "documentation"
  | "pr_generation"
  | "error";

export interface KeyFile { path: string; purpose: string }
export interface RepositoryMap {
  root_path: string; framework: string; language: string;
  key_files: KeyFile[]; entry_points: string[]; test_dirs: string[];
  config_files: string[]; summary: string;
}
export interface ExecutionStep {
  id: string; description: string; tool_hints: string[];
  files_to_modify: string[]; depends_on: string[];
  status: "pending" | "done" | "failed";
}
export interface ToolCall {
  tool_name: string; args: Record<string, unknown>;
  result: unknown; success: boolean; timestamp: string; duration_ms: number;
}
export interface ValidationResult {
  passed: boolean; pytest_output: string;
  mypy_output: string; ruff_output: string; errors: string[];
}
export interface GeneratedPR {
  title: string; summary: string; changes: string[];
  tests_executed: string[]; risks: string[]; rollback_plan: string;
  url?: string;  // GitHub PR URL when a real PR was opened
}
export interface ReflectionReport {
  failure_summary: string; root_cause: string;
  plan_patches: Record<string, unknown>[]; retry_strategy: string;
}
export interface RunState {
  run_id: string; objective: string; repo_path: string;
  repository_map?: RepositoryMap;
  execution_plan?: { goal: string; steps: ExecutionStep[]; risks: string[]; migration_notes?: string[] };
  tool_history: ToolCall[]; observations: string[]; modified_files: string[];
  validation_results?: ValidationResult; generated_pr?: GeneratedPR;
  reflection_report?: ReflectionReport;
  repair_attempts: number; current_phase: Phase; error?: string;
}
