"""
Additional categorization rules for specific merchants and patterns.
"""

ADDITIONAL_RULES = [
    # Gas Stations
    {
        'pattern': r'PILOT|SUNOCO|BP|SHELL|EXXON|MOBIL|CHEVRON|TEXACO|ARCO|VALERO|CITGO|SPEEDWAY',
        'category': 'Transportation',
        'subcategory': 'Gas',
        'priority': 1
    },
    
    # Restaurants and Food
    {
        'pattern': r'BURGER KING|MCDONALD|WENDY|TACO BELL|CHIPOTLE|PANERA|STARBUCKS|DUNKIN|DAIRY QUEEN',
        'category': 'Food',
        'subcategory': 'Fast Food',
        'priority': 1
    },
    
    # Groceries
    {
        'pattern': r'TRADER JOE|WHOLE FOODS|COSTCO|ALDI|PUBLIX|KROGER|SAFEWAY|HARRIS TEETER|WINN DIXIE',
        'category': 'Food',
        'subcategory': 'Groceries',
        'priority': 1
    },
    
    # Entertainment
    {
        'pattern': r'AMC|REGAL|CINEMARK|MOVIE THEATER|THEATRE|PEACOCK|NETFLIX|HULU|DISNEY\+?|HBO MAX|YOUTUBE TV',
        'category': 'Entertainment',
        'subcategory': 'Streaming/Movies',
        'priority': 1
    },
    
    # Retail
    {
        'pattern': r'DOLLAR GENERAL|DOLLAR TREE|FAMILY DOLLAR|WALMART|TARGET|TARGET.COM|AMAZON|AMZN|EBAY',
        'category': 'Shopping',
        'subcategory': 'General Merchandise',
        'priority': 1
    },
    
    # Health and Wellness
    {
        'pattern': r'CVS|WALGREENS|RITE AID|REAMS MEAT MARKET|BUTCHER|MEAT MARKET',
        'category': 'Health',
        'subcategory': 'Pharmacy/Groceries',
        'priority': 1
    },
    
    # Sports and Recreation
    {
        'pattern': r'GOLF|MARINA|BOAT|FISHING|CAMPING|SPORTING GOODS|DICKS|ACADEMY SPORTS',
        'category': 'Entertainment',
        'subcategory': 'Sports/Recreation',
        'priority': 1
    },
    
    # Medical
    {
        'pattern': r'NORTHWESTERN.*HOSPITAL|HOSPITAL|DOCTOR|PHYSICIAN|MEDICAL|CLINIC|URGENT CARE',
        'category': 'Health',
        'subcategory': 'Medical Care',
        'priority': 1
    },
    
    # Memberships and Subscriptions
    {
        'pattern': r'COSTCO WHSE|SAM\'?S CLUB|BJ\'?S WHOLESALE|MEMBERSHIP|SUBSCRIPTION',
        'category': 'Shopping',
        'subcategory': 'Membership',
        'priority': 1
    }
]
