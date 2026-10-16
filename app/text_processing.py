"""Unicode cleanup, lightweight section detection, and Hindi-aware chunking."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int
    section: str
    chunk_id: str


def normalize_text(text: str) -> str:
    """Make equivalent Unicode sequences compare consistently without corrupting Hindi."""
    text = unicodedata.normalize("NFC", text)
    text = (
        text.replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u00ad", "")
        # A few embedded-font PDFs expose unmapped glyphs as NUL. Removing the
        # marker is cleaner and more searchable than retaining a control byte.
        .replace("\x00", "")
    )
    text = text.replace("\u00a0", " ")
    # Ligatures occasionally appear in embedded Latin headings in PDFs.
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n[ ]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(line)).strip()


def is_probable_heading(line: str) -> bool:
    """Conservative heading heuristic that does not need font information from the PDF."""
    line = _clean_line(line)
    if not 3 <= len(line) <= 110:
        return False
    words = line.split()
    if len(words) > 14 or line[-1:] in {"।", ".", "?", "!", ";"}:
        return False
    if line.endswith(":"):
        return True
    return bool(
        re.match(r"^(?:अध्याय|भाग|परिचय|निष्कर्ष|Chapter|Section|[0-9०-९]+[.)])", line, re.I)
    )


def split_sections(page_text: str, page_number: int) -> list[tuple[str, str]]:
    """Keep a best-effort heading with the nearby text for useful citations."""
    section = f"Page {page_number}"
    collected: list[str] = []
    sections: list[tuple[str, str]] = []

    def flush() -> None:
        content = normalize_text("\n".join(collected))
        if content:
            sections.append((section, content))

    for raw_line in page_text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        if is_probable_heading(line):
            flush()
            collected.clear()
            section = line.rstrip(":").strip()
        else:
            collected.append(line)
    flush()
    return sections or [(section, normalize_text(page_text))]


def split_sentences(text: str) -> list[str]:
    """Split at Hindi danda as well as conventional sentence endings."""
    text = normalize_text(text)
    sentences = re.split(r"(?<=[।!?])\s+|(?<=\.)\s+(?=[A-Zअ-ह])|\n+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def _tail_sentences(sentences: list[str], overlap_words: int) -> list[str]:
    """Retain complete trailing sentences for overlap, never a mid-sentence fragment."""
    tail: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        tail.insert(0, sentence)
        total += _word_count(sentence)
        if total >= overlap_words:
            break
    return tail


def _split_long_sentence(sentence: str, max_words: int) -> list[str]:
    words = sentence.split()
    return [" ".join(words[index : index + max_words]) for index in range(0, len(words), max_words)]


def _chunk_section(text: str, max_words: int, overlap_words: int) -> list[str]:
    sentences: list[str] = []
    for sentence in split_sentences(text):
        if _word_count(sentence) > max_words:
            sentences.extend(_split_long_sentence(sentence, max_words))
        else:
            sentences.append(sentence)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if current and current_words + sentence_words > max_words:
            chunks.append(" ".join(current))
            current = _tail_sentences(current, overlap_words)
            current_words = sum(_word_count(item) for item in current)
        current.append(sentence)
        current_words += sentence_words
    if current:
        chunks.append(" ".join(current))
    return [normalize_text(chunk) for chunk in chunks if normalize_text(chunk)]


def build_chunks(
    pages: list[tuple[int, str]], max_words: int = 180, overlap_words: int = 30
) -> list[Chunk]:
    """Create page-local chunks so every retrieved citation has one exact page."""
    if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("Require max_words > overlap_words >= 0.")

    chunks: list[Chunk] = []
    for page_number, page_text in pages:
        for section, section_text in split_sections(page_text, page_number):
            for text in _chunk_section(section_text, max_words, overlap_words):
                chunk_id = f"chunk-{len(chunks) + 1:04d}"
                chunks.append(Chunk(text=text, page=page_number, section=section, chunk_id=chunk_id))
    if not chunks:
        raise ValueError("Text was extracted but no chunks could be made.")
    return chunks
