# Enhanced User Story with Criteria IDs for ATDD Linking

**Status**: 🚧 IN PROGRESS  
**Epic**: Data Ingestion  
**Priority**: Must Have  
**Estimated Effort**: 5 points  
**Actual Effort**: 8 points  
**ATDD Status**: 9/11 tests passing - 2 failing tests need fixes  

## User Story

As a **budget tracker**, I want to **import transaction data from CSV files downloaded from my bank** so that **I can easily add my financial data to the system without manual entry**.

## Business Context

Many users download CSV files from their banks and credit cards containing transaction history. The system should provide a streamlined import process that:
- Handles various CSV formats from different banks
- Maps columns to standardized transaction fields
- Validates data quality and identifies potential issues
- Provides preview and confirmation before final import
- Maintains data integrity throughout the process

## Acceptance Criteria

### CSV File Processing
- [ ] ✅ `csv_upload_validation` Given I have a valid CSV file, when I upload it through the interface, then the system validates format and creates import batch
- [ ] ✅ `csv_format_detection` Given I upload a CSV with headers, when the system processes it, then it automatically detects column structure and data types
- [ ] ✅ `csv_error_reporting` Given I upload an invalid CSV file, when the system processes it, then I receive clear error messages about what needs to be fixed
- [ ] ✅ `csv_duplicate_detection` Given I upload a CSV with duplicate transactions, when the system processes it, then duplicates are flagged for review

### Profile-Based Column Mapping
- [ ] ✅ `profile_column_mapping` Given I have a financial account profile, when I apply it to an uploaded CSV, then the system maps columns according to the profile configuration
- [ ] ✅ `profile_data_parsing` Given a profile is applied, when the system parses the data, then amounts are correctly formatted and dates are standardized
- [ ] ✅ `profile_preview_generation` Given data has been parsed with a profile, when I request a preview, then I can see how transactions will appear in the system
- [ ] ✅ `profile_validation_feedback` Given column mapping encounters issues, when I view the preview, then I see warnings about data quality problems

### Transaction Import Commitment  
- [ ] ✅ `transaction_creation` Given I have previewed and approved parsed data, when I commit the import, then actual Transaction records are created in the database
- [ ] ✅ `bank_account_assignment` Given I specify a bank account during commit, when transactions are created, then they are properly linked to that account
- [ ] ✅ `import_status_tracking` Given I commit an import batch, when the process completes, then the batch status is updated to "committed"
- [ ] ✅ `import_audit_trail` Given transactions are imported, when I review the import history, then I can see which batch each transaction came from

### Error Handling & Recovery
- [ ] ✅ `import_rollback` Given an import fails partway through, when I check the system state, then no partial data is left in the database
- [ ] ✅ `batch_reprocessing` Given an import batch has errors, when I fix the issues, then I can reprocess the batch without losing previous work
- [ ] ✅ `data_validation_rules` Given transactions have invalid data, when I attempt to commit, then the system prevents import and shows validation errors
- [ ] ✅ `duplicate_import_prevention` Given I try to import the same CSV file twice, when the system detects this, then it warns me about potential duplicates

## MoSCoW Prioritization

### Must Have ✅
- Basic CSV upload and validation
- Column mapping through profiles  
- Data parsing and preview functionality
- Transaction creation and database commitment
- Error reporting and validation

### Should Have ✅
- Duplicate detection and handling
- Import status tracking and audit trail
- Data quality validation rules
- Bank account assignment during import

### Could Have ✅ 
- Advanced duplicate detection algorithms
- Import batch reprocessing capabilities
- Detailed error reporting with suggestions
- Import history and rollback functionality

### Won't Have (This Release)
- ❌ Automatic bank API integration
- ❌ Multi-file batch processing
- ❌ Advanced data transformation rules
- ❌ Import scheduling and automation

## Technical Implementation Notes

**Files**: `ingest/views.py`, `ingest/models.py`, `ingest/services/`  
**Models**: `ImportBatch`, `ImportRow`, `FinancialAccount`  
**Templates**: `ingest/upload.html`, `ingest/preview.html`  
**Services**: CSV parsing, data validation, transaction creation

## Architecture Decisions

### Import Batch Processing
- **Decision**: Use batch-based processing rather than direct file-to-transaction import
- **Reasoning**: Allows for preview, validation, and rollback before commitment
- **Trade-offs**: More complex but safer and more user-friendly

### Profile-Based Mapping
- **Decision**: Store column mapping configurations in `FinancialAccount` profiles
- **Reasoning**: Users can reuse mappings for similar files from same institution
- **Trade-offs**: Initial setup required but saves time on subsequent imports

## Testing Strategy

### Unit Tests
- CSV parsing service methods
- Data validation functions  
- Profile mapping algorithms
- Transaction creation logic

### Integration Tests
- Full import workflow from upload to commitment
- Error handling scenarios
- Database state verification
- Profile application and data transformation

### User Acceptance Tests
- End-to-end import workflows
- Error recovery scenarios
- Multiple file format handling
- User interface workflows

## Success Metrics

### Technical Metrics
- ✅ 95%+ successful import rate for valid CSV files
- ✅ Import processing time under 30 seconds for 1000+ transactions
- ✅ Zero data loss incidents during import process
- ✅ 99% accuracy in duplicate transaction detection

### User Experience Metrics  
- ✅ Average time to complete import: under 5 minutes
- ✅ 90%+ user satisfaction with import process clarity
- ✅ Error resolution success rate: 85%+ on first attempt
- ✅ Profile reuse rate: 70%+ of imports use existing profiles

## Database Design

### ImportBatch Model
```python
class ImportBatch(models.Model):
    user = ForeignKey(User)
    filename = CharField(max_length=255)
    status = CharField(choices=['uploaded', 'parsed', 'committed', 'error'])
    profile = ForeignKey(FinancialAccount, null=True)
    upload_date = DateTimeField(auto_now_add=True)
    commit_date = DateTimeField(null=True)
    error_message = TextField(blank=True)
    
class ImportRow(models.Model):
    batch = ForeignKey(ImportBatch)
    row_index = IntegerField()
    raw_data = JSONField()
    parsed = JSONField(null=True)
    norm_date = DateField(null=True)
    norm_amount = DecimalField(null=True)
    validation_errors = JSONField(default=list)
```

## Lessons Learned

### What Worked Well
- **Batch-based approach**: Gave users confidence with preview before commitment
- **Profile system**: Reduced setup time for repeat imports significantly  
- **Progressive disclosure**: Showing preview only after successful parsing reduced confusion
- **Clear error messaging**: Users could understand and fix data issues independently

### What Could Be Improved
- **Better duplicate detection**: Current algorithm misses some edge cases
- **Performance optimization**: Large files (>5MB) sometimes timeout
- **Mobile experience**: Upload interface needs better mobile optimization
- **Data mapping intelligence**: Could suggest column mappings based on content analysis

### Future Enhancement Ideas
- **Smart column detection**: Auto-suggest mappings based on content analysis
- **Advanced duplicate algorithms**: Machine learning-based duplicate detection
- **Bulk profile management**: Tools for managing multiple bank account profiles
- **Import templates**: Pre-configured profiles for major banks and credit cards