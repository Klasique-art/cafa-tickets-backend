from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VenueViewSet,
    EventCategoryViewSet,
    EventViewSet,
    TicketTypeViewSet,
    OrderViewSet,
    TicketViewSet,
    CreateOrderView,
    CheckInView,
    PaymentWebhookView,
    MyEventsView,
    MyOrdersView,
    MyTicketsView,
    EventSearchView,
    FeaturedEventsView,
    UpcomingEventsView,
)

router = DefaultRouter()
router.register(r"venues", VenueViewSet, basename="venue")
router.register(r"categories", EventCategoryViewSet, basename="category")
router.register(r"events", EventViewSet, basename="event")
router.register(r"ticket-types", TicketTypeViewSet, basename="tickettype")
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("", include(router.urls)),
    path("orders/create/", CreateOrderView.as_view(), name="create-order"),
    path("tickets/check-in/", CheckInView.as_view(), name="check-in"),
    path("payments/webhook/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path("my/events/", MyEventsView.as_view(), name="my-events"),
    path("my/orders/", MyOrdersView.as_view(), name="my-orders"),
    path("my/tickets/", MyTicketsView.as_view(), name="my-tickets"),
    path("search/", EventSearchView.as_view(), name="event-search"),
    path("featured/", FeaturedEventsView.as_view(), name="featured-events"),
    path("upcoming/", UpcomingEventsView.as_view(), name="upcoming-events"),
]
