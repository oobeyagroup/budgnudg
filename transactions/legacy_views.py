import re
from django.shortcuts import render, get_object_or_404, redirect
from .models import Transaction, Payoree, Category, Tag
from rapidfuzz import fuzz, process
from .forms import TransactionForm, FileUploadForm, TransactionImportForm, TransactionReviewForm
from django.db.models import Min, Max, Count, Prefetch
from django.contrib import messages
from .utils import parse_transactions_file, map_csv_file_to_transactions, load_mapping_profiles, read_uploaded_file, trace
import datetime
import logging
import functools
from .categorization import suggest_subcategory

logger = logging.getLogger(__name__)



@trace
def resolve_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)

    # Get all top-level categories for the form
    top_level_categories = Category.objects.filter(parent=None).prefetch_related('subcategories')
    
    # Get AI suggestions using our categorization system
    category_suggestion = None
    subcategory_suggestion = None
    
    # Import here to avoid circular import
    from .categorization import categorize_transaction, suggest_subcategory
    
    try:
        # Get AI category suggestion
        suggested_category_name = categorize_transaction(transaction.description, transaction.amount)
        if suggested_category_name:
            category_suggestion = Category.objects.filter(
                name=suggested_category_name, 
                parent=None
            ).first()
        
        # Get AI subcategory suggestion  
        suggested_subcategory_name = suggest_subcategory(transaction.description, transaction.amount)
        if suggested_subcategory_name:
            subcategory_suggestion = Category.objects.filter(
                name=suggested_subcategory_name, 
                parent__isnull=False
            ).first()
    except Exception as e:
        logger.warning(f"Error getting AI suggestions for transaction {pk}: {e}")

    # Find similar transactions and their category patterns
    similar = Transaction.objects.exclude(id=transaction.id).select_related('category', 'subcategory')
    similar_transactions = [
        t for t in similar
        if fuzz.token_set_ratio(
            normalize_description(transaction.description),
            normalize_description(t.description)
        ) >= 85
    ]
    
    # Get category patterns from similar transactions
    similar_categories = []
    category_counts = {}
    
    for sim_txn in similar_transactions:
        if sim_txn.category:
            key = (sim_txn.category, sim_txn.subcategory)
            category_counts[key] = category_counts.get(key, 0) + 1
    
    # Sort by frequency and prepare for template
    for (cat, subcat), count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        similar_categories.append((cat, subcat, count))

    # Form submission
    if request.method == 'POST':
        payoree_id = request.POST.get('payoree')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        
        if payoree_id:
            transaction.payoree = Payoree.objects.get(id=payoree_id)
        
        if category_id:
            transaction.category = Category.objects.get(id=category_id)
            # Clear subcategory if new category is selected
            if subcategory_id:
                subcategory = Category.objects.get(id=subcategory_id)
                # Verify subcategory belongs to selected category
                if subcategory.parent_id == int(category_id):
                    transaction.subcategory = subcategory
                else:
                    transaction.subcategory = None
            else:
                transaction.subcategory = None
        
        transaction.save()
        return redirect('resolve_transaction', pk=transaction.id)

    # Legacy fuzzy suggestions for payoree (keeping for compatibility)
    payoree_matches = []
    if not transaction.payoree:
        payoree_names = list(Payoree.objects.values_list('name', flat=True))
        payoree_matches = process.extract(
            transaction.description,
            payoree_names,
            scorer=fuzz.partial_ratio,
            limit=5
        )

    return render(request, 'transactions/resolve_transaction.html', {
        'transaction': transaction,
        'top_level_categories': top_level_categories,
        'category_suggestion': category_suggestion,
        'subcategory_suggestion': subcategory_suggestion,
        'similar_categories': similar_categories[:5],  # Top 5 most common
        'payoree_matches': payoree_matches,
        'payorees': Payoree.objects.order_by('name'),
        'similar_transactions': similar_transactions[:10],  # Limit for performance
    })

@trace
def uncategorized_transactions(request):
    transactions = Transaction.objects.filter(subcategory__isnull=True)
    return render(request, "transactions/uncategorized_list.html", {"transactions": transactions})

