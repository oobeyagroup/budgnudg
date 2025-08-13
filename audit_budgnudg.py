# audit_budgnudg.py
# Run: python audit_budgnudg.py
# Outputs: audits/audit_report_<timestamp>.md

import re, datetime, ast
from pathlib import Path

STRICT = False  # set True to make "not found" on required items a FAIL

ROOT = Path(__file__).resolve().parent
AUDITS = ROOT / "audits"
AUDITS.mkdir(exist_ok=True)



OK, WARN, FAIL = "OK", "WARN", "FAIL"
results = []

def status_warn_or_fail():
    return FAIL if STRICT else WARN

def add(check, ok: bool, details_ok: str = "", details_fail: str = ""):
    if ok:
        results.append({"check": check, "status": OK, "details": details_ok})
    else:
        results.append({"check": check, "status": status_warn_or_fail(), "details": details_fail})

def add_fail(check, details=""):
    results.append({"check": check, "status": FAIL, "details": details})

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        add_fail(f"Read file: {p}", str(e))
        return ""

def find_all_existing(rel_paths):
    out = []
    for rel in rel_paths:
        p = ROOT / rel
        if p.exists():
            out.append(p)
    return out

def match_any(pattern, texts_by_file, flags=0):
    """Return (matched_bool, [files]) for which pattern matches."""
    matched_files = []
    rx = re.compile(pattern, flags)
    for p, txt in texts_by_file.items():
        if rx.search(txt):
            matched_files.append(str(p))
    return (len(matched_files) > 0, matched_files)

def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)

def scan_status_assignments(root: Path):
    """
    Return dict: {status_value: [(path, lineno, target_repr, is_batchy_bool), ...]}
    where target_repr is like "batch.status" or "obj.status".
    """
    hits = {s: [] for s in ALLOWED_STATUS}

    for py in root.rglob("*.py"):
        if should_skip(py):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            continue

        class StatusVisitor(ast.NodeVisitor):
            def visit_Assign(self, node: ast.Assign):
                # We only care about direct attribute assignments like x.status = "committed"
                # (not augmented assigns, which don’t apply here)
                # There can be multiple targets: x.status = y.status = "previewed" – handle each.
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "status":
                        # Value must be a string literal in our allowed set
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            val = node.value.value
                            if val in ALLOWED_STATUS:
                                # Recreate a readable target like "batch.status" or "obj.status"
                                left = target.value
                                if isinstance(left, ast.Name):
                                    name = left.id  # e.g., "batch"
                                elif isinstance(left, ast.Attribute):
                                    # e.g., self.batch -> "self.batch"
                                    parts = []
                                    cur = left
                                    while isinstance(cur, ast.Attribute):
                                        parts.append(cur.attr)
                                        cur = cur.value
                                    if isinstance(cur, ast.Name):
                                        parts.append(cur.id)
                                    parts.reverse()
                                    name = ".".join(parts)
                                else:
                                    name = "<expr>"

                                is_batchy = "batch" in name.lower()
                                target_repr = f"{name}.status"
                                hits[val].append((py, getattr(node, "lineno", 0), target_repr, is_batchy))
                self.generic_visit(node)

        StatusVisitor().visit(tree)

    return hits




# ------------ Candidate file sets (scan ALL that exist) -------------
candidates = {
    "dev_notes": ["DEV_NOTES.md", "docs/DEV_NOTES.md"],
    "models": ["transactions/models.py", "models.py", "core_ingestion.py", "ingest/models.py"],
    "mapping_service": ["transactions/services/mapping.py", "core_ingestion.py", "ingest/services/mapping.py", "ingest/services/staging.py"],
    "commit_service": ["transactions/services/commit.py", "commit_batch.py", "core_ingestion.py", "ingest/services/mapping.py", "ingest/services/staging.py"],
    "admin": ["transactions/admin.py", "admin.py", "ingest/admin.py"],
    "urls": ["transactions/urls.py", "urls.py", "urlpatterns.py", "ingest/urls.py"]
}

files = {k: find_all_existing(v) for k, v in candidates.items()}

# Load text for each category
texts = {k: {p: read_text(p) for p in ps} for k, ps in files.items()}

