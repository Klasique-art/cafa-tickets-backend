from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from decimal import Decimal

from .models import (
    Venue,
    EventCategory,
    Event,
    TicketType,
    Order,
    Ticket,
    Payment,
    EventReview,
)
from .serializers import (
    VenueSerializer,
    EventCategorySerializer,
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    TicketTypeSerializer,
    OrderSerializer,
    CreateOrderSerializer,
    TicketSerializer,
    PaymentSerializer,
    EventReviewSerializer,
    CheckInSerializer,
)
from .permissions import IsOrganizerOrReadOnly, IsOrderOwner


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "city", "country", "address"]
    ordering_fields = ["name", "city", "created_at"]
    ordering = ["name"]


class EventCategoryViewSet(viewsets.ModelViewSet):
    queryset = EventCategory.objects.filter(is_active=True)
    serializer_class = EventCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "tags"]
    ordering_fields = ["start_date", "created_at", "views_count"]
    ordering = ["-start_date"]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Event.objects.select_related(
            "category", "venue", "organizer"
        ).prefetch_related("ticket_types")

        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(status="published", privacy="public")

        category_slug = self.request.query_params.get("category", None)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        status_filter = self.request.query_params.get("status", None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        is_featured = self.request.query_params.get("featured", None)
        if is_featured == "true":
            queryset = queryset.filter(is_featured=True)

        is_free = self.request.query_params.get("free", None)
        if is_free == "true":
            queryset = queryset.filter(is_free=True)

        time_filter = self.request.query_params.get("time", None)
        now = timezone.now()
        if time_filter == "upcoming":
            queryset = queryset.filter(start_date__gt=now)
        elif time_filter == "ongoing":
            queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
        elif time_filter == "past":
            queryset = queryset.filter(end_date__lt=now)

        city = self.request.query_params.get("city", None)
        if city:
            queryset = queryset.filter(venue__city__icontains=city)

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EventDetailSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return EventCreateUpdateSerializer
        return EventListSerializer

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.views_count += 1
        instance.save(update_fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def ticket_types(self, request, slug=None):
        event = self.get_object()
        ticket_types = event.ticket_types.filter(is_active=True)
        serializer = TicketTypeSerializer(ticket_types, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_ticket_type(self, request, slug=None):
        event = self.get_object()
        if event.organizer != request.user and not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to add ticket types to this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TicketTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(event=event)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def reviews(self, request, slug=None):
        event = self.get_object()
        reviews = event.reviews.all()
        serializer = EventReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_review(self, request, slug=None):
        event = self.get_object()

        if EventReview.objects.filter(event=event, user=request.user).exists():
            return Response(
                {"error": "You have already reviewed this event."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EventReviewSerializer(data=request.data)
        if serializer.is_valid():
            has_attended = Ticket.objects.filter(
                event=event,
                purchase__user=request.user,
                purchase__status="completed",
            ).exists()

            serializer.save(
                user=request.user,
                event=event,
                is_verified_purchase=has_attended,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def stats(self, request, slug=None):
        event = self.get_object()

        if event.organizer != request.user and not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to view event stats."},
                status=status.HTTP_403_FORBIDDEN,
            )

        stats = {
            "total_tickets_sold": event.tickets_sold,
            "total_revenue": float(event.revenue_generated),
            "tickets_available": event.tickets_available,
            "is_sold_out": event.is_sold_out,
            "total_orders": event.orders.filter(status="completed").count(),
            "pending_orders": event.orders.filter(status="pending").count(),
            "views_count": event.views_count,
            "average_rating": event.reviews.aggregate(Avg("rating"))["rating__avg"],
            "total_reviews": event.reviews.count(),
        }

        ticket_type_stats = []
        for ticket_type in event.ticket_types.all():
            ticket_type_stats.append(
                {
                    "name": ticket_type.name,
                    "quantity": ticket_type.quantity,
                    "quantity_sold": ticket_type.quantity_sold,
                    "quantity_remaining": ticket_type.quantity_remaining,
                    "revenue": float(ticket_type.price * ticket_type.quantity_sold),
                }
            )

        stats["ticket_types"] = ticket_type_stats
        return Response(stats)


class TicketTypeViewSet(viewsets.ModelViewSet):
    queryset = TicketType.objects.all()
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        event_id = self.request.query_params.get("event", None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        event = Event.objects.get(id=data["event_id"])

        total_amount = Decimal("0.00")
        items_to_create = []

        for item in data["items"]:
            ticket_type = TicketType.objects.get(id=item["ticket_type_id"])
            quantity = item["quantity"]
            total_amount += ticket_type.price * quantity

            items_to_create.append(
                {
                    "ticket_type": ticket_type,
                    "quantity": quantity,
                    "attendees": item.get("attendees", []),
                }
            )

        service_fee = total_amount * Decimal("0.025")

        order = Order.objects.create(
            user=request.user,
            event=event,
            total_amount=total_amount,
            service_fee=service_fee,
            buyer_name=data["buyer_name"],
            buyer_email=data["buyer_email"],
            buyer_phone=data.get("buyer_phone", ""),
            notes=data.get("notes", ""),
            status="pending",
        )

        tickets = []
        for item_data in items_to_create:
            ticket_type = item_data["ticket_type"]
            quantity = item_data["quantity"]
            attendees = item_data["attendees"]

            for i in range(quantity):
                attendee_info = attendees[i] if i < len(attendees) else {}

                ticket = Ticket.objects.create(
                    order=order,
                    event=event,
                    ticket_type=ticket_type,
                    attendee_name=attendee_info.get("name", data["buyer_name"]),
                    attendee_email=attendee_info.get("email", data["buyer_email"]),
                    attendee_phone=attendee_info.get("phone", data.get("buyer_phone", "")),
                    price_paid=ticket_type.price,
                    status="valid",
                )
                tickets.append(ticket)

            ticket_type.quantity_sold += quantity
            ticket_type.save(update_fields=["quantity_sold"])

        payment = Payment.objects.create(
            order=order,
            amount=order.grand_total,
            gateway=data["payment_gateway"],
            status="pending",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        order_serializer = OrderSerializer(order)
        return Response(
            {
                "message": "Order created successfully",
                "order": order_serializer.data,
                "payment": {
                    "payment_id": payment.payment_id,
                    "amount": float(payment.amount),
                    "gateway": payment.gateway,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to cancel this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if order.status != "pending":
            return Response(
                {"error": "Only pending orders can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for ticket in order.tickets.all():
                ticket.status = "cancelled"
                ticket.save()

                if ticket.ticket_type:
                    ticket.ticket_type.quantity_sold -= 1
                    ticket.ticket_type.save(update_fields=["quantity_sold"])

            order.status = "cancelled"
            order.save(update_fields=["status"])

        return Response(
            {"message": "Order cancelled successfully"},
            status=status.HTTP_200_OK,
        )


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Ticket.objects.all()
        return Ticket.objects.filter(purchase__user=user)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        ticket = self.get_object()
        return Response(
            {
                "message": "Ticket download functionality to be implemented",
                "ticket": TicketSerializer(ticket).data,
            }
        )


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ticket_number = serializer.validated_data["ticket_number"]
        ticket = get_object_or_404(Ticket, ticket_number=ticket_number)

        if not ticket.can_check_in:
            return Response(
                {
                    "error": "Ticket cannot be checked in",
                    "reason": self._get_check_in_error_reason(ticket),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket.checked_in_at = timezone.now()
        ticket.checked_in_by = request.user
        ticket.status = "used"
        ticket.save()

        return Response(
            {
                "message": "Ticket checked in successfully",
                "ticket": TicketSerializer(ticket).data,
            },
            status=status.HTTP_200_OK,
        )

    def _get_check_in_error_reason(self, ticket):
        if ticket.status != "valid":
            return f"Ticket status is '{ticket.status}'"
        if ticket.checked_in_at:
            return f"Ticket already checked in at {ticket.checked_in_at}"
        now = timezone.now()
        if now < ticket.event.start_date:
            return "Event has not started yet"
        if now > ticket.event.end_date:
            return "Event has already ended"
        return "Unknown reason"


class PaymentWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        gateway = request.data.get("gateway")

        if gateway == "paystack":
            return self._handle_paystack_webhook(request.data)
        elif gateway == "stripe":
            return self._handle_stripe_webhook(request.data)
        elif gateway == "flutterwave":
            return self._handle_flutterwave_webhook(request.data)

        return Response(
            {"error": "Unknown payment gateway"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @transaction.atomic
    def _handle_paystack_webhook(self, data):
        reference = data.get("reference")
        payment_status = data.get("status")

        try:
            payment = Payment.objects.get(gateway_reference=reference)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.gateway_response = data
        payment.save()

        if payment_status == "success":
            payment.status = "completed"
            payment.completed_at = timezone.now()
            payment.save()

            order = payment.order
            order.status = "completed"
            order.completed_at = timezone.now()
            order.save()

        elif payment_status == "failed":
            payment.status = "failed"
            payment.save()

        return Response({"message": "Webhook processed"}, status=status.HTTP_200_OK)

    def _handle_stripe_webhook(self, data):
        return Response({"message": "Stripe webhook handler to be implemented"})

    def _handle_flutterwave_webhook(self, data):
        return Response({"message": "Flutterwave webhook handler to be implemented"})


class MyEventsView(generics.ListAPIView):
    serializer_class = EventListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)


class MyOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")


class MyTicketsView(generics.ListAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(purchase__user=self.request.user).order_by("-created_at")


class EventSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "")

        if not query:
            return Response(
                {"error": "Search query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        events = Event.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
            | Q(venue__city__icontains=query),
            status="published",
            privacy="public",
        ).distinct()[:20]

        serializer = EventListSerializer(events, many=True)
        return Response(
            {
                "count": len(events),
                "results": serializer.data,
            }
        )


class FeaturedEventsView(generics.ListAPIView):
    serializer_class = EventListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Event.objects.filter(
            is_featured=True, status="published", privacy="public"
        ).order_by("-start_date")[:10]


class UpcomingEventsView(generics.ListAPIView):
    serializer_class = EventListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        return Event.objects.filter(
            start_date__gt=now, status="published", privacy="public"
        ).order_by("start_date")[:20]
