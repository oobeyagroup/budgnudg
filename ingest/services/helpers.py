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