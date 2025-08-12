"""
Merchant name mappings and categorization rules for specific merchants.
This file contains mappings of merchant names to their standardized forms
and specific categorization rules for certain merchants.
"""
import re
import pandas as pd

# Merchant name standardization mappings
MERCHANT_NAME_MAPPINGS = {
    # Standard patterns from debug output
    r'(?i)tjmaxx\s*#?\d*': 'TJ Maxx',
    r'(?i)homegoods\s*#?\d*': 'HomeGoods',
    r'(?i)wholefds\s*whn\s*#?\d*': 'Whole Foods',
    r'(?i)audible\*[a-z0-9]+': 'Audible',
    r'(?i)mariano\'?s\s*(?:fuel\s*)?#?\d*': 'Mariano\'s',
    r'(?i)ilsos\s*int\s*veh\s*renewal': 'IL SOS - Vehicle Registration',
    r'(?i)bar\s*taco\s*\w+': 'Bar Taco',
    r'(?i)springhill\s*suites': 'SpringHill Suites',
    r'(?i)casey\'?s\s*#?\d*': 'Casey\'s General Store',
    r'(?i)menards\s*\w+\s*\w*': 'Menards',
    r'(?i)at\s*\*?\w+\s*\w*': lambda m: m.group(0).replace('AT *', '').title(),
    r'(?i)slice\*\w+': 'Slice - Pizza Delivery',
    r'(?i)patio\s*cafe\s*at\s*\w+': 'Patio Cafe',
    r'(?i)all\s*american\s*modern': 'All American Modern',
    r'(?i)house\s*of\s*comedy': 'House of Comedy',
    r'(?i)uber\s*\*?trip': 'Uber',
    r'(?i)pitch\s*pizzeria': 'Pitch Pizzeria',
    r'(?i)grayhawk\s*isabellas': 'Grayhawk Isabella\'s',
    r'(?i)stl\s*kingside\s*diner': 'Kingside Diner',
    r'(?i)national\s*multiple\s*scleros': 'National MS Society',
    r'(?i)grubhub\*\w+': 'Grubhub',
    r'(?i)crate\s*&\s*barrel': 'Crate & Barrel',
    r'(?i)thornton\'?s\s*#?\d*': 'Thornton\'s',
    r'(?i)portillo\'?s': 'Portillo\'s',
    r'(?i)sav\s*factors\s*row': 'SAV Factors Row',
    r'(?i)aaa\s*\w+\s*\w*': 'AAA',
    r'(?i)vco\*[\w\s\']+': lambda m: m.group(0).replace('VCO*', '').title(),
    r'(?i)hampton\s*inn': 'Hampton Inn',
    r'(?i)culvers\s*of\s*\w+': 'Culver\'s',
    r'(?i)abercrombie\s*and\s*fitch': 'Abercrombie & Fitch',
    r'(?i)morton\s*arboretum': 'Morton Arboretum',
    r'(?i)fresh\s*thyme\s*#?\d*': 'Fresh Thyme',
    r'(?i)aurorastolpparkgarage': 'Aurora Stoll Park Garage',
    r'(?i)cs\s*\*\w+\s*\w*': lambda m: m.group(0).replace('CS *', '').title(),
    r'(?i)five\s*0\s*four\s*kitchen': '504 Kitchen',
    r'(?i)burst\s*oral\s*care': 'Burst Oral Care',
    r'(?i)adelle\'?s': 'Adelle\'s',
    r'(?i)sq\s*\*[\w\s\']+': lambda m: m.group(0).replace('SQ *', '').title(),
    r'(?i)southwes\s*\d+': 'Southwest Airlines',
    r'(?i)sp\s*\w+\s*culinary': 'Specialty Culinary',
    r'(?i)swim\s*2000': 'Swim 2000',
    r'(?i)verizon\s*wireless': 'Verizon Wireless',
    r'(?i)verizon': 'Verizon Wireless',
    r'(?i)olive\'?n\s*vinnie\'?s': 'Olive N Vinnie\'s',
    r'(?i)dd\s*\*doordash': 'DoorDash',
    r'(?i)xero\s*shoes': 'Xero Shoes',
    r'(?i)milk\s*street\s*magazine': 'Milk Street Magazine',
    r'(?i)pete\'?s\s*fresh\s*market': 'Pete\'s Fresh Market',
    r'(?i)world\s*market\s*#?\d*': 'World Market',
    r'(?i)u\.?t\.?\s*dallas': 'UT Dallas',
    r'(?i)mahjongglea': 'Mahjongg Lea',
    
    # Original mappings
    # Standardize common merchant name variations
    r'(?i)walmart': 'Walmart',
    r'(?i)target': 'Target',
    r'(?i)amazon\.?com': 'Amazon',
    r'(?i)costco\s*whse': 'Costco',
    r'(?i)meijer\s*store': 'Meijer',
    r'(?i)casey\'?s': 'Casey\'s General Store',
    r'(?i)culver\'?s': 'Culver\'s',
    r'(?i)panera\s+.*': 'Panera Bread',
    r'(?i)starbucks.*': 'Starbucks',
    r'(?i)home\s*goods': 'HomeGoods',
    r'(?i)mariano\'?s': 'Mariano\'s',
    r'(?i)j\.?\s*crew': 'J.Crew',
    r'(?i)macys?\b': 'Macy\'s',
    r'(?i)huntington\s+bank': 'Huntington Bank',
    r'(?i)spothero': 'SpotHero',
    r'(?i)kindle\s*svcs': 'Amazon Kindle',
    r'(?i)menards': 'Menards',
    r'(?i)creators?\s*foundry': 'Creator Foundry',
    r'(?i)holland\s*bulb\s*farms': 'Holland Bulb Farms',
    r'(?i)pan-?mass\s*challenge': 'Pan-Mass Challenge',
    r'(?i)von\s*maur': 'Von Maur',
    r'(?i)hie\s+rochelle': 'Holiday Inn Express Rochelle',
    r'(?i)lake\s+station\s+fuel': 'Lake Station Fuel',
    r'(?i)axs\.com': 'AXS (Ticketing)',
    r'(?i)sq\s*\*?\s*\w+\s+auction': 'Square Online Purchase',
    r'(?i)photo\s*enforce': 'Photo Enforcement',
    r'(?i)northwestern\s*my\s*chart': 'Northwestern Medicine',
    r'(?i)axs\.comdenver': 'AXS (Ticketing)',
    r'(?i)lake\s+station\s+fuel\s*&': 'Lake Station Fuel',
    r'(?i)casey\'?s\s*#?\d+': 'Casey\'s General Store',
    r'(?i)wal-?mart\s*#?\d+': 'Walmart',
    r'(?i)meijer\s*store\s*#?\d+': 'Meijer',
    r'(?i)hie\s+rochelle': 'Holiday Inn Express Rochelle',
    r'(?i)huntington\s+bank\s+pavili': 'Huntington Bank Pavilion',
    r'(?i)sweetgreen': 'Sweetgreen',
    r'(?i)von\s+maur\s+\w+\s+\d+': 'Von Maur',
    r'(?i)spothero\s+\d{3}-\d{3}-\d{4}': 'SpotHero',
    r'(?i)culver\'?s\s+of\s+\w+': 'Culver\'s',
    r'(?i)kindle\s+svcs\*?\w+': 'Amazon Kindle',
    r'(?i)mariano\'?s\s*#?\d+': 'Mariano\'s',
    r'(?i)j\s*crew\s*factory\s*#?\d+': 'J.Crew Factory',
    r'(?i)homegoods\s*#?\d+': 'HomeGoods',
    r'(?i)culvers': 'Culver\'s',
    r'(?i)sq\s*\*[\w\s]+auction': 'Square Online Purchase',
    r'(?i)photoenforcementprogram': 'Photo Enforcement',
    r'(?i)menards\s+\w+\s+in': 'Menards',
    r'(?i)creator\s+foundry': 'Creator Foundry',
    r'(?i)holland\s*bulb\s*farms': 'Holland Bulb Farms',
}

