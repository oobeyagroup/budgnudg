# Budgnudg

Budgnudg is a Django-based financial transaction management system designed to import, categorize, review, and report on transactions from multiple bank and credit card sources. It supports a workflow for mapping CSV files to your internal `Transaction` model, previewing imports, and resolving duplicates.

## Features

### Transaction Management
- **Multi-step CSV import flow**:
  1. **Upload** – Select a CSV file and mapping profile.
  2. **Preview** – Review parsed transactions before committing.
  3. **Review One-by-One** – Step through transactions for manual edits.
  4. **Confirm & Save** – Persist transactions to the database.
- **Duplicate detection** – Skip or flag transactions already in the system.
- **CSV mapping profiles** – Map arbitrary CSV headers to your model fields.
- **Bank account association** – Link imports to existing or new accounts.

### Categorization & Payoree Suggestions
- **Category hierarchy** – Top-level categories and subcategories.
- **Fuzzy matching** – Suggest subcategories based on past transactions.
- **Payoree suggestions** – Auto-fill known merchants or payees.

### Reporting
- **Account time span report**
- **Income statement report**
- **Uncategorized transactions list**

### Admin & Lists
- **Transactions list view** – Paginated, sortable, and filterable.
- **Category list**
- **Payoree list**
- **Bank accounts list**
---

## Technology Stack

- **Backend**: Django 5.2+
- **Frontend**: Bootstrap 5 (with `django-widget-tweaks` for form styling)
- **Database**: SQLite (default) — can be swapped for PostgreSQL or MySQL
- **Python**: 3.13 (tested)
- **Testing**: pytest + pytest-django

