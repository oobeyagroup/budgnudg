from django.shortcuts import render, redirect
from .models import Transaction, Category, Payoree
from .forms import TransactionForm

# Create your views here.

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