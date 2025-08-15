import re
import logging
from .models import LearnedSubcat, LearnedPayoree, Category, Payoree
from .utils import trace
from django.db.models import Sum

logger = logging.getLogger(__name__)

MERCHANT_NAME_MAPPINGS = {
    # Gas Stations
    r'BP\#?\d*': 'gas',
    r'SHELL': 'gas',
    r'CITGO': 'gas',
    r'MOBIL': 'gas',
    r'EXXON': 'gas',
    r'CHEVRON': 'gas',
    r'MARATHON': 'gas',
    r'SPEEDWAY': 'gas',
    r'VALERO': 'gas',
    
    # Transportation & Tolls
    r'TOLLWAY': 'tolls',
    r'TOLL': 'tolls',
    r'IPASS': 'tolls',
    r'EZ.*PASS': 'tolls',
    r'AUTO.*REPLENISH': 'tolls',
    
    # Medical & Healthcare
    r'NORTHWESTERN.*MEDICAL': 'medical',
    r'NORTHWESTERN.*MY.*CHART': 'medical',
    r'NORTHWESTERN': 'medical',
    r'MEDICAL': 'medical',
    r'HOSPITAL': 'medical',
    r'CLINIC': 'medical',
    r'DR\s': 'medical',
    r'DENTAL': 'medical',
    r'PHARMACY': 'medical',
    r'CVS': 'pharmacy',
    r'WALGREENS': 'pharmacy',
    
    # Retail & Shopping
    r'STARBUCKS': 'starbucks',
    r'TARGET': 'target',
    r'AMAZON': 'amazon',
    r'MCDONALD\'S': 'fast food',
    r'WALMART': 'walmart',
    r'BEST BUY': 'electronics',
    r'BINNYS BEVERAGE': 'alcohol',
    r'HOME DEPOT': 'home improvement',
    r'LOWE\'S': 'home improvement',
    
    # Recreation & Entertainment
    r'GOLF': 'golf',
    r'MARINA': 'marina',
    r'LAKE': 'recreation',
    
    # Financial & Banking
    r'PAYPAL': 'paypal',
    r'APPLE PAY': 'apple pay',
    r'MASTERCARD': 'mastercard',
    r'AMEX': 'american express',
    r'DIRECT DEP': 'Paycheck',
    r'ZELLE': 'gift',
    r'VENMO': 'venmo',
    r'BANK TRANSFER': 'transfer',
    r'ATM WITHDRAWAL': 'Cash & ATM',
    r'CHECK DEPOSIT': 'check deposit',
    r'CREDIT CRD AUTOPAY': 'transfer',
    r'CHECK PAYMENT': 'check payment',
    r'Payment': 'Bills & Utilities',
    r'Deposit': 'Income',
    r'Expense': 'Miscellaneous',
    r'MORTGAGE': 'Mortgage',
    r'INSURANCE': 'Insurance',
    r'TAX': 'Taxes',
    r'DONATION': 'Charity',
    r'TUITION': 'Education',
    r'CHILDCARE': 'Child Care',
    r'SUBSCRIPTION': 'Subscriptions',
    r'HOME IMPROVEMENT': 'Home Improvement',
    r'PET': 'Pet Care',
    r'GYM': 'Fitness',
    r'TRANSPORT': 'Public Transportation',
    r'PARKING': 'Parking',
    r'TOLL': 'Tolls',
    r'CASH': 'Cash',
    r'REFUND': 'Refunds',
    r'INTEREST': 'Interest',
    r'FEE': 'Fees',
    r'BUSINESS': 'Business',
    r'LEGAL': 'Legal',
    r'MEDICAL': 'Medical',
    r'DENTAL': 'Dental',
    r'VISION': 'Vision',
    r'PHARMACY': 'Pharmacy',
    r'ELECTRONICS': 'Electronics',
    r'FURNITURE': 'Furniture',
    r'CLOTHING': 'Clothing',
    r'GIFT': 'Gifts',
    r'HOBBY': 'Hobbies',
    r'VACATION': 'Vacation',
    r'GAME': 'Gaming',
    r'ALCOHOL': 'Alcohol',
    r'TOBACCO': 'Tobacco',
    r'LOTTERY': 'Lottery',
    r'VERIZON': 'Bills & Utilities',
    r'COMED': 'Bills & Utilities',
    r'NICOR': 'Bills & Utilities',
    r'NORTHWESTERN MU': 'Insurance',
    r'VENMO': 'Transfers',
    r'ZELLE': 'Transfers',
    r'CHASE': 'Banking',
    r'MORTGAGE': 'Mortgage',
    r'AUTOPAY': 'Bills & Utilities',
    r'DIRECT DEP': 'Income',
    r'PAYROLL': 'Work Income',
    r'SALARY': 'Work Income',
    # Utilities & Services
    r'NICOR.*GAS': 'gas utility',
    r'NICOR': 'gas utility',
    r'COMMONWEALTH.*EDISON': 'electric utility',
    r'COMED': 'electric utility',
    
    # Banking & ATM
    r'ATM.*WITHDRAWAL': 'atm',
    r'ATM': 'atm',
    r'WITHDRAWAL': 'withdrawal',
    r'DIRECT.*DEP': 'direct dep',
    r'PAYCHECK': 'paycheck',
    
    # Mortgage & Loans  
    r'MORTGAGE.*PAYMENT': 'mortgage',
    r'MORTGAGE.*LN': 'mortgage',
    r'MORTGAGE': 'mortgage',
    
    r'INVESTMENT': 'Investments',
    r'ROTH': 'Investments',
    r'IRA': 'Investments',
    r'401K': 'Investments',
    r'ETF': 'Investments',
    r'STOCK': 'Investments',
    r'MUTUAL FUND': 'Investments',
    r'BROKERAGE': 'Investments',
    r'RETIREMENT': 'Investments',
    r'NOBEL HOUSE': 'Restaurants GE',
    # Add more patterns as needed
}

