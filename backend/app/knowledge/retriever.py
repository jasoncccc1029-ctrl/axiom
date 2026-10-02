"""Retriever abstraction combining embeddings and a replaceable vector store."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.knowledge.embedding import EmbeddingProvider
from app.knowledge.vector_store import VectorSearchResult, VectorStore


class Retriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        subject: str | None = None,
        topic: str | None = None,
        document_id: int | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError


class KnowledgeRetriever(Retriever):
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        subject: str | None = None,
        topic: str | None = None,
        document_id: int | None = None,
    ) -> list[VectorSearchResult]:
        [embedding] = await self.embedding_provider.embed([query])
        return self.vector_store.search(
            embedding,
            limit=limit,
            subject=subject,
            topic=topic,
            document_id=document_id,
        )
