from django.core.management.base import BaseCommand
from django.db import transaction
from transactions.models import Category, Transaction


class Command(BaseCommand):
    help = 'Rebuild the category database with a clean, practical structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-all',
            action='store_true',
            help='Delete all existing categories (WARNING: This will also delete transaction category assignments)',
        )
        parser.add_argument(
            '--create-fresh',
            action='store_true',
            help='Create a fresh set of practical categories',
        )
        parser.add_argument(
            '--delete-transactions',
            action='store_true',
            help='Delete all existing transactions (WARNING: This will delete all transaction data)',
        )

    def handle(self, *args, **options):
        if options['delete_transactions']:
            self.delete_all_transactions()
        
        if options['delete_all']:
            self.delete_all_categories()
        
        if options['create_fresh']:
            self.create_fresh_categories()

    def delete_all_transactions(self):
        self.stdout.write(self.style.WARNING('WARNING: This will delete ALL transactions!'))
        
        with transaction.atomic():
            transaction_count = Transaction.objects.count()
            
            if transaction_count == 0:
                self.stdout.write('No transactions to delete.')
                return
            
            self.stdout.write(f'Deleting {transaction_count} transactions...')
            Transaction.objects.all().delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {transaction_count} transactions')
            )

    def delete_all_categories(self):
        self.stdout.write(self.style.WARNING('WARNING: This will delete all categories and reset transaction category assignments!'))
        
        with transaction.atomic():
            # First, reset all transaction category assignments to avoid foreign key constraints
            transaction_count = Transaction.objects.count()
            self.stdout.write(f'Resetting category assignments for {transaction_count} transactions...')
            
            # We'll need to create a temporary "Uncategorized" category to maintain the non-null constraint
            temp_category, created = Category.objects.get_or_create(
                name='Uncategorized',
                defaults={'parent': None}
            )
            
            # Update all transactions to use the temporary category
            Transaction.objects.update(category=temp_category, subcategory=None)
            
            # Now delete all categories except the temporary one
            categories_to_delete = Category.objects.exclude(id=temp_category.id)
            deleted_count = categories_to_delete.count()
            categories_to_delete.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {deleted_count} categories')
            )
            self.stdout.write(
                self.style.WARNING(f'All {transaction_count} transactions now assigned to "Uncategorized"')
            )

    def create_fresh_categories(self):
        self.stdout.write('Creating fresh category structure...')
        
        # Define a practical category structure for personal finance
        category_structure = {
            'Income': [
                'Salary',
                'Bonus',
                'Investment Income',
                'Other Income'
            ],
            'Housing': [
                'Mortgage/Rent',
                'Property Tax',
                'Home Insurance',
                'HOA Fees',
                'Utilities',
                'Home Maintenance',
                'Home Improvement'
            ],
            'Transportation': [
                'Gas',
                'Car Payment',
                'Car Insurance',
                'Car Maintenance',
                'Public Transit',
                'Parking',
                'Tolls'
            ],
            'Food & Dining': [
                'Groceries',
                'Restaurants',
                'Coffee/Tea',
                'Alcohol',
                'Fast Food'
            ],
            'Health & Medical': [
                'Health Insurance',
                'Doctor Visits',
                'Dental',
                'Vision',
                'Pharmacy',
                'Medical Equipment'
            ],
            'Shopping': [
                'Clothing',
                'Electronics',
                'Home Goods',
                'Personal Care',
                'Gifts',
                'Online Shopping'
            ],
            'Entertainment': [
                'Movies',
                'Concerts/Events',
                'Hobbies',
                'Sports',
                'Subscriptions',
                'Books/Media'
            ],
            'Financial': [
                'Bank Fees',
                'Credit Card Payment',
                'Investment',
                'Savings',
                'Loans',
                'Taxes'
            ],
            'Personal': [
                'Education',
                'Charity',
                'Personal Services',
                'Pet Care'
            ],
            'Business': [
                'Office Supplies',
                'Business Travel',
                'Professional Services',
                'Business Insurance'
            ],
            'Cash & ATM': [],  # No subcategories needed
            'Miscellaneous': []  # Catch-all category
        }
        
        created_categories = 0
        
        with transaction.atomic():
            for category_name, subcategories in category_structure.items():
                # Create parent category
                parent_category, created = Category.objects.get_or_create(
                    name=category_name,
                    parent=None
                )
                if created:
                    created_categories += 1
                    self.stdout.write(f'  Created category: {category_name}')
                
                # Create subcategories
                for subcategory_name in subcategories:
                    subcategory, created = Category.objects.get_or_create(
                        name=subcategory_name,
                        parent=parent_category
                    )
                    if created:
                        created_categories += 1
                        self.stdout.write(f'    Created subcategory: {subcategory_name}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_categories} new categories')
        )
        
        # Show summary
        total_categories = Category.objects.count()
        top_level = Category.objects.filter(parent=None).count()
        subcategories = Category.objects.filter(parent__isnull=False).count()
        
        self.stdout.write(f'\nCategory Summary:')
        self.stdout.write(f'  Total categories: {total_categories}')
        self.stdout.write(f'  Top-level categories: {top_level}')
        self.stdout.write(f'  Subcategories: {subcategories}')
