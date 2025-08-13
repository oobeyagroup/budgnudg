from .helpers import iter_csv, read_uploaded_text
from ingest.models import ImportBatch, ImportRow, MappingProfile

def create_batch_from_csv(file, user=None, profile: MappingProfile|None=None):
    text, name = read_uploaded_text(file)
    rows = list(iter_csv(text))
    header = list(rows[0].keys()) if rows else []
    batch = ImportBatch.objects.create(
        created_by=user, source_filename=name, header=header,
        row_count=len(rows), profile=profile, status= "uploaded"
    )
    ImportRow.objects.bulk_create([
        ImportRow(batch=batch, row_index=i, raw=r) for i, r in enumerate(rows)
    ], batch_size=1000)
    return batch