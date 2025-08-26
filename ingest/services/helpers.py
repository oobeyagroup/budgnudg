from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Tuple
import csv, logging
from io import StringIO
log = logging.getLogger(__name__)

def iter_csv(file_or_text):
    if hasattr(file_or_text, "read"):
        content = file_or_text.read()
    else:
        content = file_or_text
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = str(content)
        if text.startswith("\ufeff"):  # BOM in str
            text = text.lstrip("\ufeff")
    reader = csv.DictReader(StringIO(text), skipinitialspace=True)
    for i, row in enumerate(reader, start=1):
        cleaned = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v)
                    for k,v in row.items() }
        if not any((str(v).strip() if v is not None else "") for v in cleaned.values()):
            log.warning("iter_csv: skip blank row %d", i)
            continue
        yield cleaned

def read_uploaded_text(file):
    raw = file.read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8-sig", errors="replace"), getattr(file, "name", "upload.csv")
    return str(raw), getattr(file, "name", "upload.csv")


def collect_gifs(
    source_root: Path | str = ".",
    dest_dir: Path | str = "check_images",
    min_bytes: int = 1500,
) -> list[Tuple[Path, Path]]:
    """
    Recursively find .gif files under `source_root` larger than `min_bytes`,
    copy them into `dest_dir`, and prefix each copied filename with the first
    8 chars of its immediate parent folder name.

    Returns a list of (src, dest) path pairs for copied files.
    """
    source_root = Path(source_root).resolve()
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Tuple[Path, Path]] = []

    # Walk tree and gather candidate files
    for src in source_root.rglob("*.gif"):
        # Skip files inside dest_dir
        try:
            # If dest_dir is a parent of src, skip
            src.relative_to(dest_dir)
            continue
        except ValueError:
            pass

        if src.is_file() and src.stat().st_size > min_bytes:
            parent = src.parent.name
            prefix = parent[:8] if parent else ""
            base = src.name
            name, dot, ext = base.partition(".")
            candidate = dest_dir / f"{prefix}_{base}"

            # Ensure unique filename if collision
            if candidate.exists():
                i = 1
                while True:
                    alt = dest_dir / f"{prefix}_{name}_{i}{dot}{ext}" if dot else dest_dir / f"{prefix}_{name}_{i}"
                    if not alt.exists():
                        candidate = alt
                        break
                    i += 1

            # Copy with metadata preserved
            shutil.copy2(src, candidate)
            copied.append((src, candidate))

    return copied


if __name__ == "__main__":
    # Minimal CLI usage: python utils/collect_gifs.py [source_root] [dest_dir] [min_bytes]
    import argparse

    parser = argparse.ArgumentParser(description="Collect GIFs into a single folder with prefixed names.")
    parser.add_argument("source_root", nargs="?", default=".", help="Root folder to search (default: current dir)")
    parser.add_argument("dest_dir", nargs="?", default="check_images", help="Destination folder (default: check_images)")
    parser.add_argument("--min-bytes", type=int, default=1500, help="Minimum file size in bytes (default: 1500)")
    args = parser.parse_args()

    results = collect_gifs(args.source_root, args.dest_dir, args.min_bytes)
    for src, dst in results:
        print(f"Copied: {src} -> {dst}")
