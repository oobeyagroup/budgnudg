#!/usr/bin/env python3
"""
Script to read CSV files from data/raw and derive categories from the description field.
"""
import os
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Import merchant mappings and categorization functions
from config.merchant_mappings import (
    MERCHANT_CATEGORIES,
    MERCHANT_NAME_MAPPINGS,
    standardize_merchant_name,
    get_merchant_category
)
from config.category_mapping_rules import normalize_category
from config.constants import ALLOWED_CATEGORIES

# Define directories
RAW_DATA_DIR = Path(__file__).parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).parent / "reports"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_merchant_from_description(description: str) -> str:
    """Extract a clean merchant name from a transaction description."""
    if not isinstance(description, str):
        return ""
    
    # Common patterns to remove from descriptions
    patterns_to_remove = [
        r'PPD\s*ID:\s*\d+',  # Remove PPD IDs
        r'WEB\s*ID:\s*\d+',   # Remove WEB IDs
        r'\b(?:ACH|CC|DEBIT|CREDIT|PAYMENT|PYMT|PMT|AUTOPAY|AUTO\s*PAY)\b',
        r'\b(?:ONLINE\s*PAYMENT|ELECTRONIC\s*PAYMENT)\b',
        r'\b(?:BILL\s*PAY|BILLPAY|BP|BP\s*PAYMENT|BILL\s*PAYMENT)\b',
        r'\b(?:ID\s*\d+|#\s*\d+)\b',  # Remove IDs
        r'\b(?:REF\s*\d+|REF#\s*\d+)\b',  # Remove REF numbers
        r'\b(?:TRANS\s*\d+|TRANS#\s*\d+)\b',  # Remove transaction numbers
        r'\b(?:ACCT\s*\*\d+)\b',  # Remove account numbers
        r'\b(?:X\*?\d+)\b',  # Remove X followed by numbers
        r'\b(?:\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})\b',  # Remove card numbers
        r'\b(?:\d{3,4})\b',  # Remove remaining 3-4 digit numbers
    ]
    
    # Apply patterns to clean the description
    cleaned = description.upper()
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up remaining special characters and extra spaces
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)  # Replace non-word chars with space
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse multiple spaces
    cleaned = cleaned.strip()
    
    # Standardize common merchant name variations
    for pattern, replacement in MERCHANT_NAME_MAPPINGS.items():
        if re.search(pattern, cleaned, re.IGNORECASE):
            if callable(replacement):
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
            else:
                cleaned = replacement
                break  # Stop after first match
    
    return cleaned

