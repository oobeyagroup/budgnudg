import re
import logging
from .models import LearnedSubcat, LearnedPayoree, Category, Payoree
from .utils import trace
from django.db.models import Sum

logger = logging.getLogger(__name__)

# Safe lookup utilities for hybrid error handling
@trace
def safe_category_lookup(category_name, error_context="UNKNOWN"):
    """
    Safely look up Category, return (obj, error_code) tuple.
    Returns (Category_obj, None) on success or (None, error_code) on failure.
    
    When multiple categories exist with the same name, prefer:
    1. Top-level categories (parent=None) 
    2. First category found if all are at same level
    """
    if not category_name or not category_name.strip():
        return None, f"{error_context}_NO_SUBCATEGORY_SUGGESTION"
        
    try:
        category_name = category_name.strip()
        
        # Try exact match first
        categories = Category.objects.filter(name=category_name)
        
        if not categories.exists():
            logger.warning(f"Category lookup failed: '{category_name}' -> {error_context}")
            return None, f"{error_context}_SUBCATEGORY_LOOKUP_FAILED"
            
        elif categories.count() == 1:
            return categories.first(), None
            
        else:
            # Multiple categories found - prefer top-level category
            top_level = categories.filter(parent=None).first()
            if top_level:
                logger.debug(f"Multiple categories for '{category_name}', using top-level: {top_level.id}")
                return top_level, None
            else:
                # No top-level match, use first category
                selected = categories.first() 
                logger.debug(f"Multiple categories for '{category_name}', using first: {selected.id}")
                return selected, None
                
    except Exception as e:
        logger.error(f"Database error during category lookup: {e}")
        return None, "DATABASE_ERROR"

