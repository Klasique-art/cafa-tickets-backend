from django.urls import path
from .views import update_user_settings, delete_account, login_view

urlpatterns = [
    path("settings/", update_user_settings, name="update_user_settings"),
    path("delete/", delete_account, name="delete_account"),
    path("login/", login_view, name="login_view"),
]