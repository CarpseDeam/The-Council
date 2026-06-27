"""File ingestion — read, combine, and format source documents."""

import os
from pathlib import Path
from typing import List

from councilcast.models import SourceDocument

SUPPORTED_EXTENSIONS: set = {".txt", ".md", ".pdf"}


def read_documents(paths: List[str]) -> List[SourceDocument]:
    """Read supported source files and return SourceDocument objects."""
    documents: List[SourceDocument] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {p}")
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {path.suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        if suffix == ".pdf":
            content = _read_pdf(path)
        else:
            content = path.read_text(encoding="utf-8")
        documents.append(SourceDocument(path=str(path), content=content))
    return documents


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        import pypdf

        reader = pypdf.PdfReader(path)
        texts: List[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
        return "\n".join(texts)
    except ImportError:
        raise ImportError(
            "PDF support requires the 'pypdf' package. Install with: pip install pypdf"
        )


def combine_documents(documents: List[SourceDocument]) -> str:
    """Merge multiple documents into a single text block."""
    parts: List[str] = []
    for doc in documents:
        parts.append(f"--- Source: {doc.path} ---")
        parts.append(doc.content)
        parts.append("")
    return "\n".join(parts)


def format_file_list(documents: List[SourceDocument]) -> str:
    """Format document list for display."""
    lines: List[str] = []
    for i, doc in enumerate(documents, start=1):
        char_count = len(doc.content)
        filename = os.path.basename(doc.path)
        lines.append(f"{i}. {filename} ({char_count} characters)")
    return "\n".join(lines)