def categorize_transaction(description: str, amount: float) -> Tuple[str, str]:
    """Categorize a transaction based on its description and amount."""
    if not description:
        return ("Uncategorized", "No Description")
    
    # Standardize the merchant name
    merchant = extract_merchant_from_description(description)
    
    # Try to get category from merchant-specific rules
    if merchant:
        category_info = get_merchant_category(merchant)
        if category_info and category_info[0] != "Uncategorized":
            return category_info
    
    # If no merchant-specific rule, try to determine category from description
    description_upper = description.upper()
    
    # Check for common income patterns
    income_terms = [
        'DIRECT DEP', 'DIRECTDEP', 'DIRECT DEPOSIT', 'PAYROLL', 'DEPOSIT',
        'DEPOSIT FROM', 'TRANSFER FROM', 'TRANSFER RECEIVED', 'VENMO CASHOUT',
        'ZELLE FROM', 'PAYPAL TRANSFER'
    ]
    if any(term in description_upper for term in income_terms) and amount > 0:
        return ("Income", "Work")
    
    # Check for common transfer patterns
    transfer_terms = [
        'TRANSFER', 'XFER', 'TRANS TO', 'TRANS FROM', 'ZELLE', 'VENMO',
        'CASH APP', 'PAYPAL', 'CHASE QUICKPAY', 'QUICKPAY'
    ]
    if any(term in description_upper for term in transfer_terms):
        return ("Transfer", "")
    
    # Check for common bill payments
    bill_terms = {
        'ELECTRIC': ('Bills & Utilities', 'Electric'),
        'GAS': ('Bills & Utilities', 'Gas'),
        'WATER': ('Bills & Utilities', 'Water'),
        'INTERNET': ('Bills & Utilities', 'Internet'),
        'CABLE': ('Bills & Utilities', 'Cable'),
        'PHONE': ('Bills & Utilities', 'Phone'),
        'MOBILE': ('Bills & Utilities', 'Phone'),
        'CELL': ('Bills & Utilities', 'Phone'),
        'INSURANCE': ('Insurance', ''),
        'MORTGAGE': ('Mortgage & Rent', 'Mortgage'),
        'RENT': ('Mortgage & Rent', 'Rent'),
        'HOA': ('Housing', 'HOA Fees'),
        'TAX': ('Taxes', ''),
        'CREDIT CARD': ('Credit Card Payment', ''),
        'LOAN': ('Loan Payment', ''),
        'CAR PAYMENT': ('Auto & Transport', 'Car Payment'),
        'AUTO PAYMENT': ('Auto & Transport', 'Car Payment'),
    }
    
    for term, category in bill_terms.items():
        if term in description_upper:
            return category
    
    # Check for common shopping categories
    shopping_terms = {
        'AMAZON': ('Shopping', 'Online'),
        'WALMART': ('Shopping', 'Department Store'),
        'TARGET': ('Shopping', 'Department Store'),
        'COSTCO': ('Shopping', 'Wholesale'),
        'WHOLEFDS': ('Groceries', 'Grocery Store'),
        'TRADER JOE': ('Groceries', 'Grocery Store'),
        'MARIANO': ('Groceries', 'Grocery Store'),
        'JEWEL': ('Groceries', 'Grocery Store'),
    }
    
    for term, category in shopping_terms.items():
        if term in description_upper:
            return category
    
    # Check for dining categories
    dining_terms = {
        'RESTAURANT': ('Food & Dining', 'Restaurant'),
        'CAFE': ('Food & Dining', 'Coffee Shop'),
        'STARBUCKS': ('Food & Dining', 'Coffee Shop'),
        'DUNKIN': ('Food & Dining', 'Coffee Shop'),
        'MCDONALD': ('Food & Dining', 'Fast Food'),
        'BURGER KING': ('Food & Dining', 'Fast Food'),
        'TACO BELL': ('Food & Dining', 'Fast Food'),
        'CHIPOTLE': ('Food & Dining', 'Fast Casual'),
        'PANERA': ('Food & Dining', 'Fast Casual'),
    }
    
    for term, category in dining_terms.items():
        if term in description_upper:
            return category
    
    # Default to Uncategorized if no match found
    return ("Uncategorized", "")

def format_transaction(transaction: pd.Series) -> str:
    """Format a transaction's details into a readable string."""
    lines = ["\nTransaction Details:", "=" * 50]
    
    # Get all non-empty fields
    non_empty_fields = transaction.dropna()
    
    # Format each field with its label
    for field, value in non_empty_fields.items():
        # Skip empty values and internal pandas fields
        if pd.isna(value) or str(value).strip() == '':
            continue
            
        # Format the field name (replace underscores with spaces, title case)
        field_name = field.replace('_', ' ').title()
        
        # Handle different value types
        if isinstance(value, (int, float)) and field.lower() in ['amount', 'debit', 'credit']:
            # Format monetary values with 2 decimal places
            formatted_value = f"${abs(value):.2f}"
            if value < 0:
                formatted_value = f"-{formatted_value}"
            lines.append(f"{field_name}: {formatted_value}")
        elif isinstance(value, str):
            # For strings, just show as is
            lines.append(f"{field_name}: {value.strip()}")
        else:
            # For other types, use string representation
            lines.append(f"{field_name}: {str(value).strip()}")
    
    return "\n".join(lines)

