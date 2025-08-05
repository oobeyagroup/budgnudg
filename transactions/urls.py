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
    path('apply_current/<int:transaction_id>/', views.apply_current_to_similar, name='apply_current_to_similar'),
    path('bank-accounts/', views.bank_accounts_list, name='bank_accounts_list'),
    path('report_account_time_span/', views.report_account_time_span, name='report_account_time_span'),
    path('report_income_statement/', views.report_income_statement, name='report_income_statement'),
    path('import/categories/', views.import_categories, name='import_categories'),
    path('import/payoree/', views.import_payoree, name='import_payoree'),
    path('import/transactions/', views.import_transactions_upload, name='import_transactions_upload'),
    path('import/transactions/preview/', views.import_transactions_preview, name='import_transactions_preview'),
]