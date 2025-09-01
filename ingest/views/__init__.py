"""Package-level exports for the ingest.views package.

Some tests and callsites import names from "ingest.views" (the package)
expecting certain functions to be available at the package-level. The
real implementations live in "ingest.views.views"; re-export them here
to preserve that import surface.
"""

from .views import (
    upload_csv,
    apply_profile,
    commit,
    BatchPreviewView,
    CreateMappingProfileView,
    preview_batch,
)

# apply_profile_to_batch and commit_batch are implemented in the mapping
# service module; re-export them here to preserve the historical import
# surface used in unit tests (tests patch 'ingest.views.apply_profile_to_batch').
from ingest.services.mapping import apply_profile_to_batch, commit_batch

__all__ = [
    "upload_csv",
    "apply_profile",
    "commit",
    "BatchPreviewView",
    "CreateMappingProfileView",
    "apply_profile_to_batch",
    "commit_batch",
    "preview_batch",
]
