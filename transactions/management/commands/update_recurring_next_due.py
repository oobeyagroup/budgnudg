from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from transactions.models import RecurringSeries
from datetime import timedelta


class Command(BaseCommand):
    help = "Update next_due field for RecurringSeries records that have it set to None or in the past, and optionally mark series as manually disabled"

    def add_arguments(self, parser):
        parser.add_argument(
            "--disable-payoree",
            type=str,
            help="Mark all recurring series for a specific payoree as manually disabled",
        )
        parser.add_argument(
            "--list-disabled",
            action="store_true",
            help="List all manually disabled recurring series",
        )

    def handle(self, *args, **options):
        if options["list_disabled"]:
            self.list_disabled_series()
            return

        if options["disable_payoree"]:
            self.disable_payoree_series(options["disable_payoree"])
            return

        # Original functionality for updating next_due dates
        self.update_next_due_dates()

    def update_next_due_dates(self):
        today = timezone.now().date()
        updated_count = 0

        # Update records with null next_due OR past next_due
        for series in RecurringSeries.objects.filter(
            models.Q(next_due__isnull=True) | models.Q(next_due__lt=today)
        ):
            reference_date = None

            if series.last_seen:
                reference_date = series.last_seen
            elif series.first_seen:
                reference_date = series.first_seen

            if reference_date:
                # Calculate next due date based on interval
                if series.interval == "weekly":
                    days = 7
                elif series.interval == "biweekly":
                    days = 14
                elif series.interval == "monthly":
                    days = 30
                elif series.interval == "quarterly":
                    days = 90
                elif series.interval == "yearly":
                    days = 365
                else:
                    days = 30  # default to monthly

                next_due = reference_date + timedelta(days=days)

                # If calculated next_due is in the past, add another interval
                while next_due < today:
                    next_due += timedelta(days=days)

                series.next_due = next_due
                series.save()
                updated_count += 1

                self.stdout.write(
                    f'Updated {series.payoree.name if series.payoree else "Unknown"}: '
                    f"next_due set to {next_due}"
                )

        self.stdout.write(f"Updated {updated_count} recurring series next_due dates")

    def disable_payoree_series(self, payoree_name):
        """Mark all recurring series for a payoree as manually disabled"""
        from transactions.models import Payoree

        try:
            payoree = Payoree.objects.get(name__iexact=payoree_name)
            series_count = RecurringSeries.objects.filter(
                payoree=payoree, manually_disabled=False
            ).update(manually_disabled=True)

            self.stdout.write(
                f"Marked {series_count} recurring series for payoree '{payoree.name}' as manually disabled"
            )
        except Payoree.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Payoree '{payoree_name}' not found"))

    def list_disabled_series(self):
        """List all manually disabled recurring series"""
        disabled_series = RecurringSeries.objects.filter(manually_disabled=True)

        if not disabled_series:
            self.stdout.write("No manually disabled recurring series found")
            return

        self.stdout.write("Manually disabled recurring series:")
        for series in disabled_series:
            payoree_name = series.payoree.name if series.payoree else "Unknown"
            self.stdout.write(
                f"  - ID {series.id}: {payoree_name} (${series.amount_cents/100:.2f} {series.interval})"
            )
