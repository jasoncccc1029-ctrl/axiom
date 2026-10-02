"""Material service helpers."""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.knowledge.ingestion import DocumentIngestionService
from app.models import Material
from app.services.image_validation import detect_mime


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def list_materials(db: Session, user_id: int | None = None) -> list[Material]:
    uid = user_id or settings.default_user_id
    return (
        db.query(Material)
        .filter(Material.user_id == uid)
        .order_by(Material.created_at.desc())
        .all()
    )


async def save_upload(
    db: Session,
    file: UploadFile,
    title: str,
    subject: str,
    description: str | None = None,
    user_id: int | None = None,
    ingestion_service: DocumentIngestionService | None = None,
) -> Material:
    uid = user_id or settings.default_user_id
    filename = Path((file.filename or "upload.bin").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or '(none)'}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"檔案過大，上限 {settings.max_upload_size // (1024 * 1024)} MB。",
        )

    declared_mime = (file.content_type or "").lower().split(";")[0].strip()
    if ext == ".pdf":
        detected_mime = "application/pdf" if content.startswith(b"%PDF-") else None
    else:
        detected_mime = detect_mime(content)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="不支援或無效的檔案內容。")
    if declared_mime and declared_mime not in {detected_mime, "image/jpg"}:
        raise HTTPException(status_code=400, detail="檔案內容與 MIME type 不符。")

    file_type = "pdf" if detected_mime == "application/pdf" else "image"
    safe_ext = ".jpg" if detected_mime == "image/jpeg" else ext
    safe_name = f"{uuid.uuid4().hex}{safe_ext}"
    storage_dir = settings.document_upload_dir if file_type == "pdf" else settings.upload_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / safe_name
    if dest.resolve().parent != storage_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid upload path")
    dest.write_bytes(content)

    material = Material(
        user_id=uid,
        title=title.strip() or Path(filename).stem,
        subject=subject.strip() or "未分類",
        file_type=file_type,
        file_path=str(dest),
        original_filename=filename,
        description=description,
        mime_type=detected_mime,
        size_bytes=len(content),
        ingestion_status="pending" if file_type == "pdf" else "ready",
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    if file_type == "pdf" and ingestion_service:
        await ingestion_service.ingest_pdf(material, content)
        db.refresh(material)
    elif file_type == "image" and ingestion_service:
        try:
            await ingestion_service.ingest_image(
                material,
                content,
                detected_mime,
                filename=filename,
            )
        except Exception:
            material.ingestion_status = "failed"
            db.commit()
        db.refresh(material)
    return material


def create_note_material(
    db: Session,
    title: str,
    subject: str,
    description: str | None = None,
    user_id: int | None = None,
) -> Material:
    uid = user_id or settings.default_user_id
    material = Material(
        user_id=uid,
        title=title.strip(),
        subject=subject.strip(),
        file_type="note",
        description=description,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def delete_material(db: Session, material_id: int, user_id: int | None = None) -> None:
    uid = user_id or settings.default_user_id
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.user_id == uid)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if material.file_path:
        path = Path(material.file_path)
        if path.exists():
            path.unlink(missing_ok=True)

    db.delete(material)
    db.commit()
