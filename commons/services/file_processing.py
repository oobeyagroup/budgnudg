# commons/services/file_processing.py
"""
Shared file processing utilities for CSV imports and file handling.
"""
import csv
from io import StringIO
import logging
from typing import Iterable, Dict, Any, Tuple
from commons.utils import trace

logger = logging.getLogger(__name__)


@trace
def read_uploaded_text(django_file) -> Tuple[str, str]:
    """
    Read an uploaded file-like object from a Django form into a decode-safe text string.
    Returns (text, original_filename).
    """
    name = getattr(django_file, "name", "uploaded.csv")
    # decode with utf-8-sig to handle BOM; fall back to plain utf-8
    try:
        text = django_file.read().decode("utf-8-sig")
    except AttributeError:
        # already str-like?
        text = django_file.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    return text, name


@trace
def iter_csv(file_or_text) -> Iterable[Dict[str, Any]]:
    """
    Yield dict rows from CSV:
      - Accepts str, bytes, or file-like.
      - Decodes UTF-8 with BOM.
      - Skips blank lines/fully-empty rows.
      - Strips header/value whitespace.
    """
    # Normalize to text
    if hasattr(file_or_text, "read"):
        content = file_or_text.read()
    else:
        content = file_or_text

    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    elif isinstance(content, str):
        text = content
    else:
        raise ValueError(f"Expected str, bytes, or file-like, got {type(content)}")

    # Parse CSV
    lines = text.strip().split("\n")
    if not lines:
        return

    reader = csv.DictReader(StringIO(text))

    # Clean headers
    if reader.fieldnames:
        reader.fieldnames = [h.strip() for h in reader.fieldnames if h]

    for row in reader:
        # Skip empty rows
        if not any(v.strip() for v in row.values() if v):
            continue

        # Strip all values
        clean_row = {k.strip(): v.strip() if v else v for k, v in row.items()}
        yield clean_row