@trace
def categorize_transaction(request, pk):
    transaction = Transaction.objects.get(pk=pk)
    if request.method == "POST":
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            return redirect("uncategorized_transactions")
    else:
        form = TransactionForm(instance=transaction)
    return render(request, "transactions/categorize.html", {"form": form})

@trace
def categories_list(request):
    # Get all categories
    subcats = Category.objects.annotate(transaction_count=Count('transaction'))
    
    categories = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=subcats)
    )

    return render(request, 'transactions/categories_list.html', {'categories': categories})

from django.db.models import Count
from .models import Payoree

@trace
def payorees_list(request):
    payorees = Payoree.objects.annotate(transaction_count=Count('transaction')).order_by('name')

    if request.GET.get('nonzero'):
        payorees = payorees.filter(transaction_count__gt=0)

    return render(request, 'transactions/payoree_list.html', {
        'payorees': payorees,
        'request': request  # Pass request to template for checkbox state
    })

@trace
def transactions_list(request):
    sort_field = request.GET.get('sort', 'date')  # Default sort by date
    valid_fields = [
        'source', 'bank_account', 'sheet_account', 'date', 'description',
        'amount', 'account_type', 'check_num', 'payoree'
    ]
    if sort_field not in valid_fields:
        sort_field = 'date'
    all_transactions = Transaction.objects.all().order_by(sort_field)
    return render(request, "transactions/transactions_list.html", {"all_transactions": all_transactions})
    
@trace
def home(request):
    return render(request, "home.html")

from django.shortcuts import render
from .models import Transaction

@trace
def bank_accounts_list(request):
    # Get distinct bank_account values, exclude empty/null
    accounts = Transaction.objects.exclude(bank_account__isnull=True).exclude(bank_account='') \
                                  .values_list('bank_account', flat=True).distinct().order_by('bank_account')

    return render(request, 'transactions/bank_accounts_list.html', {'accounts': accounts})


@trace
def set_transaction_field(request, transaction_id, field, value_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)

    if field == 'payoree':
        payoree = get_object_or_404(Payoree, id=value_id)
        transaction.payoree = payoree
    elif field == 'subcategory':
        subcategory = get_object_or_404(Category, id=value_id)
        transaction.subcategory = subcategory
    else:
        return redirect('resolve_transaction', pk=transaction_id)  # Invalid field, redirect back

    transaction.save()
    return redirect('resolve_transaction', pk=transaction_id)

@trace
def apply_current_to_similar(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)

    if not transaction.payoree and not transaction.subcategory:
        return redirect('resolve_transaction', pk=transaction_id)  # Nothing to apply

    # Normalize description
    from transactions.models import Payoree, Category
    norm_desc = Payoree.normalize_name(transaction.description)

    # Find similar transactions
    similar = Transaction.objects.exclude(id=transaction.id)
    similar = [
        t for t in similar
        if fuzz.token_set_ratio(
            normalize_description(transaction.description),
            normalize_description(t.description)
        ) >= 85
    ]
    for t in similar:
        if transaction.payoree and not t.payoree:
            t.payoree = transaction.payoree
        if transaction.subcategory and not t.subcategory:
            t.subcategory = transaction.subcategory
        t.save()

    return redirect('resolve_transaction', pk=transaction_id)


@trace
def report_account_time_span(request):
    report = (
        Transaction.objects
        .exclude(bank_account__isnull=True)
        .exclude(bank_account='')
        .values('bank_account')
        .annotate(
            first_date=Min('date'),
            last_date=Max('date')
        )
        .order_by('bank_account')
    )

    return render(request, 'transactions/report_account_time_span.html', {'report': report})

@trace
def report_income_statement(request):
    transactions = Transaction.objects.all().order_by('date')
    income_statement = {}

    for transaction in transactions:
        if transaction.subcategory:
            category_name = transaction.subcategory.name
            if category_name not in income_statement:
                income_statement[category_name] = 0
            income_statement[category_name] += transaction.amount

    return render(request, 'transactions/report_income_statement.html', {'income_statement': income_statement})


