import csv
from io import TextIOWrapper
from datetime import datetime
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import logging
import functools

logger = logging.getLogger(__name__)

def trace(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("TRACE: Called %s.%s", func.__module__, func.__qualname__)
        return func(*args, **kwargs)
    return wrapper

@trace
def parse_transaction_row(row, mapping, bank_account):
    txn_data = {
        'bank_account': bank_account,
        'suggested_subcategory': None,
        'suggested_category': None
    }

    for csv_col, model_field in mapping.items():
        value = (row.get(csv_col) or '').strip()
        if model_field == 'date':
            txn_data['date'] = parse_date(value)
        elif model_field == 'amount':
            try:
                txn_data['amount'] = float(Decimal(value))
            except (ValueError, Decimal.InvalidOperation):
                txn_data['amount'] = 0.0
        elif model_field == 'subcategory':
            txn_data['subcategory_name'] = value  # Just display in preview
        elif model_field == 'payoree':
            txn_data['payoree_name'] = value  # Display only
        else:
            txn_data[model_field] = value

    return txn_data

MAPPING_FILE = Path(__file__).resolve().parent.parent / 'csv_mappings.json'

@trace
def load_mapping_profiles():
    with open(MAPPING_FILE, 'r') as f:
        return json.load(f)

@trace
def parse_date(value):
    date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in date_formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None

@trace
def parse_transactions_file(file, profile_name, bank_account):
    profiles = load_mapping_profiles()
    profile = profiles.get(profile_name)

    if not profile:
        raise ValueError(f"Mapping profile '{profile_name}' not found.")

    mapping = profile['mapping']
    decoded_file = TextIOWrapper(file, encoding='utf-8')
    reader = csv.DictReader(decoded_file)

    transactions = []
    for row in reader:
        txn = {
            'bank_account': bank_account,
            'suggested_subcategory': None,
            'suggested_category': None
        }

        for csv_col, model_field in mapping.items():
            value = (row.get(csv_col) or '').strip()
            print(f"CSV Column: {csv_col}, Model Field: {model_field}, Value: {value}")
            if model_field == 'date':
                txn['date'] = parse_date(value)
            elif model_field == 'amount':
                try:
                    txn['amount'] = float(Decimal(value))
                except (ValueError, InvalidOperation):
                    txn['amount'] = 0.0
            elif model_field == 'subcategory':
                txn['subcategory'] = value
            elif model_field == 'payoree':
                txn['payoree_name'] = value
            else:
                txn[model_field] = value

        transactions.append(txn)

    return transactions

@trace
def parse_transaction_row(row, mapping, bank_account):
    txn = {
        'bank_account': bank_account,
        'suggested_subcategory': None,
        'suggested_category': None
    }

    for csv_col, model_field in mapping.items():
        value = (row.get(csv_col) or '').strip()
        # logger.debug("CSV C: %-16s  M: %-14s V: %s ", csv_col, model_field, value)
        if model_field == 'date':
            txn['date'] = parse_date(value)
        elif model_field == 'amount':
            try:
                txn['amount'] = float(Decimal(value))
            except (ValueError, InvalidOperation):
                txn['amount'] = 0.0
        elif model_field == 'subcategory':
            txn['subcategory'] = value  
        elif model_field == 'payoree':
            txn['payoree_name'] = value 
        else:
            txn[model_field] = value

    return txn

@trace
def map_csv_file_to_transactions(file_obj, profile_name, bank_account):
    all_profiles = load_mapping_profiles()
    profile = all_profiles.get(profile_name)

    if not profile:
        raise ValueError(f"Mapping profile '{profile_name}' not found.")

    mapping = profile['mapping']
    reader = csv.DictReader(file_obj)

    transactions = []
    for row in reader:
        logger
        txn = parse_transaction_row(row, mapping, bank_account)
        transactions.append(txn)
    logger.debug("Parsed %d transactions from CSV", len(transactions))  
    return transactions

@trace
def read_uploaded_file(uploaded_file, encoding='utf-8-sig'):
    """
    Safely read uploaded file content, handling BOM and decoding.
    Returns decoded string.
    """
    return uploaded_file.read().decode(encoding)
