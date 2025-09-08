from django.core.management.base import BaseCommand
from transactions.models import Payoree, Transaction


class Command(BaseCommand):
    help = "Reset transaction needs_level values to match their payoree's default_needs_level"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without actually making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Get all transactions that have a payoree with default_needs_level
        transactions = Transaction.objects.filter(
            payoree__isnull=False, payoree__default_needs_level__isnull=False
        ).select_related("payoree")

        total_transactions = transactions.count()
        updated_count = 0

        self.stdout.write(f"Processing {total_transactions} transactions...")

        for transaction in transactions:
            # Check if the transaction's needs_level differs from payoree's default
            if transaction.needs_level != transaction.payoree.default_needs_level:
                if dry_run:
                    self.stdout.write(
                        f"Would update transaction {transaction.id} ({transaction.description[:50]}...): "
                        f"needs_level from {transaction.needs_level} to {transaction.payoree.default_needs_level}"
                    )
                else:
                    transaction.needs_level = transaction.payoree.default_needs_level
                    transaction.save()
                    self.stdout.write(
                        f"Updated transaction {transaction.id} ({transaction.description[:50]}...): "
                        f"needs_level from {transaction.needs_level} to {transaction.payoree.default_needs_level}"
                    )
                updated_count += 1
            else:
                # Transaction already has correct needs_level
                pass  # We can be quiet about these to reduce noise

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN COMPLETE: Would update {updated_count} out of {total_transactions} transactions"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"COMPLETE: Updated {updated_count} out of {total_transactions} transactions"
                )
            )