@trace  
def safe_payoree_lookup(payoree_name, error_context="UNKNOWN"):
    """
    Safely look up Payoree, return (obj, error_code) tuple.
    Returns (Payoree_obj, None) on success or (None, error_code) on failure.
    """
    if not payoree_name or not payoree_name.strip():
        return None, f"{error_context}_NO_PAYOREE_SUGGESTION"
        
    try:
        # Try exact match first
        payoree_obj = Payoree.objects.get(name=payoree_name.strip())
        return payoree_obj, None
    except Payoree.DoesNotExist:
        # Try normalized lookup
        existing = Payoree.get_existing(payoree_name.strip())
        if existing:
            return existing, None
        logger.warning(f"Payoree lookup failed: '{payoree_name}' -> {error_context}")
        return None, f"{error_context}_PAYOREE_LOOKUP_FAILED"
    except Payoree.MultipleObjectsReturned:
        logger.error(f"Multiple payorees found for: '{payoree_name}'")
        return None, "MULTIPLE_PAYOREES_FOUND"
    except Exception as e:
        logger.error(f"Database error during payoree lookup: {e}")
        return None, "DATABASE_ERROR"

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
    if cleaned != description:
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
        return ("Miscellaneous", "")
    
    logger.debug(f"Categorizing transaction with description: {description} and amount: {amount}")
    merchant = extract_merchant_from_description(description)
    logger.debug(f"Extracted merchant: {merchant} from description: {description}")
    
    # Updated merchant-to-category mappings based on our new clean category structure
    merchant_category_map = {
        # Transportation
        'gas': ('Transportation', 'Gas'),
        'bp': ('Transportation', 'Gas'),
        'shell': ('Transportation', 'Gas'),
        'exxon': ('Transportation', 'Gas'),
        'mobil': ('Transportation', 'Gas'),
        'speedway': ('Transportation', 'Gas'),
        'chevron': ('Transportation', 'Gas'),
        'citgo': ('Transportation', 'Gas'),
        'texaco': ('Transportation', 'Gas'),
        'sunoco': ('Transportation', 'Gas'),
        'tolls': ('Transportation', 'Tolls'),
        'tollway': ('Transportation', 'Tolls'),
        'toll': ('Transportation', 'Tolls'),
        'ipass': ('Transportation', 'Tolls'),
        'parking': ('Transportation', 'Parking'),
        'uber': ('Transportation', 'Public Transit'),
        'lyft': ('Transportation', 'Public Transit'),
        'taxi': ('Transportation', 'Public Transit'),
        
        # Food & Dining
        'starbucks': ('Food & Dining', 'Coffee/Tea'),
        'dunkin': ('Food & Dining', 'Coffee/Tea'),
        'coffee': ('Food & Dining', 'Coffee/Tea'),
        'mcdonald': ('Food & Dining', 'Fast Food'),
        'burger king': ('Food & Dining', 'Fast Food'),
        'taco bell': ('Food & Dining', 'Fast Food'),
        'subway': ('Food & Dining', 'Fast Food'),
        'kfc': ('Food & Dining', 'Fast Food'),
        'wendy': ('Food & Dining', 'Fast Food'),
        'chipotle': ('Food & Dining', 'Fast Food'),
        'panera': ('Food & Dining', 'Fast Food'),
        'restaurant': ('Food & Dining', 'Restaurants'),
        'diner': ('Food & Dining', 'Restaurants'),
        'bistro': ('Food & Dining', 'Restaurants'),
        'bar': ('Food & Dining', 'Restaurants'),
        'grill': ('Food & Dining', 'Restaurants'),
        'pizza': ('Food & Dining', 'Restaurants'),
        'domino': ('Food & Dining', 'Restaurants'),
        'papa john': ('Food & Dining', 'Restaurants'),
        'grocery': ('Food & Dining', 'Groceries'),
        'kroger': ('Food & Dining', 'Groceries'),
        'safeway': ('Food & Dining', 'Groceries'),
        'whole foods': ('Food & Dining', 'Groceries'),
        'trader joe': ('Food & Dining', 'Groceries'),
        'costco': ('Food & Dining', 'Groceries'),
        'walmart': ('Food & Dining', 'Groceries'),
        'target': ('Food & Dining', 'Groceries'),
        'alcohol': ('Food & Dining', 'Alcohol'),
        'liquor': ('Food & Dining', 'Alcohol'),
        'wine': ('Food & Dining', 'Alcohol'),
        'beer': ('Food & Dining', 'Alcohol'),
        'binnys': ('Food & Dining', 'Alcohol'),
        
        # Health & Medical
        'medical': ('Health & Medical', 'Doctor Visits'),
        'hospital': ('Health & Medical', 'Doctor Visits'),
        'clinic': ('Health & Medical', 'Doctor Visits'),
        'northwestern': ('Health & Medical', 'Doctor Visits'),
        'mayo clinic': ('Health & Medical', 'Doctor Visits'),
        'doctor': ('Health & Medical', 'Doctor Visits'),
        'physician': ('Health & Medical', 'Doctor Visits'),
        'pharmacy': ('Health & Medical', 'Pharmacy'),
        'cvs': ('Health & Medical', 'Pharmacy'),
        'walgreens': ('Health & Medical', 'Pharmacy'),
        'rite aid': ('Health & Medical', 'Pharmacy'),
        'dental': ('Health & Medical', 'Dental'),
        'dentist': ('Health & Medical', 'Dental'),
        'orthodont': ('Health & Medical', 'Dental'),
        'vision': ('Health & Medical', 'Vision'),
        'optometrist': ('Health & Medical', 'Vision'),
        'eye care': ('Health & Medical', 'Vision'),
        'glasses': ('Health & Medical', 'Vision'),
        'contacts': ('Health & Medical', 'Vision'),
        
        # Shopping
        'amazon': ('Shopping', 'Online Shopping'),
        'ebay': ('Shopping', 'Online Shopping'),
        'etsy': ('Shopping', 'Online Shopping'),
        'online': ('Shopping', 'Online Shopping'),
        'best buy': ('Shopping', 'Electronics'),
        'apple store': ('Shopping', 'Electronics'),
        'microsoft': ('Shopping', 'Electronics'),
        'electronics': ('Shopping', 'Electronics'),
        'computer': ('Shopping', 'Electronics'),
        'phone': ('Shopping', 'Electronics'),
        'macy': ('Shopping', 'Clothing'),
        'nordstrom': ('Shopping', 'Clothing'),
        'gap': ('Shopping', 'Clothing'),
        'nike': ('Shopping', 'Clothing'),
        'clothing': ('Shopping', 'Clothing'),
        'apparel': ('Shopping', 'Clothing'),
        'home depot': ('Shopping', 'Home Goods'),
        'lowe': ('Shopping', 'Home Goods'),
        'bed bath': ('Shopping', 'Home Goods'),
        'ikea': ('Shopping', 'Home Goods'),
        'furniture': ('Shopping', 'Home Goods'),
        'gift': ('Shopping', 'Gifts'),
        'present': ('Shopping', 'Gifts'),
        
        # Entertainment
        'netflix': ('Entertainment', 'Subscriptions'),
        'hulu': ('Entertainment', 'Subscriptions'),
        'disney': ('Entertainment', 'Subscriptions'),
        'spotify': ('Entertainment', 'Subscriptions'),
        'apple music': ('Entertainment', 'Subscriptions'),
        'youtube': ('Entertainment', 'Subscriptions'),
        'subscription': ('Entertainment', 'Subscriptions'),
        'movie': ('Entertainment', 'Movies'),
        'theater': ('Entertainment', 'Movies'),
        'cinema': ('Entertainment', 'Movies'),
        'amc': ('Entertainment', 'Movies'),
        'regal': ('Entertainment', 'Movies'),
        'concert': ('Entertainment', 'Concerts/Events'),
        'ticketmaster': ('Entertainment', 'Concerts/Events'),
        'stubhub': ('Entertainment', 'Concerts/Events'),
        'sports': ('Entertainment', 'Sports'),
        'gym': ('Entertainment', 'Sports'),
        'fitness': ('Entertainment', 'Sports'),
        'golf': ('Entertainment', 'Sports'),
        'tennis': ('Entertainment', 'Sports'),
        'book': ('Entertainment', 'Books/Media'),
        'barnes': ('Entertainment', 'Books/Media'),
        'library': ('Entertainment', 'Books/Media'),
        'hobby': ('Entertainment', 'Hobbies'),
        
        # Financial
        'atm': ('Cash & ATM', ''),
        'withdrawal': ('Cash & ATM', ''),
        'cash': ('Cash & ATM', ''),
        'bank fee': ('Financial', 'Bank Fees'),
        'overdraft': ('Financial', 'Bank Fees'),
        'service charge': ('Financial', 'Bank Fees'),
        'credit card': ('Financial', 'Credit Card Payment'),
        'payment': ('Financial', 'Credit Card Payment'),
        'investment': ('Financial', 'Investment'),
        'vanguard': ('Financial', 'Investment'),
        'fidelity': ('Financial', 'Investment'),
        'schwab': ('Financial', 'Investment'),
        'loan': ('Financial', 'Loans'),
        'mortgage': ('Housing', 'Mortgage/Rent'),
        'tax': ('Financial', 'Taxes'),
        'irs': ('Financial', 'Taxes'),
        
        # Housing
        'rent': ('Housing', 'Mortgage/Rent'),
        'mortgage': ('Housing', 'Mortgage/Rent'),
        'electric': ('Housing', 'Utilities'),
        'electricity': ('Housing', 'Utilities'),
        'gas utility': ('Housing', 'Utilities'),
        'water': ('Housing', 'Utilities'),
        'sewer': ('Housing', 'Utilities'),
        'internet': ('Housing', 'Utilities'),
        'cable': ('Housing', 'Utilities'),
        'phone service': ('Housing', 'Utilities'),
        'comcast': ('Housing', 'Utilities'),
        'at&t': ('Housing', 'Utilities'),
        'verizon': ('Housing', 'Utilities'),
        'property tax': ('Housing', 'Property Tax'),
        'home insurance': ('Housing', 'Home Insurance'),
        'homeowners': ('Housing', 'Home Insurance'),
        'hoa': ('Housing', 'HOA Fees'),
        'maintenance': ('Housing', 'Home Maintenance'),
        'repair': ('Housing', 'Home Maintenance'),
        'plumber': ('Housing', 'Home Maintenance'),
        'electrician': ('Housing', 'Home Maintenance'),
        'hvac': ('Housing', 'Home Maintenance'),
        
        # Income
        'direct dep': ('Income', 'Salary'),
        'paycheck': ('Income', 'Salary'),
        'salary': ('Income', 'Salary'),
        'bonus': ('Income', 'Bonus'),
        'dividend': ('Income', 'Investment Income'),
        'interest': ('Income', 'Investment Income'),
        
        # Personal
        'education': ('Personal', 'Education'),
        'school': ('Personal', 'Education'),
        'tuition': ('Personal', 'Education'),
        'college': ('Personal', 'Education'),
        'university': ('Personal', 'Education'),
        'charity': ('Personal', 'Charity'),
        'donation': ('Personal', 'Charity'),
        'church': ('Personal', 'Charity'),
        'pet': ('Personal', 'Pet Care'),
        'veterinarian': ('Personal', 'Pet Care'),
        'vet': ('Personal', 'Pet Care'),
        'animal': ('Personal', 'Pet Care'),
        
        # Business (if applicable)
        'office': ('Business', 'Office Supplies'),
        'supplies': ('Business', 'Office Supplies'),
        'business travel': ('Business', 'Business Travel'),
        'hotel': ('Business', 'Business Travel'),
        'flight': ('Business', 'Business Travel'),
        'conference': ('Business', 'Business Travel'),
    }
    
    # Check merchant mappings first
    merchant_lower = merchant.lower()
    for merchant_key, (category, subcategory) in merchant_category_map.items():
        if merchant_key in merchant_lower:
            return (category, subcategory)
    
    # Legacy term-based matching for specific patterns
    description_upper = description.upper()
    
    # Utility bill patterns
    if any(term in description_upper for term in ['ELECTRIC', 'ELECTRICITY', 'POWER']):
        return ('Housing', 'Utilities')
    if any(term in description_upper for term in ['GAS UTIL', 'NATURAL GAS', 'NICOR']):
        return ('Housing', 'Utilities')
    if 'WATER' in description_upper and 'BILL' in description_upper:
        return ('Housing', 'Utilities')
    if any(term in description_upper for term in ['INTERNET', 'CABLE', 'COMCAST', 'XFINITY']):
        return ('Housing', 'Utilities')
    
    # Transportation patterns
    if any(term in description_upper for term in ['GAS STATION', 'FUEL', 'GASOLINE']):
        return ('Transportation', 'Gas')
    
    # Financial patterns
    if 'ATM' in description_upper:
        return ('Cash & ATM', '')
    
    # Income detection (positive amounts)
    if amount > 0 and any(term in description_upper for term in ['DEPOSIT', 'PAYROLL', 'SALARY', 'PAYCHECK']):
        return ('Income', 'Salary')
    
    # Default fallback
    return ('Miscellaneous', '')

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