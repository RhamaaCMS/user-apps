from django.urls import include, path

from .views import profile_view

app_name = "users"

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("profile/", profile_view, name="profile"),
]
