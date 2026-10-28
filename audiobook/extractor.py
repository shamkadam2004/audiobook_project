"""Stage 1 - Text extraction (PDF / TXT) with error handling."""
import os
from typing import Callable, List, Optional


class ExtractionError(Exception):
    pass


def _read_text_file(path: str) -> str:
    """Try several encodings so encoding issues don't crash the run."""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_pdf_pages(path: str) -> List[str]:
    try:
        from PyPDF2 import PdfReader
    except ImportError:  # modern fallback
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ExtractionError("Install PyPDF2:  pip install PyPDF2") from e
    try:
        reader = PdfReader(path)
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                raise ExtractionError("PDF is password protected.")
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Could not open PDF: {e}") from e
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # bad page: skip, keep going
            pages.append("")
    return pages


def extract_text(path: str, page_range: Optional[tuple] = None,
                 log: Callable[[str], None] = lambda m: None) -> str:
    """Return the text of a .pdf or .txt file.

    page_range: optional (first, last) 1-based inclusive page numbers (PDF only).
    """
    if not os.path.isfile(path):
        raise ExtractionError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        text = _read_text_file(path)
    elif ext == ".pdf":
        pages = _read_pdf_pages(path)
        if page_range:
            a, b = page_range
            pages = pages[max(a - 1, 0):b]
        empty = sum(1 for p in pages if not p.strip())
        if empty:
            log(f"Skipped {empty} empty page(s) (scanned images have no text).")
        text = "\n\n".join(p for p in pages if p.strip())
    else:
        raise ExtractionError("Unsupported file type. Use .pdf or .txt")
    if not text.strip():
        raise ExtractionError("No readable text found in the file.")
    return text