@trace
def import_transactions(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            handle_file_upload(request.FILES['file'], 'transactions')
            messages.success(request, 'Transactions imported successfully.')
            return redirect('import_transactions')
    else:
        form = FileUploadForm()
    return render(request, 'transactions/import_form.html', {'form': form, 'title': 'Import Transactions'})

@trace
def import_categories(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            handle_file_upload(request.FILES['file'], 'categories')
            messages.success(request, 'Categories imported successfully.')
            return redirect('import_categories')
    else:
        form = FileUploadForm()
    return render(request, 'transactions/import_form.html', {'form': form, 'title': 'Import Categories'})

@trace
def import_payoree(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            handle_file_upload(request.FILES['file'], 'payoree')
            messages.success(request, 'Payoree imported successfully.')
            return redirect('import_payoree')
    else:
        form = FileUploadForm()
    return render(request, 'transactions/import_form.html', {'form': form, 'title': 'Import Payoree'})


# @trace
# def import_transactions_upload(request):
#     # Load real profiles from csv_mappings.json
#     profiles_dict = load_mapping_profiles()
#     profile_choices = [(name, name.capitalize()) for name in profiles_dict.keys()]
    
#     # Extract existing bank accounts for dropdown
#     existing_accounts = Transaction.objects.values_list('bank_account', flat=True).distinct()
#     account_choices = [(acct, acct) for acct in existing_accounts]

#     if request.method == 'POST':
#         form = TransactionImportForm(
#             request.POST,
#             request.FILES,
#             profile_choices=profile_choices,
#             account_choices=account_choices
#         )
#         if form.is_valid():
#             file = request.FILES['file']
#             profile = form.cleaned_data['mapping_profile']
#             bank_account = form.cleaned_data['bank_account']

#             request.session['import_file_name'] = file.name 
#             request.session['import_profile'] = profile
#             request.session['import_bank_account'] = bank_account
#             request.session['import_file'] = read_uploaded_file(file)

#             return redirect('import_transactions_preview')
#     else:
#         form = TransactionImportForm(
#             profile_choices=profile_choices,
#             account_choices=account_choices
#         )

#     return render(request, 'transactions/import_form.html', {'form': form, 'title': 'Import Transactions'})

# @trace
# def import_transactions_preview(request):
#     try:
#         profile_name = request.session['import_profile']
#         bank_account = request.session['import_bank_account']
#         file_data = request.session['import_file']
#         file_name = request.session.get('import_file_name', 'unknown.csv')
#     except KeyError:
#         logger.warning("Import preview failed due to missing session data.")
#         messages.error(request, "Import session data missing. Please re-upload.")
#         return redirect('import_transactions_upload')

#     from io import StringIO
#     parsed_file = StringIO(file_data)

#     transactions = map_csv_file_to_transactions(parsed_file, profile_name, bank_account)
#     logger.debug("Parsed %d transactions for preview.", len(transactions))

#     # 🚨 Warn if large import
#     if len(transactions) > 400:
#         logger.warning(f"Large import detected: {len(transactions)} transactions from {file_name}")

#     # Ensure serializable data
#     for txn in transactions:
#         if isinstance(txn.get('date'), datetime.date):
#             txn['date'] = txn['date'].isoformat()

#     request.session['parsed_transactions'] = transactions
#     request.session['import_file_name'] = file_name
#     request.session['review_index'] = 0

#     return render(request, 'transactions/import_transaction_preview.html', {
#         'transactions': transactions
#     })

# @trace
# def import_transactions_confirm(request):
#     from io import StringIO
#     from decimal import Decimal, InvalidOperation

#     transactions = request.session.get('parsed_transactions', [])
#     source_file = request.session.get('import_file_name', 'unknown.csv')
#     bank_account = request.session.get('import_bank_account')

#     imported = []
#     duplicates = []
#     skipped = []

#     for txn in transactions:
#         raw_date = txn.get('date')
#         try:
#             parsed_date = datetime.date.fromisoformat(raw_date)
#         except (ValueError, TypeError):
#             parsed_date = None

#         if not parsed_date:
#             skipped.append(txn)
#             continue

#         txn_data = {
#             'source': source_file,
#             'bank_account': bank_account,
#             'date': parsed_date,
#             'description': txn.get('description'),
#             'amount': txn.get('amount'),
#             'sheet_account': txn.get('sheet_account'),
#             'account_type': txn.get('account_type'),
#             'check_num': txn.get('check_num'),
#             'memo': txn.get('memo'),
#         }

#         # Duplicate check
#         existing = Transaction.objects.filter(
#             date=txn_data['date'],
#             amount=txn_data['amount'],
#             description=txn_data['description'],
#             bank_account=bank_account
#         )

#         if existing.exists():
#             logging.info("Duplicate transaction found: %s %50s",txn_data['date'], txn_data['description'])
#             duplicates.append((txn_data, list(existing)))
#             continue  # For now, skip; later allow user override

#         # Suggest subcategory if not mapped
#         subcat_name = txn.get('subcategory')
#         if not subcat_name:
#             subcat_name = suggest_subcategory(txn_data['description'])
#         subcat = Category.objects.filter(name=subcat_name).first()
#         txn_data['subcategory'] = subcat

#         # Suggest payoree if not mapped
#         payoree_name = txn.get('payoree')
#         if not payoree_name:
#             payoree_name = suggest_payoree(txn_data['description'])
        
#         if not payoree_name:
#             payoree = None  # Still None after suggestion — skip
#         else:
#             payoree = Payoree.get_existing(payoree_name)
#             if not payoree:
#                 payoree = Payoree.objects.create(name=payoree_name)
        
#         txn_data['payoree'] = payoree
#         # Ensure empty strings for nullable text fields to avoid IntegrityError
#         for field in ['account_type', 'sheet_account', 'check_num', 'memo']:
#             if txn_data.get(field) is None:
#                 txn_data[field] = ''

#         # Save transaction
#         try:
            
#             saved_txn = Transaction.objects.create(**txn_data)
#             assign_default_tags(saved_txn)
#             imported.append(saved_txn)
#             logger.debug("Imported transaction: %60s", saved_txn)
#         except Exception:
#             logging.exception("Failed to save transaction: %s %30s",txn_data['date'], txn_data['description'])
#             skipped.append(txn_data)

#     all_transactions = Transaction.objects.all().order_by('-date')[:50]
#     context = {
#         'imported_count': len(imported),
#         'duplicate_count': len(duplicates),
#         'skipped_count': len(skipped),
#         'duplicates': duplicates,
#         'all_transactions': all_transactions  
#     }

#     return render(request, 'transactions/transactions_list.html', context)


@trace
def suggest_payoree(description):
    known = Payoree.objects.values_list('name', flat=True)
    for name in known:
        if name.lower() in description.lower():
            return name
    return None

@trace
def assign_default_tags(transaction):
    tag_names = ['day2day', 'monitor']  # Placeholder logic
    for name in tag_names:
        tag, _ = Tag.objects.get_or_create(name=name)
        transaction.tags.add(tag)

@trace
def legacy_dashboard_home(request):

    # Panel 1: Recurring Transactions (placeholder logic)
    today = date.today()
    recurring = Transaction.objects.filter(tags__name='recurring')\
                .annotate(last_paid_date=Max('date'))\
                .order_by('date')[:10]

    # Panel 2: Accounts Summary (past 6 months)
    from django.db.models.functions import TruncMonth
    six_months_ago = today - timedelta(days=180)
    accounts_summary = Transaction.objects.filter(date__gte=six_months_ago)\
                          .annotate(month=TruncMonth('date'))\
                          .values('bank_account', 'month')\
                          .annotate(txn_count=Count('id'))\
                          .order_by('-month')

    # Panel 3: Tagged Transactions (hardcoded tag)
    tagged = Transaction.objects.filter(tags__name='monitor').order_by('-date')[:10]

    # Full Transaction List (recent first)
    all_transactions = Transaction.objects.all().order_by('-date')[:50]

    uncategorized_counts = Transaction.objects.filter(subcategory__isnull=True)\
        .values('bank_account')\
        .annotate(uncategorized_count=Count('id'))
    uncategorized_map = {item['bank_account']: item['uncategorized_count'] for item in uncategorized_counts}

    no_payoree_counts = Transaction.objects.filter(payoree__isnull=True)\
        .values('bank_account')\
        .annotate(no_payoree_count=Count('id'))
    no_payoree_map = {item['bank_account']: item['no_payoree_count'] for item in no_payoree_counts}

    months = sorted(
        {item['month'].strftime('%Y-%m') for item in accounts_summary},
        reverse=True
    )

    summary_dict = {}
    for item in accounts_summary:
        acct = item['bank_account']
        month = item['month'].strftime('%Y-%m')
        count = item['txn_count']
        if acct not in summary_dict:
            summary_dict[acct] = {}
        summary_dict[acct][month] = count



    return render(request, 'transactions/dashboard_home.html', {
        'recurring': recurring,
        'accounts_summary': accounts_summary,
        'tagged': tagged,
        'all_transactions': all_transactions,
        'uncategorized_map': uncategorized_map,
        'no_payoree_map': no_payoree_map,
        'months': months,
        'summary_dict': summary_dict,
    })

@trace
def review_transaction(request):
    session_txns = request.session.get('parsed_transactions')
    current_index = request.session.get('review_index', 0)

    if not session_txns:
        logger.warning("Review transaction failed: no transactions in session.")
        return redirect('import_transactions_preview')

    if current_index >= len(session_txns):
        return redirect('import_transactions_confirm')

    txn = session_txns[current_index]

    # Auto-suggest subcategory if missing
    if not txn.get('subcategory'):
        suggested = suggest_subcategory(txn.get('description', ''))
        if suggested:
            txn['subcategory'] = suggested

    if request.method == 'POST':
        form = TransactionReviewForm(request.POST)
        if form.is_valid():
            txn_data = form.cleaned_data
            from decimal import Decimal
            for key, value in txn_data.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    txn_data[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    txn_data[key] = str(value)
            session_txns[current_index] = txn_data
            request.session['parsed_transactions'] = session_txns
            request.session['review_index'] = current_index + 1
            return redirect('review_transaction')
    else:
        form = TransactionReviewForm(initial=txn)

    return render(request, 'transactions/review_transaction.html', {
        'form': form,
        'current_index': current_index + 1,
        'total': len(session_txns)
    })


def normalize_description(desc):
    # Remove 11-digit numbers and WEB ID numbers
    cleaned = re.sub(r'\b\d{11}\b', '', desc)
    cleaned = re.sub(r'WEB ID[:]? \d+', '', cleaned, flags=re.IGNORECASE)
    return cleaned.lower().strip()


@trace
def normalize_text(text):
    text = re.sub(r'\W+', ' ', text)
    return text.lower().strip()

@trace
def review_transaction(request):
    session_txns = request.session.get('parsed_transactions')
    current_index = request.session.get('review_index', 0)

    if not session_txns:
        logger.warning("Review transaction failed: no transactions in session.")
        return redirect('import_transactions_preview')

    if current_index >= len(session_txns):
        return redirect('import_transactions_confirm')

    txn = session_txns[current_index]

    # Auto-suggest subcategory if missing
    if not txn.get('subcategory'):
        suggested = suggest_subcategory(txn.get('description', ''))
        if suggested:
            txn['subcategory'] = suggested

    if request.method == 'POST':
        form = TransactionReviewForm(request.POST)
        if form.is_valid():
            txn_data = form.cleaned_data
            from decimal import Decimal
            for key, value in txn_data.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    txn_data[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    txn_data[key] = str(value)
            session_txns[current_index] = txn_data
            request.session['parsed_transactions'] = session_txns
            request.session['review_index'] = current_index + 1
            return redirect('review_transaction')
    else:
        form = TransactionReviewForm(initial=txn)

    return render(request, 'transactions/review_transaction.html', {
        'form': form,
        'current_index': current_index + 1,
        'total': len(session_txns)
    })