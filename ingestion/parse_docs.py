"""Parse PDF manuals and compliance documents into tagged text chunks."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAX_CHUNK_CHARS = 1500
MIN_CHUNK_CHARS = 200
OVERLAP_PARAGRAPHS = 1

# Root-level PDFs grouped by ingestion category.
DOCUMENT_CATALOG: dict[str, list[tuple[str, str]]] = {
    "manual": [
        ("Manual-Hydraulic-Press-Manual.pdf", "manual"),
        ("BPROSP20TManual.pdf", "manual"),
    ],
    "compliance": [
        ("Guidelines-on-Safe-Use-of-Press-Machines-2015.pdf", "compliance"),
        ("hydraulic-press.pdf", "compliance"),
    ],
}

SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*[\.\)]?\s+\S"  # numbered headings: 1., 1.1, 2)
    r"|[A-Z][A-Z0-9 \-/&]{3,}$"  # ALL CAPS headings
    r"|[A-Z][a-z]+(?: [A-Z][a-z]+){0,6}:?$"  # Title Case headings
    r")",
    re.MULTILINE,
)


@dataclass
class DocumentChunk:
    text: str
    source_file: str
    category: str
    chunk_index: int
    page_numbers: list[int] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{self.source_file}:{self.category}:{self.chunk_index}",
            )
        )

    def to_payload(self) -> dict:
        return asdict(self)


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if SECTION_HEADING_RE.match(stripped):
        return True
    if stripped.isupper() and len(stripped.split()) <= 12:
        return True
    return False


def _extract_page_blocks(page: fitz.Page) -> list[tuple[str, int]]:
    """Return ordered (text, page_number) blocks from a PDF page."""
    blocks: list[tuple[str, int]] = []
    page_number = page.number + 1

    for block in page.get_text("blocks"):
        if len(block) < 5:
            continue
        text = block[4].strip()
        if text:
            blocks.append((text, page_number))

    if blocks:
        return blocks

    fallback = page.get_text("text").strip()
    if fallback:
        blocks.append((fallback, page_number))
    return blocks


def _blocks_to_paragraphs(blocks: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Split block text into paragraph units while keeping page provenance."""
    paragraphs: list[tuple[str, int]] = []

    for block_text, page_number in blocks:
        parts = re.split(r"\n\s*\n", block_text)
        for part in parts:
            cleaned = _normalize_whitespace(part)
            if cleaned:
                paragraphs.append((cleaned, page_number))

    return paragraphs


def _merge_short_paragraphs(
    paragraphs: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Merge tiny paragraphs with neighbors to avoid noisy micro-chunks."""
    if not paragraphs:
        return []

    merged: list[tuple[str, int]] = []
    buffer_text = ""
    buffer_pages: list[int] = []

    def flush() -> None:
        nonlocal buffer_text, buffer_pages
        if buffer_text:
            merged.append((buffer_text, buffer_pages[0]))
            buffer_text = ""
            buffer_pages = []

    for text, page in paragraphs:
        if _is_heading(text):
            flush()
            merged.append((text, page))
            continue

        if not buffer_text:
            buffer_text = text
            buffer_pages = [page]
        elif len(buffer_text) < MIN_CHUNK_CHARS:
            buffer_text = f"{buffer_text}\n\n{text}"
            if page not in buffer_pages:
                buffer_pages.append(page)
        else:
            flush()
            buffer_text = text
            buffer_pages = [page]

    flush()
    return merged


def _chunk_paragraphs(
    paragraphs: list[tuple[str, int]],
    source_file: str,
    category: str,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    current_parts: list[str] = []
    current_pages: list[int] = []
    current_len = 0

    def flush_chunk() -> None:
        nonlocal current_parts, current_pages, current_len
        if not current_parts:
            return

        text = "\n\n".join(current_parts).strip()
        if text:
            chunks.append(
                DocumentChunk(
                    text=text,
                    source_file=source_file,
                    category=category,
                    chunk_index=len(chunks),
                    page_numbers=sorted(set(current_pages)),
                )
            )

        overlap = current_parts[-OVERLAP_PARAGRAPHS:] if OVERLAP_PARAGRAPHS else []
        overlap_pages = current_pages[-OVERLAP_PARAGRAPHS:] if OVERLAP_PARAGRAPHS else []
        current_parts = overlap.copy()
        current_pages = overlap_pages.copy()
        current_len = sum(len(part) for part in current_parts) + max(
            0, len(current_parts) - 1
        ) * 2

    for text, page in paragraphs:
        if _is_heading(text) and current_parts and current_len >= MIN_CHUNK_CHARS:
            flush_chunk()

        projected_len = current_len + len(text) + (2 if current_parts else 0)
        if current_parts and projected_len > MAX_CHUNK_CHARS:
            flush_chunk()

        current_parts.append(text)
        if page not in current_pages:
            current_pages.append(page)
        current_len = sum(len(part) for part in current_parts) + max(
            0, len(current_parts) - 1
        ) * 2

    flush_chunk()
    return chunks


def extract_text_blocks(pdf_path: Path) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            blocks.extend(_extract_page_blocks(page))
    return blocks


def chunk_pdf(
    pdf_path: Path,
    source_file: str,
    category: str,
) -> list[DocumentChunk]:
    blocks = extract_text_blocks(pdf_path)
    paragraphs = _blocks_to_paragraphs(blocks)
    paragraphs = _merge_short_paragraphs(paragraphs)
    return _chunk_paragraphs(paragraphs, source_file, category)


def parse_all_documents(project_root: Path | None = None) -> list[DocumentChunk]:
    root = project_root or PROJECT_ROOT
    all_chunks: list[DocumentChunk] = []

    for entries in DOCUMENT_CATALOG.values():
        for filename, category in entries:
            pdf_path = root / filename
            if not pdf_path.exists():
                raise FileNotFoundError(f"Expected PDF not found: {pdf_path}")

            file_chunks = chunk_pdf(pdf_path, filename, category)
            all_chunks.extend(file_chunks)

    return all_chunks


def chunk_counts_by_file(chunks: list[DocumentChunk]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.source_file] = counts.get(chunk.source_file, 0) + 1
    return counts


def print_chunk_summary(chunks: list[DocumentChunk]) -> None:
    counts = chunk_counts_by_file(chunks)
    print(f"Total chunks: {len(chunks)}")
    print("Chunks per file:")
    for filename in sorted(counts):
        category = next(
            cat
            for entries in DOCUMENT_CATALOG.values()
            for name, cat in entries
            if name == filename
        )
        print(f"  [{category}] {filename}: {counts[filename]}")


if __name__ == "__main__":
    parsed = parse_all_documents()
    print_chunk_summary(parsed)
