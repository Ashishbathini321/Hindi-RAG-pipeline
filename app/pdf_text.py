"""PDF extraction with a text fallback for unusually encoded PDFs."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from .text_processing import normalize_text


def _pypdf_text(page: object) -> str:
    """Extract natural word spacing before trying pypdf's layout mode.

    Some Hindi PDFs encode wide glyph positions.  `extraction_mode="layout"`
    turns those positions into spaces between individual Devanagari characters,
    which is far worse for multilingual retrieval than a plain text extraction.
    """
    try:
        text = page.extract_text() or ""
    except TypeError:
        return ""
    if text.strip():
        return text
    try:
        return page.extract_text(extraction_mode="layout") or ""
    except TypeError:
        return ""


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return `(one_based_page_number, normalized_text)` for every usable page.

    pypdf is tried first. If it finds no text, pdfplumber gets a second attempt;
    this makes the pipeline more tolerant of simple table layouts.
    """
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = _pypdf_text(page)
        if not text.strip():
            text = _pdfplumber_page_text(pdf_path, page_number - 1)
        text = normalize_text(text)
        if text:
            pages.append((page_number, text))

    if not pages:
        raise ValueError(
            "No extractable text was found. The PDF may be scanned; run OCR first "
            "and then ingest the OCR'd copy."
        )
    return pages


def _pdfplumber_page_text(pdf_path: Path, page_index: int) -> str:
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - documented dependency is installed normally
        return ""

    with pdfplumber.open(str(pdf_path)) as pdf:
        return pdf.pages[page_index].extract_text(layout=True) or ""
