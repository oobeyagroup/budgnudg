from django.core.management.base import BaseCommand
from django.db.models import Count
from transactions.models import Transaction


class Command(BaseCommand):
    help = 'Analyze categorization errors in transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-examples',
            action='store_true',
            help='Show example transactions for each error type',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Transaction Categorization Error Analysis')
        )
        self.stdout.write('=' * 60)
        
        # Overall statistics
        total_transactions = Transaction.objects.count()
        error_transactions = Transaction.objects.filter(
            categorization_error__isnull=False
        ).count()
        success_transactions = total_transactions - error_transactions
        
        self.stdout.write(f'\nOverall Statistics:')
        self.stdout.write(f'  Total Transactions: {total_transactions}')
        self.stdout.write(f'  Successfully Categorized: {success_transactions}')
        self.stdout.write(f'  Categorization Errors: {error_transactions}')
        
        if total_transactions > 0:
            success_rate = (success_transactions / total_transactions) * 100
            self.stdout.write(f'  Success Rate: {success_rate:.1f}%')
        
        # Error breakdown
        if error_transactions > 0:
            self.stdout.write(f'\nError Breakdown:')
            error_counts = Transaction.objects.filter(
                categorization_error__isnull=False
            ).values('categorization_error').annotate(
                count=Count('id')
            ).order_by('-count')
            
            for error in error_counts:
                error_code = error['categorization_error']
                count = error['count']
                percentage = (count / error_transactions) * 100
                
                # Get human-readable description
                description = Transaction.ERROR_CODES.get(error_code, error_code)
                
                self.stdout.write(
                    f'  {error_code}: {count} ({percentage:.1f}%)'
                )
                self.stdout.write(f'    → {description}')
                
                # Show examples if requested
                if options['show_examples']:
                    examples = Transaction.objects.filter(
                        categorization_error=error_code
                    )[:3]
                    
                    for example in examples:
                        self.stdout.write(
                            f'    Example: {example.date} - '
                            f'{example.description[:50]}... '
                            f'(${example.amount})'
                        )
                
                self.stdout.write('')
        
        # Suggestions for improvement
        if error_transactions > 0:
            self.stdout.write(f'\nSuggestions for Improvement:')
            
            # Check for common patterns
            lookup_failures = Transaction.objects.filter(
                categorization_error__contains='_LOOKUP_FAILED'
            ).count()
            
            no_suggestions = Transaction.objects.filter(
                categorization_error__contains='_NO_'
            ).count()
            
            if lookup_failures > 0:
                self.stdout.write(
                    f'  • Fix {lookup_failures} lookup failures by checking '
                    'category/payoree name mismatches'
                )
                
            if no_suggestions > 0:
                self.stdout.write(
                    f'  • Improve AI suggestions for {no_suggestions} '
                    'transactions with no categorization'
                )
                
            self.stdout.write(
                f'  • Consider adding missing categories to the database'
            )
            self.stdout.write(
                f'  • Review CSV import profiles for mapping accuracy'
            )
