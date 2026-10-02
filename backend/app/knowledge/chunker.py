"""Page-aware text chunking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    page: int
    chunk_index: int
    text: str
    metadata: dict[str, object]


class DocumentChunker:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("Invalid chunk configuration")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_page(
        self,
        text: str,
        *,
        page: int,
        start_index: int = 0,
        metadata: dict[str, object] | None = None,
    ) -> list[TextChunk]:
        value = text.strip()
        if not value:
            return []
        chunks: list[TextChunk] = []
        cursor = 0
        index = start_index
        while cursor < len(value):
            end = min(cursor + self.chunk_size, len(value))
            if end < len(value):
                boundary = max(value.rfind("\n", cursor, end), value.rfind("。", cursor, end))
                if boundary > cursor + self.chunk_size // 2:
                    end = boundary + 1
            piece = value[cursor:end].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        page=page,
                        chunk_index=index,
                        text=piece,
                        metadata=dict(metadata or {}),
                    )
                )
                index += 1
            if end >= len(value):
                break
            cursor = max(cursor + 1, end - self.overlap)
        return chunks
