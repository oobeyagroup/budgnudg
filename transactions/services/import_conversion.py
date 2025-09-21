# transactions/services/import_conversion.py
"""
Clean interface for converting ImportRow data to Transaction objects.
This service provides a clear boundary between the ingest and transactions apps.
"""
from typing import Dict, Any, Tuple, List, Optional
from decimal import Decimal
from datetime import date
import logging

from django.db import transaction as dbtx
from transactions.models import Transaction, Category, Payoree
from ingest.models import FinancialAccount
from commons.utils import trace

logger = logging.getLogger(__name__)


class ImportRowData:
    """
    Data structure representing an ImportRow's data for transaction conversion.
    This provides a clean interface without direct ImportRow model dependency.
    """
    def __init__(
        self,
        row_index: int,
        date: date,
        amount: Decimal,
        description: str,
        parsed_data: Optional[Dict[str, Any]] = None,
        suggestions: Optional[Dict[str, Any]] = None,
        bank_account: Optional[FinancialAccount] = None,
        source_filename: str = "",
    ):
        self.row_index = row_index
        self.date = date
        self.amount = amount
        self.description = description
        self.parsed_data = parsed_data or {}
        self.suggestions = suggestions or {}
        self.bank_account = bank_account
        self.source_filename = source_filename


class TransactionConversionResult:
    """Result of attempting to convert ImportRow data to a Transaction."""
    def __init__(
        self,
        success: bool,
        transaction: Optional[Transaction] = None,
        errors: Optional[List[str]] = None,
        row_index: Optional[int] = None,
    ):
        self.success = success
        self.transaction = transaction
        self.errors = errors or []
        self.row_index = row_index


class ImportRowConverter:
    """
    Service for converting ImportRow data to Transaction objects.
    Provides clean separation between ingest staging and transaction creation.
    """

    @trace
    def convert_import_row_to_transaction(
        self, 
        import_data: ImportRowData,
        reverse_amounts: bool = False
    ) -> TransactionConversionResult:
        """
        Convert ImportRow data to a Transaction object.
        
        Args:
            import_data: ImportRowData containing all necessary conversion data
            reverse_amounts: Whether to reverse the sign of amounts
            
        Returns:
            TransactionConversionResult with success status and transaction or errors
        """
        try:
            # Build base transaction data
            transaction_data = {
                "date": import_data.date,
                "amount": -import_data.amount if reverse_amounts else import_data.amount,
                "description": import_data.description,
                "bank_account": import_data.bank_account,
                "source": import_data.source_filename or f"import:row:{import_data.row_index}",
            }
            
            # Resolve category and subcategory
            category_result = self._resolve_category_from_import(import_data)
            if category_result.get('category'):
                transaction_data['category'] = category_result['category']
            if category_result.get('subcategory'):
                transaction_data['subcategory'] = category_result['subcategory']
            
            # Resolve payoree
            payoree_result = self._resolve_payoree_from_import(import_data)
            if payoree_result.get('payoree'):
                transaction_data['payoree'] = payoree_result['payoree']
            
            # Collect any errors
            all_errors = category_result.get('errors', []) + payoree_result.get('errors', [])
            if all_errors:
                transaction_data['categorization_error'] = all_errors[0]  # Use first/most significant
            
            # Validate required fields
            if not transaction_data['date'] or transaction_data['amount'] is None:
                return TransactionConversionResult(
                    success=False,
                    errors=['Missing required date or amount'],
                    row_index=import_data.row_index
                )
            
            # Create the transaction
            with dbtx.atomic():
                transaction = Transaction.objects.create(**transaction_data)
                
                return TransactionConversionResult(
                    success=True,
                    transaction=transaction,
                    row_index=import_data.row_index
                )
                
        except Exception as e:
            logger.exception(
                "Failed to convert import row %s to transaction", 
                import_data.row_index
            )
            return TransactionConversionResult(
                success=False,
                errors=[f'Transaction creation failed: {str(e)}'],
                row_index=import_data.row_index
            )

    @trace
    def _resolve_category_from_import(self, import_data: ImportRowData) -> Dict[str, Any]:
        """
        Resolve category and subcategory from ImportRow data.
        Priority: 1) CSV category field, 2) AI suggestions
        """
        errors = []
        category_obj = None
        subcategory_obj = None
        
        # Priority 1: CSV Category field (from parsed data)
        csv_category_name = import_data.parsed_data.get('subcategory')  # CSV 'Category' -> 'subcategory'
        
        if csv_category_name:
            try:
                from transactions.categorization import safe_category_lookup
                subcategory_obj, error_code = safe_category_lookup(csv_category_name, "CSV")
                if error_code:
                    errors.append(error_code)
                elif subcategory_obj and subcategory_obj.parent:
                    category_obj = subcategory_obj.parent
                elif subcategory_obj and not subcategory_obj.parent:
                    # This is actually a top-level category
                    category_obj = subcategory_obj
                    subcategory_obj = None
            except Exception as e:
                errors.append("CSV_SUBCATEGORY_LOOKUP_FAILED")
                logger.warning("CSV category lookup failed for '%s': %s", csv_category_name, e)
        
        # Priority 2: AI-suggested subcategory (fallback if no CSV category)
        if not subcategory_obj and not category_obj:
            ai_category_name = import_data.suggestions.get('subcategory')
            if ai_category_name:
                try:
                    from transactions.categorization import safe_category_lookup
                    subcategory_obj, error_code = safe_category_lookup(ai_category_name, "AI")
                    if error_code:
                        errors.append(error_code)
                    elif subcategory_obj and subcategory_obj.parent:
                        category_obj = subcategory_obj.parent
                    elif subcategory_obj and not subcategory_obj.parent:
                        category_obj = subcategory_obj
                        subcategory_obj = None
                except Exception as e:
                    errors.append("AI_SUBCATEGORY_LOOKUP_FAILED")
                    logger.warning("AI category lookup failed for '%s': %s", ai_category_name, e)
            else:
                errors.append("AI_NO_SUBCATEGORY_SUGGESTION")
        
        return {
            'category': category_obj,
            'subcategory': subcategory_obj,
            'errors': errors
        }

    @trace
    def _resolve_payoree_from_import(self, import_data: ImportRowData) -> Dict[str, Any]:
        """
        Resolve payoree from ImportRow data.
        """
        errors = []
        payoree_obj = None
        
        payoree_name = import_data.suggestions.get('payoree')
        if payoree_name:
            try:
                from transactions.categorization import safe_payoree_lookup
                payoree_obj, error_code = safe_payoree_lookup(payoree_name, "AI")
                if error_code:
                    # Check if this is a "not found" error where we should create new payoree
                    if "PAYOREE_LOOKUP_FAILED" in error_code:
                        # Create new payoree since it doesn't exist
                        try:
                            payoree_obj = Payoree.objects.create(name=payoree_name)
                            logger.debug("Created new payoree: %s", payoree_obj)
                        except Exception as e:
                            errors.append("DATABASE_ERROR")
                            logger.error("Failed to create payoree %s: %s", payoree_name, e)
                    else:
                        # Other errors (DATABASE_ERROR, etc.) - don't try to create
                        errors.append(error_code)
            except Exception as e:
                errors.append("AI_PAYOREE_LOOKUP_FAILED")
                logger.warning("Payoree lookup failed for '%s': %s", payoree_name, e)
        
        return {
            'payoree': payoree_obj,
            'errors': errors
        }


# Singleton instance for easy access
converter = ImportRowConverter()