@trace
def extract_merchant_from_description(description: str) -> str:
    if not isinstance(description, str):
        return ""

    patterns_to_remove = [
        r'PPD\s*ID:\s*\d+',
        r'WEB\s*ID:\s*\d+',
        r'\b(?:ACH|CC|DEBIT|CREDIT|PAYMENT|PYMT|PMT|AUTOPAY|AUTO\s*PAY)\b',
        r'\b(?:ONLINE\s*PAYMENT|ELECTRONIC\s*PAYMENT)\b',
        r'\b(?:BILL\s*PAY|BILLPAY|BP\s*PAYMENT|BILL\s*PAYMENT)\b',  # Removed standalone BP
        r'\b(?:ID\s*\d+|#\s*\d+)\b',
        r'\b(?:REF\s*\d+|REF#\s*\d+)\b',
        r'\b(?:TRANS\s*\d+|TRANS#\s*\d+)\b',
        r'\b(?:ACCT\s*\*\d+)\b',
        r'\b(?:X\*?\d+)\b',
        r'\b(?:\d{3,4})\b',
    ]

    cleaned = description.upper()
    logger.debug(f"Original description: {description}")
    logger.debug(f"Cleaned description: {cleaned}")

    # Remove unwanted patterns
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    for pattern, replacement in MERCHANT_NAME_MAPPINGS.items():
        # logger.debug(f"Checking pattern: {pattern} against cleaned description: {cleaned}")
        if re.search(pattern, cleaned, re.IGNORECASE):
            return replacement

    return cleaned

