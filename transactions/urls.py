# transactions/urls.py
from django.urls import path

# CBVs (import from submodules directly)
from transactions.views.import_flow import (
    ImportUploadView,
    ImportPreviewView,
    ReviewTransactionView,
    ImportConfirmView,
)
from transactions.views.import_categories import ImportCategoriesView
from transactions.views.transactions_list import TransactionListView
from transactions.views.dashboard import DashboardView
from transactions.views.payorees import PayoreesListView
from transactions.views.categorize import CategorizeTransactionView
from transactions.views.uncategorized import UncategorizedTransactionsView
from transactions.views.categories import CategoriesListView
from transactions.views.resolve import ResolveTransactionView
from transactions.views.set_field import SetTransactionFieldView
from transactions.views.apply_current import ApplyCurrentToSimilarView
from transactions.views.bank_accounts import BankAccountsListView
from transactions.views.reports import (
    ReportAccountTimeSpanView,
    ReportIncomeStatementView,
)
from transactions.views.import_payoree import ImportPayoreeView
from transactions.views.category_training import (
    CategoryTrainingUploadView,
    CategoryTrainingAnalyzeView,
    CategoryTrainingSessionView,
    CategoryTrainingCompleteView,
    LearnFromCurrentView,
)

# Legacy FBVs (temporary)
from transactions import legacy_import_views as legacy

urlpatterns = [
    # Dashboard
    path("", DashboardView.as_view(), name="dashboard"),

    # NEW: import flow (CBV)
    # path("import/transactions/", ImportUploadView.as_view(), name="import_transactions_upload"),
    # path("import/transactions/preview/", ImportPreviewView.as_view(), name="import_transactions_preview"),
    # path("import/transactions/review/", ReviewTransactionView.as_view(), name="review_transaction"),
    # path("import/transactions/confirm/", ImportConfirmView.as_view(), name="import_transactions_confirm"),
    path("payorees/", PayoreesListView.as_view(), name="payorees_list"),
    path("categories/", CategoriesListView.as_view(), name="categories_list"),
    path("categorize/<int:pk>/", CategorizeTransactionView.as_view(), name="categorize_transaction"),

    # NEW: categories import (CBV)
    path("import/categories/", ImportCategoriesView.as_view(), name="import_categories"),

    # Category Training System
    path("training/upload/", CategoryTrainingUploadView.as_view(), name="category_training_upload"),
    path("training/analyze/", CategoryTrainingAnalyzeView.as_view(), name="category_training_analyze"),
    path("training/session/", CategoryTrainingSessionView.as_view(), name="category_training_session"),
    path("training/complete/", CategoryTrainingCompleteView.as_view(), name="category_training_complete"),
    path("learn-from-current/<int:transaction_id>/", LearnFromCurrentView.as_view(), name="learn_from_current"),

    # Import wizard (FBV)
    path("import/transactions/", legacy.import_transactions_upload, name="import_transactions_upload"),
    path("import/transactions/preview/", legacy.import_transactions_preview, name="import_transactions_preview"),
    path("import/transactions/review/", legacy.review_transaction, name="review_transaction"),
    path("import/transactions/confirm/", legacy.import_transactions_confirm, name="import_transactions_confirm"),

    # Transactions list (CBV)
    path("list/", TransactionListView.as_view(), name="transactions_list"),
    path("uncategorized/", UncategorizedTransactionsView.as_view(), name="uncategorized_transactions"),
    path("resolve/<int:pk>/", ResolveTransactionView.as_view(), name="resolve_transaction"),
    path("set/<int:transaction_id>/<str:field>/<int:value_id>/", SetTransactionFieldView.as_view(), name="set_transaction_field"),
    path("apply_current/<int:transaction_id>/", ApplyCurrentToSimilarView.as_view(), name="apply_current_to_similar"),
    path("bank-accounts/", BankAccountsListView.as_view(), name="bank_accounts_list"),
    path("report_account_time_span/", ReportAccountTimeSpanView.as_view(), name="report_account_time_span"),
    path("report_income_statement/", ReportIncomeStatementView.as_view(), name="report_income_statement"),
    path("import/payoree/", ImportPayoreeView.as_view(), name="import_payoree"),


    # Legacy FBVs (keep ONLY the ones you still use; avoid duplicates)
    # path("uncategorized/", fbv.uncategorized_transactions, name="uncategorized_transactions"),
    # path("categories/", fbv.categories_list, name="categories_list"),
    # path("resolve/<int:pk>/", fbv.resolve_transaction, name="resolve_transaction"),
    # path("set/<int:transaction_id>/<str:field>/<int:value_id>/", fbv.set_transaction_field, name="set_transaction_field"),
    # path("apply_current/<int:transaction_id>/", fbv.apply_current_to_similar, name="apply_current_to_similar"),
    # path("bank-accounts/", fbv.bank_accounts_list, name="bank_accounts_list"),
    # path("report_account_time_span/", fbv.report_account_time_span, name="report_account_time_span"),
    # path("report_income_statement/", fbv.report_income_statement, name="report_income_statement"),
    #  removed: duplicate import/categories and import/payoree FBVs
]