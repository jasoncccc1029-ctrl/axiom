"""Explicit allow-listed tool routing. No recursive or dynamic imports."""

from __future__ import annotations

from app.core.errors import ToolExecutionError
from app.tools.base import Tool, ToolResult


class ToolRouter:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or [])}

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    async def execute(self, name: str, payload: dict[str, object]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError(f"Tool 不存在或未允許：{name}")
        return await tool.execute(dict(payload))