@trace
def categorize_transaction(description: str, amount: float = 0.0) -> tuple[str, str]:
    if not description:
        return ("Uncategorized", "")
    
    logger.debug(f"Categorizing transaction with description: {description} and amount: {amount}")
    merchant = extract_merchant_from_description(description)
    logger.debug(f"Extracted merchant: {merchant} from description: {description}")
    
    # Enhanced merchant-to-category mappings based on our imported categories
    merchant_category_map = {
        # Gas/Fuel
        'gas': ('Auto', 'Gas'),
        'bp': ('Auto', 'Gas'),
        'shell': ('Auto', 'Gas'),
        'exxon': ('Auto', 'Gas'),
        'mobil': ('Auto', 'Gas'),
        'nicor': ('Bills & Utilities', 'Gas'),
        'gas utility': ('Bills & Utilities', 'Gas'),
        
        # Transportation/Tolls
        'tolls': ('Auto', 'Auto - Tolls'),
        'tollway': ('Auto', 'Auto - Tolls'),
        'toll': ('Auto', 'Auto - Tolls'),
        
        # Medical/Healthcare
        'medical': ('Medical', 'Medical'),
        'northwestern': ('Medical', 'Northwestern Medical'),
        'pharmacy': ('Medical', 'Pharmacy'),
        'cvs': ('Medical', 'Pharmacy'),
        'walgreens': ('Medical', 'Pharmacy'),
        'dental': ('Medical', 'Dental'),
        'dentist': ('Medical', 'Dentist'),
        
        # Banking & Financial
        'atm': ('Cash & ATM', 'Cash & ATM'),
        'withdrawal': ('Cash & ATM', 'Cash & ATM'),
        'direct dep': ('Prior Year Income', 'Paycheck'),
        'paycheck': ('Prior Year Income', 'Paycheck'),
        
        # Recreation/Entertainment
        'golf': ('Entertainment', 'Golf'),
        'marina': ('Entertainment', 'Activities'),
        'recreation': ('Entertainment', 'Activities'),
        
        # Utilities (fallback patterns)
        'electric': ('Bills & Utilities', 'Electric'),
        'electric utility': ('Bills & Utilities', 'Electric'),
        'water': ('Bills & Utilities', 'Water'),
        'mortgage': ('Home', 'Mortgage (>10/27)'),
        'insurance': ('Insurance', 'Life Insurance'),
    }
    
    # Check merchant mappings first
    merchant_lower = merchant.lower()
    for merchant_key, (category, subcategory) in merchant_category_map.items():
        if merchant_key in merchant_lower:
            return (category, subcategory)
    
    # Legacy term-based matching for specific patterns
    bill_terms = {
        'ELECTRIC': ('Bills & Utilities', 'Electric'),
        'GAS': ('Bills & Utilities', 'Gas'),
        'MORTGAGE': ('Home', 'Mortgage (>10/27)'),
        'WATER': ('Bills & Utilities', 'Water'),
        'PHONE': ('Bills & Utilities', 'Mobile Phone'),
        'INSURANCE': ('Insurance', 'Life Insurance'),
    }

    description_upper = description.upper()
    for term, cat_pair in bill_terms.items():
        if term in description_upper:
            return cat_pair

    # Income detection
    if 'DEPOSIT' in merchant.upper() and amount > 0:
        return ('Prior Year Income', 'Paycheck')

    return ('Misc', 'Misc')

@trace
def suggest_subcategory_old(description: str, amount: float = 0.0) -> str:
    _, subcat = categorize_transaction(description, amount)
    return subcat


CONFIDENCE_MIN = 0.65  # tweak

@trace
def _top_learned_subcat(key):
    qs = (LearnedSubcat.objects
          .filter(key=key)
          .values('subcategory__name')
          .annotate(total=Sum('count'))
          .order_by('-total'))
    if qs:
        return qs[0]['subcategory__name'], qs[0]['total']
    return None, 0

@trace
def _top_learned_payoree(key):
    qs = (LearnedPayoree.objects
          .filter(key=key)
          .values('payoree__name')
          .annotate(total=Sum('count'))
          .order_by('-total'))
    if qs:
        return qs[0]['payoree__name'], qs[0]['total']
    return None, 0

@trace
def suggest_subcategory(description: str, amount: float = 0.0) -> str | None:
    key = extract_merchant_from_description(description)
    if key:
        name, cnt = _top_learned_subcat(key)
        if name:
            return name
    # fallback to your existing categorize_transaction / fuzzy logic
    _, sub = categorize_transaction(description, amount)
    return sub or None

@trace
def suggest_payoree(description: str) -> str | None:
    key = extract_merchant_from_description(description)
    if key:
        name, cnt = _top_learned_payoree(key)
        if name:
            return name
    # fallback: fuzzy from existing payorees or None
    return None