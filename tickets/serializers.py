from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import (
    Venue,
    EventCategory,
    Event,
    TicketType,
    Purchase,
    Payment,
    Payment,
    Ticket,
    Order,
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
        return obj.get_event_count()


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
    organizer = OrganizerSerializer(read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    status = serializers.ReadOnlyField()
    lowest_price = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "category",
            "organizer",
            "featured_image",
            "venue_name",
            "venue_city",
            "venue_country",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
            "is_published",
            "is_upcoming",
            "is_ongoing",
            "is_past",
            "tickets_sold",
            "is_sold_out",
            "lowest_price",
            "max_attendees",
            "views_count",
            "created_at",
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    organizer = OrganizerSerializer(read_only=True)
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    revenue_generated = serializers.ReadOnlyField()
    status = serializers.ReadOnlyField()
    lowest_price = serializers.ReadOnlyField()
    highest_price = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "short_description",
            "category",
            "organizer",
            "payment_profile",
            "featured_image",
            "additional_images",
            "venue_name",
            "venue_address",
            "venue_city",
            "venue_country",
            "venue_latitude",
            "venue_longitude",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "is_recurring",
            "recurrence_pattern",
            "check_in_policy",
            "status",
            "is_published",
            "max_attendees",
            "views_count",
            "is_upcoming",
            "is_ongoing",
            "is_past",
            "tickets_sold",
            "tickets_available",
            "is_sold_out",
            "lowest_price",
            "highest_price",
            "revenue_generated",
            "ticket_types",
            "created_at",
            "updated_at",
        ]


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "short_description",
            "category_id",
            "featured_image",
            "additional_images",
            "venue_name",
            "venue_address",
            "venue_city",
            "venue_country",
            "venue_latitude",
            "venue_longitude",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "is_recurring",
            "recurrence_pattern",
            "check_in_policy",
            "is_published",
            "max_attendees",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )

        return data

    def create(self, validated_data):
        category_id = validated_data.pop("category_id", None)

        event = Event.objects.create(**validated_data)

        if category_id:
            try:
                category = EventCategory.objects.get(id=category_id)
                event.category = category
                event.save()
            except EventCategory.DoesNotExist:
                pass

        return event

    def update(self, instance, validated_data):
        category_id = validated_data.pop("category_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if category_id is not None:
            try:
                category = EventCategory.objects.get(id=category_id)
                instance.category = category
            except EventCategory.DoesNotExist:
                instance.category = None

        instance.save()
        return instance


class PurchaseSerializer(serializers.ModelSerializer):
    event = EventListSerializer(read_only=True)
    ticket_type = TicketTypeSerializer(read_only=True)
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "purchase_id",
            "event",
            "ticket_type",
            "quantity",
            "buyer_name",
            "buyer_email",
            "buyer_phone",
            "ticket_price",
            "subtotal",
            "service_fee",
            "total",
            "status",
            "is_expired",
            "reserved_at",
            "reservation_expires_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "purchase_id",
            "reserved_at",
            "reservation_expires_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class CreatePurchaseSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    ticket_type_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    buyer_name = serializers.CharField(max_length=255)
    buyer_email = serializers.EmailField()
    buyer_phone = serializers.CharField(max_length=20)

    def validate(self, data):
        try:
            event = Event.objects.get(id=data["event_id"])
        except Event.DoesNotExist:
            raise serializers.ValidationError({"event_id": "Event not found."})

        if not event.is_published:
            raise serializers.ValidationError(
                {"event_id": "Event is not available for ticket purchase."}
            )

        try:
            ticket_type = TicketType.objects.get(
                id=data["ticket_type_id"], event=event
            )
        except TicketType.DoesNotExist:
            raise serializers.ValidationError(
                {"ticket_type_id": "Ticket type not found."}
            )

        if not ticket_type.is_on_sale:
            raise serializers.ValidationError(
                {"ticket_type_id": f"Ticket type '{ticket_type.name}' is not on sale."}
            )

        quantity = data["quantity"]
        if quantity < ticket_type.min_purchase:
            raise serializers.ValidationError(
                {
                    "quantity": f"Minimum purchase for '{ticket_type.name}' is {ticket_type.min_purchase}."
                }
            )

        if quantity > ticket_type.max_purchase:
            raise serializers.ValidationError(
                {
                    "quantity": f"Maximum purchase for '{ticket_type.name}' is {ticket_type.max_purchase}."
                }
            )

        if quantity > ticket_type.quantity_remaining:
            raise serializers.ValidationError(
                {
                    "quantity": f"Only {ticket_type.quantity_remaining} tickets remaining for '{ticket_type.name}'."
                }
            )

        return data


class TicketSerializer(serializers.ModelSerializer):
    event = serializers.SerializerMethodField()
    ticket_type = serializers.SerializerMethodField()
    attendee_info = serializers.SerializerMethodField()
    purchase_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_reference = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "ticket_id",
            "qr_code",
            "event",
            "ticket_type",
            "attendee_info",
            "purchase_date",
            "payment_reference",
            "amount_paid",
            "price",
            "status",
            "is_checked_in",
            "checked_in_at",
        ]
        read_only_fields = [
            "ticket_id",
            "qr_code",
            "price",
            "is_checked_in",
            "checked_in_at",
        ]

    def get_event(self, obj):
        """Return event info in expected format"""
        request = self.context.get('request')
        return {
            'id': obj.event.id,
            'title': obj.event.title,
            'slug': obj.event.slug,
            'featured_image': request.build_absolute_uri(obj.event.featured_image.url) if obj.event.featured_image else None,
            'category': {
                'id': obj.event.category.id,
                'name': obj.event.category.name
            } if obj.event.category else None,
            'venue_name': obj.event.venue_name,
            'venue_city': obj.event.venue_city,
            'start_date': obj.event.start_date,
            'start_time': obj.event.start_time,
            'status': obj.event.status
        }

    def get_ticket_type(self, obj):
        """Return ticket type info"""
        return {
            'id': obj.ticket_type.id,
            'name': obj.ticket_type.name,
            'price': str(obj.ticket_type.price)
        }

    def get_attendee_info(self, obj):
        """Return attendee info as nested object"""
        return {
            'name': obj.attendee_name,
            'email': obj.attendee_email,
            'phone': obj.attendee_phone
        }

    def get_payment_reference(self, obj):
        """Get payment reference from purchase"""
        if obj.purchase:
            try:
                # Payment has OneToOneField relationship with Purchase
                payment = obj.purchase.payment
                return payment.reference if payment else None
            except Payment.DoesNotExist:
                return None
        return None

    def get_amount_paid(self, obj):
        """Get amount paid (ticket price)"""
        return str(obj.ticket_type.price) if obj.ticket_type else '0.00'

class PaymentSerializer(serializers.ModelSerializer):
    purchase = PurchaseSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_id",
            "purchase",
            "amount",
            "currency",
            "payment_method",
            "provider",
            "reference",
            "payment_url",
            "status",
            "provider_response",
            "failure_reason",
            "created_at",
            "completed_at",
            "failed_at",
        ]
        read_only_fields = [
            "id",
            "payment_id",
            "provider_response",
            "created_at",
            "completed_at",
            "failed_at",
        ]


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
    ticket_id = serializers.CharField(max_length=100)

    def validate_ticket_id(self, value):
        try:
            ticket = Ticket.objects.get(ticket_id=value)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Invalid ticket ID.")
        return value
