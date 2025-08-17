import re
from django.db import models
from django.db.models import Q

# -----------------------------------------------------
class Payoree(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_payoree')
    ]
        indexes = [
            models.Index(fields=['name']),
    ]
        
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    @staticmethod
    def normalize_name(name):
        """Convert name to lowercase and remove spaces and special characters."""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    @classmethod
    def get_existing(cls, name):
        """Find existing Payoree with normalized name."""
        if not name:  # Return None early if name is empty or None
            return None
    
        normalized = cls.normalize_name(name)
        for payoree in cls.objects.all():
            if cls.normalize_name(payoree.name) == normalized:
                return payoree
        return None   
    
# -----------------------------------------------------
class Category(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['parent', 'name'], name='unique_subcategory_per_parent'),
            models.UniqueConstraint(fields=['name'], condition=Q(parent__isnull=True), name='unique_top_level_category')
    ]
        indexes = [
            models.Index(fields=['name']),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=30, choices=[
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('transfer', 'Transfer'),
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity')
    ], default='expense')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )

    @staticmethod
    def normalize_name(name):
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def __str__(self):
        return self.name

    def is_top_level(self):
        return self.parent is None
# -----------------------------------------------------
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# -----------------------------------------------------    
class Transaction(models.Model):
    '''Model representing a financial transaction.
        Attributes:
        - source: Filename of the CSV file this transaction was imported from.
        - bank_account: Financial institution or account name.
        - sheet_account: Type of account (e.g., income, expense).
        - date: Date of the transaction.
        - description: Description of the transaction.
        - amount: Amount of the transaction.
        - account_type: Type of account (e.g., checking, savings).
        - check_num: Check number if applicable.
        - memo: Additional notes or memo for the transaction.
        - payoree: **Foreign key to Payoree model. 
        - subcategory: **Foreign key to Category model for categorization.
        - categorization_error: Error description when categorization fails
        - tags: **Many-to-many relationship with Tag model for tagging transactions.    
    '''
    
    # Error codes for categorization failures
    ERROR_CODES = {
        # Subcategory errors
        'CSV_SUBCATEGORY_LOOKUP_FAILED': 'CSV subcategory name not found in database',
        'AI_SUBCATEGORY_LOOKUP_FAILED': 'AI suggested subcategory not found in database',
        'USER_SUBCATEGORY_OVERRIDE_FAILED': 'User-entered subcategory not found in database',
        'AI_NO_SUBCATEGORY_SUGGESTION': 'AI could not suggest a subcategory',
        'MULTIPLE_SUBCATEGORIES_FOUND': 'Multiple subcategories found for name',
        
        # Payoree errors
        'CSV_PAYOREE_LOOKUP_FAILED': 'CSV payoree name not found in database',
        'AI_PAYOREE_LOOKUP_FAILED': 'AI suggested payoree not found in database', 
        'USER_PAYOREE_OVERRIDE_FAILED': 'User-entered payoree not found in database',
        'AI_NO_PAYOREE_SUGGESTION': 'AI could not suggest a payoree',
        'MULTIPLE_PAYOREES_FOUND': 'Multiple payorees found for name',
        
        # System errors
        'CATEGORIES_NOT_IMPORTED': 'Category database is empty or not loaded',
        'PAYOREES_NOT_IMPORTED': 'Payoree database is empty or not loaded',
        'DATABASE_ERROR': 'Database connection or query error',
        'PROFILE_MAPPING_ERROR': 'Wrong CSV profile applied',
        'DATA_CORRUPTION': 'Invalid or corrupted category data',
        'BATCH_PROCESSING_FAILED': 'Row failed during batch processing',
        'LEARNED_DATA_CORRUPT': 'Historical learning data unavailable'
    }
    
    class Meta:
       constraints = [
        models.UniqueConstraint(fields=['date', 'amount', 'description', 'bank_account'], name='unique_transaction')
    ]
       indexes = [
        models.Index(fields=['date', 'amount', 'description', 'bank_account']),
    ]

    source = models.CharField(max_length=255)  # Filename of CSV
    bank_account = models.CharField(max_length=100)  # Financial institution
    sheet_account = models.CharField(max_length=100)  # Income, expense, etc.

    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    account_type = models.CharField(max_length=50)  # Checking, savings, etc.
    check_num = models.CharField(max_length=50, blank=True, null=True)
    payoree = models.ForeignKey(
        Payoree,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    ) 
    memo = models.TextField(blank=True, null=True)

    # Clear separation: every transaction has a category, optionally a subcategory
    category = models.ForeignKey(
        Category,
        related_name='transactions_in_category',
        null=True,  # Temporarily allow null to support import process
        blank=True,
        on_delete=models.PROTECT,  # Prevent deletion of categories with transactions
        help_text="Primary category for this transaction"
    )
    
    subcategory = models.ForeignKey(
        Category,
        related_name='transactions_in_subcategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Optional subcategory - must belong to the specified category"
    )
    
    # Unified error field for categorization failures
    categorization_error = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Describes why subcategory/payoree assignment failed"
    )
    
    tags = models.ManyToManyField(Tag, blank=True, related_name='transactions')

    def __str__(self):
        truncated = self.description
        if len(truncated) > 50:
            truncated = truncated[:50] + "..."
        return f"{self.date} - {truncated}"

    def clean(self):
        """Validate that subcategory belongs to the specified category."""
        super().clean()
        if self.subcategory and self.category:
            if self.subcategory.parent != self.category:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'subcategory': f'Subcategory "{self.subcategory.name}" must belong to category "{self.category.name}"'
                })
    
    def get_top_level_category(self):
        """Get the top-level category for this transaction."""
        if self.category:
            # If we have a category, return it (could be top-level or not)
            cat = self.category
            while cat.parent:
                cat = cat.parent
            return cat
        elif self.subcategory:
            # Fallback: derive from subcategory for backward compatibility
            cat = self.subcategory
            while cat.parent:
                cat = cat.parent
            return cat
        return None
    
    def has_categorization_error(self):
        """Check if this transaction has any categorization errors."""
        return bool(self.categorization_error)
    
    def get_error_description(self):
        """Get human-readable description of categorization error."""
        if not self.categorization_error:
            return None
        return self.ERROR_CODES.get(self.categorization_error, self.categorization_error)
    
    def is_successfully_categorized(self):
        """Check if transaction has both category and payoree successfully assigned."""
        return self.payoree is not None and not self.has_categorization_error()
    
    def effective_category_display(self):
        """Get display value for category (name or error)."""
        if self.category:
            return self.category.name
        elif self.has_categorization_error():
            return f"ERROR: {self.categorization_error}"
        else:
            return "Uncategorized"
    
    def effective_subcategory_display(self):
        """Get display value for subcategory (name or error)."""
        if self.subcategory:
            return self.subcategory.name
        elif self.has_categorization_error():
            return f"ERROR: {self.categorization_error}"
        else:
            return "Uncategorized"
    
    def effective_payoree_display(self):
        """Get display value for payoree (name or error)."""
        if self.payoree:
            return self.payoree.name
        elif self.has_categorization_error():
            return f"ERROR: {self.categorization_error}"
        else:
            return "Unknown"
    
