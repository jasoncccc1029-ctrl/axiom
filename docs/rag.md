# Document ingestion and RAG

Material flow:

```text
PDF/image/note -> MIME/magic validation -> UUID storage -> extraction
PDFParser -> page text
-> render pages with insufficient text -> optional VisionProvider extraction
-> cleaner -> page-aware chunker -> EmbeddingProvider -> VectorStore
```

The first implementation uses deterministic local feature hashing and stores
vectors in SQLite `document_chunks`. It downloads no embedding model.
`EmbeddingProvider`, `VectorStore`, and `Retriever` are replaceable contracts.

Retrieval supports subject, topic, and document filters. Local hash embeddings
are lightweight but less semantic than learned embedding models.
Image materials use Vision extraction before indexing; notes index their title
and body directly.
