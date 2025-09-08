from django.urls import include, path
from .views import profile_view, public_profile_view

app_name = "users"

urlpatterns = [
    path('accounts/', include('allauth.urls')),
    path('accounts/profile/', profile_view, name='profile'),
    path('@<str:username>/', public_profile_view, name='public_profile'),
]