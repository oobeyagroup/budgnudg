from django.core.management.base import BaseCommand
from transactions.models import Payoree, Transaction


class Command(BaseCommand):
    help = "Set default category and subcategory for payorees based on their first transaction"

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

        # Get all payorees
        payorees = Payoree.objects.all()
        total_payorees = payorees.count()
        updated_count = 0

        self.stdout.write(f"Processing {total_payorees} payorees...")

        for payoree in payorees:
            # Find the first transaction for this payoree (ordered by date)
            first_transaction = (
                Transaction.objects.filter(payoree=payoree)
                .exclude(category__isnull=True)
                .order_by("date")
                .first()
            )

            if first_transaction:
                # Check if we need to update the payoree
                needs_update = (
                    payoree.default_category != first_transaction.category
                    or payoree.default_subcategory != first_transaction.subcategory
                )

                if needs_update:
                    if dry_run:
                        self.stdout.write(
                            f"Would update {payoree.name}: "
                            f'category="{first_transaction.category.name if first_transaction.category else None}", '
                            f'subcategory="{first_transaction.subcategory.name if first_transaction.subcategory else None}" '
                            f"(from transaction on {first_transaction.date})"
                        )
                    else:
                        payoree.default_category = first_transaction.category
                        payoree.default_subcategory = first_transaction.subcategory
                        payoree.save()
                        self.stdout.write(
                            f"Updated {payoree.name}: "
                            f'category="{first_transaction.category.name if first_transaction.category else None}", '
                            f'subcategory="{first_transaction.subcategory.name if first_transaction.subcategory else None}" '
                            f"(from transaction on {first_transaction.date})"
                        )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{payoree.name}: already has correct defaults"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"{payoree.name}: no transactions found with categories"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN COMPLETE: Would update {updated_count} out of {total_payorees} payorees"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"COMPLETE: Updated {updated_count} out of {total_payorees} payorees"
                )
            )
