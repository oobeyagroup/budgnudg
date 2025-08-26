from django.urls import path
from ingest import views as v
from .views import review_scanned_check, check_upload, ScannedCheckListView

app_name = "ingest"

urlpatterns = [
    path("", v.BatchListView.as_view(), name="batch_list"),
    path("upload/", v.upload_csv, name="batch_upload"),
    path("<int:pk>/apply_profile/", v.apply_profile, name="batch_apply_profile"),
    path("<int:pk>/preview/", v.BatchPreviewView.as_view(), name="batch_preview"),
    path("<int:pk>/commit/", v.commit, name="batch_commit"),
    path("profiles/", v.MappingProfileListView.as_view(), name="profile_list"),
    path("profiles/<int:pk>/", v.MappingProfileDetailView.as_view(), name="profile_detail"),

    path("checks/reconcile/", v.check_reconcile, name="checks_reconcile"),
    path("checks/match/", v.match_check, name="checks_match"),           # POST
    path("checks/unlink/<int:check_id>/", v.unlink_check, name="checks_unlink"),  # POST
    path("checks/upload/", v.check_upload, name="check_upload"),
    path("checks/review/<int:pk>/", v.check_review, name="check_review"),
    # path("checks/", v.ScannedCheckListView.as_view(), name="check_list"),

    path("checks/", ScannedCheckListView.as_view(), name="scannedcheck_list"),
    path("checks/<int:pk>/review/", v.review_scanned_check, name="scannedcheck_review"),
]