def find_matching_category(user_input: str) -> tuple[bool, str, str]:
    """
    Find a matching category from user input, with auto-completion.
    
    Args:
        user_input: The user's input to match against categories
        
    Returns:
        A tuple of (is_valid, category, message)
    """
    if not user_input or not isinstance(user_input, str):
        return False, "", "Category cannot be empty"
    
    user_input = user_input.strip()
    
    # Check for exact match first (case-insensitive)
    for cat in ALLOWED_CATEGORIES:
        if cat.lower() == user_input.lower():
            return True, cat, ""
    
    # Check for partial match at the start of category names
    matches = [
        cat for cat in ALLOWED_CATEGORIES 
        if cat.lower().startswith(user_input.lower())
    ]
    
    if matches:
        # Return the first match (alphabetically first if multiple)
        return True, sorted(matches)[0], f"Using '{sorted(matches)[0]}'"
    
    # No match found
    return False, "", f"No matching category found for '{user_input}'"

def validate_category(category: str) -> tuple[bool, str]:
    """
    Validate that a category exists in the allowed categories.
    
    Args:
        category: The category to validate
        
    Returns:
        A tuple of (is_valid, message)
    """
    is_valid, matched_cat, message = find_matching_category(category)
    if is_valid:
        return True, message
    
    # If no match, show the full list of allowed categories
    categories_str = ', '.join(sorted(ALLOWED_CATEGORIES))
    return False, f"Invalid category. Must be one of: {categories_str}"

def get_user_category(transaction: pd.Series, suggested_category: str, suggested_subcategory: str) -> tuple[str, str]:
    """
    Prompt the user to accept or modify the suggested category.
    
    Args:
        transaction: The full transaction data as a pandas Series
        suggested_category: The automatically determined category
        suggested_subcategory: The automatically determined subcategory
        
    Returns:
        A tuple of (category, subcategory) as chosen by the user, or (None, None) to skip, or ('QUIT', 'QUIT') to quit
    """
    # Get the description for reference (if available)
    description = str(transaction.get('description', 'No Description')).strip()
    
    # Print the full transaction details
    print("\n" + "="*80)
    print(format_transaction(transaction))
    print("\n" + "-"*50)
    print(f"Suggested category: {suggested_category} - {suggested_subcategory}")
    
    while True:
        print("\nOptions (press Enter to accept):")
        print("  [Enter] or y - Accept suggested category")
        print("  n - Enter a different category")
        print("  s - Skip this transaction")
        print("  q - Quit and save progress")
        
        response = input("\nYour choice [Y]/n/s/q: ").strip().lower()
        response = response if response else 'y'  # Default to 'y' if empty
        
        if response == 'y':
            return suggested_category, suggested_subcategory
        elif response == 'n':
            while True:
                # Display categories in a compact, comma-separated format
                categories_str = ', '.join(sorted(ALLOWED_CATEGORIES))
                print(f"\nAllowed categories: {categories_str}")
                print("\nEnter new category (or press Enter to keep current):")
                user_input = input("> ").strip()
                
                if not user_input:
                    return suggested_category, suggested_subcategory
                
                # Find matching category with auto-completion
                is_valid, matched_cat, message = find_matching_category(user_input)
                
                if is_valid:
                    if message:  # Show auto-completion message if applicable
                        print(f"  {message}")
                    return matched_cat, suggested_subcategory
                else:
                    print(f"\n{message}")
        elif response == 's':
            return None, None
        elif response == 'q':
            return 'QUIT', 'QUIT'
        else:
            print("Invalid choice. Please enter 'y', 'n', 's', or 'q'.")

