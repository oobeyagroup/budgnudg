# python manage.py collect_gifs . check_images --min-bytes 1500
from __future__ import annotations
from pathlib import Path
from django.core.management.base import BaseCommand, CommandParser

# Adjust the import path to where you put the module:
from utils.collect_gifs import collect_gifs

class Command(BaseCommand):
    help = "Collect GIFs > N bytes from subfolders into a 'check_images' directory, prefixing filenames."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("source_root", nargs="?", default=".", help="Root folder to search (default: .)")
        parser.add_argument("dest_dir", nargs="?", default="check_images", help="Destination folder (default: check_images)")
        parser.add_argument("--min-bytes", type=int, default=1500, help="Minimum file size in bytes (default: 1500)")

    def handle(self, *args, **options):
        source_root: str = options["source_root"]
        dest_dir: str = options["dest_dir"]
        min_bytes: int = options["min_bytes"]

        results = collect_gifs(Path(source_root), Path(dest_dir), min_bytes)
        for src, dst in results:
            self.stdout.write(self.style.SUCCESS(f"Copied: {src} -> {dst}"))

        self.stdout.write(self.style.NOTICE(f"Total copied: {len(results)}"))