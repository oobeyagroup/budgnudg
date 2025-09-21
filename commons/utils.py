# commons/utils.py
"""
Shared utilities used across multiple Django apps in BudgNudg.
"""
import functools
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def trace(func):
    """Decorator for tracing function calls in debug mode."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("TRACE: Called %s.%s", func.__module__, func.__qualname__)
        return func(*args, **kwargs)
    return wrapper


def normalize_description(desc):
    """
    Normalize transaction descriptions for comparison and similarity matching.
    Removes common variable elements like transaction IDs and web identifiers.
    """
    import re

    if not desc:
        return ""
    
    # Remove 11-digit numbers and WEB ID numbers
    cleaned = re.sub(r"\b\d{11}\b", "", desc)
    cleaned = re.sub(r"WEB ID[:]? \d+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.lower().strip()


def parse_date(value):
    """Parse date from common formats used in CSV imports."""
    if not value:
        return None
        
    date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in date_formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def read_uploaded_file(uploaded_file, encoding="utf-8-sig"):
    """
    Safely read uploaded file content, handling BOM and decoding.
    Returns decoded string.
    """
    return uploaded_file.read().decode(encoding)