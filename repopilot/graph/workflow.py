"""LangGraph supervisor workflow for RepoPilot.

Build the graph by calling build_graph(). The optional `phases` argument lets
sub-graph (subagent) invocations restrict which nodes run.
"""
from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from repopilot.agents.architecture import ArchitectureAgent
from repopilot.agents.discovery import DiscoveryAgent
from repopilot.agents.documentation import DocumentationAgent
from repopilot.agents.implementation import ImplementationAgent
from repopilot.agents.knowledge import KnowledgeAgent
from repopilot.agents.planning import PlanningAgent
from repopilot.agents.pr_generation import PRAgent
from repopilot.agents.reflection import ReflectionAgent
from repopilot.agents.validation import ValidationAgent
from repopilot.state import RepoPilotState
from repopilot.tools.base import load_all_tools, registry
from repopilot.tools.executor import ToolExecutor

logger = structlog.get_logger(__name__)

_ALL_PHASES = [
    "discovery",
    "knowledge",
    "architecture",
    "planning",
    "implementation",
    "validation",
    "reflection",
    "documentation",
    "pr_generation",
]

MAX_REPAIR_ATTEMPTS = 3


def _make_executor(state: RepoPilotState) -> ToolExecutor:
    load_all_tools()
    return ToolExecutor(registry, state)


def _discovery_node(state: RepoPilotState) -> RepoPilotState:
    executor = _make_executor(state)
    return DiscoveryAgent(executor=executor).run(state)


def _knowledge_node(state: RepoPilotState) -> RepoPilotState:
    return KnowledgeAgent().run(state)


def _architecture_node(state: RepoPilotState) -> RepoPilotState:
    executor = _make_executor(state)
    return ArchitectureAgent(executor=executor).run(state)


def _planning_node(state: RepoPilotState) -> RepoPilotState:
    return PlanningAgent().run(state)


def _implementation_node(state: RepoPilotState) -> RepoPilotState:
    executor = _make_executor(state)
    return ImplementationAgent(executor=executor).run(state)


def _validation_node(state: RepoPilotState) -> RepoPilotState:
    executor = _make_executor(state)
    return ValidationAgent(executor=executor).run(state)


def _reflection_node(state: RepoPilotState) -> RepoPilotState:
    # Increment the repair counter HERE (in a node, where the mutation persists)
    # rather than in the routing edge, where LangGraph may drop it.
    state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    return ReflectionAgent().run(state)


def _documentation_node(state: RepoPilotState) -> RepoPilotState:
    executor = _make_executor(state)
    return DocumentationAgent(executor=executor).run(state)


def _pr_generation_node(state: RepoPilotState) -> RepoPilotState:
    return PRAgent().run(state)


def _stub_node(phase: str):
    def node(state: RepoPilotState) -> RepoPilotState:
        logger.info("stub.node", phase=phase, run_id=state["run_id"])
        state["current_phase"] = phase
        state["observations"].append(f"{phase}: stub (not yet implemented)")
        return state
    node.__name__ = f"_{phase}_node"
    return node


def _route_after_validation(state: RepoPilotState) -> str:
    """Pure routing decision — validation is ADVISORY, so the run always
    proceeds to documentation → PR.

    The repair loop only engages when validation surfaced findings AND we
    haven't already retried — and even then only for tiers where a retry could
    help (i.e. real test/lint failures, not 'not_validated'). Otherwise we pass.
    """
    val = state.get("validation_results") or {}
    severity = val.get("severity", "not_validated")

    # Clean, unverifiable, or already retried → proceed to documentation.
    if severity in ("pass", "not_validated"):
        return "pass"
    if state.get("repair_attempts", 0) >= MAX_REPAIR_ATTEMPTS:
        logger.info("validation.max_repairs_reached", run_id=state.get("run_id"))
        return "pass"  # advisory: ship anyway with findings noted in the PR

    # severity == "warnings" with a real, fixable failure → one repair attempt.
    validated_with = val.get("validated_with", "none")
    if validated_with in ("tests", "lint"):
        return "repair"
    return "pass"  # syntax-only findings: note them, don't loop


def build_graph(phases: list[str] | None = None) -> Any:
    active = set(phases or _ALL_PHASES)

    g: StateGraph = StateGraph(RepoPilotState)  # type: ignore[type-var]

    # Always include nodes that are in the active set
    node_map = {
        "discovery": _discovery_node,
        "knowledge": _knowledge_node,
        "architecture": _architecture_node,
        "planning": _planning_node,
        "implementation": _implementation_node,
        "validation": _validation_node,
        "reflection": _reflection_node,
        "documentation": _documentation_node,
        "pr_generation": _pr_generation_node,
    }

    for phase in _ALL_PHASES:
        if phase in active:
            g.add_node(phase, node_map[phase])

    # Determine entry point (first active phase in order)
    entry = next((p for p in _ALL_PHASES if p in active), None)
    if entry is None:
        raise ValueError("No phases selected")
    g.set_entry_point(entry)

    # Wire edges only between consecutive active phases
    active_ordered = [p for p in _ALL_PHASES if p in active]
    for i, phase in enumerate(active_ordered[:-1]):
        nxt = active_ordered[i + 1]
        if phase == "validation":
            # Conditional routing after validation
            g.add_conditional_edges(
                "validation",
                _route_after_validation,
                {"repair": "reflection", "pass": "documentation", "abort": END},
            )
        elif phase == "reflection":
            g.add_edge("reflection", "planning")
        else:
            g.add_edge(phase, nxt)

    # Last active phase → END
    last = active_ordered[-1]
    if last not in ("validation",):
        g.add_edge(last, END)

    return g.compile()
