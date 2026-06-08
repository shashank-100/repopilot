import importlib.metadata

from repopilot.tools.base import ToolInput, ToolOutput, tool


class GetPackageInfoInput(ToolInput):
    package_name: str


@tool("research.get_package_info", "Return installed version and metadata for a Python package")
def get_package_info(inp: GetPackageInfoInput) -> ToolOutput:
    try:
        meta = importlib.metadata.metadata(inp.package_name)
        return ToolOutput(success=True, data={
            "name": meta["Name"],
            "version": meta["Version"],
            "summary": meta.get("Summary", ""),
            "home_page": meta.get("Home-page", ""),
        })
    except importlib.metadata.PackageNotFoundError:
        return ToolOutput(success=False, error=f"package {inp.package_name!r} not installed")
    except Exception as exc:
        return ToolOutput(success=False, error=str(exc))
