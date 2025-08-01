from django.urls import path
from . import views

urlpatterns = [
    path("uncategorized/", views.uncategorized_transactions, name="uncategorized_transactions"),
    path("list/", views.transactions_list, name="transactions_list"),
    path("categorize/<int:pk>/", views.categorize_transaction, name="categorize_transaction"),
    path("categories/", views.categories_list, name="categories_list"),]