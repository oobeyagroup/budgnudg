import re
from django.shortcuts import render, get_object_or_404, redirect
from .models import Transaction, Payoree, Category
from rapidfuzz import fuzz, process
from .forms import TransactionForm, FileUploadForm, TransactionImportForm
from django.db.models import Min, Max, Count, Prefetch
from django.contrib import messages
from .utils import parse_transactions_file, map_csv_file_to_transactions, load_mapping_profiles

def normalize_description(desc):
    # Remove 11-digit numbers and WEB ID numbers
    cleaned = re.sub(r'\b\d{11}\b', '', desc)
    cleaned = re.sub(r'WEB ID[:]? \d+', '', cleaned, flags=re.IGNORECASE)
    return cleaned.lower().strip()

def resolve_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)

    # Fuzzy suggestions
    payoree_matches = []
    category_matches = []

    if not transaction.payoree:
        payoree_names = list(Payoree.objects.values_list('name', flat=True))
        payoree_matches = process.extract(
            transaction.description,
            payoree_names,
            scorer=fuzz.partial_ratio,  # Favors beginning matches
            limit=5
        )

    if not transaction.subcategory:
        category_names = list(Category.objects.values_list('name', flat=True))
        category_matches = process.extract(
            transaction.description,
            category_names,
            scorer=fuzz.partial_ratio,  # Favors prefix
            limit=5
        )

    # Find similar transactions
    similar = Transaction.objects.exclude(id=transaction.id)
    similar = [
        t for t in similar
        if fuzz.token_set_ratio(
            normalize_description(transaction.description),
            normalize_description(t.description)
        ) >= 85
    ]
    # Form submission
    if request.method == 'POST':
        payoree_id = request.POST.get('payoree')
        subcategory_id = request.POST.get('subcategory')
        if payoree_id:
            transaction.payoree = Payoree.objects.get(id=payoree_id)
        if subcategory_id:
            transaction.subcategory = Category.objects.get(id=subcategory_id)
        transaction.save()
        return redirect('resolve_transaction', pk=transaction.id)

    return render(request, 'transactions/resolve_transaction.html', {
        'transaction': transaction,
        'payoree_matches': payoree_matches,
        'category_matches': category_matches,
        'payorees': Payoree.objects.order_by('name'),
        'categories': Category.objects.order_by('name'),
        'similar_transactions': similar, 
    })

def uncategorized_transactions(request):
    transactions = Transaction.objects.filter(subcategory__isnull=True)
    return render(request, "transactions/uncategorized_list.html", {"transactions": transactions})

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

def categories_list(request):
    # Get all categories
    subcats = Category.objects.annotate(transaction_count=Count('transaction'))
    
    categories = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=subcats)
    )

    return render(request, 'transactions/categories_list.html', {'categories': categories})

from django.db.models import Count
from .models import Payoree

def payorees_list(request):
    payorees = Payoree.objects.annotate(transaction_count=Count('transaction')).order_by('name')

    if request.GET.get('nonzero'):
        payorees = payorees.filter(transaction_count__gt=0)

    return render(request, 'transactions/payoree_list.html', {
        'payorees': payorees,
        'request': request  # Pass request to template for checkbox state
    })

def transactions_list(request):
    sort_field = request.GET.get('sort', 'date')  # Default sort by date
    valid_fields = [
        'source', 'bank_account', 'sheet_account', 'date', 'description',
        'amount', 'account_type', 'check_num', 'payoree'
    ]
    if sort_field not in valid_fields:
        sort_field = 'date'
    transactions = Transaction.objects.all().order_by(sort_field)
    return render(request, "transactions/transactions_list.html", {"transactions": transactions})
    
def home(request):
    return render(request, "home.html")

from django.shortcuts import render
from .models import Transaction

def bank_accounts_list(request):
    # Get distinct bank_account values, exclude empty/null
    accounts = Transaction.objects.exclude(bank_account__isnull=True).exclude(bank_account='') \
                                  .values_list('bank_account', flat=True).distinct().order_by('bank_account')

    return render(request, 'transactions/bank_accounts_list.html', {'accounts': accounts})


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



def handle_file_upload(file, import_type):
    # Placeholder for actual processing logic
    # import_type: 'transactions', 'categories', 'payoree'
    # Implement parsing here
    pass

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



# def import_transactions(request):
#     # Build choices for mapping profile and bank account
#     mapping_profiles = [('default', 'Default Profile')]  # TODO: pull real profiles if stored
#     existing_accounts = Transaction.objects.values_list('bank_account', flat=True).distinct()
#     account_choices = [(acct, acct) for acct in existing_accounts]

#     if request.method == 'POST':
#         form = TransactionImportForm(request.POST, request.FILES, profile_choices=mapping_profiles, account_choices=account_choices)
#         if form.is_valid():
#             file = request.FILES['file']
#             profile = form.cleaned_data['mapping_profile']
#             bank_account = form.cleaned_data['bank_account']

#             try:
#                 # Parse and transform the uploaded file
#                 imported_transactions = parse_transactions_file(file, profile, bank_account)

#                 # Display them using your existing list template
#                 return render(request, 'transaction_list.html', {
#                     'transactions': imported_transactions,
#                     'import_mode': True  # So you can hide edit/resolve buttons if needed
#                 })

#             except Exception as e:
#                 messages.error(request, f'Import failed: {str(e)}')
#     else:
#         form = TransactionImportForm(profile_choices=mapping_profiles, account_choices=account_choices)

#     return render(request, 'transactions/import_transaction_preview.html', {  'transactions': import_transactions})

def import_transactions_upload(request):
    # Load real profiles from csv_mappings.json
    profiles_dict = load_mapping_profiles()
    profile_choices = [(name, name.capitalize()) for name in profiles_dict.keys()]
    
    # Extract existing bank accounts for dropdown
    existing_accounts = Transaction.objects.values_list('bank_account', flat=True).distinct()
    account_choices = [(acct, acct) for acct in existing_accounts]

    if request.method == 'POST':
        form = TransactionImportForm(
            request.POST,
            request.FILES,
            profile_choices=profile_choices,
            account_choices=account_choices
        )
        if form.is_valid():
            file = request.FILES['file']
            profile = form.cleaned_data['mapping_profile']
            bank_account = form.cleaned_data['bank_account']

            request.session['import_profile'] = profile
            request.session['import_bank_account'] = bank_account
            request.session['import_file'] = file.read().decode('utf-8')

            return redirect('import_transactions_preview')
    else:
        form = TransactionImportForm(
            profile_choices=profile_choices,
            account_choices=account_choices
        )

    return render(request, 'transactions/import_form.html', {'form': form, 'title': 'Import Transactions'})

def import_transactions_preview(request):
    try:
        profile_name = request.session['import_profile']
        bank_account = request.session['import_bank_account']
        file_data = request.session['import_file']
    except KeyError:
        messages.error(request, "Import session data missing. Please re-upload.")
        return redirect('import_transactions_upload')

    from io import StringIO
    parsed_file = StringIO(file_data)

    transactions = map_csv_file_to_transactions(parsed_file, profile_name, bank_account)

    return render(request, 'transactions/import_transaction_preview.html', {
        'transactions': transactions
    })