## Project Structure
- **budgnudg/**                  # Django project root
- **settings.py**
- **urls.py**
- **transactions/**              # Main application
- **models.py**
- **views/**                  # Split by domain (import_flow, dashboard, list, etc.)
- **templates/transactions/**
- **services/**               # Helpers, CSV parsing, categorization logic
- **tests/**                 # pytest tests
- **csv_mappings.json**           # Field mapping profiles
- **requirements.txt**
- **README.md**

## Installation

1. **Clone the repository**

    ```bash
    git clone https://github.com/YOUR_USERNAME/budgnudg.git
    cd budgnudg
    ```
2. **Create a virtual environment & install dependencies**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3. **Set up the database**

    ```bash
    python manage.py migrate
    ```
4. **Create a superuser**

    ```bash
    python manage.py createsuperuser
    ```
5. **Run the development server**
  ```bash
  python manage.py runserver
  ```

## Testing
```bash
pytest --tb=short -v
```


## CSV Import Workflow

1. Navigate to `/transactions/import/transactions/`
2. Select your CSV file, mapping profile, and bank account.
3. Preview the parsed transactions.
4. Review transactions one by one.
5. Confirm to save — duplicates and errors are logged/skipped.

## Development Notes
### Typing Approach: *Typed Edges, Dynamic Core*  

**budgnudg** uses type hints to improve clarity and catch bugs early, without trying to force Django’s dynamic ORM into a fully static type system.  

- **Typed edges** – Functions, service layers, and utility modules have clear type annotations for inputs/outputs. We use `TypedDict`, `Protocol`, and `Optional` where stable types are known.  
- **Dynamic core** – Django models and reverse relations rely on runtime attribute creation. We don’t over-annotate these; `# type: ignore` is used sparingly where static analysis can’t infer types.  
- **Tooling** – `mypy` with `django-stubs` provides better model/queryset awareness, while still allowing Django’s dynamic patterns.  

This approach gives us **strong static checks where it’s practical** while keeping development friction low.  

**Example:**  
```python
rows = batch.rows.order_by("row_index").all()  # type: ignore[attr-defined]
```
ImportBatch.rows is a reverse relation dynamically added by Django, so Pylance/mypy can’t see it at analysis time.  We explicitly tell the type checker to ignore the “unknown attribute” warning while retaining runtime correctness.

### Other Notes
- **Large CSV imports** (>250 rows) trigger a warning in the logs.  For very large files, consider refactoring session storage to use a temporary table or cache.

- **Mapping Profiles**: Currently stored as JSON; migration to database-backed mappings is planned.
- **Testing**: Uses `pytest` + `pytest-django` for unit testing.

### end‑to‑end picture
how a CSV row (a plain Python `dict`) moves through your ingest pipeline and becomes a `Transaction`.

#### Core data structures (mental model)
 - CSV row (`dict`) – what `csv.DictReader` yields, e.g. 

```
 {
  "Posting Date": "07/11/2025", 
  "Description": "Test", 
  "Amount": "1.23"
 }
```

 - Mapped row (`dict`) – after applying a `MappingProfile.column_map`, e.g. 
 
 ```
 {
  "date": "07/11/2025", 
  "description": "Test", 
  "amount": "1.23", 
  "_date": date(2025,7,11), 
  "_amount": Decimal("1.23"), 
  "_suggestions": {"subcategory": "Fast Food"}, 
  "_errors": []
  }
 ```

 - `ImportBatch` (DB row) – one upload; stores metadata (filename, header list, status).
 - `ImportRow` (DB row) – one line in the CSV; JSON fields like raw (original CSV row dict), parsed (mapped row dict), plus norm_date, norm_amount, flags, and errors.

#### Upload → create batch + raw rows
1.	User uploads a CSV at `/ingest/upload/`.
2.	You create an ImportBatch (`filename`, `uploaded_by`, `status=“uploaded”`).
3.	You parse the file once to get the header and rows (each a dict from the CSV).
4.	For each CSV row, create an `ImportRow`:
 -- `raw` = the unmodified CSV row dict (JSONField)
 -- `row_index` = position in CSV
 -- leave parsed/norm_date/norm_amount empty for now.
    
  Outcome: DB now has 1 `ImportBatch` + N `ImportRow` records holding the `“raw”` dicts.

#### Apply profile (mapping) → preview
1.	User selects a `MappingProfile` (e.g., “visa”).
2.	For each `ImportRow` in that batch:
    - Call `map_row_with_profile(raw_row=dict, profile=MappingProfile)`
    - That produces the mapped dict out with:
    -- Canonical keys (date, description, amount, etc.)
    -- Parsed “norm” helpers (_date, _amount)
    -- Suggestions (_suggestions)
    -- Validation errors (_errors)
    - Optionally flatten a few of those into columns on `ImportRow` for fast filtering/sorting:
      -- norm_date = out.get("_date")
      -- norm_amount = out.get("_amount")
      -- suggestions = out.get("_suggestions")
      -- errors = out.get("_errors")
 - Save parsed = out (JSON) on the row.
3.	In the preview template, you iterate batch.rows and render:
  -- Original fields (via r.raw|get_item:"Posting Date")
  -- Normalized fields (r.norm_date, r.norm_amount)
  -- Flags (r.is_duplicate) and r.errors  
  
    __Outcome:__ The dicts are central—raw is the input dict, parsed is the output dict. The template shows both.

#### Duplicate pass (optional but recommended)
 - After mapping, run a duplicate check per ImportRow:
 - Query Transaction for (date, amount, description, bank_account) match.
 - Set r.is_duplicate = True if found.
 - You can also embed a _is_duplicate flag into parsed for consistency, but it’s cleaner to keep a proper boolean column on the model.

#### Commit → create Transactions
When the user clicks Commit for a batch:



```
services/mapping.py
def commit_batch(batch, bank_account: str):
    ...
    with dbtx.atomic():  # outer transaction for the whole batch
        for r in batch.rows.filter(is_duplicate=False):
            try:
                with dbtx.atomic():  # per-row savepoint
                  ...
                      obj = Transaction.objects.create(**data)
                  ...
```
1.	Wrap the whole commit in an outer transaction.atomic() for integrity.	
2.	Iterate rows not marked as duplicates. For each row:
 - Build the Transaction payload from parsed (dict) and normalized columns:

  ```python
  data = {
    "date": r.norm_date,                         # from _date
    "amount": r.norm_amount,                     # from _amount
    "description": parsed.get("description",""),
    "bank_account": chosen_bank,
  }
  ```
  __Outcome:__ Each ImportRow.parsed dict has served as the source of truth for constructing a real Transaction. Errors get captured on a row and the commit continues.

#### Where dicts matter (short answers)
 - raw_row (dict) – trusted snapshot of the CSV line. Never mutate—store it as-is on ImportRow.raw.
 - parsed (dict) – computed by map_row_with_profile. Contains canonical keys, helpers (_date, _amount), and _suggestions/_errors. Save it to ImportRow.parsed so you can re‑render previews without re‑mapping on every request.
 - Template access – use a get_item filter to pull dynamic keys from raw when rendering the original CSV columns.
 - Commit – read from ImportRow.norm_date/ norm_amount (fast, typed), fall back to parsed when needed (e.g., description), and translate suggestions to FKs.

#### Minimal code “map” (what calls what)
 - UploadView.post → creates ImportBatch + ImportRow(raw=row_dict)
 - ApplyProfile (or PreviewView) → for each row: parsed = map_row_with_profile(raw, profile) → save parsed, norm_*, errors, is_duplicate
 - Preview template → shows raw via get_item, norm_*, and errors
 - CommitView.post → loops non‑duplicate rows → builds Transaction data from norm_* + parsed → creates Transaction inside per‑row atomic block

#### Practical advice
 - Keep all per‑row transforms in the mapped dict; store a couple of denormalized columns on ImportRow for speed.
 - Never throw away raw; you’ll need it when a profile changes or for audits.
 - Keep suggestions advisory—users can override during “review one by one” before commit.
 - Log row‑level errors with exc_info=True; annotate ImportRow.errors so the UI can surface them.



## License

MIT License
