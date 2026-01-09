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
    CreateWithdrawalRequestView,
    WithdrawalHistoryView,
    WithdrawalDetailView,
    CancelWithdrawalView,
)
# Import from tickets app for user dashboard stats
from tickets.ticket_dashboard_views import UserDashboardStatsView

# User identity verification views (renamed to avoid conflicts)
from .verification_views import (
    UploadIDView,
    UploadSelfieView,
    UserVerificationStatusView,   # Renamed!
    UserRetryVerificationView      # Renamed!
)

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

    # User Identity Verification endpoints (for becoming an organizer)
    path('verification/upload-id/', UploadIDView.as_view(), name='upload-id'),
    path('verification/upload-selfie/', UploadSelfieView.as_view(), name='upload-selfie'),
    path('verification/status/', UserVerificationStatusView.as_view(), name='user-verification-status'),
    path('verification/retry/', UserRetryVerificationView.as_view(), name='user-retry-verification'),

    # Withdrawal endpoints
    path('withdrawal/request/', CreateWithdrawalRequestView.as_view(), name='withdrawal-request'),
    path('withdrawal/history/', WithdrawalHistoryView.as_view(), name='withdrawal-history'),
    path('withdrawal/<str:withdrawal_id>/', WithdrawalDetailView.as_view(), name='withdrawal-detail'),
    path('withdrawal/<str:withdrawal_id>/cancel/', CancelWithdrawalView.as_view(), name='withdrawal-cancel'),
]