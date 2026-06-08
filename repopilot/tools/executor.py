from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from opentelemetry import trace

from repopilot.errors import ToolNotFoundError
from repopilot.state import RepoPilotState, ToolCall
from repopilot.tools.base import ToolOutput, ToolRegistry

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer("repopilot.tools")


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, state: RepoPilotState) -> None:
        self._registry = registry
        self._state = state

    def run(self, tool_name: str, **kwargs: Any) -> ToolOutput:
        try:
            meta = self._registry.get(tool_name)
        except KeyError as exc:
            raise ToolNotFoundError(str(exc)) from exc
        inp = meta.input_schema(**kwargs)

        log = logger.bind(tool=tool_name, run_id=self._state["run_id"])

        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("run_id", self._state["run_id"])

            start = time.monotonic()
            try:
                result = meta.fn(inp)
                duration_ms = (time.monotonic() - start) * 1000
                log.info("tool.ok", duration_ms=round(duration_ms, 1))
                span.set_attribute("tool.success", True)
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                log.warning("tool.error", error=str(exc))
                span.set_attribute("tool.success", False)
                span.record_exception(exc)
                result = ToolOutput(success=False, error=str(exc))

        record: ToolCall = {
            "tool_name": tool_name,
            "args": inp.model_dump(),
            "result": result.model_dump(),
            "success": result.success,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": round(duration_ms, 1),
        }
        self._state["tool_history"].append(record)

        return result
