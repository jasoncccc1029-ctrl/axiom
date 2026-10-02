"""Document ingestion application service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import DocumentParseError
from app.knowledge.chunker import DocumentChunker
from app.knowledge.document import PDFParser
from app.knowledge.embedding import EmbeddingProvider, LocalHashEmbeddingProvider
from app.knowledge.vector_store import SQLiteVectorStore, VectorStore
from app.models import DocumentChunk, Material
from app.vision.base import VisionProvider


class DocumentIngestionService:
    def __init__(
        self,
        db: Session,
        *,
        parser: PDFParser | None = None,
        chunker: DocumentChunker | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        vision_provider: VisionProvider | None = None,
    ) -> None:
        self.db = db
        self.parser = parser or PDFParser()
        self.chunker = chunker or DocumentChunker(settings.chunk_size, settings.chunk_overlap)
        self.embedding_provider = embedding_provider or LocalHashEmbeddingProvider(
            settings.embedding_dimensions
        )
        self.vector_store = vector_store or SQLiteVectorStore(db)
        self.vision_provider = vision_provider

    async def ingest_pdf(self, material: Material, content: bytes) -> int:
        if material.file_type != "pdf":
            raise DocumentParseError("只有 PDF 教材可使用 PDF ingestion pipeline。")
        material.ingestion_status = "processing"
        self.db.flush()
        try:
            pages = self.parser.parse(content)
            material.page_count = len(pages)
            all_text: list[str] = []
            prepared = []
            next_index = 0
            for page in pages:
                page_text = page.text
                source = page.source
                if not page_text and page.image_bytes and self.vision_provider:
                    vision = await self.vision_provider.analyze(
                        page.image_bytes,
                        mime_type="image/png",
                        filename=f"document-page-{page.page}.png",
                    )
                    page_text = "\n".join(
                        value
                        for value in (vision.problem_text, vision.diagram_description)
                        if value
                    )
                    source = "vision"
                if not page_text:
                    continue
                all_text.append(page_text)
                chunks = self.chunker.chunk_page(
                    page_text,
                    page=page.page,
                    start_index=next_index,
                    metadata={
                        "source": source,
                        "trust": "untrusted_document",
                        "subject": material.subject,
                    },
                )
                prepared.extend(chunks)
                next_index += len(chunks)

            self.db.query(DocumentChunk).filter(
                DocumentChunk.material_id == material.id
            ).delete()
            embeddings = await self.embedding_provider.embed([item.text for item in prepared])
            rows = [
                DocumentChunk(
                    material_id=material.id,
                    page=item.page,
                    chunk_index=item.chunk_index,
                    text=item.text,
                    metadata_json=json.dumps(item.metadata, ensure_ascii=False),
                    embedding_json=json.dumps(embedding),
                    embedding_provider=self.embedding_provider.name,
                )
                for item, embedding in zip(prepared, embeddings)
            ]
            self.vector_store.add_chunks(rows)
            material.content_text = "\n\n".join(all_text)
            material.ingestion_status = "ready" if rows else "empty"
            self.db.commit()
            return len(rows)
        except Exception:
            self.db.rollback()
            material = self.db.get(Material, material.id)
            if material:
                material.ingestion_status = "failed"
                self.db.commit()
            raise

    async def ingest_text(
        self,
        material: Material,
        text: str,
        *,
        source: str = "note",
        topic: str | None = None,
    ) -> int:
        cleaned = text.strip()
        prepared = self.chunker.chunk_page(
            cleaned,
            page=1,
            metadata={
                "source": source,
                "trust": "untrusted_document",
                "subject": material.subject,
                "topic": topic,
            },
        )
        embeddings = await self.embedding_provider.embed([item.text for item in prepared])
        self.db.query(DocumentChunk).filter(
            DocumentChunk.material_id == material.id
        ).delete()
        self.vector_store.add_chunks(
            [
                DocumentChunk(
                    material_id=material.id,
                    page=item.page,
                    chunk_index=item.chunk_index,
                    text=item.text,
                    metadata_json=json.dumps(item.metadata, ensure_ascii=False),
                    embedding_json=json.dumps(embedding),
                    embedding_provider=self.embedding_provider.name,
                )
                for item, embedding in zip(prepared, embeddings)
            ]
        )
        material.content_text = cleaned or None
        material.page_count = 1 if cleaned else 0
        material.ingestion_status = "ready" if prepared else "empty"
        self.db.commit()
        return len(prepared)

    async def ingest_image(
        self,
        material: Material,
        content: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> int:
        if self.vision_provider is None:
            raise DocumentParseError("Image indexing requires a configured VisionProvider.")
        material.ingestion_status = "processing"
        self.db.commit()
        try:
            result = await self.vision_provider.analyze(
                content,
                mime_type=mime_type,
                filename=filename,
            )
            text = "\n".join(
                value
                for value in (
                    result.problem_text,
                    " ".join(result.detected_formula),
                    result.diagram_description,
                )
                if value
            )
            return await self.ingest_text(
                material,
                text,
                source="vision",
                topic=result.topic if result.topic != "unknown" else None,
            )
        except Exception:
            self.db.rollback()
            current = self.db.get(Material, material.id)
            if current:
                current.ingestion_status = "failed"
                self.db.commit()
            raise