# transactions/models.py
class LearnedSubcat(models.Model):
    key = models.CharField(max_length=200, db_index=True)   # normalized merchant or signature
    subcategory = models.ForeignKey(Category, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)
    last_seen = models.DateField(auto_now=True)

    class Meta:
        unique_together = ('key', 'subcategory')

class LearnedPayoree(models.Model):
    key = models.CharField(max_length=200, db_index=True)
    payoree = models.ForeignKey(Payoree, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)
    last_seen = models.DateField(auto_now=True)

    class Meta:
        unique_together = ('key', 'payoree')

class KeywordRule(models.Model):
    """
    User-defined keyword rules for categorization.
    Allows users to specify that certain words/phrases strongly influence category assignment.
    """
    keyword = models.CharField(max_length=100, help_text='Word or phrase that influences categorization')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='keyword_rules')
    subcategory = models.ForeignKey(Category, blank=True, null=True, on_delete=models.CASCADE, related_name='keyword_subcategory_rules')
    priority = models.IntegerField(default=100, help_text='Higher numbers = higher priority (1-1000)')
    is_active = models.BooleanField(default=True)
    created_by_user = models.BooleanField(default=True, help_text='True if created by user, False if system default')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'keyword']
        indexes = [
            models.Index(fields=['keyword'], name='kw_rule_keyword_idx'),
            models.Index(fields=['priority'], name='kw_rule_priority_idx'),
            models.Index(fields=['is_active'], name='kw_rule_active_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['keyword', 'category', 'subcategory'], name='unique_keyword_category'),
        ]

    def __str__(self):
        if self.subcategory:
            return f'"{self.keyword}" → {self.category.name}/{self.subcategory.name}'
        return f'"{self.keyword}" → {self.category.name}'

    def clean(self):
        """Validate that subcategory belongs to the specified category."""
        super().clean()
        if self.subcategory and self.category:
            if self.subcategory.parent != self.category:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'subcategory': f'Subcategory "{self.subcategory.name}" must belong to category "{self.category.name}"'
                })