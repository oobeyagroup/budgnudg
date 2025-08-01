from django.shortcuts import render, redirect
from .models import Transaction, Category
from .forms import TransactionForm

# Create your views here.

def uncategorized_transactions(request):
    transactions = Transaction.objects.filter(category__isnull=True)
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

def transactions_list(request):
    transactions = Transaction.objects.all()
    return render(request, "transactions/transactions_list.html", {"transactions": transactions})   

def home(request):
    return render(request, "home.html")