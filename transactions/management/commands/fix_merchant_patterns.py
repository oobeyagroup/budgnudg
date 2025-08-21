#!/usr/bin/env python3
"""
Management command to fix incorrect merchant extraction patterns.
Useful when the extraction logic produces inconsistent or incorrect keys.

Usage:
    python manage.py fix_merchant_patterns --list                    # Show all patterns
    python manage.py fix_merchant_patterns --find "STARBUCKS"       # Find patterns containing text
    python manage.py fix_merchant_patterns --merge "OLD" "NEW"      # Merge OLD pattern into NEW
    python manage.py fix_merchant_patterns --rename "OLD" "NEW"     # Rename OLD pattern to NEW
    python manage.py fix_merchant_patterns --clean                  # Remove patterns with zero count
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Q, Count
from transactions.models import LearnedSubcat, LearnedPayoree
from transactions.categorization import extract_merchant_from_description


class Command(BaseCommand):
    help = 'Fix and manage merchant extraction patterns in learning data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all learned patterns',
        )
        parser.add_argument(
            '--find',
            type=str,
            help='Find patterns containing the specified text',
        )
        parser.add_argument(
            '--merge',
            nargs=2,
            metavar=('OLD_PATTERN', 'NEW_PATTERN'),
            help='Merge old pattern into new pattern (combines counts)',
        )
        parser.add_argument(
            '--rename',
            nargs=2,
            metavar=('OLD_PATTERN', 'NEW_PATTERN'),
            help='Rename old pattern to new pattern',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove patterns with zero count',
        )
        parser.add_argument(
            '--test-extraction',
            type=str,
            help='Test merchant extraction on a sample description',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_patterns()
        elif options['find']:
            self.find_patterns(options['find'])
        elif options['merge']:
            old_pattern, new_pattern = options['merge']
            self.merge_patterns(old_pattern, new_pattern, options['dry_run'])
        elif options['rename']:
            old_pattern, new_pattern = options['rename']
            self.rename_pattern(old_pattern, new_pattern, options['dry_run'])
        elif options['clean']:
            self.clean_empty_patterns(options['dry_run'])
        elif options['test_extraction']:
            self.test_extraction(options['test_extraction'])
        else:
            self.print_help('manage.py', 'fix_merchant_patterns')

    def list_patterns(self):
        """List all learned patterns with counts"""
        self.stdout.write(self.style.SUCCESS('\n=== LEARNED SUBCATEGORY PATTERNS ==='))
        subcats = (LearnedSubcat.objects
                  .values('key')
                  .annotate(total_count=Sum('count'), 
                           pattern_count=Count('id'))
                  .order_by('-total_count'))
        
        for item in subcats:
            # Get associated subcategories for this key
            associated = LearnedSubcat.objects.filter(key=item['key']).select_related('subcategory__parent')
            subcategory_info = []
            for assoc in associated:
                if assoc.subcategory.parent:
                    subcategory_info.append(f"{assoc.subcategory.parent.name}/{assoc.subcategory.name} ({assoc.count}×)")
                else:
                    subcategory_info.append(f"{assoc.subcategory.name} ({assoc.count}×)")
            
            self.stdout.write(f"Key: '{item['key']}' | Total: {item['total_count']} | Categories: {', '.join(subcategory_info)}")

        self.stdout.write(self.style.SUCCESS('\n=== LEARNED PAYOREE PATTERNS ==='))
        payorees = (LearnedPayoree.objects
                   .values('key')
                   .annotate(total_count=Sum('count'),
                            pattern_count=Count('id'))
                   .order_by('-total_count'))
        
        for item in payorees:
            # Get associated payorees for this key
            associated = LearnedPayoree.objects.filter(key=item['key']).select_related('payoree')
            payoree_info = [f"{assoc.payoree.name} ({assoc.count}×)" for assoc in associated]
            
            self.stdout.write(f"Key: '{item['key']}' | Total: {item['total_count']} | Payorees: {', '.join(payoree_info)}")

    def find_patterns(self, search_text):
        """Find patterns containing specified text"""
        search_text = search_text.upper()
        self.stdout.write(self.style.SUCCESS(f'\n=== PATTERNS CONTAINING "{search_text}" ==='))
        
        # Search subcategory patterns
        subcats = LearnedSubcat.objects.filter(key__icontains=search_text).select_related('subcategory__parent')
        for subcat in subcats:
            parent = subcat.subcategory.parent.name if subcat.subcategory.parent else "NO PARENT"
            self.stdout.write(f"SUBCAT: '{subcat.key}' → {parent}/{subcat.subcategory.name} ({subcat.count}×)")
        
        # Search payoree patterns  
        payorees = LearnedPayoree.objects.filter(key__icontains=search_text).select_related('payoree')
        for payoree in payorees:
            self.stdout.write(f"PAYOREE: '{payoree.key}' → {payoree.payoree.name} ({payoree.count}×)")

    def merge_patterns(self, old_pattern, new_pattern, dry_run=False):
        """Merge old pattern into new pattern, combining counts"""
        old_pattern = old_pattern.upper()
        new_pattern = new_pattern.upper()
        
        self.stdout.write(self.style.WARNING(f'\n=== MERGING "{old_pattern}" INTO "{new_pattern}" ==='))
        
        # Handle subcategory patterns
        old_subcats = LearnedSubcat.objects.filter(key=old_pattern)
        for old_subcat in old_subcats:
            try:
                # Try to find existing pattern with new key
                new_subcat, created = LearnedSubcat.objects.get_or_create(
                    key=new_pattern,
                    subcategory=old_subcat.subcategory,
                    defaults={'count': 0, 'last_seen': old_subcat.last_seen}
                )
                
                action = "CREATE" if created else "MERGE"
                self.stdout.write(f"SUBCAT {action}: '{new_pattern}' → {old_subcat.subcategory.name} ({old_subcat.count}× + {new_subcat.count}× = {old_subcat.count + new_subcat.count}×)")
                
                if not dry_run:
                    new_subcat.count += old_subcat.count
                    new_subcat.save()
                    old_subcat.delete()
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error merging subcat pattern: {e}"))

        # Handle payoree patterns
        old_payorees = LearnedPayoree.objects.filter(key=old_pattern)
        for old_payoree in old_payorees:
            try:
                new_payoree, created = LearnedPayoree.objects.get_or_create(
                    key=new_pattern,
                    payoree=old_payoree.payoree,
                    defaults={'count': 0, 'last_seen': old_payoree.last_seen}
                )
                
                action = "CREATE" if created else "MERGE"
                self.stdout.write(f"PAYOREE {action}: '{new_pattern}' → {old_payoree.payoree.name} ({old_payoree.count}× + {new_payoree.count}× = {old_payoree.count + new_payoree.count}×)")
                
                if not dry_run:
                    new_payoree.count += old_payoree.count
                    new_payoree.save()
                    old_payoree.delete()
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error merging payoree pattern: {e}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made. Run without --dry-run to apply changes."))

    def rename_pattern(self, old_pattern, new_pattern, dry_run=False):
        """Rename a pattern key"""
        old_pattern = old_pattern.upper()
        new_pattern = new_pattern.upper()
        
        self.stdout.write(self.style.WARNING(f'\n=== RENAMING "{old_pattern}" TO "{new_pattern}" ==='))
        
        # Update subcategory patterns
        subcat_count = LearnedSubcat.objects.filter(key=old_pattern).count()
        if subcat_count > 0:
            self.stdout.write(f"Renaming {subcat_count} subcategory patterns")
            if not dry_run:
                LearnedSubcat.objects.filter(key=old_pattern).update(key=new_pattern)

        # Update payoree patterns  
        payoree_count = LearnedPayoree.objects.filter(key=old_pattern).count()
        if payoree_count > 0:
            self.stdout.write(f"Renaming {payoree_count} payoree patterns")
            if not dry_run:
                LearnedPayoree.objects.filter(key=old_pattern).update(key=new_pattern)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made. Run without --dry-run to apply changes."))

    def clean_empty_patterns(self, dry_run=False):
        """Remove patterns with zero count"""
        self.stdout.write(self.style.WARNING('\n=== CLEANING EMPTY PATTERNS ==='))
        
        empty_subcats = LearnedSubcat.objects.filter(count=0)
        empty_payorees = LearnedPayoree.objects.filter(count=0)
        
        self.stdout.write(f"Found {empty_subcats.count()} empty subcategory patterns")
        self.stdout.write(f"Found {empty_payorees.count()} empty payoree patterns")
        
        if not dry_run:
            deleted_subcats, _ = empty_subcats.delete()
            deleted_payorees, _ = empty_payorees.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_subcats} subcategory patterns"))
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_payorees} payoree patterns"))
        else:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made. Run without --dry-run to apply changes."))

    def test_extraction(self, description):
        """Test merchant extraction on sample description"""
        self.stdout.write(self.style.SUCCESS(f'\n=== TESTING EXTRACTION ==='))
        self.stdout.write(f"Input: '{description}'")
        
        extracted = extract_merchant_from_description(description)
        self.stdout.write(f"Extracted: '{extracted}'")
        
        # Check if this key exists in learned patterns
        subcat_matches = LearnedSubcat.objects.filter(key=extracted)
        payoree_matches = LearnedPayoree.objects.filter(key=extracted)
        
        if subcat_matches.exists():
            self.stdout.write(self.style.SUCCESS("SUBCATEGORY MATCHES:"))
            for match in subcat_matches:
                parent = match.subcategory.parent.name if match.subcategory.parent else "NO PARENT"
                self.stdout.write(f"  → {parent}/{match.subcategory.name} ({match.count}×)")
        
        if payoree_matches.exists():
            self.stdout.write(self.style.SUCCESS("PAYOREE MATCHES:"))
            for match in payoree_matches:
                self.stdout.write(f"  → {match.payoree.name} ({match.count}×)")
                
        if not subcat_matches.exists() and not payoree_matches.exists():
            self.stdout.write(self.style.WARNING("No learned patterns match this extracted key"))
