"""
Tickets App URL Configuration
Matches the API specification from documentation
"""
from django.urls import path

# Event Views
from .event_views import (
    EventCategoryListView,
    EventListView,
    PastEventsListView,
    EventDetailView,
    EventCreateView,
    EventUpdateView,
    MyEventsView,
    MyEventDetailView,
    CreateTicketTypeView,
    UpdateTicketTypeView,
    DeleteTicketTypeView,
    DeleteEventView,
)

# Purchase Views
from .purchase_views import (
    InitiatePurchaseView,
    PaymentWebhookView,
    PaymentStatusView,
    CancelPurchaseView,
    ResendTicketsView,
    PaymentHistoryView,
    PaymentDetailView,
)

# Dashboard and Ticket Management Views
from .ticket_dashboard_views import (
    MyTicketsView,
    TicketDetailView,
    CheckInTicketView,
    CheckInHistoryView,
    EventAttendeesView,
    UserDashboardStatsView,
    EventAnalyticsView,
    AttendedEventsView,
    DownloadTicketView,
    OrganizerRevenueView,
)

from .public_views import PublicStatsView

from .contact_views import (
    ContactMessageView,
    NewsletterSubscribeView,
    NewsletterUnsubscribeView
)

urlpatterns = [
    # ============================================================================
    # EVENT CATEGORIES
    # ============================================================================
    path('event-categories/', EventCategoryListView.as_view(), name='event-categories'),

    # ============================================================================
    # EVENT LISTINGS
    # ============================================================================
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/past/', PastEventsListView.as_view(), name='past-events'),

    # Event Creation & Management (must come before <slug> to avoid conflicts)
    path('events/create/', EventCreateView.as_view(), name='event-create'),
    path('events/<str:slug_or_id>/delete/', DeleteEventView.as_view(), name='delete-event'),
    path('events/my-events/', MyEventsView.as_view(), name='my-events'),
    path('events/my-events/<str:slug_or_id>/', MyEventDetailView.as_view(), name='my-event-detail'),
    path('events/my-events/<str:slug_or_id>/analytics/', EventAnalyticsView.as_view(), name='my-event-analytics'),

    # Event Detail (must come after specific paths to avoid slug conflicts)
    path('events/<slug:slug>/', EventDetailView.as_view(), name='event-detail'),
    path('events/<str:slug_or_id>/update/', EventUpdateView.as_view(), name='event-update'),

    # Event Analytics & Attendees (Organizer) - Changed to support slug or ID
    path('events/<str:slug_or_id>/analytics/', EventAnalyticsView.as_view(), name='event-analytics'),
    path('events/<str:slug_or_id>/attendees/', EventAttendeesView.as_view(), name='event-attendees'),
    path('events/<str:slug_or_id>/checkin/', CheckInTicketView.as_view(), name='event-checkin'),
    path('events/<str:slug_or_id>/checkin-history/', CheckInHistoryView.as_view(), name='checkin-history'),

    # Ticket Types
    path('events/<str:slug_or_id>/tickets/', CreateTicketTypeView.as_view(), name='create-ticket-type'),
    path('events/<str:slug_or_id>/tickets/<int:ticket_id>/', UpdateTicketTypeView.as_view(), name='update-ticket-type'),
    path('events/<str:slug_or_id>/tickets/<int:ticket_id>/delete/', DeleteTicketTypeView.as_view(), name='delete-ticket-type'),

    # ============================================================================
    # TICKET PURCHASE
    # ============================================================================
    path('tickets/purchase/', InitiatePurchaseView.as_view(), name='ticket-purchase'),
    path('tickets/purchase/<str:purchase_id>/cancel/', CancelPurchaseView.as_view(), name='cancel-purchase'),

    # ============================================================================
    # TICKET MANAGEMENT
    # ============================================================================
    path('tickets/my-tickets/', MyTicketsView.as_view(), name='my-tickets'),
    path('tickets/attended-events/', AttendedEventsView.as_view(), name='attended-events'),
    path('tickets/<str:ticket_id>/', TicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/<str:ticket_id>/download/', DownloadTicketView.as_view(), name='download-ticket'),

    # ============================================================================
    # ORGANIZER REVENUE
    # ============================================================================
    path('organizers/revenue/', OrganizerRevenueView.as_view(), name='organizer-revenue'),

    # ============================================================================
    # PAYMENTS
    # ============================================================================
    # Webhook (must come first - specific path)
    path('payments/webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
    
    # Payment History (list all payments)
    path('payments/', PaymentHistoryView.as_view(), name='payment-history'),
    
    # Payment actions (specific paths with payment_id)
    path('payments/<str:payment_id>/status/', PaymentStatusView.as_view(), name='payment-status'),
    path('payments/<str:payment_id>/resend-tickets/', ResendTicketsView.as_view(), name='resend-tickets'),
    
    # Payment Detail (must come last - catch-all for payment_id)
    path('payments/<str:payment_id>/', PaymentDetailView.as_view(), name='payment-detail'),

    # PUBLIC ENDPOINTS (no auth required)
    path('public/stats/', PublicStatsView.as_view(), name='public-stats'),

    # CONTACT & NEWSLETTER (public endpoints)
    path('contact/', ContactMessageView.as_view(), name='contact-submit'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('newsletter/unsubscribe/', NewsletterUnsubscribeView.as_view(), name='newsletter-unsubscribe'),
]