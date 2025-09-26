# Import CSV Transactions

**Status**: 🔄 NEEDS ATDD CONVERSION  
**Epic**: Data Ingestion  
**Priority**: Must Have  
**Estimated Effort**: 5 points  
**Actual Effort**: 8 points  
**ATDD Status**: Legacy format - needs conversion to ATDD criteria format  

## User Story

As a **personal finance user**, I want to **upload CSV files containing my bank transaction data** so that **I can quickly import months of historical transactions into my budget tracking system**.

## Business Context

Users often export transaction data from their banks or financial institutions as CSV files. Manual entry would be time-prohibitive for historical data analysis and budget creation.

## Acceptance Criteria

### Must Have Functionality
- [ ] ✅ Given a valid CSV file with transaction data, when I upload it via the web interface, then the transactions are parsed and imported into the database
- [ ] ✅ Given a CSV file with standard bank columns (date, amount, description), when I upload it, then the system automatically maps columns to transaction fields
- [ ] ✅ Given duplicate transactions in my CSV, when I import, then the system detects and prevents duplicate imports
- [ ] ✅ Given an invalid CSV format, when I try to upload, then I receive clear error messages explaining what's wrong

### Error Handling
- [ ] ✅ Given a CSV with malformed dates, when I import, then I see specific row-level errors with suggestions for fixing
- [ ] ✅ Given a CSV that's too large, when I upload, then I get a clear file size limit message
- [ ] ✅ Given network interruption during upload, when the process fails, then I can resume or restart the import

### Data Validation
- [ ] ✅ Given imported transactions, when they're saved, then amounts are properly formatted as decimals
- [ ] ✅ Given transaction descriptions, when they're imported, then they're cleaned and standardized
- [ ] ✅ Given transaction dates, when imported, then they're parsed correctly regardless of common date formats

## MoSCoW Prioritization

### Must Have ✅
- CSV file upload interface
- Basic column mapping (date, amount, description)
- Duplicate detection
- Error reporting for invalid data
- Transaction parsing and storage

### Should Have ✅
- Multiple date format support (MM/DD/YYYY, DD/MM/YYYY, etc.)
- Amount format handling (negatives, parentheses, currency symbols)
- Preview before import functionality
- Import progress indicators

### Could Have ✅
- Custom column mapping interface
- Import history and rollback
- Batch processing for large files
- CSV template download

### Won't Have (Current Version)
- ❌ Real-time bank API integration
- ❌ Multi-file simultaneous upload
- ❌ Advanced data transformation rules
- ❌ Integration with QuickBooks/Mint formats

## Technical Implementation Notes

**Files**: `ingest/views.py`, `ingest/forms.py`, `ingest/services/csv_processor.py`  
**Models**: Transaction, ImportLog  
**Templates**: `ingest/upload.html`, `ingest/upload_results.html`  

## Testing Strategy

- Unit tests for CSV parsing edge cases
- Integration tests for complete upload workflow
- Performance tests with large CSV files
- User acceptance testing with real bank export files

## Success Metrics

- ✅ Users can import 1000+ transactions in under 30 seconds
- ✅ 95%+ successful import rate for standard bank CSV formats
- ✅ Zero data corruption incidents
- ✅ Clear error messages for 100% of failure cases

## Lessons Learned

- **Date parsing complexity**: Required more robust handling than initially estimated
- **Memory usage**: Large CSVs needed streaming processing approach
- **User feedback**: Progress indicators were crucial for user confidence
- **Edge cases**: Bank CSV formats vary more than anticipated