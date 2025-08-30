from django.urls import path
from ingest.views import views as v
from .views.views import  check_upload, ScannedCheckListView
from ingest.views import match_check as mc
from .views.match_check import match_check

app_name = "ingest"

urlpatterns = [
    path("", v.BatchListView.as_view(), name="batch_list"),
    path("upload/", v.upload_csv, name="batch_upload"),
    path("<int:pk>/apply_profile/", v.apply_profile, name="batch_apply_profile"),
    path("<int:pk>/preview/", v.BatchPreviewView.as_view(), name="batch_preview"),
    path("<int:pk>/commit/", v.commit, name="batch_commit"),
    path("profiles/", v.FinancialAccountListView.as_view(), name="profile_list"),
    path(
        "profiles/<int:pk>/",
        v.FinancialAccountDetailView.as_view(),
        name="profile_detail",
    ),
    path("profiles/create/", v.CreateMappingProfileView.as_view(), name="create_mapping_profile"),
    path("checks/reconcile/", v.check_reconcile, name="checks_reconcile"),
    path("checks/match/<int:pk>/", mc.match_check, name="match_check"),
    path("checks/unlink/<int:check_id>/", v.unlink_check, name="checks_unlink"),  # POST
    path("checks/upload/", v.check_upload, name="check_upload"),
    path("checks/", ScannedCheckListView.as_view(), name="scannedcheck_list"),
    path("checks/txn/<int:pk>/edit/", v.txn_edit_partial, name="txn_edit_partial"),
    path("checks/txn/cancel/", v.txn_edit_cancel, name="txn_edit_cancel"),
]
