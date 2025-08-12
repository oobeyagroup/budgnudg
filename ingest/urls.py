from django.urls import path
from ingest import views as v

app_name = "ingest"
urlpatterns = [
    path("", v.BatchListView.as_view(), name="batch_list"),
    path("<int:pk>/", v.BatchDetailView.as_view(), name="batch_detail"),
    path("upload/", v.upload_csv, name="batch_upload"),
    path("<int:pk>/apply-profile/", v.apply_profile, name="batch_apply_profile"),
    path("<int:pk>/commit/", v.commit, name="batch_commit"),
]