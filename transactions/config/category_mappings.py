"""
Category mapping configuration for standardizing transaction categories.
"""
from typing import Dict, List, Set

# Standard categories that should be included in the monthly summary
STANDARD_CATEGORIES = [
    'Automotive', 'Bills & Utilities', 'Credit', 'Debit', 'Entertainment',
    'Fees & Adjustments', 'Food & Drink', 'Gas', 'Gifts & Donations',
    'Groceries', 'Health & Wellness', 'Home', 'Installment', 'Other',
    'Personal', 'Restaurants', 'Shopping', 'Travel', 'Utilities',
    'Work Income',  # For payroll and salary income
    'Mortgage',     # For mortgage payments
    'Insurance',    # For insurance payments
    'Investments',  # For investment-related transactions
    'Transfers',    # For transfers between accounts
    'Taxes',        # For tax payments
    'Charity',      # For donations and charitable giving
    'Education',    # For education-related expenses
    'Child Care',   # For child care expenses
    'Subscriptions', # For subscription services
    'Home Improvement', # For home maintenance and improvement
    'Pet Care',     # For pet-related expenses
    'Fitness',      # For gym memberships and fitness
    'Public Transportation', # For buses, trains, etc.
    'Parking',      # For parking fees
    'Tolls',        # For road/bridge tolls
    'Cash',         # For cash withdrawals
    'Refunds',      # For refunds received
    'Income',       # For general income
    'Interest',     # For interest earned/paid
    'Fees',         # For bank fees and charges
    'Business',     # For business expenses
    'Legal',        # For legal fees
    'Medical',      # For medical expenses
    'Dental',       # For dental expenses
    'Vision',       # For vision/eye care
    'Pharmacy',     # For pharmacy expenses
    'Electronics',  # For electronic purchases
    'Furniture',    # For furniture purchases
    'Clothing',     # For clothing purchases
    'Gifts',        # For gifts given
    'Hobbies',      # For hobby-related expenses
    'Vacation',     # For vacation expenses
    'Gaming',       # For gaming-related expenses
    'Alcohol',      # For alcohol purchases
    'Tobacco',      # For tobacco purchases
    'Lottery',      # For lottery/gambling
    'Miscellaneous', # For uncategorized expenses
    '(blank)',      # Uncategorized transactions
    'Grand Total'   # Column sums
]

# Mapping from source category names to standardized category names
CATEGORY_MAPPING: Dict[str, str] = {
    # Map all categories to themselves by default
    **{cat: cat for cat in STANDARD_CATEGORIES if cat not in ['(blank)', 'Grand Total']},
    
    # Special mappings and aliases
    'Payment': 'Bills & Utilities',  # Map generic 'Payment' to 'Bills & Utilities'
    'Deposit': 'Income',            # Map generic 'Deposit' to 'Income'
    'Expense': 'Miscellaneous',     # Map generic 'Expense' to 'Miscellaneous'
    'Uncategorized': '(blank)',     # Map 'Uncategorized' to '(blank)'
    
    # Common transaction types mapping to standard categories
    'MORTGAGE': 'Mortgage',
    'INSURANCE': 'Insurance',
    'TAX': 'Taxes',
    'DONATION': 'Charity',
    'TUITION': 'Education',
    'CHILDCARE': 'Child Care',
    'SUBSCRIPTION': 'Subscriptions',
    'HOME IMPROVEMENT': 'Home Improvement',
    'PET': 'Pet Care',
    'GYM': 'Fitness',
    'TRANSPORT': 'Public Transportation',
    'PARKING': 'Parking',
    'TOLL': 'Tolls',
    'CASH': 'Cash',
    'REFUND': 'Refunds',
    'INTEREST': 'Interest',
    'FEE': 'Fees',
    'BUSINESS': 'Business',
    'LEGAL': 'Legal',
    'MEDICAL': 'Medical',
    'DENTAL': 'Dental',
    'VISION': 'Vision',
    'PHARMACY': 'Pharmacy',
    'ELECTRONICS': 'Electronics',
    'FURNITURE': 'Furniture',
    'CLOTHING': 'Clothing',
    'GIFT': 'Gifts',
    'HOBBY': 'Hobbies',
    'VACATION': 'Vacation',
    'GAME': 'Gaming',
    'ALCOHOL': 'Alcohol',
    'TOBACCO': 'Tobacco',
    'LOTTERY': 'Lottery',
    
    # Common merchant-specific mappings
    'VERIZON': 'Bills & Utilities',
    'COMED': 'Bills & Utilities',
    'NICOR': 'Bills & Utilities',
    'NORTHWESTERN': 'Insurance',
    'VENMO': 'Transfers',
    'ZELLE': 'Transfers',
    'CHASE': 'Banking',
    'MORTGAGE': 'Mortgage',
    'AUTOPAY': 'Bills & Utilities',
    'DIRECT DEP': 'Income',
    'PAYROLL': 'Work Income',
    'SALARY': 'Work Income',
    'INVESTMENT': 'Investments',
    'ROTH': 'Investments',
    'IRA': 'Investments',
    '401K': 'Investments',
    'ETF': 'Investments',
    'STOCK': 'Investments',
    'MUTUAL FUND': 'Investments',
    'BROKERAGE': 'Investments',
    'RETIREMENT': 'Investments',
}

