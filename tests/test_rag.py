"""RAG foundation tests: parser, chunker, embeddings, vector search and ingestion."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.knowledge.chunker import DocumentChunker  # noqa: E402
from app.knowledge.document import PDFParser  # noqa: E402
from app.knowledge.embedding import LocalHashEmbeddingProvider  # noqa: E402
from app.knowledge.ingestion import DocumentIngestionService  # noqa: E402
from app.knowledge.retriever import KnowledgeRetriever  # noqa: E402
from app.knowledge.vector_store import SQLiteVectorStore, cosine_similarity  # noqa: E402
from app.models import Material, User  # noqa: E402


def make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    content = doc.tobytes()
    doc.close()
    return content


def test_pdf_parser_extracts_page_text():
    pages = PDFParser().parse(make_pdf("Matrix determinant lesson and examples"))
    assert len(pages) == 1
    assert "Matrix" in pages[0].text
    assert pages[0].page == 1


def test_chunker_has_page_and_overlap():
    chunks = DocumentChunker(chunk_size=30, overlap=5).chunk_page(
        "A" * 70, page=3, metadata={"subject": "math"}
    )
    assert len(chunks) >= 3
    assert all(chunk.page == 3 for chunk in chunks)
    assert chunks[0].chunk_index == 0


@pytest.mark.asyncio
async def test_local_embedding_is_deterministic_and_normalized():
    provider = LocalHashEmbeddingProvider(dimensions=64)
    first, second, other = await provider.embed(
        ["matrix determinant", "matrix determinant", "english grammar"]
    )
    assert first == second
    assert cosine_similarity(first, second) == pytest.approx(1.0)
    assert cosine_similarity(first, other) < 1.0


@pytest.mark.asyncio
async def test_pdf_ingestion_and_retrieval():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, name="Test", email="test@example.local")
        material = Material(
            user_id=1,
            title="Matrix Notes",
            subject="mathematics",
            file_type="pdf",
            ingestion_status="pending",
        )
        db.add(user)
        db.add(material)
        db.commit()
        db.refresh(material)

        embedding = LocalHashEmbeddingProvider(dimensions=64)
        store = SQLiteVectorStore(db)
        service = DocumentIngestionService(
            db,
            embedding_provider=embedding,
            vector_store=store,
        )
        count = await service.ingest_pdf(
            material,
            make_pdf("A matrix determinant for a two by two matrix is ad minus bc."),
        )
        assert count >= 1
        assert material.ingestion_status == "ready"
        assert material.page_count == 1

        retriever = KnowledgeRetriever(embedding, store)
        results = await retriever.retrieve(
            "matrix determinant", subject="mathematics", document_id=material.id
        )
        assert results
        assert results[0].document_id == material.id
        assert "matrix" in results[0].text.lower()
