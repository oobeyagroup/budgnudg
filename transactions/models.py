from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )

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
    payoree = models.CharField(max_length=255)  # Who it went to/from
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