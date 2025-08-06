import re
from django.db import models
from django.db.models import Q


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


class Transaction(models.Model):
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

    subcategory = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    def __str__(self):
        truncated = self.description
        if len(truncated) > 50:
            truncated = truncated[:50] + "..."
        return f"{self.date} - {truncated}"

    def category(self):
        return self.subcategory.parent if self.subcategory else None