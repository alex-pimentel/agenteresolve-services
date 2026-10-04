"""Document text extraction helpers shared by text/LLM handlers.

PDF/DOCX extraction uses optional pure-python dependencies imported lazily; when a document
has no embedded text (a scan) callers fall back to the OCR capability provider.
"""

from __future__ import annotations

import io

from common.providers.base import OcrProvider, ProviderUnavailable


def extract_pdf_text(data: bytes) -> str:
    """Return embedded text from a PDF, or an empty string when it is a scan.

    A missing optional dependency propagates as :class:`ProviderUnavailable`; a malformed
    or image-only PDF yields an empty string so callers can fall back to OCR.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ProviderUnavailable(
            "PDF text extraction requires 'pypdf'. Install it or send plain text."
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception:  # noqa: BLE001 - malformed PDF: let OCR handle it
        return ""


def extract_docx_text(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ProviderUnavailable(
            "DOCX text extraction requires 'python-docx'. Install it or send plain text."
        ) from exc
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - malformed DOCX: let OCR handle it
        return ""
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()


def ocr_text(ocr: OcrProvider, data: bytes, *, content_type: str, lang: str | None = None) -> str:
    blocks = ocr.extract(data, content_type=content_type, lang=lang)
    return "\n".join(block.text for block in blocks).strip()


def extract_document_text(
    data: bytes,
    *,
    content_type: str,
    ocr: OcrProvider | None = None,
    lang: str | None = None,
) -> tuple[str, bool]:
    """Extract text from a document, falling back to OCR when there is no native text.

    Returns ``(text, used_ocr)``.
    """
    ctype = (content_type or "").lower()
    text = ""
    try:
        if "pdf" in ctype:
            text = extract_pdf_text(data)
        elif "word" in ctype or "docx" in ctype or "wordprocessingml" in ctype:
            text = extract_docx_text(data)
        elif ctype.startswith("text/") or "json" in ctype:
            return data.decode("utf-8", errors="replace"), False
    except ProviderUnavailable:
        if ocr is None:
            raise
        text = ""

    if not text and ocr is not None:
        text = ocr_text(ocr, data, content_type=content_type, lang=lang)
        return text, True
    return text, False


def chunk_text(text: str, *, size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping character windows for chunking/embedding."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(size - overlap, 1)
    while start < len(text):
        chunks.append(text[start : start + size])
        start += step
    return chunks
