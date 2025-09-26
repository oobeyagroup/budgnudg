"""
Simple Django view to serve the ATDD dashboard.
Add this to your main urls.py for easy access.
"""

from django.http import FileResponse, Http404
from django.shortcuts import render
from pathlib import Path
from django.conf import settings
import os


def atdd_dashboard(request):
    """Serve the ATDD dashboard HTML file."""
    dashboard_path = Path(settings.BASE_DIR) / "docs" / "atdd_dashboard" / "index.html"

    if not dashboard_path.exists():
        raise Http404(
            "ATDD dashboard not found. Run 'python manage.py generate_atdd_dashboard' first."
        )

    return FileResponse(open(dashboard_path, "rb"), content_type="text/html")


def generate_and_serve_dashboard(request):
    """Generate and serve the ATDD dashboard."""
    from django.core.management import call_command
    from io import StringIO
    import sys

    # Capture command output
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()

    try:
        # Generate the dashboard
        call_command("generate_atdd_dashboard", "--generate-only")
        output = mystdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # Serve the generated dashboard
    return atdd_dashboard(request)
