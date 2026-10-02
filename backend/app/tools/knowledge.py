"""Knowledge search tool backed by the Retriever abstraction."""

from __future__ import annotations

import time
from typing import Any

from app.knowledge.retriever import Retriever
from app.tools.base import Tool, ToolResult


class KnowledgeSearchTool(Tool):
    name = "knowledge_search"
    description = "Search uploaded, untrusted study materials for relevant passages."
    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "subject": {"type": ["string", "null"]},
            "topic": {"type": ["string", "null"]},
            "document_id": {"type": ["integer", "null"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"results": {"type": "array"}},
    }

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    async def execute(self, payload: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        query = str(payload.get("query") or "").strip()
        if not query:
            return ToolResult(ok=False, error="query is required")
        results = await self.retriever.retrieve(
            query,
            subject=_optional_str(payload.get("subject")),
            topic=_optional_str(payload.get("topic")),
            document_id=_optional_int(payload.get("document_id")),
            limit=min(10, max(1, int(payload.get("limit") or 5))),
        )
        return ToolResult(
            ok=True,
            output={
                "results": [
                    {
                        "chunk_id": item.chunk_id,
                        "document_id": item.document_id,
                        "document_title": item.document_title,
                        "page": item.page,
                        "text": item.text,
                        "subject": item.subject,
                        "topic": item.topic,
                        "score": round(item.score, 4),
                        "trust": "untrusted_document",
                    }
                    for item in results
                ]
            },
            execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
        )


def _optional_str(value: object) -> str | None:
    return str(value) if value not in {None, ""} else None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
