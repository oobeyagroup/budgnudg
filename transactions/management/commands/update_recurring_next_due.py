from django.core.management.base import BaseCommand
from django.utils import timezone
from transactions.models import RecurringSeries
from datetime import timedelta


class Command(BaseCommand):
    help = 'Update next_due field for RecurringSeries records that have it set to None'

    def handle(self, *args, **options):
        today = timezone.now().date()
        updated_count = 0

        for series in RecurringSeries.objects.filter(next_due__isnull=True):
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
                    f'next_due set to {next_due}'
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} RecurringSeries records')
        )
