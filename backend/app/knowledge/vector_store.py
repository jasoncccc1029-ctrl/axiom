"""VectorStore abstraction backed by the existing SQLite document_chunks table."""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DocumentChunk, Material


@dataclass
class VectorSearchResult:
    chunk_id: int
    document_id: int
    document_title: str
    page: int
    chunk_index: int
    text: str
    subject: str
    topic: str | None
    score: float
    metadata: dict[str, object]


class VectorStore(ABC):
    @abstractmethod
    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 5,
        subject: str | None = None,
        topic: str | None = None,
        document_id: int | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError


class SQLiteVectorStore(VectorStore):
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 5,
        subject: str | None = None,
        topic: str | None = None,
        document_id: int | None = None,
    ) -> list[VectorSearchResult]:
        query = self.db.query(DocumentChunk, Material).join(
            Material, DocumentChunk.material_id == Material.id
        )
        if subject:
            query = query.filter(Material.subject == subject)
        if document_id is not None:
            query = query.filter(DocumentChunk.material_id == document_id)

        scored: list[VectorSearchResult] = []
        for chunk, material in query.all():
            metadata = _load_json(chunk.metadata_json, {})
            chunk_topic = str(metadata.get("topic")) if metadata.get("topic") else None
            if topic and chunk_topic and chunk_topic.lower() != topic.lower():
                continue
            embedding = _load_json(chunk.embedding_json, [])
            if not isinstance(embedding, list) or not embedding:
                continue
            score = cosine_similarity(query_embedding, [float(v) for v in embedding])
            scored.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=material.id,
                    document_title=material.title,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    subject=material.subject,
                    topic=chunk_topic,
                    score=score,
                    metadata=metadata,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    lnorm = math.sqrt(sum(a * a for a in left))
    rnorm = math.sqrt(sum(b * b for b in right))
    if not lnorm or not rnorm:
        return 0.0
    return dot / (lnorm * rnorm)


def _load_json(value: str | None, default):  # type: ignore[no-untyped-def]
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
