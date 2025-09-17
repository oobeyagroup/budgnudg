from django.core.management.base import BaseCommand
from transactions.models import Transaction, Payoree


class Command(BaseCommand):
    help = 'Apply payoree defaults to transactions that have a payoree but no category'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each transaction',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']

        # Find transactions with payoree but no category
        transactions_to_update = Transaction.objects.filter(
            payoree__isnull=False,
            category__isnull=True
        ).select_related('payoree')

        self.stdout.write(
            self.style.SUCCESS(
                f'Found {transactions_to_update.count()} transactions with payoree but no category'
            )
        )

        if transactions_to_update.count() == 0:
            self.stdout.write('No transactions to update.')
            return

        updated_count = 0
        skipped_count = 0

        for transaction in transactions_to_update:
            payoree = transaction.payoree
            
            # Check if payoree has default category
            if not payoree.default_category:
                if verbose:
                    self.stdout.write(
                        f'SKIP: {transaction.date} | {transaction.description} | '
                        f'Payoree "{payoree.name}" has no default_category'
                    )
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'WOULD UPDATE: {transaction.date} | {transaction.description} | '
                    f'Payoree: {payoree.name} -> '
                    f'Category: {payoree.default_category}, '
                    f'Subcategory: {payoree.default_subcategory or "None"}'
                )
            else:
                # Apply the defaults
                transaction.category = payoree.default_category
                transaction.subcategory = payoree.default_subcategory
                transaction.save()
                
                if verbose:
                    self.stdout.write(
                        f'UPDATED: {transaction.date} | {transaction.description} | '
                        f'Payoree: {payoree.name} -> '
                        f'Category: {payoree.default_category}, '
                        f'Subcategory: {payoree.default_subcategory or "None"}'
                    )
                
                updated_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would update {transactions_to_update.count() - skipped_count} transactions'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would skip {skipped_count} transactions (payoree has no default_category)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} transactions with payoree defaults'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Skipped {skipped_count} transactions (payoree has no default_category)'
                )
            )