# Specific merchant categorizations
MERCHANT_CATEGORIES = {
    # Payment processors and financial institutions
    'VERIZON WIRELESS': ('Bills & Utilities', 'Telephone'),
    'VERIZON': ('Bills & Utilities', 'Telephone'),
    'COMED': ('Bills & Utilities', 'Electric'),
    'NICOR': ('Bills & Utilities', 'Gas'),
    'VILLAGE OF GLEN': ('Bills & Utilities', 'Utilities'),
    'NORTHWESTERN MUTUAL': ('Insurance', 'Life Insurance'),
    '5/3 MORTGAGE': ('Banking', 'Mortgage'),
    'MFSUSA LOAN': ('Banking', 'Loan Payment'),
    'CHASE': ('Banking', 'Banking Fees'),
    'ZELLE': ('Transfers', 'Person-to-Person'),
    'VENMO': ('Transfers', 'Person-to-Person'),
    'PAYPAL': ('Online Services', 'Payment Processing'),
    'SQUARE': ('Online Services', 'Payment Processing'),
    'CASH APP': ('Transfers', 'Person-to-Person'),
    'APPLE PAY': ('Transfers', 'Digital Wallet'),
    'GOOGLE PAY': ('Transfers', 'Digital Wallet'),
    'SAMSUNG PAY': ('Transfers', 'Digital Wallet'),
    'DIRECT DEPOSIT': ('Income Sources', 'Payroll Deposit'),
    'DIRECTDEP': ('Income Sources', 'Payroll Deposit'),
    'DIRECT DEP': ('Income Sources', 'Payroll Deposit'),
    'PAYROLL': ('Income Sources', 'Payroll Deposit'),
    'SALARY': ('Income Sources', 'Salary Payment'),
    'BONUS': ('Income Sources', 'Bonus Payment'),
    'COMMISSION': ('Income Sources', 'Commission Payment'),
    'REIMBURSEMENT': ('Income Sources', 'Reimbursement Payment'),
    'REFUND': ('Income Sources', 'Refund Payment'),
    'REBATE': ('Income Sources', 'Rebate Payment'),
    'INTEREST': ('Income Sources', 'Interest Payment'),
    'DIVIDEND': ('Income Sources', 'Dividend Payment'),
    'CAPITAL GAINS': ('Income Sources', 'Investment Income'),
    'INVESTMENT': ('Investments', 'Investment Deposit'),
    'ROTH': ('Investments', 'Retirement Account'),
    'IRA': ('Investments', 'Retirement Account'),
    '401K': ('Investments', 'Retirement Account'),
    '403B': ('Investments', 'Retirement Account'),
    'BROKERAGE': ('Investments', 'Brokerage Account'),
    'TRANSFER': ('Transfers', 'Internal Transfer'),
    'EXTERNAL TRANSFER': ('Transfers', 'External Transfer'),
    'WIRE TRANSFER': ('Transfers', 'Wire Transfer'),
    'ACH': ('Transfers', 'ACH Transfer'),
    'AUTOMATIC PAYMENT': ('Bills & Utilities', 'Auto Payment'),
    'AUTOPAY': ('Bills & Utilities', 'Auto Payment'),
    'AUTO PAY': ('Bills & Utilities', 'Auto Payment'),
    'AUTOMATIC WITHDRAWAL': ('Bills & Utilities', 'Auto Payment'),
    'AUTOMATIC TRANSFER': ('Transfers', 'Recurring Transfer'),
    'RECURRING PAYMENT': ('Bills & Utilities', 'Recurring Payment'),
    'RECURRING TRANSFER': ('Transfers', 'Recurring Transfer'),
    'BILL PAY': ('Bills & Utilities', 'Bill Payment'),
    'ONLINE PAYMENT': ('Bills & Utilities', 'Online Bill Payment'),
    'ELECTRONIC PAYMENT': ('Bills & Utilities', 'Electronic Bill Payment'),
    'ONLINE TRANSFER': ('Transfers', 'Online'),
    'MOBILE DEPOSIT': ('Deposits', 'Check'),
    'DIRECT DEBIT': ('Bills & Utilities', 'Auto Pay'),
    'OVERDRAFT': ('Fees', 'Overdraft'),
    'NSF': ('Fees', 'Non-Sufficient Funds'),
    'LATE FEE': ('Fees', 'Late Payment'),
    'ANNUAL FEE': ('Fees', 'Annual'),
    'MONTHLY FEE': ('Fees', 'Monthly'),
    'SERVICE FEE': ('Fees', 'Service'),
    'TRANSACTION FEE': ('Fees', 'Transaction'),
    'ATM FEE': ('Fees', 'ATM'),
    'WIRE FEE': ('Fees', 'Wire Transfer'),
    'FOREIGN TRANSACTION FEE': ('Fees', 'Foreign Transaction'),
    'CASH ADVANCE FEE': ('Fees', 'Cash Advance'),
    'BALANCE TRANSFER FEE': ('Fees', 'Balance Transfer'),
    'LATE PAYMENT FEE': ('Fees', 'Late Payment'),
    'RETURNED ITEM FEE': ('Fees', 'Returned Item'),
    'STOP PAYMENT FEE': ('Fees', 'Stop Payment'),
    'CASHIER\'S CHECK FEE': ('Fees', 'Cashier\'s Check'),
    'MONEY ORDER FEE': ('Fees', 'Money Order'),
    'CASHIER\'S CHECK': ('Banking', 'Cashier\'s Check'),
    'MONEY ORDER': ('Banking', 'Money Order'),
    'CERTIFIED CHECK': ('Banking', 'Certified Check'),
    'TRAVELER\'S CHECK': ('Banking', 'Traveler\'s Check'),
    'CASHIER\'S CHECK FEE': ('Fees', 'Cashier\'s Check'),
    'MONEY ORDER FEE': ('Fees', 'Money Order'),
    'CERTIFIED CHECK FEE': ('Fees', 'Certified Check'),
    'TRAVELER\'S CHECK FEE': ('Fees', 'Traveler\'s Check'),
    
    # Retail and shopping
    'TJ MAXX': ('Shopping', 'Clothing'),
    'T.J. MAXX': ('Shopping', 'Clothing'),
    'T J MAXX': ('Shopping', 'Clothing'),
    'HOMEGOODS': ('Home', 'Home Goods'),
    'HOME GOODS': ('Home', 'Home Goods'),
    'TARGET': ('Shopping', 'Department Store'),
    'WALMART': ('Shopping', 'Department Store'),
    'AMAZON': ('Shopping', 'Online Retail'),
    'WHOLE FOODS': ('Groceries', 'Supermarket'),
    'TRADER JOE\'S': ('Groceries', 'Supermarket'),
    'TRADER JOES': ('Groceries', 'Supermarket'),
    'COSTCO': ('Shopping', 'Warehouse Club'),
    'BEST BUY': ('Shopping', 'Electronics'),
    'APPLE STORE': ('Shopping', 'Electronics'),
    'APPLE.COM': ('Shopping', 'Electronics'),
    'MICROSOFT': ('Shopping', 'Electronics'),
    'GOOGLE STORE': ('Shopping', 'Electronics'),
    'SAMSUNG': ('Shopping', 'Electronics'),
    'BESTBUY': ('Shopping', 'Electronics'),
    'BEST BUY': ('Shopping', 'Electronics'),
    'BESTBUY.COM': ('Shopping', 'Electronics'),
    'BEST BUY.COM': ('Shopping', 'Electronics'),
    'BESTBUY MOBILE': ('Shopping', 'Electronics'),
    'BEST BUY MOBILE': ('Shopping', 'Electronics'),
    'BESTBUY.COM/STORES': ('Shopping', 'Electronics'),
    'BEST BUY.COM/STORES': ('Shopping', 'Electronics'),
    'BESTBUY STORE': ('Shopping', 'Electronics'),
    'BEST BUY STORE': ('Shopping', 'Electronics'),
    'BESTBUY RETAIL': ('Shopping', 'Electronics'),
    'BEST BUY RETAIL': ('Shopping', 'Electronics'),
    'BESTBUY RETAIL STORE': ('Shopping', 'Electronics'),
    'BEST BUY RETAIL STORE': ('Shopping', 'Electronics'),
    'BESTBUY RETAIL STORES': ('Shopping', 'Electronics'),
    'BEST BUY RETAIL STORES': ('Shopping', 'Electronics'),
    'Whole Foods': ('Food', 'Groceries'),
    'Audible': ('Entertainment', 'Digital Media'),
    'IL SOS - Vehicle Registration': ('Auto', 'Registration'),
    'Bar Taco': ('Food', 'Restaurant'),
    'SpringHill Suites': ('Travel', 'Hotel'),
    'Slice - Pizza Delivery': ('Food', 'Delivery'),
    'Patio Cafe': ('Food', 'Restaurant'),
    'All American Modern': ('Shopping', 'Home Goods'),
    'House of Comedy': ('Entertainment', 'Events'),
    'Uber': ('Transportation', 'Ride Share'),
    'Pitch Pizzeria': ('Food', 'Restaurant'),
    'Grayhawk Isabella\'s': ('Food', 'Restaurant'),
    'Kingside Diner': ('Food', 'Restaurant'),
    'National MS Society': ('Giving', 'Charity'),
    'Grubhub': ('Food', 'Delivery'),
    'Crate & Barrel': ('Shopping', 'Home Goods'),
    'Thornton\'s': ('Transportation', 'Gas'),
    'Portillo\'s': ('Food', 'Fast Food'),
    'SAV Factors Row': ('Shopping', 'Retail'),
    'AAA': ('Auto', 'Membership'),
    'Hampton Inn': ('Travel', 'Hotel'),
    'Abercrombie & Fitch': ('Shopping', 'Clothing'),
    'Morton Arboretum': ('Entertainment', 'Attractions'),
    'Fresh Thyme': ('Food', 'Groceries'),
    'Aurora Stoll Park Garage': ('Transportation', 'Parking'),
    'Burst Oral Care': ('Health', 'Personal Care'),
    'Adelle\'s': ('Food', 'Restaurant'),
    'Southwest Airlines': ('Travel', 'Airfare'),
    'Specialty Culinary': ('Food', 'Restaurant'),
    'Swim 2000': ('Recreation', 'Sports'),
    'Olive N Vinnie\'s': ('Food', 'Restaurant'),
    'DoorDash': ('Food', 'Delivery'),
    'Xero Shoes': ('Shopping', 'Clothing'),
    'Milk Street Magazine': ('Entertainment', 'Subscriptions'),
    'Pete\'s Fresh Market': ('Food', 'Groceries'),
    'World Market': ('Shopping', 'Home Goods'),
    'UT Dallas': ('Education', 'Tuition'),
    'Mahjongg Lea': ('Entertainment', 'Games'),
    
    # Original categories
    # Retail
    'Walmart': ('Shopping', 'Retail'),
    'Target': ('Shopping', 'Retail'),
    'Amazon': ('Shopping', 'Online Retail'),
    'Costco': ('Shopping', 'Wholesale'),
    'Meijer': ('Shopping', 'Retail'),
    'HomeGoods': ('Shopping', 'Home Goods'),
    'Mariano\'s': ('Food', 'Groceries'),
    'J.Crew': ('Shopping', 'Clothing'),
    'J.Crew Factory': ('Shopping', 'Clothing'),
    'Macy\'s': ('Shopping', 'Department Store'),
    'Menards': ('Shopping', 'Home Improvement'),
    'Holland Bulb Farms': ('Shopping', 'Garden'),
    'Von Maur': ('Shopping', 'Department Store'),
    'Huntington Bank Pavilion': ('Entertainment', 'Events'),
    'SpotHero': ('Transportation', 'Parking'),
    'Square Online Purchase': ('Shopping', 'Online Retail'),
    'Photo Enforcement': ('Automotive', 'Fines'),
    'Creator Foundry': ('Business', 'Services'),
    
    # Food & Dining
    'Casey\'s General Store': ('Food', 'Convenience'),
    'Culver\'s': ('Food', 'Fast Food'),
    'Panera Bread': ('Food', 'Restaurant'),
    'Starbucks': ('Food', 'Coffee Shop'),
    'Sweetgreen': ('Food', 'Restaurant'),
    'Holiday Inn Express Rochelle': ('Travel', 'Hotel'),
    
    # Services & Other
    'Huntington Bank': ('Banking', 'Fees'),
    'Amazon Kindle': ('Entertainment', 'Digital Media'),
    'Pan-Mass Challenge': ('Giving', 'Charity'),
    'Lake Station Fuel': ('Transportation', 'Gas'),
    'AXS (Ticketing)': ('Entertainment', 'Tickets'),
    'Northwestern Medicine': ('Health', 'Medical'),
    'Legends': ('Food', 'Restaurant'),
    'Sweetgreen Oakbrook': ('Food', 'Restaurant'),
    
    # Additional categories for specific merchants
    'Huntington Bank Pavili': ('Entertainment', 'Events'),
    'Hie Rochelle': ('Travel', 'Hotel'),
    'Macys Oakbrook Ctr': ('Shopping', 'Department Store'),
    'Mariano S 5543': ('Food', 'Groceries'),
    'Homegoods 316': ('Shopping', 'Home Goods'),
    'Caseys 6445': ('Food', 'Convenience'),
    'Caseys 6446': ('Food', 'Convenience'),
    'Meijer Store 291': ('Shopping', 'Retail'),
    'Wal Mart 1593': ('Shopping', 'Retail'),
}

def get_merchant_category(merchant_name):
    """
    Get the category and subcategory for a merchant.
    
    Args:
        merchant_name: The name of the merchant
        
    Returns:
        tuple: (category, subcategory) or (None, None) if no match found
    """
    if not merchant_name or pd.isna(merchant_name):
        return None, None
        
    # Check for exact matches first
    if merchant_name in MERCHANT_CATEGORIES:
        return MERCHANT_CATEGORIES[merchant_name]
    
    # Check for partial matches
    for merchant_pattern, categories in MERCHANT_CATEGORIES.items():
        if re.search(merchant_pattern, merchant_name, re.IGNORECASE):
            return categories
    
    return None, None

def standardize_merchant_name(merchant_name):
    """
    Standardize a merchant name using the defined mappings.
    
    Args:
        merchant_name: The original merchant name
        
    Returns:
        str: The standardized merchant name
    """
    if not merchant_name or pd.isna(merchant_name):
        return ""
        
    standardized = str(merchant_name).strip()
    
    # Apply standardizations
    for pattern, replacement in MERCHANT_NAME_MAPPINGS.items():
        standardized = re.sub(pattern, replacement, standardized, flags=re.IGNORECASE)
    
    return standardized.strip()
