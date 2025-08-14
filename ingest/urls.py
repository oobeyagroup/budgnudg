from django.urls import path
from ingest import views as v

app_name = "ingest"
urlpatterns = [
    path("", v.BatchListView.as_view(), name="batch_list"),
    path("upload/", v.upload_csv, name="batch_upload"),
    path("<int:pk>/apply_profile/", v.apply_profile, name="batch_apply_profile"),
    path("<int:pk>/preview/", v.BatchPreviewView.as_view(), name="batch_preview"),
    path("<int:pk>/commit/", v.commit, name="batch_commit"),
    path("profiles/", v.MappingProfileListView.as_view(), name="profile_list"),
    path("profiles/<int:pk>/", v.MappingProfileDetailView.as_view(), name="profile_detail"),
]