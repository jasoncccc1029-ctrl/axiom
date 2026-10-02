"""PDF parsing, cleaning and page rendering for scanned pages."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

from app.config import settings
from app.core.errors import DocumentParseError


@dataclass
class ParsedPage:
    page: int
    text: str
    image_bytes: bytes | None = None
    source: str = "text"


class PDFParser:
    def parse(self, content: bytes) -> list[ParsedPage]:
        if not content.startswith(b"%PDF-"):
            raise DocumentParseError("檔案內容不是有效 PDF。")
        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:
            raise DocumentParseError("無法解析 PDF 檔案。") from exc
        if len(reader.pages) > settings.max_pdf_pages:
            raise DocumentParseError(f"PDF 頁數超過上限 {settings.max_pdf_pages} 頁。")

        pages: list[ParsedPage] = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            image = None
            source = "text"
            if len(text) < 20:
                image = render_pdf_page(content, index - 1)
                source = "image"
            pages.append(ParsedPage(page=index, text=text, image_bytes=image, source=source))
        return pages


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_pdf_page(content: bytes, page_index: int) -> bytes | None:
    try:
        import fitz

        document = fitz.open(stream=content, filetype="pdf")
        try:
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            return pixmap.tobytes("png")
        finally:
            document.close()
    except Exception:
        return None
