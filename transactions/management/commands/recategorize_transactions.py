from django.core.management.base import BaseCommand
from django.db import transaction
from transactions.models import Category, Transaction
from transactions.categorization import categorize_transaction, safe_category_lookup


class Command(BaseCommand):
    help = 'Re-categorize all transactions using the updated categorization logic'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of transactions to process (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        limit = options.get('limit')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get transactions to recategorize
        transactions = Transaction.objects.select_related('category', 'subcategory')
        if limit:
            transactions = transactions[:limit]
            self.stdout.write(f'Processing {limit} transactions...')
        else:
            total_count = transactions.count()
            self.stdout.write(f'Processing {total_count} transactions...')
        
        successful_updates = 0
        failed_updates = 0
        unchanged = 0
        
        with transaction.atomic():
            for txn in transactions:
                try:
                    # Get suggested categorization
                    suggested_category, suggested_subcategory = categorize_transaction(
                        txn.description, float(txn.amount)
                    )
                    
                    # Look up the actual category objects
                    category_obj, category_error = safe_category_lookup(suggested_category, "AUTO")
                    subcategory_obj = None
                    subcategory_error = None
                    
                    if suggested_subcategory:
                        subcategory_obj, subcategory_error = safe_category_lookup(suggested_subcategory, "AUTO")
                    
                    # Determine what needs updating
                    needs_update = False
                    current_category_name = txn.category.name if txn.category else "None"
                    current_subcategory_name = txn.subcategory.name if txn.subcategory else "None"
                    
                    new_category_name = category_obj.name if category_obj else "ERROR"
                    new_subcategory_name = subcategory_obj.name if subcategory_obj else "None"
                    
                    if category_obj and (not txn.category or txn.category.id != category_obj.id):
                        needs_update = True
                    
                    if ((subcategory_obj and (not txn.subcategory or txn.subcategory.id != subcategory_obj.id)) or
                        (not subcategory_obj and txn.subcategory)):
                        needs_update = True
                    
                    if needs_update:
                        if dry_run:
                            self.stdout.write(
                                f'Would update Transaction {txn.id}: '
                                f'"{current_category_name}" / "{current_subcategory_name}" -> '
                                f'"{new_category_name}" / "{new_subcategory_name}"'
                            )
                        else:
                            if category_obj:
                                txn.category = category_obj
                            if subcategory_obj:
                                txn.subcategory = subcategory_obj
                            elif not subcategory_obj and txn.subcategory:
                                txn.subcategory = None
                            
                            # Clear any previous categorization errors
                            txn.categorization_error = None
                            txn.save(update_fields=['category', 'subcategory', 'categorization_error'])
                        
                        successful_updates += 1
                    else:
                        unchanged += 1
                    
                    if category_error or subcategory_error:
                        error_msg = f"Category: {category_error}, Subcategory: {subcategory_error}"
                        if not dry_run:
                            txn.categorization_error = error_msg
                            txn.save(update_fields=['categorization_error'])
                        failed_updates += 1
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing transaction {txn.id}: {e}')
                    )
                    failed_updates += 1
        
        # Show summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'DRY RUN COMPLETE:')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'RE-CATEGORIZATION COMPLETE:')
            )
        
        self.stdout.write(f'  Transactions updated: {successful_updates}')
        self.stdout.write(f'  Transactions unchanged: {unchanged}')
        self.stdout.write(f'  Transactions with errors: {failed_updates}')
        
        if not dry_run and successful_updates > 0:
            self.stdout.write('\nUpdated transactions are now using the new category structure!')
