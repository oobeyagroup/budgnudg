# transactions/urls.py
from django.urls import path

# CBVs (import from submodules directly)
from transactions.views.transactions_list import TransactionListView
from transactions.views.collapsible_list import CollapsibleTransactionListView
from transactions.views.needs_level_report import NeedsLevelReportView
from transactions.views.dashboard import DashboardView
from transactions.views.payorees import PayoreesListView, PayoreeEditView
from transactions.views.categorize import CategorizeTransactionView
from transactions.views.categories import CategoriesListView
from transactions.views.payoree_report import PayoreeReportView
from transactions.views.set_field import SetTransactionFieldView
from transactions.views.apply_current import ApplyCurrentToSimilarView
from transactions.views.bank_accounts import BankAccountsListView
from transactions.views.edit import TransactionEditView, get_subcategories_for_category
from transactions.views.search import search_transactions
from transactions.views.reports import (
    ReportAccountTimeSpanView,
    ReportIncomeStatementView,
    UpcomingReportView,
)
from transactions.views.category_training import (
    CategoryTrainingUploadView,
    CategoryTrainingAnalyzeView,
    CategoryTrainingSessionView,
    CategoryTrainingCompleteView,
    LearnFromCurrentView,
    KeywordRulesView,
    AddKeywordRuleView,
    DeleteKeywordRuleView,
)
from transactions.views.pattern_management import (
    pattern_management,
    pattern_detail,
    merge_patterns,
    rename_pattern,
    test_extraction,
    search_patterns,
)
from transactions.views.api import (
    SubcategoriesAPIView,
    TransactionSuggestionsAPIView,
    PayoreeDefaultsAPIView,
    SimilarTransactionsAPIView,
    ExcludeSimilarTransactionAPIView,
)
from transactions.views.recurring import CreateRecurringFromTransactionView
from transactions.views.payorees import RecurringSeriesListView
from transactions.views.recurring import UpdateSeedTxnView
from transactions.views.test_api import create_test_transaction, check_series_for_seed
from transactions.views.reports import BudgetMonthlyReport2
from transactions.views.report_budget import BudgetNestedReportView, BudgetDrilldownView
from transactions.views.pivot_table import FlexiblePivotTableView

app_name = "transactions"

