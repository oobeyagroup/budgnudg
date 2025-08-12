"""
Constants used throughout the application.
"""

# Allowed values for the 'Category' column in processed files
# Removed 'Payment', 'Income', and 'Expense' as they are too generic
ALLOWED_CATEGORIES = {
    'Banking', 'Bills & Utilities', 'Business', 'Education', 'Entertainment',
    'Fees & Adjustments', 'Food & Dining', 'Gifts & Donations', 'Groceries',
    'Health & Medical', 'Home', 'Insurance', 'Personal Care', 'Pets',
    'Shopping', 'Taxes', 'Travel', 'Work', 'Miscellaneous', 'Uncategorized'
}

# Add other constants here as needed
