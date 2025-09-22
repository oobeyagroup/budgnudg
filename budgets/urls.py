from django.urls import path
from . import views

app_name = "budgets"

urlpatterns = [
    # Main views
    path("", views.BudgetListView.as_view(), name="list"),
    path("report/", views.BudgetReportView.as_view(), name="report"),
    path("<int:year>/<int:month>/", views.BudgetDetailView.as_view(), name="detail"),
    path("vs-actual/", views.BudgetVsActualView.as_view(), name="vs_actual"),
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
