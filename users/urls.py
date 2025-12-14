from django.urls import path
from .views import (
    UserProfileView,
    UserSettingsView,
    DeleteAccountView,
    LoginView,
)

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('settings/', UserSettingsView.as_view(), name='user-settings'),
    path('delete/', DeleteAccountView.as_view(), name='delete-account'),
    path('login/', LoginView.as_view(), name='login'),
]