urlpatterns = [
    # Search functionality
    path("search/", search_transactions, name="search"),
    # Dashboard
    path("", DashboardView.as_view(), name="dashboard"),
    # Payoree Report
    path("payoree-report/", PayoreeReportView.as_view(), name="payoree_report"),
    path(
        "payoree/<int:pk>/",
        __import__(
            "transactions.views.payoree_detail"
        ).views.payoree_detail.PayoreeDetailView.as_view(),
        name="payoree_detail",
    ),
    path("reports/budget2/", BudgetMonthlyReport2.as_view(), name="report_budget"),
    path(
        "reports/budget/", BudgetNestedReportView.as_view(), name="report_budget_nested"
    ),
    path(
        "reports/budget/subcat/<int:subcat_id>/",
        BudgetDrilldownView.as_view(),
        name="report_budget_drilldown",
    ),
    path(
        "reports/pivot/",
        FlexiblePivotTableView.as_view(),
        name="pivot_table",
    ),
    path("payoree/<int:pk>/edit/", PayoreeEditView.as_view(), name="payoree_edit"),
    path("payorees/", PayoreesListView.as_view(), name="payorees_list"),
    path("categories/", CategoriesListView.as_view(), name="categories_list"),
    path(
        "categorize/<int:pk>/",
        CategorizeTransactionView.as_view(),
        name="categorize_transaction",
    ),
    # Category Training System
    path(
        "training/upload/",
        CategoryTrainingUploadView.as_view(),
        name="category_training_upload",
    ),
    path(
        "training/analyze/",
        CategoryTrainingAnalyzeView.as_view(),
        name="category_training_analyze",
    ),
    path(
        "training/session/",
        CategoryTrainingSessionView.as_view(),
        name="category_training_session",
    ),
    path(
        "training/complete/",
        CategoryTrainingCompleteView.as_view(),
        name="category_training_complete",
    ),
    path(
        "learn-from-current/<int:transaction_id>/",
        LearnFromCurrentView.as_view(),
        name="learn_from_current",
    ),
    # Keyword Rules Management
    path("keyword-rules/", KeywordRulesView.as_view(), name="keyword_rules"),
    path("keyword-rules/add/", AddKeywordRuleView.as_view(), name="add_keyword_rule"),
    path(
        "keyword-rules/delete/<int:rule_id>/",
        DeleteKeywordRuleView.as_view(),
        name="delete_keyword_rule",
    ),
    # Transactions list (CBV)
    path("list/", TransactionListView.as_view(), name="transactions_list"),
    # Collapsible transaction list (CBV)
    path(
        "collapsible/",
        CollapsibleTransactionListView.as_view(),
        name="collapsible_transaction_list",
    ),
    # Needs level report (CBV)
    path(
        "needs-level-report/",
        NeedsLevelReportView.as_view(),
        name="needs_level_report",
    ),
    # Transaction edit
    path("edit/<int:pk>/", TransactionEditView.as_view(), name="edit_transaction"),
    path(
        "set/<int:transaction_id>/<str:field>/<int:value_id>/",
        SetTransactionFieldView.as_view(),
        name="set_transaction_field",
    ),
    path(
        "apply_current/<int:transaction_id>/",
        ApplyCurrentToSimilarView.as_view(),
        name="apply_current_to_similar",
    ),
    path("bank-accounts/", BankAccountsListView.as_view(), name="bank_accounts_list"),
    path(
        "report_account_time_span/",
        ReportAccountTimeSpanView.as_view(),
        name="report_account_time_span",
    ),
    path(
        "report_income_statement/",
        ReportIncomeStatementView.as_view(),
        name="report_income_statement",
    ),
    path("report_upcoming/", UpcomingReportView.as_view(), name="report_upcoming"),
    # API Endpoints
    path(
        "api/subcategories/<int:category_id>/",
        SubcategoriesAPIView.as_view(),
        name="api_subcategories",
    ),
    path(
        "api/suggestions/<int:transaction_id>/",
        TransactionSuggestionsAPIView.as_view(),
        name="api_suggestions",
    ),
    path(
        "api/payoree-defaults/<int:payoree_id>/",
        PayoreeDefaultsAPIView.as_view(),
        name="api_payoree_defaults",
    ),
    path(
        "api/similar/<int:transaction_id>/",
        SimilarTransactionsAPIView.as_view(),
        name="api_similar",
    ),
    path(
        "api/exclude/<int:transaction_id>/",
        ExcludeSimilarTransactionAPIView.as_view(),
        name="api_exclude_similar",
    ),
    path(
        "recurring/from-txn/<int:pk>/",
        CreateRecurringFromTransactionView.as_view(),
        name="recurring_from_txn",
    ),
    path("recurring/", RecurringSeriesListView.as_view(), name="recurring_series_list"),
    path(
        "recurring/update-seed/<int:series_id>/",
        UpdateSeedTxnView.as_view(),
        name="recurring_update_seed",
    ),
    # Test-only API endpoints (enabled when DEBUG=True or ENABLE_TEST_API=1)
    path(
        "test-api/create-transaction/",
        create_test_transaction,
        name="test_create_transaction",
    ),
    path(
        "test-api/check-series/<int:txn_id>/",
        check_series_for_seed,
        name="test_check_series",
    ),
    path(
        "test-api/seed-series/<int:txn_id>/",
        __import__("transactions.views.test_api").views.test_api.seed_series_test_api,
        name="test_seed_series",
    ),
    path(
        "test-api/debug-series/<int:txn_id>/",
        __import__(
            "transactions.views.test_api"
        ).views.test_api.debug_list_series_for_txn,
        name="test_debug_series",
    ),
    # Pattern Management
    path("patterns/", pattern_management, name="pattern_management"),
    path("patterns/<str:pattern_key>/", pattern_detail, name="pattern_detail"),
    path("patterns/api/merge/", merge_patterns, name="merge_patterns"),
    path("patterns/api/rename/", rename_pattern, name="rename_pattern"),
    path("patterns/api/test-extraction/", test_extraction, name="test_extraction"),
    path("patterns/api/search/", search_patterns, name="search_patterns"),
]
