"""Central LLM configuration with token tracking.

One place to control which Claude model every agent uses, plus a global
token counter so each run can report total input/output tokens.

Set REPOPILOT_MODEL env var to override (e.g. "claude-sonnet-4-6").
Default is Haiku for cost efficiency — sufficient for most agent tasks.
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache
from typing import Any, TypeVar

import structlog
from aiolimiter import AsyncLimiter
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import LLMResult
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from repopilot.errors import LLMError

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Rate limit on outbound LLM calls: max 50 requests per 60s window.
# Protects against hammering the Anthropic API under heavy fan-out.
_RATE = float(os.getenv("REPOPILOT_LLM_RATE", "50"))
_llm_limiter = AsyncLimiter(_RATE, 60)
# Sync guard mirroring the async limiter for non-async call sites.
_sync_lock = threading.Semaphore(int(_RATE))

# Retryable transient failures from the Anthropic API.
_RETRYABLE = (RateLimitError, APIConnectionError, APIStatusError)

# Hybrid model strategy:
#   DEFAULT (Haiku) — mechanical agents: discovery, knowledge, architecture,
#                     implementation, documentation
#   HEAVY (Sonnet)  — reasoning agents: planning, pr_generation, reflection
#
# Override either via env var.
DEFAULT_MODEL = os.getenv("REPOPILOT_MODEL", "claude-haiku-4-5-20251001")
HEAVY_MODEL = os.getenv("REPOPILOT_HEAVY_MODEL", "claude-sonnet-4-6")


# ── token tracking ──────────────────────────────────────────────────────────

class TokenCounter:
    """Process-wide accumulator for LLM token usage."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, input_t: int, output_t: int) -> None:
        self.input_tokens += input_t
        self.output_tokens += output_t
        self.calls += 1

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def snapshot(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total,
            "llm_calls": self.calls,
        }

    def reset(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0


token_counter = TokenCounter()


class _TokenCallback(BaseCallbackHandler):
    """LangChain callback that records token usage from each LLM response."""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage = None
        # Anthropic returns usage under llm_output or response_metadata
        if response.llm_output:
            usage = response.llm_output.get("usage") or response.llm_output.get("token_usage")
        if not usage:
            for gen_list in response.generations:
                for gen in gen_list:
                    meta = getattr(gen.message, "response_metadata", {}) if hasattr(gen, "message") else {}
                    usage = meta.get("usage")
                    if usage:
                        break
        if usage:
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            token_counter.add(in_t, out_t)
            logger.info("llm.tokens", input=in_t, output=out_t,
                        running_total=token_counter.total)


_callback = _TokenCallback()


@lru_cache(maxsize=4)
def get_llm(model: str | None = None) -> BaseChatModel:
    """Return a cached ChatAnthropic instance with token tracking attached.

    Temperature 0 for deterministic, reproducible agent behavior.
    """
    return ChatAnthropic(  # type: ignore[call-arg]
        model=model or DEFAULT_MODEL,
        temperature=0,
        callbacks=[_callback],
    )


def default_llm() -> BaseChatModel:
    return get_llm(DEFAULT_MODEL)


def heavy_llm() -> BaseChatModel:
    return get_llm(HEAVY_MODEL)


# ── retry + rate-limit wrappers for external LLM calls ──────────────────────────

@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def invoke_with_retry(runnable: Any, payload: Any) -> Any:
    """Invoke a LangChain runnable with rate limiting + exponential backoff.

    Retries transient Anthropic errors (429 / connection / 5xx) up to 5 times
    with exponential backoff (2s → 4s → 8s → 16s → 30s cap). Non-transient
    errors surface immediately as LLMError.
    """
    with _sync_lock:
        try:
            return runnable.invoke(payload)
        except _RETRYABLE:
            raise  # let tenacity handle the backoff/retry
        except Exception as exc:  # noqa: BLE001 — boundary: wrap as typed error
            raise LLMError(str(exc)) from exc


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def ainvoke_with_retry(runnable: Any, payload: Any) -> Any:
    """Async variant of invoke_with_retry, gated by the shared rate limiter."""
    async with _llm_limiter:
        try:
            return await runnable.ainvoke(payload)
        except _RETRYABLE:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc
