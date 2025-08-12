"""
Mapping rules for normalizing categories to the allowed set of categories.

This module provides a mapping from various category names found in source data
to the standard set of allowed categories defined in config.constants.ALLOWED_CATEGORIES.
"""

# Mapping from source category names to standard allowed categories
CATEGORY_MAPPING = {
    # Income-related categories
    'Income': 'Work',
    'Salary': 'Work',
    'Distribution': 'Work',
    'Oobeya Distribution': 'Work',
    'Oobeya Capital': 'Work',
    'Marcus Savings': 'Banking',
    
    # Banking and financial
    'Banking Fees': 'Fees & Adjustments',
    'Credit Card Payment': 'Banking',
    'Cash & ATM': 'Banking',
    'Auto Payment': 'Banking',
    'Mortgage & Rent': 'Housing',
    'Property Tax': 'Taxes',
    
    # Bills & Utilities
    'Utilities': 'Bills & Utilities',
    'Cable/Internet': 'Bills & Utilities',
    'Mobile Phone': 'Bills & Utilities',
    
    # Health & Medical
    'Health & Wellness': 'Health & Medical',
    'Health & Fitness': 'Health & Medical',
    'Health Insurance': 'Insurance',
    'Life Insurance': 'Insurance',
    'HSA': 'Health & Medical',
    
    # Shopping and retail
    'Amazon': 'Shopping',
    'Clothing': 'Shopping',
    'Software': 'Shopping',
    'Liquor': 'Shopping',
    
    # Food & Dining
    'Restaurant GE': 'Food & Dining',
    'Restaurant Travel': 'Food & Dining',
    'Restaurant Lake': 'Food & Dining',
    
    # Gifts & Donations
    'Gift Received': 'Gifts & Donations',
    'Gift Given': 'Gifts & Donations',
    'gift Given': 'Gifts & Donations',  # Case variation
    'Charity': 'Gifts & Donations',
    'Wedding': 'Gifts & Donations',
    
    # Automotive
    'Automotive': 'Transportation',
    'Auto': 'Transportation',
    'Auto Insurance': 'Insurance',
    'Gas': 'Transportation',
    'Auto Payment': 'Transportation',
    
    # Home
    'Home Services': 'Home',
    'home': 'Home',  # Case variation
    'Lake': 'Home',
    'Mortgage & Rent': 'Home',  # Map to Home instead of Housing
    'Property Tax': 'Home',  # Property taxes are related to home ownership
    
    # Personal
    'Personal': 'Personal Care',
    'pets': 'Pets',  # Case variation
    'Venmo': 'Miscellaneous',
    'Bill&Julie': 'Miscellaneous',
    'Misc Reimbursement': 'Miscellaneous',
    
    # Education
    'College': 'Education',
    
    # Health & Medical
    'Health & Wellness': 'Health & Medical',
    'Health & Fitness': 'Health & Medical',
    'Health Insurance': 'Insurance',
    'Life Insurance': 'Insurance',
    'HSA': 'Health & Medical',
    
    # Shopping
    'Amazon': 'Shopping',
    'Clothing': 'Shopping',
    'Software': 'Shopping',
    'Liquor': 'Shopping',
    
    # Food & Dining
    'Restaurant GE': 'Food & Dining',
    'Restaurant Travel': 'Food & Dining',
    'Restaurant Lake': 'Food & Dining',
    
    # Banking & Financial
    'Banking Fees': 'Fees & Adjustments',
    'Credit Card Payment': 'Banking',
    'Cash & ATM': 'Banking',
    'Marcus Savings': 'Banking',
    
    # Work & Income
    'Oobeya Capital': 'Work',
    'Oobeya Distribution': 'Work',
    'Distribution': 'Work',
    'Salary': 'Work',
    'Income': 'Work',
    
    # Bills & Utilities
    'Utilities': 'Bills & Utilities',
    'Cable/Internet': 'Bills & Utilities',
    'Mobile Phone': 'Bills & Utilities',
    
    # Other
    'Home Services': 'Home',
    'Misc Reimbursement': 'Miscellaneous',
    'Bill&Julie': 'Miscellaneous',
    'Venmo': 'Miscellaneous',
}

def normalize_category(category: str) -> str:
    """
    Normalize a category name to one of the allowed categories.
    
    Args:
        category: The input category name to normalize
        
    Returns:
        The normalized category name, or 'Uncategorized' if no mapping is found
    """
    if not category or not isinstance(category, str):
        return 'Uncategorized'
        
    # Strip whitespace and normalize case for matching
    normalized = category.strip()
    
    # Check for direct match first
    if normalized in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[normalized]
    
    # Check case-insensitive match
    for source, target in CATEGORY_MAPPING.items():
        if normalized.lower() == source.lower():
            return target
    
    # If no mapping found, return as-is (it should be in ALLOWED_CATEGORIES already)
    return normalized
