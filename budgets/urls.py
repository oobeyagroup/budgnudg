from django.urls import path
from . import views
from .views.classification import budget_classification_analysis, update_budget_allocation

app_name = "budgets"

urlpatterns = [
    # Main views
    path("", views.BudgetListView.as_view(), name="list"),
    path("report/", views.BudgetReportView.as_view(), name="report"),
    path("<int:year>/<int:month>/", views.BudgetDetailView.as_view(), name="detail"),
    path("vs-actual/", views.BudgetVsActualView.as_view(), name="vs_actual"),
    # Classification analysis
    path("classification/", budget_classification_analysis, name="classification_analysis"),
    path("classification/update/", update_budget_allocation, name="classification_update"),
    # Wizard flow
    path("wizard/", views.BudgetWizardView.as_view(), name="wizard"),
    path(
        "wizard-simple/", views.BudgetWizardSimpleView.as_view(), name="wizard_simple"
    ),
    # API endpoints
    path("api/baseline/", views.BudgetBaselineAPIView.as_view(), name="api_baseline"),
    path("api/suggest/", views.BudgetSuggestAPIView.as_view(), name="api_suggest"),
    path("api/commit/", views.BudgetCommitAPIView.as_view(), name="api_commit"),
]
