from rest_framework import serializers
from django.contrib.auth import get_user_model
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

User = get_user_model()


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = [
            "id",
            "name",
            "address",
            "city",
            "country",
            "capacity",
            "description",
            "image",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EventCategorySerializer(serializers.ModelSerializer):
    event_count = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "is_active",
            "event_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_event_count(self, obj):
        return obj.events.filter(status="published").count()


class OrganizerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "profile_image"]


class TicketTypeSerializer(serializers.ModelSerializer):
    quantity_remaining = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()

    class Meta:
        model = TicketType
        fields = [
            "id",
            "name",
            "description",
            "price",
            "quantity",
            "tickets_sold",
            "quantity_remaining",
            "min_purchase",
            "max_purchase",
            "available_from",
            "available_until",
            "is_sold_out",
            "is_on_sale",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tickets_sold",
            "created_at",
            "updated_at",
        ]


class EventListSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = VenueSerializer(read_only=True)
    organizer = OrganizerSerializer(read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "category",
            "venue",
            "organizer",
            "banner_image",
            "thumbnail_image",
            "start_date",
            "end_date",
            "status",
            "privacy",
            "is_featured",
            "is_free",
            "is_upcoming",
            "is_ongoing",
            "is_past",
            "tickets_sold",
            "is_sold_out",
            "max_attendees",
            "tags",
            "views_count",
            "created_at",
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = VenueSerializer(read_only=True)
    organizer = OrganizerSerializer(read_only=True)
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    revenue_generated = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "short_description",
            "category",
            "venue",
            "organizer",
            "banner_image",
            "thumbnail_image",
            "start_date",
            "end_date",
            "status",
            "privacy",
            "is_featured",
            "is_free",
            "max_attendees",
            "tags",
            "external_url",
            "terms_and_conditions",
            "views_count",
            "is_upcoming",
            "is_ongoing",
            "is_past",
            "tickets_sold",
            "tickets_available",
            "is_sold_out",
            "revenue_generated",
            "ticket_types",
            "created_at",
            "updated_at",
        ]


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(required=False, allow_null=True)
    venue_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "short_description",
            "category_id",
            "venue_id",
            "banner_image",
            "thumbnail_image",
            "start_date",
            "end_date",
            "status",
            "privacy",
            "is_featured",
            "is_free",
            "max_attendees",
            "tags",
            "external_url",
            "terms_and_conditions",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        if "start_date" in data and "end_date" in data:
            if data["start_date"] >= data["end_date"]:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )
        return data

    def create(self, validated_data):
        category_id = validated_data.pop("category_id", None)
        venue_id = validated_data.pop("venue_id", None)

        event = Event.objects.create(**validated_data)

        if category_id:
            try:
                category = EventCategory.objects.get(id=category_id)
                event.category = category
            except EventCategory.DoesNotExist:
                pass

        if venue_id:
            try:
                venue = Venue.objects.get(id=venue_id)
                event.venue = venue
            except Venue.DoesNotExist:
                pass

        event.save()
        return event

    def update(self, instance, validated_data):
        category_id = validated_data.pop("category_id", None)
        venue_id = validated_data.pop("venue_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if category_id is not None:
            try:
                category = EventCategory.objects.get(id=category_id)
                instance.category = category
            except EventCategory.DoesNotExist:
                instance.category = None

        if venue_id is not None:
            try:
                venue = Venue.objects.get(id=venue_id)
                instance.venue = venue
            except Venue.DoesNotExist:
                instance.venue = None

        instance.save()
        return instance


class TicketSerializer(serializers.ModelSerializer):
    event = EventListSerializer(read_only=True)
    ticket_type = TicketTypeSerializer(read_only=True)
    is_valid = serializers.ReadOnlyField()
    can_check_in = serializers.ReadOnlyField()
    price_paid = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_number",
            "event",
            "ticket_type",
            "attendee_name",
            "attendee_email",
            "attendee_phone",
            "price_paid",
            "status",
            "qr_code",
            "checked_in_at",
            "is_valid",
            "can_check_in",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "qr_code",
            "checked_in_at",
            "created_at",
            "updated_at",
        ]

    def get_price_paid(self, obj):
        """Get ticket price from purchase"""
        if obj.purchase:
            return obj.purchase.ticket_price
        return None


class OrderItemSerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    attendees = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(max_length=255)
        ),
        required=False,
    )


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)
    event = EventListSerializer(read_only=True)
    total_tickets = serializers.ReadOnlyField()
    grand_total = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_id",
            "event",
            "total_amount",
            "service_fee",
            "grand_total",
            "status",
            "buyer_email",
            "buyer_phone",
            "buyer_name",
            "payment_method",
            "payment_reference",
            "notes",
            "total_tickets",
            "tickets",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "order_id",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class CreateOrderSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    items = OrderItemSerializer(many=True)
    buyer_name = serializers.CharField(max_length=255)
    buyer_email = serializers.EmailField()
    buyer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    payment_gateway = serializers.ChoiceField(
        choices=Payment.PROVIDER_CHOICES
    )

    def validate(self, data):
        try:
            event = Event.objects.get(id=data["event_id"])
        except Event.DoesNotExist:
            raise serializers.ValidationError({"event_id": "Event not found."})

        if event.status != "published":
            raise serializers.ValidationError(
                {"event_id": "Event is not available for ticket purchase."}
            )

        for item in data["items"]:
            try:
                ticket_type = TicketType.objects.get(
                    id=item["ticket_type_id"], event=event
                )
            except TicketType.DoesNotExist:
                raise serializers.ValidationError(
                    {"items": f"Ticket type {item['ticket_type_id']} not found."}
                )

            if not ticket_type.is_on_sale:
                raise serializers.ValidationError(
                    {"items": f"Ticket type '{ticket_type.name}' is not on sale."}
                )

            quantity = item["quantity"]
            if quantity < ticket_type.min_purchase:
                raise serializers.ValidationError(
                    {
                        "items": f"Minimum purchase for '{ticket_type.name}' is {ticket_type.min_purchase}."
                    }
                )

            if quantity > ticket_type.max_purchase:
                raise serializers.ValidationError(
                    {
                        "items": f"Maximum purchase for '{ticket_type.name}' is {ticket_type.max_purchase}."
                    }
                )

            if quantity > ticket_type.quantity_remaining:
                raise serializers.ValidationError(
                    {
                        "items": f"Only {ticket_type.quantity_remaining} tickets remaining for '{ticket_type.name}'."
                    }
                )

        return data


class PaymentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_id",
            "order",
            "amount",
            "gateway",
            "status",
            "gateway_reference",
            "gateway_response",
            "metadata",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "payment_id",
            "gateway_response",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class EventReviewSerializer(serializers.ModelSerializer):
    user = OrganizerSerializer(read_only=True)

    class Meta:
        model = EventReview
        fields = [
            "id",
            "user",
            "rating",
            "comment",
            "is_verified_purchase",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "is_verified_purchase",
            "created_at",
            "updated_at",
        ]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class CheckInSerializer(serializers.Serializer):
    ticket_number = serializers.CharField(max_length=100)

    def validate_ticket_number(self, value):
        try:
            ticket = Ticket.objects.get(ticket_number=value)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Invalid ticket number.")
        return value