def process_csv_file(file_path: Path) -> pd.DataFrame:
    """
    Process a single CSV file and add category information with interactive user input.
    
    Args:
        file_path: Path to the CSV file to process
        
    Returns:
        DataFrame with added category and subcategory columns, or None if there was an error
    """
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Standardize column names
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        
        # Ensure we have required columns
        required_columns = {'description', 'amount'}
        if not required_columns.issubset(df.columns):
            print(f"Warning: Missing required columns in {file_path}. Available columns: {df.columns.tolist()}")
            return None
        
        # Add category and subcategory columns if they don't exist
        if 'category' not in df.columns:
            df['category'] = ''
        if 'subcategory' not in df.columns:
            df['subcategory'] = ''
        
        # Get the number of uncategorized transactions
        uncategorized = df[df['category'].isna() | (df['category'] == '')].copy()
        total = len(uncategorized)
        
        if total == 0:
            print("All transactions already categorized!")
            return df
            
        print(f"\nFound {total} uncategorized transactions.")
        
        # Process each uncategorized transaction
        for idx, row in uncategorized.iterrows():
            description = str(row.get('description', '')).strip()
            if not description:
                continue
                
            try:
                amount = float(row.get('amount', 0))
            except (ValueError, TypeError):
                amount = 0.0
            
            # Get the suggested category
            suggested_category, suggested_subcategory = categorize_transaction(description, amount)
            
            # Get user input for this transaction
            print(f"\nProcessing transaction {len(df[df['category'] != ''])} of {len(df)}...")
            category, subcategory = get_user_category(row, suggested_category, suggested_subcategory)
            
            if category == 'QUIT':
                print("\nSaving progress and exiting...")
                break
            elif category is None:  # User chose to skip
                continue
                
            # Update the row
            df.at[idx, 'category'] = category
            df.at[idx, 'subcategory'] = subcategory
            
            # Save progress after each transaction
            output_file = OUTPUT_DIR / f"categorized_{file_path.stem}.csv"
            df.to_csv(output_file, index=False)
            
        return df
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to process all CSV files in the raw data directory."""
    # Get all CSV files in the raw data directory
    csv_files = list(RAW_DATA_DIR.glob('*.csv')) + list(RAW_DATA_DIR.glob('*.CSV'))
    
    if not csv_files:
        print(f"No CSV files found in {RAW_DATA_DIR}")
        return
    
    # Process each CSV file
    for csv_file in csv_files:
        print(f"Processing {csv_file.name}...")
        
        # Process the CSV file
        df = process_csv_file(csv_file)
        
        if df is not None and not df.empty:
            # Generate output filename
            output_file = OUTPUT_DIR / f"categorized_{csv_file.stem}.csv"
            
            # Save the processed data
            df.to_csv(output_file, index=False)
            print(f"  -> Saved categorized data to {output_file}")
            
            # Print a summary of categories
            print("\nCategory Summary:")
            # Replace NaN/None with 'Uncategorized' for summary
            df_summary = df.fillna({'category': 'Uncategorized', 'subcategory': 'None'})
            category_summary = df_summary['category'].value_counts()
            print(category_summary)
            
            # Save summary to a text file
            summary_file = OUTPUT_DIR / f"summary_{csv_file.stem}.txt"
            with open(summary_file, 'w') as f:
                f.write("Category Summary:\n")
                f.write("=" * 50 + "\n")
                f.write(category_summary.to_string())
                
                # Add subcategory summary for each category
                f.write("\n\nSubcategory Summary:\n")
                f.write("=" * 50 + "\n")
                for category in sorted(df_summary['category'].unique()):
                    if pd.isna(category) or not str(category).strip():
                        category = 'Uncategorized'
                    f.write(f"\n{category}:\n")
                    f.write("-" * (len(str(category)) + 1) + "\n")
                    if category != '':
                        f.write(f"\n\nSubcategories for {category}:\n")
                        f.write("-" * (len(category) + 20) + "\n")
                        subcat_summary = df[df['category'] == category]['subcategory'].value_counts()
                        f.write(subcat_summary.to_string())
            
            print(f"  -> Saved category summary to {summary_file}\n")

if __name__ == "__main__":
    main()
