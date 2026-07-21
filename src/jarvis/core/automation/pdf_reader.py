# src/jarvis/core/automation/pdf_reader.py
#
# WHY THIS FILE EXISTS:
# Lets JARVIS read PDF files — extracting their text so you can ask
# things like "summarize this PDF" or "what does page 3 say about X."
#
# WHY pypdf: it's a small, pure-Python library (no external binaries or
# heavy downloads, unlike something like Ollama) that's actively
# maintained and handles the vast majority of real-world PDFs.
#
# HONEST LIMITATION: pypdf extracts TEXT. If a PDF is a scanned image
# (no actual text layer — just a picture of a page), there is no text
# to extract, and this will return an empty or near-empty result. True
# OCR (reading text out of an image) would need a much heavier
# dependency (e.g. Tesseract), which we're deliberately not adding.

from pathlib import Path

import pypdf

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class PDFReadError(Exception):
    """Raised when a PDF file can't be found, opened, or read."""


# Cap how much text we hand back in one go. A tool result this large
# would bloat the conversation sent to Gemini on every subsequent
# message (expensive, and closer to hitting free-tier limits) — for
# a genuinely huge PDF, truncating with a clear note is better than
# silently blowing up the request size.
_MAX_CHARACTERS = 12000


def read_pdf(filepath: str, max_pages: int = None) -> str:
    """
    Extract text from a PDF file.

    Args:
        filepath: Path to the PDF file, e.g. "~/Documents/report.pdf".
        max_pages: If given, only read the first this-many pages
            (useful for a quick look at a huge document without
            extracting the whole thing).

    Returns:
        The extracted text, prefixed with a small header noting the
        source file and page count. Truncated with a clear note if it
        exceeds _MAX_CHARACTERS.

    Raises:
        PDFReadError: if the file doesn't exist, isn't a valid/readable
            PDF, or is password-protected (which pypdf can't read
            without the password — not supported here, to avoid a
            confusing partial-read scenario).
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        raise PDFReadError(f"No file found at '{path}'.")

    try:
        reader = pypdf.PdfReader(path)
    except pypdf.errors.PdfReadError as error:
        raise PDFReadError(f"'{path}' doesn't appear to be a valid/readable PDF: {error}")

    if reader.is_encrypted:
        raise PDFReadError(
            f"'{path}' is password-protected. JARVIS can't read encrypted PDFs."
        )

    total_pages = len(reader.pages)
    pages_to_read = reader.pages[:max_pages] if max_pages else reader.pages

    logger.info(
        "Reading PDF '%s' (%d of %d pages)", path, len(pages_to_read), total_pages
    )

    text_parts = []
    for page_number, page in enumerate(pages_to_read, start=1):
        # extract_text() can return an empty string for a page with no
        # real text layer (e.g. a scanned image) — that's expected and
        # not an error, so we just include whatever came back.
        page_text = page.extract_text() or ""
        text_parts.append(f"--- Page {page_number} ---\n{page_text}")

    full_text = "\n\n".join(text_parts).strip()

    header = f"[PDF: {path.name}, {total_pages} page(s) total]\n\n"

    if not full_text:
        return header + (
            "No extractable text was found. This PDF may be a scanned "
            "image without a real text layer — JARVIS can't OCR images."
        )

    combined = header + full_text

    if len(combined) > _MAX_CHARACTERS:
        combined = (
            combined[:_MAX_CHARACTERS]
            + f"\n\n[Truncated — showing the first {_MAX_CHARACTERS} characters "
            f"of a longer document. Ask about a specific page for more detail.]"
        )

    return combined
