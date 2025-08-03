from django.shortcuts import render, get_object_or_404, redirect
from .models import Transaction, Payoree, Category
from rapidfuzz import process
from .forms import TransactionForm

def resolve_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)

    # Fuzzy suggestions
    payoree_matches = []
    category_matches = []

    if not transaction.payoree:
        payoree_names = Payoree.objects.values_list('name', flat=True)
        payoree_matches = process.extract(transaction.description, payoree_names, limit=5)

    if not transaction.subcategory:
        category_names = Category.objects.values_list('name', flat=True)
        category_matches = process.extract(transaction.description, category_names, limit=5)

    # Find similar transactions
    norm_desc = Payoree.normalize_name(transaction.description)
    all_other = Transaction.objects.exclude(id=transaction.id)
    similar_transactions = [t for t in all_other if Payoree.normalize_name(t.description) == norm_desc]

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
        'payorees': Payoree.objects.all(),
        'categories': Category.objects.all(),
        'similar_transactions': similar_transactions,  # ✅ Important
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
    categories = Category.objects.all()
    return render(request, "transactions/categories_list.html", {"categories": categories})

def payorees_list(request):
    payorees = Payoree.objects.all()
    return render(request, "transactions/payoree_list.html", {"payorees": payorees})

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
    similar = Transaction.objects.exclude(id=transaction_id)
    similar = [t for t in similar if Payoree.normalize_name(t.description) == norm_desc]

    for t in similar:
        if transaction.payoree and not t.payoree:
            t.payoree = transaction.payoree
        if transaction.subcategory and not t.subcategory:
            t.subcategory = transaction.subcategory
        t.save()

    return redirect('resolve_transaction', pk=transaction_id)