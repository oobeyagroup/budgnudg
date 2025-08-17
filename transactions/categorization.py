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
def categorize_transaction_with_reasoning(description: str, amount: float = 0.0) -> tuple[str, str, str]:
    """
    Categorize transaction and provide reasoning for the AI's decision.
    Returns (category, subcategory, reasoning).
    """
    if not description:
        return ("Miscellaneous", "", "No description provided")
    
    logger.debug(f"Categorizing transaction with description: {description} and amount: {amount}")
    merchant = extract_merchant_from_description(description)
    logger.debug(f"Extracted merchant: {merchant} from description: {description}")
    
    # First, check if we have learned patterns for this merchant key
    learned_subcat, learned_count = _top_learned_subcat(merchant)
    if learned_subcat and learned_count > 0:
        # Find the category for this subcategory
        try:
            subcategory_obj = Category.objects.filter(name=learned_subcat, parent__isnull=False).first()
            if subcategory_obj and subcategory_obj.parent:
                reasoning = f"Based on {learned_count} previous user confirmations for similar transactions with merchant '{merchant}'"
                return (subcategory_obj.parent.name, learned_subcat, reasoning)
        except Exception as e:
            logger.warning(f"Error looking up learned subcategory: {e}")
    
    # Updated merchant-to-category mappings based on our new clean category structure
    merchant_category_map = {
        # Transportation
        'gas': ('Transportation', 'Gas', 'Merchant identified as gas station'),
        'bp': ('Transportation', 'Gas', 'BP identified as major gas station brand'),
        'shell': ('Transportation', 'Gas', 'Shell identified as major gas station brand'),
        'exxon': ('Transportation', 'Gas', 'ExxonMobil identified as major gas station brand'),
        'mobil': ('Transportation', 'Gas', 'Mobil identified as major gas station brand'),
        'speedway': ('Transportation', 'Gas', 'Speedway identified as gas station chain'),
        'chevron': ('Transportation', 'Gas', 'Chevron identified as major gas station brand'),
        'citgo': ('Transportation', 'Gas', 'Citgo identified as gas station brand'),
        'texaco': ('Transportation', 'Gas', 'Texaco identified as gas station brand'),
        'sunoco': ('Transportation', 'Gas', 'Sunoco identified as gas station brand'),
        'tolls': ('Transportation', 'Tolls', 'Merchant identified as toll system'),
        'tollway': ('Transportation', 'Tolls', 'Tollway identified in transaction description'),
        'toll': ('Transportation', 'Tolls', 'Toll payment identified in description'),
        'ipass': ('Transportation', 'Tolls', 'I-PASS identified as electronic toll system'),
        'parking': ('Transportation', 'Parking', 'Parking payment identified in description'),
        'uber': ('Transportation', 'Public Transit', 'Uber identified as ride-sharing service'),
        'lyft': ('Transportation', 'Public Transit', 'Lyft identified as ride-sharing service'),
        'taxi': ('Transportation', 'Public Transit', 'Taxi service identified'),
        
        # Food & Dining
        'starbucks': ('Food & Dining', 'Coffee/Tea', 'Starbucks identified as major coffee chain'),
        'dunkin': ('Food & Dining', 'Coffee/Tea', 'Dunkin identified as coffee/donut chain'),
        'coffee': ('Food & Dining', 'Coffee/Tea', 'Coffee-related merchant identified'),
        'mcdonald': ('Food & Dining', 'Fast Food', 'McDonald\'s identified as major fast food chain'),
        'burger king': ('Food & Dining', 'Fast Food', 'Burger King identified as fast food chain'),
        'taco bell': ('Food & Dining', 'Fast Food', 'Taco Bell identified as fast food chain'),
        'subway': ('Food & Dining', 'Fast Food', 'Subway identified as sandwich chain'),
        'kfc': ('Food & Dining', 'Fast Food', 'KFC identified as fast food chicken chain'),
        'wendy': ('Food & Dining', 'Fast Food', 'Wendy\'s identified as fast food chain'),
        'chipotle': ('Food & Dining', 'Fast Food', 'Chipotle identified as fast-casual restaurant chain'),
        'panera': ('Food & Dining', 'Fast Food', 'Panera identified as fast-casual bakery-cafe'),
        'restaurant': ('Food & Dining', 'Restaurants', 'Generic restaurant identifier found'),
        'diner': ('Food & Dining', 'Restaurants', 'Diner identified in description'),
        'bistro': ('Food & Dining', 'Restaurants', 'Bistro identified in description'),
        'bar': ('Food & Dining', 'Restaurants', 'Bar/restaurant identified'),
        'grill': ('Food & Dining', 'Restaurants', 'Grill/restaurant identified'),
        'pizza': ('Food & Dining', 'Restaurants', 'Pizza restaurant identified'),
        'domino': ('Food & Dining', 'Restaurants', 'Domino\'s pizza identified'),
        'papa john': ('Food & Dining', 'Restaurants', 'Papa John\'s pizza identified'),
        'grocery': ('Food & Dining', 'Groceries', 'Grocery store identifier found'),
        'kroger': ('Food & Dining', 'Groceries', 'Kroger identified as major grocery chain'),
        'safeway': ('Food & Dining', 'Groceries', 'Safeway identified as grocery chain'),
        'whole foods': ('Food & Dining', 'Groceries', 'Whole Foods identified as organic grocery chain'),
        'trader joe': ('Food & Dining', 'Groceries', 'Trader Joe\'s identified as specialty grocery chain'),
        'costco': ('Food & Dining', 'Groceries', 'Costco identified as warehouse grocery store'),
        'walmart': ('Food & Dining', 'Groceries', 'Walmart identified as retail/grocery store'),
        'target': ('Food & Dining', 'Groceries', 'Target identified as retail store with groceries'),
        'alcohol': ('Food & Dining', 'Alcohol', 'Alcohol-related purchase identified'),
        'liquor': ('Food & Dining', 'Alcohol', 'Liquor store identified'),
        'wine': ('Food & Dining', 'Alcohol', 'Wine purchase identified'),
        'beer': ('Food & Dining', 'Alcohol', 'Beer purchase identified'),
        'binnys': ('Food & Dining', 'Alcohol', 'Binny\'s identified as liquor store chain'),
        
        # Health & Medical
        'medical': ('Health & Medical', 'Doctor Visits', 'Medical service identifier found'),
        'hospital': ('Health & Medical', 'Doctor Visits', 'Hospital identified in description'),
        'clinic': ('Health & Medical', 'Doctor Visits', 'Medical clinic identified'),
        'northwestern': ('Health & Medical', 'Doctor Visits', 'Northwestern Medicine identified as major healthcare provider'),
        'mayo clinic': ('Health & Medical', 'Doctor Visits', 'Mayo Clinic identified as major medical institution'),
        'doctor': ('Health & Medical', 'Doctor Visits', 'Doctor/physician service identified'),
        'physician': ('Health & Medical', 'Doctor Visits', 'Physician service identified'),
        'pharmacy': ('Health & Medical', 'Pharmacy', 'Pharmacy identifier found'),
        'cvs': ('Health & Medical', 'Pharmacy', 'CVS identified as major pharmacy chain'),
        'walgreens': ('Health & Medical', 'Pharmacy', 'Walgreens identified as major pharmacy chain'),
        'rite aid': ('Health & Medical', 'Pharmacy', 'Rite Aid identified as pharmacy chain'),
        'dental': ('Health & Medical', 'Dental', 'Dental service identifier found'),
        'dentist': ('Health & Medical', 'Dental', 'Dentist service identified'),
        'orthodont': ('Health & Medical', 'Dental', 'Orthodontic service identified'),
        'vision': ('Health & Medical', 'Vision', 'Vision care service identified'),
        'optometrist': ('Health & Medical', 'Vision', 'Optometrist service identified'),
        'eye care': ('Health & Medical', 'Vision', 'Eye care service identified'),
        'glasses': ('Health & Medical', 'Vision', 'Eyeglass purchase identified'),
        'contacts': ('Health & Medical', 'Vision', 'Contact lens purchase identified'),
        
        # Shopping
        'amazon': ('Shopping', 'Online Shopping', 'Amazon identified as major online retailer'),
        'ebay': ('Shopping', 'Online Shopping', 'eBay identified as online marketplace'),
        'etsy': ('Shopping', 'Online Shopping', 'Etsy identified as online marketplace for handmade items'),
        'online': ('Shopping', 'Online Shopping', 'Online shopping identifier found'),
        'best buy': ('Shopping', 'Electronics', 'Best Buy identified as electronics retailer'),
        'apple store': ('Shopping', 'Electronics', 'Apple Store identified as technology retailer'),
        'microsoft': ('Shopping', 'Electronics', 'Microsoft identified as technology company'),
        'electronics': ('Shopping', 'Electronics', 'Electronics purchase identifier found'),
        'computer': ('Shopping', 'Electronics', 'Computer-related purchase identified'),
        'phone': ('Shopping', 'Electronics', 'Phone-related purchase identified'),
        'macy': ('Shopping', 'Clothing', 'Macy\'s identified as department store'),
        'nordstrom': ('Shopping', 'Clothing', 'Nordstrom identified as upscale department store'),
        'gap': ('Shopping', 'Clothing', 'Gap identified as clothing retailer'),
        'nike': ('Shopping', 'Clothing', 'Nike identified as athletic wear brand'),
        'clothing': ('Shopping', 'Clothing', 'Clothing purchase identifier found'),
        'apparel': ('Shopping', 'Clothing', 'Apparel purchase identifier found'),
        'home depot': ('Shopping', 'Home Goods', 'Home Depot identified as home improvement retailer'),
        'lowe': ('Shopping', 'Home Goods', 'Lowe\'s identified as home improvement retailer'),
        'bed bath': ('Shopping', 'Home Goods', 'Bed Bath & Beyond identified as home goods retailer'),
        'ikea': ('Shopping', 'Home Goods', 'IKEA identified as furniture retailer'),
        'furniture': ('Shopping', 'Home Goods', 'Furniture purchase identified'),
        'gift': ('Shopping', 'Gifts', 'Gift purchase identifier found'),
        'present': ('Shopping', 'Gifts', 'Present purchase identifier found'),
        
        # Entertainment
        'netflix': ('Entertainment', 'Subscriptions', 'Netflix identified as streaming service'),
        'hulu': ('Entertainment', 'Subscriptions', 'Hulu identified as streaming service'),
        'disney': ('Entertainment', 'Subscriptions', 'Disney+ identified as streaming service'),
        'spotify': ('Entertainment', 'Subscriptions', 'Spotify identified as music streaming service'),
        'apple music': ('Entertainment', 'Subscriptions', 'Apple Music identified as music streaming service'),
        'youtube': ('Entertainment', 'Subscriptions', 'YouTube Premium identified as video service'),
        'subscription': ('Entertainment', 'Subscriptions', 'Subscription service identifier found'),
        'movie': ('Entertainment', 'Movies', 'Movie-related purchase identified'),
        'theater': ('Entertainment', 'Movies', 'Movie theater identified'),
        'cinema': ('Entertainment', 'Movies', 'Cinema identified'),
        'amc': ('Entertainment', 'Movies', 'AMC identified as movie theater chain'),
        'regal': ('Entertainment', 'Movies', 'Regal identified as movie theater chain'),
        'concert': ('Entertainment', 'Concerts/Events', 'Concert event identified'),
        'ticketmaster': ('Entertainment', 'Concerts/Events', 'Ticketmaster identified as event ticketing service'),
        'stubhub': ('Entertainment', 'Concerts/Events', 'StubHub identified as ticket resale platform'),
        'sports': ('Entertainment', 'Sports', 'Sports-related activity identified'),
        'gym': ('Entertainment', 'Sports', 'Gym membership or visit identified'),
        'fitness': ('Entertainment', 'Sports', 'Fitness-related activity identified'),
        'golf': ('Entertainment', 'Sports', 'Golf-related activity identified'),
        'tennis': ('Entertainment', 'Sports', 'Tennis-related activity identified'),
        'book': ('Entertainment', 'Books/Media', 'Book purchase identified'),
        'barnes': ('Entertainment', 'Books/Media', 'Barnes & Noble identified as bookstore'),
        'library': ('Entertainment', 'Books/Media', 'Library-related service identified'),
        'hobby': ('Entertainment', 'Hobbies', 'Hobby-related purchase identified'),
        
        # Financial
        'atm': ('Cash & ATM', '', 'ATM transaction identified'),
        'withdrawal': ('Cash & ATM', '', 'Cash withdrawal identified'),
        'cash': ('Cash & ATM', '', 'Cash transaction identified'),
        'bank fee': ('Financial', 'Bank Fees', 'Bank fee identified'),
        'overdraft': ('Financial', 'Bank Fees', 'Overdraft fee identified'),
        'service charge': ('Financial', 'Bank Fees', 'Service charge identified'),
        'credit card': ('Financial', 'Credit Card Payment', 'Credit card payment identified'),
        'payment': ('Financial', 'Credit Card Payment', 'Payment transaction identified'),
        'investment': ('Financial', 'Investment', 'Investment transaction identified'),
        'vanguard': ('Financial', 'Investment', 'Vanguard identified as investment company'),
        'fidelity': ('Financial', 'Investment', 'Fidelity identified as investment company'),
        'schwab': ('Financial', 'Investment', 'Charles Schwab identified as investment company'),
        'loan': ('Financial', 'Loans', 'Loan payment identified'),
        'mortgage': ('Housing', 'Mortgage/Rent', 'Mortgage payment identified'),
        'tax': ('Financial', 'Taxes', 'Tax payment identified'),
        'irs': ('Financial', 'Taxes', 'IRS payment identified'),
        
        # Housing
        'rent': ('Housing', 'Mortgage/Rent', 'Rent payment identified'),
        'electric': ('Housing', 'Utilities', 'Electric utility payment identified'),
        'electricity': ('Housing', 'Utilities', 'Electricity payment identified'),
        'gas utility': ('Housing', 'Utilities', 'Gas utility payment identified'),
        'water': ('Housing', 'Utilities', 'Water utility payment identified'),
        'sewer': ('Housing', 'Utilities', 'Sewer utility payment identified'),
        'internet': ('Housing', 'Utilities', 'Internet service payment identified'),
        'cable': ('Housing', 'Utilities', 'Cable service payment identified'),
        'phone service': ('Housing', 'Utilities', 'Phone service payment identified'),
        'comcast': ('Housing', 'Utilities', 'Comcast identified as cable/internet provider'),
        'at&t': ('Housing', 'Utilities', 'AT&T identified as telecommunications provider'),
        'verizon': ('Housing', 'Utilities', 'Verizon identified as telecommunications provider'),
        'property tax': ('Housing', 'Property Tax', 'Property tax payment identified'),
        'home insurance': ('Housing', 'Home Insurance', 'Home insurance payment identified'),
        'homeowners': ('Housing', 'Home Insurance', 'Homeowners insurance identified'),
        'hoa': ('Housing', 'HOA Fees', 'HOA fee payment identified'),
        'maintenance': ('Housing', 'Home Maintenance', 'Home maintenance service identified'),
        'repair': ('Housing', 'Home Maintenance', 'Home repair service identified'),
        'plumber': ('Housing', 'Home Maintenance', 'Plumbing service identified'),
        'electrician': ('Housing', 'Home Maintenance', 'Electrical service identified'),
        'hvac': ('Housing', 'Home Maintenance', 'HVAC service identified'),
        
        # Income
        'direct dep': ('Income', 'Salary', 'Direct deposit payment identified'),
        'paycheck': ('Income', 'Salary', 'Paycheck deposit identified'),
        'salary': ('Income', 'Salary', 'Salary payment identified'),
        'bonus': ('Income', 'Bonus', 'Bonus payment identified'),
        'dividend': ('Income', 'Investment Income', 'Dividend payment identified'),
        'interest': ('Income', 'Investment Income', 'Interest payment identified'),
        
        # Personal
        'education': ('Personal', 'Education', 'Education-related expense identified'),
        'school': ('Personal', 'Education', 'School payment identified'),
        'tuition': ('Personal', 'Education', 'Tuition payment identified'),
        'college': ('Personal', 'Education', 'College payment identified'),
        'university': ('Personal', 'Education', 'University payment identified'),
        'charity': ('Personal', 'Charity', 'Charitable donation identified'),
        'donation': ('Personal', 'Charity', 'Donation payment identified'),
        'church': ('Personal', 'Charity', 'Church donation identified'),
        'pet': ('Personal', 'Pet Care', 'Pet-related expense identified'),
        'veterinarian': ('Personal', 'Pet Care', 'Veterinary service identified'),
        'vet': ('Personal', 'Pet Care', 'Veterinary service identified'),
        'animal': ('Personal', 'Pet Care', 'Animal-related expense identified'),
        
        # Business (if applicable)
        'office': ('Business', 'Office Supplies', 'Office supplies purchase identified'),
        'supplies': ('Business', 'Office Supplies', 'Office supplies purchase identified'),
        'business travel': ('Business', 'Business Travel', 'Business travel expense identified'),
        'hotel': ('Business', 'Business Travel', 'Hotel expense identified'),
        'flight': ('Business', 'Business Travel', 'Flight expense identified'),
        'conference': ('Business', 'Business Travel', 'Conference expense identified'),
    }
    
    # Check merchant mappings first
    merchant_lower = merchant.lower()
    for merchant_key, (category, subcategory, reason) in merchant_category_map.items():
        if merchant_key in merchant_lower:
            return (category, subcategory, reason)
    
    # Legacy term-based matching for specific patterns
    description_upper = description.upper()
    
    # Utility bill patterns
    if any(term in description_upper for term in ['ELECTRIC', 'ELECTRICITY', 'POWER']):
        return ('Housing', 'Utilities', 'Electric utility keywords found in description')
    if any(term in description_upper for term in ['GAS UTIL', 'NATURAL GAS', 'NICOR']):
        return ('Housing', 'Utilities', 'Gas utility keywords found in description')
    if 'WATER' in description_upper and 'BILL' in description_upper:
        return ('Housing', 'Utilities', 'Water bill keywords found in description')
    if any(term in description_upper for term in ['INTERNET', 'CABLE', 'COMCAST', 'XFINITY']):
        return ('Housing', 'Utilities', 'Internet/cable service keywords found in description')
    
    # Transportation patterns
    if any(term in description_upper for term in ['GAS STATION', 'FUEL', 'GASOLINE']):
        return ('Transportation', 'Gas', 'Gas/fuel keywords found in description')
    
    # Financial patterns
    if 'ATM' in description_upper:
        return ('Cash & ATM', '', 'ATM transaction keyword found in description')
    
    # Income detection (positive amounts)
    if amount > 0 and any(term in description_upper for term in ['DEPOSIT', 'PAYROLL', 'SALARY', 'PAYCHECK']):
        return ('Income', 'Salary', f'Positive amount (${amount}) with salary/payroll keywords suggests income')
    
    # Default fallback
    return ('Miscellaneous', '', 'No matching patterns found - using default category')

@trace
def categorize_transaction(description: str, amount: float = 0.0) -> tuple[str, str]:
    """Original function that returns just category and subcategory."""
    category, subcategory, _ = categorize_transaction_with_reasoning(description, amount)
    return (category, subcategory)

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