# --------------- DEV_NOTES ---------------
dev_notes_files = files.get("dev_notes", [])
if not dev_notes_files:
    add_fail("DEV_NOTES present", "No DEV_NOTES.md found in expected locations.")
else:
    add("DEV_NOTES present", True, details_ok="\n    - " + "\n    - ".join(map(str, dev_notes_files)))

# --------------- Models: classes ---------------
models_txt = texts.get("models", {})
for cls in ["MappingProfile", "ImportBatch", "ImportRow"]:
    ok, where = match_any(rf"\bclass\s+{cls}\b.*?:", models_txt, flags=re.DOTALL)
    add(f"Model class exists: {cls}", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, models_txt.keys())) or "No model files read."
    )

# ImportRow fields (very forgiving: name followed by '=' anywhere)
for fld in ["raw", "parsed", "norm_date", "norm_amount", "norm_description",
            "errors", "suggestions", "is_duplicate", "committed_txn_id"]:
    ok, where = match_any(rf"\b{re.escape(fld)}\s*=", models_txt)
    add(f"ImportRow has field: {fld}", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, models_txt.keys()))
    )




# ---- Static check: status literals used in assignments or call kwargs ----

ALLOWED_STATUS = {"uploaded", "previewed", "committing", "committed"}
SKIP_DIRS = {"venv", ".venv", ".git", "migrations", "__pycache__", "node_modules"}

def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)

def scan_status_usage(root: Path):
    hits = {s: [] for s in ALLOWED_STATUS}

    for py in root.rglob("*.py"):
        if should_skip(py):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            continue

        class Visitor(ast.NodeVisitor):
            def visit_Assign(self, node: ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "status":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            val = node.value.value
                            if val in ALLOWED_STATUS:
                                # build a readable LHS like "batch.status" or "self.batch.status"
                                def lhs_name(expr):
                                    if isinstance(expr, ast.Name): return expr.id
                                    if isinstance(expr, ast.Attribute):
                                        parts = []
                                        cur = expr
                                        while isinstance(cur, ast.Attribute):
                                            parts.append(cur.attr)
                                            cur = cur.value
                                        if isinstance(cur, ast.Name): parts.append(cur.id)
                                        parts.reverse()
                                        return ".".join(parts)
                                    return "<expr>"
                                base = lhs_name(target.value)
                                is_batchy = "batch" in (base or "").lower()
                                desc = f"{base}.status = '{val}'"
                                hits[val].append((str(py), getattr(node, "lineno", 0), desc, is_batchy))
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):
                # func(..., status="literal", ...)
                for kw in node.keywords or []:
                    if kw.arg == "status" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        val = kw.value.value
                        if val in ALLOWED_STATUS:
                            # Try to render a function name for context (purely cosmetic)
                            def fn_name(fn):
                                if isinstance(fn, ast.Name): return fn.id
                                if isinstance(fn, ast.Attribute):
                                    parts = []
                                    cur = fn
                                    while isinstance(cur, ast.Attribute):
                                        parts.append(cur.attr)
                                        cur = cur.value
                                    if isinstance(cur, ast.Name): parts.append(cur.id)
                                    parts.reverse()
                                    return ".".join(parts)
                                return "<call>"
                            name = fn_name(node.func)
                            is_batchy = "batch" in name.lower()
                            desc = f"{name}(status='{val}', ...)"
                            hits[val].append((str(py), getattr(node, "lineno", 0), desc, is_batchy))
                self.generic_visit(node)

        Visitor().visit(tree)

    return hits

status_hits = scan_status_usage(ROOT)

def _report_hits(label: str, entries):
    if entries:
        batchy = [e for e in entries if e[3]]
        others = [e for e in entries if not e[3]]
        def fmt(e):
            p, ln, desc, is_batchy = e
            suffix = "  (batch-like)" if is_batchy else ""
            return f"{p}:{ln} — {desc}{suffix}"
        details = "Found:\n    - " + "\n    - ".join([fmt(e) for e in (batchy + others)])
        add(f"Status usage found: '{label}'", True, details_ok=details)
    else:
        add(f"Status usage found: '{label}'", False,
            details_fail=f"No usages found of either `<x>.status = '{label}'` or `status='{label}'` in calls.")

