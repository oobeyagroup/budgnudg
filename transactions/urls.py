from django.urls import path
from . import views

urlpatterns = [
    path("uncategorized/", views.uncategorized_transactions, name="uncategorized_transactions"),
    path("list/", views.transactions_list, name="transactions_list"),
    path("categorize/<int:pk>/", views.categorize_transaction, name="categorize_transaction"),
    path("payorees/", views.payorees_list, name="payoree_list"),
    path("categories/", views.categories_list, name="categories_list"),
    path('resolve/<int:pk>/', views.resolve_transaction, name='resolve_transaction'),
    path('set/<int:transaction_id>/<str:field>/<int:value_id>/', views.set_transaction_field, name='set_transaction_field'),
    path('apply_current/<int:transaction_id>/', views.apply_current_to_similar, name='apply_current_to_similar'),]