import csv
import json
import os
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from transactions.models import Transaction
from django.db import IntegrityError

MAPPING_FILE = "csv_mappings.json"

class Command(BaseCommand):
    help = "Import transactions from a CSV file using saved header mapping and duplicate detection."

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        if not os.path.exists(csv_file):
            self.stderr.write(f"File not found: {csv_file}")
            return

        if not os.path.exists(MAPPING_FILE):
            self.stderr.write(f"No mapping file found: {MAPPING_FILE}")
            return

        with open(MAPPING_FILE, 'r') as f:
            all_mappings = json.load(f)

        self.stdout.write("Available mapping profiles:")
        profiles = list(all_mappings.keys())
        for idx, name in enumerate(profiles, start=1):
            self.stdout.write(f"{idx}. {name}")

        while True:
            choice = input("Select a mapping profile by number: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(profiles):
                selected_profile = profiles[int(choice) - 1]
                break
            else:
                self.stdout.write("Invalid selection. Try again.")

        mapping = all_mappings[selected_profile]['mapping']
        self.stdout.write(f"Using mapping profile: {selected_profile}")

        existing_accounts = Transaction.objects.values_list('bank_account', flat=True).distinct()
        existing_accounts = sorted(set(filter(None, existing_accounts)))

        self.stdout.write("\nExisting bank accounts:")
        for idx, acct in enumerate(existing_accounts, start=1):
            self.stdout.write(f"{idx}. {acct}")
        self.stdout.write(f"{len(existing_accounts)+1}. Enter a new account name")

        while True:
            acct_choice = input("Select bank account by number or enter a new name: ").strip()
            if acct_choice.isdigit():
                acct_choice = int(acct_choice)
                if 1 <= acct_choice <= len(existing_accounts):
                    selected_account = existing_accounts[acct_choice - 1]
                    break
                elif acct_choice == len(existing_accounts) + 1:
                    selected_account = input("Enter new bank account name: ").strip()
                    break
            elif acct_choice:
                selected_account = acct_choice
                break
            self.stdout.write("Invalid selection. Try again.")

        self.stdout.write(f"Using bank account: {selected_account}")

        imported_count = 0
        skipped_count = 0
        duplicates_found = []

        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                txn_data = {}
                for csv_col, model_field in mapping.items():
                    value = (row.get(csv_col) or '').strip()
                    if model_field == 'date':
                        txn_data['date'] = self.parse_date(value)
                    elif model_field == 'amount':
                        txn_data['amount'] = Decimal(value)

                    elif model_field == 'subcategory':
                        from transactions.models import Category
                        category_name = value
                        try:
                            subcat = Category.objects.get(name=category_name)
                        except Category.DoesNotExist:
                            self.stderr.write(f"Subcategory '{category_name}' not found. Skipping row.")
                            skipped_count += 1
                            continue
                        txn_data['subcategory'] = subcat
                    else:
                        txn_data[model_field] = value

                txn_data['bank_account'] = selected_account  # set selected bank account

                # Duplicate detection
                potential_duplicates = Transaction.objects.filter(
                    date=txn_data.get('date'),
                    amount=txn_data.get('amount'),
                    description=txn_data.get('description'),
                    bank_account=txn_data.get('bank_account')
                )

                if potential_duplicates.exists():
                    duplicates_found.append((txn_data, list(potential_duplicates)))
                    skipped_count += 1
                    continue  # Skip this transaction

                txn = Transaction(**txn_data)
                txn.source = csv_file  # Save source filename
                try:
                    txn.save()
                    imported_count += 1
                except IntegrityError:
                    skipped_count += 1
                    duplicates_found.append((txn_data, ['DB constraint violation']))

        self.stdout.write(self.style.SUCCESS(f"Import complete: {imported_count} imported, {skipped_count} skipped."))
        if duplicates_found:
            self.stdout.write("Potential duplicates found:")
            for dup in duplicates_found:
                self.stdout.write(f"CSV Data: {dup[0]}")
                for existing in dup[1]:
                    self.stdout.write(f" - Existing: {existing}")

    def parse_date(self, value):
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"]
        for fmt in date_formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unrecognized date format: '{value}'")