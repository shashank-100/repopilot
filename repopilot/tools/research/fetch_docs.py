import httpx

from repopilot.tools.base import ToolInput, ToolOutput, tool


class FetchDocsInput(ToolInput):
    url: str
    timeout: int = 15


@tool("research.fetch_docs", "Fetch the text content of a documentation URL")
def fetch_docs(inp: FetchDocsInput) -> ToolOutput:
    try:
        resp = httpx.get(inp.url, timeout=inp.timeout, follow_redirects=True)
        resp.raise_for_status()
        return ToolOutput(success=True, data={"url": inp.url, "status": resp.status_code, "content": resp.text[:8000]})
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
