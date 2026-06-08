from __future__ import annotations

import functools
import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class ToolInput(BaseModel):
    model_config = {"extra": "forbid"}


class ToolOutput(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


@dataclass
class ToolMeta:
    name: str        # e.g. "fs.read_file"
    namespace: str   # e.g. "fs"
    description: str
    input_schema: type[ToolInput]
    fn: Callable[..., ToolOutput]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolMeta] = {}

    def register(self, meta: ToolMeta) -> None:
        self._tools[meta.name] = meta

    def get(self, name: str) -> ToolMeta:
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def list_namespace(self, ns: str) -> list[ToolMeta]:
        return [m for m in self._tools.values() if m.namespace == ns]

    def all(self) -> list[ToolMeta]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())


registry = ToolRegistry()


def tool(name: str, description: str) -> Callable[[Callable[..., ToolOutput]], Callable[..., ToolOutput]]:
    """Decorator that auto-registers a tool function with the global registry."""
    namespace = name.split(".")[0]

    def decorator(fn: Callable[..., ToolOutput]) -> Callable[..., ToolOutput]:
        import inspect
        import typing
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if not params:
            raise TypeError(f"Tool function {fn.__name__} must accept one ToolInput parameter")
        # Resolve stringified annotations (from __future__ import annotations)
        try:
            hints = typing.get_type_hints(fn)
            param_name = params[0].name
            input_schema = hints.get(param_name, params[0].annotation)
        except Exception:
            input_schema = params[0].annotation
        if not (isinstance(input_schema, type) and issubclass(input_schema, ToolInput)):
            raise TypeError(
                f"Tool function {fn.__name__} first parameter must be a ToolInput subclass, "
                f"got {input_schema!r}"
            )

        registry.register(ToolMeta(
            name=name,
            namespace=namespace,
            description=description,
            input_schema=input_schema,
            fn=fn,
        ))

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> ToolOutput:
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _import_namespace(package_name: str) -> None:
    """Import all modules in a namespace package to trigger @tool decorators."""
    try:
        pkg = importlib.import_module(package_name)
        pkg_path = getattr(pkg, "__path__", [])
        for _, module_name, _ in pkgutil.iter_modules(pkg_path):
            importlib.import_module(f"{package_name}.{module_name}")
    except ImportError:
        pass


def load_all_tools() -> None:
    namespaces = [
        "repopilot.tools.fs",
        "repopilot.tools.git",
        "repopilot.tools.terminal",
        "repopilot.tools.analysis",
        "repopilot.tools.research",
    ]
    for ns in namespaces:
        _import_namespace(ns)
    # Register top-level tool modules (not in a namespace sub-package)
    try:
        importlib.import_module("repopilot.tools.subagent")
    except ImportError:
        pass
