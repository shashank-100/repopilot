from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class KeyFile(TypedDict):
    path: str
    purpose: str


class RepositoryMap(TypedDict):
    root_path: str
    framework: str
    language: str
    key_files: list[KeyFile]
    entry_points: list[str]
    test_dirs: list[str]
    config_files: list[str]
    summary: str


class RouteInfo(TypedDict):
    method: str
    path: str
    handler: str
    file: str


class ModelInfo(TypedDict):
    name: str
    type: str  # "pydantic" | "sqlalchemy" | "dataclass"
    file: str


class ServiceInfo(TypedDict):
    name: str
    files: list[str]
    dependencies: list[str]


class ArchitectureContext(TypedDict):
    services: list[ServiceInfo]
    api_routes: list[RouteInfo]
    data_models: list[ModelInfo]
    external_deps: list[str]
    test_coverage_estimate: str
    summary: str


class ExecutionStep(TypedDict):
    id: str
    description: str
    tool_hints: list[str]
    files_to_modify: list[str]
    depends_on: list[str]
    status: str  # "pending" | "done" | "failed"


class ToolCall(TypedDict):
    tool_name: str
    args: dict[str, Any]
    result: Any
    success: bool
    timestamp: str
    duration_ms: float


class ValidationResult(TypedDict):
    # Advisory only — never blocks the run.
    # severity: "pass" | "warnings" | "not_validated"
    severity: str
    # How validation was performed: "tests" | "lint" | "syntax" | "none"
    validated_with: str
    passed: bool          # kept for back-compat; mirrors severity == "pass"
    summary: str          # human-readable one-liner
    pytest_output: str
    mypy_output: str
    ruff_output: str
    findings: list[str]   # advisory notes (renamed from "errors")
    errors: list[str]     # back-compat alias of findings


class GeneratedPR(TypedDict):
    title: str
    summary: str
    changes: list[str]
    tests_executed: list[str]
    risks: list[str]
    rollback_plan: str


class ReflectionReport(TypedDict):
    failure_summary: str
    root_cause: str
    plan_patches: list[dict[str, Any]]
    retry_strategy: str


class RepoPilotState(TypedDict):
    run_id: str
    objective: str
    repo_path: str
    repository_map: NotRequired[RepositoryMap]
    architecture_context: NotRequired[ArchitectureContext]
    # networkx DiGraph — not JSON-serializable, held purely in memory
    repository_graph: NotRequired[Any]
    # {"goal": str, "steps": list[ExecutionStep]}
    execution_plan: NotRequired[dict[str, Any]]
    tool_history: list[ToolCall]
    observations: list[str]
    modified_files: list[str]
    validation_results: NotRequired[ValidationResult]
    generated_pr: NotRequired[GeneratedPR]
    reflection_report: NotRequired[ReflectionReport]
    repair_attempts: int
    current_phase: str
    error: NotRequired[str]
