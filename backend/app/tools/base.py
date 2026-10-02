"""Tool contract and safe, typed execution result."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> ToolResult:
        raise NotImplementedError
