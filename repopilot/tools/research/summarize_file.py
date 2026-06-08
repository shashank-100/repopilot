"""Summarize a file's purpose via LLM (lazy import to avoid circular deps)."""
from pathlib import Path

from repopilot.tools.base import ToolInput, ToolOutput, tool


class SummarizeFileInput(ToolInput):
    path: str
    max_chars: int = 4000


@tool("research.summarize_file", "Use an LLM to summarize the purpose of a source file")
def summarize_file(inp: SummarizeFileInput) -> ToolOutput:
    try:
        from anthropic import Anthropic

        content = Path(inp.path).read_text(encoding="utf-8", errors="ignore")[: inp.max_chars]
        client = Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"In 2-3 sentences, summarize what this file does:\n\n```python\n{content}\n```",
            }],
        )
        summary = msg.content[0].text if msg.content else ""
        return ToolOutput(success=True, data={"path": inp.path, "summary": summary})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