for sv in sorted(ALLOWED_STATUS):
    _report_hits(sv, status_hits.get(sv, []))

# --------------- Mapping service ---------------
mapping_txt = texts.get("mapping_service", {})
ok, where = match_any(r"\bdef\s+apply_profile_to_batch\s*\(", mapping_txt)
if not ok:
    add_fail("apply_profile_to_batch defined",
             "Not found. Searched in:\n    - " + "\n    - ".join(map(str, mapping_txt.keys())))
else:
    results.append({"check":"apply_profile_to_batch defined", "status": OK,
                    "details": "Found in:\n    - " + "\n    - ".join(where)})

for must in [
    r"_json_safe",
    r"row\.parsed",
    r"row\.norm_date",
    r"row\.norm_amount",
    r"row\.norm_description",
    r"row\.suggestions",
    r"row\.errors",
    r"row\.is_duplicate",
    r"batch\.status\s*=\s*[\"']previewed[\"']",
]:
    ok, where = match_any(must, mapping_txt)
    add(f"apply_profile_to_batch uses '{must}'", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, mapping_txt.keys()))
    )

ok, where = match_any(r"from\s+transactions\.services\.helpers\s+import\s+is_duplicate", mapping_txt)
add("Duplicate uses transactions.services.helpers.is_duplicate", ok,
    details_ok="Found in:\n    - " + "\n    - ".join(where),
    details_fail="Searched in:\n    - " + "\n    - ".join(map(str, mapping_txt.keys()))
)

# --------------- Commit service ---------------
commit_txt = texts.get("commit_service", {})
ok, where = match_any(r"\bdef\s+commit_batch\s*\(", commit_txt)
if not ok:
    add_fail("commit_batch defined",
             "Not found. Searched in:\n    - " + "\n    - ".join(map(str, commit_txt.keys())))
else:
    results.append({"check":"commit_batch defined", "status": OK,
                    "details": "Found in:\n    - " + "\n    - ".join(where)})

for must in [
    r"batch\.status\s*=\s*[\"']committing[\"']",
    r"batch\.status\s*=\s*[\"']committed[\"']",
    r"row\.is_duplicate",
    r"row\.committed_txn_id",
    r"Transaction\.objects\.create",
]:
    ok, where = match_any(must, commit_txt)
    add(f"commit_batch uses '{must}'", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, commit_txt.keys()))
    )

# --------------- URLs ---------------
urls_txt = texts.get("urls", {})
for name in ["batch_list", "batch_detail", "upload_csv", "batch_apply_profile", "batch_commit"]:
    ok, where = match_any(re.escape(name), urls_txt)
    add(f"URL name present: {name}", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, urls_txt.keys()))
    )

# --------------- Admin ---------------
admin_txt = texts.get("admin", {})
for must in ["ImportRowInline", "inlines", "list_display", "search_fields", "list_filter"]:
    ok, where = match_any(re.escape(must), admin_txt)
    add(f"Admin config includes '{must}'", ok,
        details_ok="Found in:\n    - " + "\n    - ".join(where),
        details_fail="Searched in:\n    - " + "\n    - ".join(map(str, admin_txt.keys()))
    )

# --------------- Report ---------------
ok_ct = sum(1 for r in results if r["status"] == OK)
warn_ct = sum(1 for r in results if r["status"] == WARN)
fail_ct = sum(1 for r in results if r["status"] == FAIL)

lines = [
    "# budgnudg – DEV_NOTES Compliance Audit",
    f"_Run at {datetime.datetime.now().isoformat(timespec='seconds')}_",
    "",
    f"**Summary:** {ok_ct} OK, {warn_ct} WARN, {fail_ct} FAIL",
    "",
    f"_Strict mode: {'ON' if STRICT else 'OFF'}_",
    "",
]
for r in results:
    emoji = "✅" if r["status"] == OK else ("⚠️" if r["status"] == WARN else "❌")
    out = f"{emoji} **{r['check']}** — {r['status']}"
    if r.get("details"):
        out += f"\n    - {r['details']}"
    lines.append(out)

report = "\n".join(lines)
print(report)

out = AUDITS / f"audit_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
out.write_text(report, encoding="utf-8")
print(f"\nSaved: {out}")