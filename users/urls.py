from django.urls import path
from .views import (
    UserProfileView,
    UserSettingsView,
    DeleteAccountView,
    LoginView,
    ChangePasswordView,
    ChangeUsernameView
)
from .payment_views import (
    PaymentProfileListCreateView,
    PaymentProfileDetailView,
    SetDefaultPaymentProfileView,
    VerificationStatusView,
    RetryVerificationView,
)
# Import from tickets app for user dashboard stats
from tickets.ticket_dashboard_views import UserDashboardStatsView

urlpatterns = [
    # User Profile & Settings
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('settings/', UserSettingsView.as_view(), name='user-settings'),
    path('delete/', DeleteAccountView.as_view(), name='delete-account'),
    path('login/', LoginView.as_view(), name='login'),

    # User Dashboard Stats
    path('stats/', UserDashboardStatsView.as_view(), name='user-stats'),

    # Payment Profile Management
    path('payment-profile/', PaymentProfileListCreateView.as_view(), name='payment-profile-list-create'),
    path('payment-profile/<uuid:pk>/', PaymentProfileDetailView.as_view(), name='payment-profile-detail'),
    path('payment-profile/<uuid:pk>/set-default/', SetDefaultPaymentProfileView.as_view(), name='payment-profile-set-default'),
    path('payment-profile/<uuid:pk>/verification-status/', VerificationStatusView.as_view(), name='payment-profile-verification-status'),
    path('payment-profile/<uuid:pk>/retry-verification/', RetryVerificationView.as_view(), name='payment-profile-retry-verification'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('change-username/', ChangeUsernameView.as_view(), name='change-username'),
]