# transactions/urls.py
from django.urls import path

# CBVs (import from submodules directly)
from transactions.views.import_categories import ImportCategoriesView
from transactions.views.transactions_list import TransactionListView
from transactions.views.collapsible_list import CollapsibleTransactionListView
from transactions.views.dashboard import DashboardView
from transactions.views.payorees import PayoreesListView
from transactions.views.categorize import CategorizeTransactionView
# Legacy uncategorized view import - replaced with filters on transaction list
# from transactions.views.uncategorized import UncategorizedTransactionsView
from transactions.views.categories import CategoriesListView
from transactions.views.payoree_report import PayoreeReportView
from transactions.views.set_field import SetTransactionFieldView
from transactions.views.apply_current import ApplyCurrentToSimilarView
from transactions.views.bank_accounts import BankAccountsListView
from transactions.views.edit import TransactionEditView, get_subcategories_for_category
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
    SimilarTransactionsAPIView,
    ExcludeSimilarTransactionAPIView,
)

app_name = 'transactions'

urlpatterns = [
    # Dashboard
    path("", DashboardView.as_view(), name="dashboard"),


    # Payoree Report
    path("payoree-report/", PayoreeReportView.as_view(), name="payoree_report"),
    path("payoree/<int:pk>/", __import__('transactions.views.payoree_detail').views.payoree_detail.PayoreeDetailView.as_view(), name="payoree_detail"),

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
    
    # Keyword Rules Management
    path("keyword-rules/", KeywordRulesView.as_view(), name="keyword_rules"),
    path("keyword-rules/add/", AddKeywordRuleView.as_view(), name="add_keyword_rule"),
    path("keyword-rules/delete/<int:rule_id>/", DeleteKeywordRuleView.as_view(), name="delete_keyword_rule"),
    
    # Transactions list (CBV)
    path("list/", TransactionListView.as_view(), name="transactions_list"),
    
    # Collapsible transaction list (CBV)
    path("collapsible/", CollapsibleTransactionListView.as_view(), name="collapsible_transaction_list"),
    
    # Transaction edit
    path("edit/<int:pk>/", TransactionEditView.as_view(), name="edit_transaction"),
    
    # Legacy uncategorized view - replaced with filters on transaction list
    # path("uncategorized/", UncategorizedTransactionsView.as_view(), name="uncategorized_transactions"),
    path("set/<int:transaction_id>/<str:field>/<int:value_id>/", SetTransactionFieldView.as_view(), name="set_transaction_field"),
    path("apply_current/<int:transaction_id>/", ApplyCurrentToSimilarView.as_view(), name="apply_current_to_similar"),
    path("bank-accounts/", BankAccountsListView.as_view(), name="bank_accounts_list"),
    path("report_account_time_span/", ReportAccountTimeSpanView.as_view(), name="report_account_time_span"),
    path("report_income_statement/", ReportIncomeStatementView.as_view(), name="report_income_statement"),
    path("import/payoree/", ImportPayoreeView.as_view(), name="import_payoree"),

    # API Endpoints
    path("api/subcategories/<int:category_id>/", SubcategoriesAPIView.as_view(), name="api_subcategories"),
    path("api/suggestions/<int:transaction_id>/", TransactionSuggestionsAPIView.as_view(), name="api_suggestions"),
    path("api/similar/<int:transaction_id>/", SimilarTransactionsAPIView.as_view(), name="api_similar"),
    path("api/exclude/<int:transaction_id>/", ExcludeSimilarTransactionAPIView.as_view(), name="api_exclude_similar"),

    # Pattern Management
    path("patterns/", pattern_management, name="pattern_management"),
    path("patterns/<str:pattern_key>/", pattern_detail, name="pattern_detail"),
    path("patterns/api/merge/", merge_patterns, name="merge_patterns"),
    path("patterns/api/rename/", rename_pattern, name="rename_pattern"),
    path("patterns/api/test-extraction/", test_extraction, name="test_extraction"),
    path("patterns/api/search/", search_patterns, name="search_patterns"),

    # Learning Patterns Management - Commented out until views are implemented
    # path("learning-patterns/", LearningPatternsView.as_view(), name="learning_patterns"),
    # path("learning-patterns/export/", ExportLearningDataView.as_view(), name="export_learning_data"),
    # path("learning-patterns/import/", ImportLearningDataView.as_view(), name="import_learning_data"),
    # path("learning-patterns/delete-subcat/<int:learned_id>/", DeleteLearnedSubcatView.as_view(), name="delete_learned_subcat"),
    # path("learning-patterns/delete-payoree/<int:learned_id>/", DeleteLearnedPayoreeView.as_view(), name="delete_learned_payoree"),
    # path("learning-patterns/clear-subcats/", ClearAllLearnedSubcatsView.as_view(), name="clear_all_learned_subcats"),
    # path("learning-patterns/clear-payorees/", ClearAllLearnedPayoreesView.as_view(), name="clear_all_learned_payorees"),


]