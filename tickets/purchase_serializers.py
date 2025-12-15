"""
Purchase and Ticket Serializers
Handles the ticket purchase flow matching the API specification
"""
from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from .models import Purchase, Payment, Ticket, Event, TicketType
from .new_serializers import EventListSerializer, TicketTypeSerializer


# ============================================================================
# TICKET PURCHASE SERIALIZERS
# ============================================================================

class PurchaseInitiateSerializer(serializers.Serializer):
    """Serializer for initiating ticket purchase"""
    event_id = serializers.IntegerField(required=True)
    ticket_type_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    attendee_info = serializers.DictField(required=True)
    payment_method = serializers.ChoiceField(
        choices=['card', 'mobile_money', 'bank_transfer'],
        required=True
    )

    def validate_attendee_info(self, value):
        """Validate attendee information"""
        required_fields = ['name', 'email', 'phone']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"{field} is required in attendee_info")

        # Validate email format
        email = value.get('email')
        if email and '@' not in email:
            raise serializers.ValidationError("Invalid email address in attendee_info")

        # Validate phone format (E.164)
        phone = value.get('phone')
        if phone and not phone.startswith('+'):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g., +233241234567)"
            )

        return value

    def validate(self, data):
        """Validate purchase request"""
        # Validate event exists and is available
        try:
            event = Event.objects.get(id=data['event_id'])
        except Event.DoesNotExist:
            raise serializers.ValidationError({'event_id': 'Event not found'})

        if not event.is_published:
            raise serializers.ValidationError({'event_id': 'Event is not published'})

        if event.status != 'upcoming':
            raise serializers.ValidationError({
                'event_id': f'Tickets cannot be purchased for this event. Event status: {event.status}'
            })

        # Validate ticket type exists
        try:
            ticket_type = TicketType.objects.get(id=data['ticket_type_id'], event=event)
        except TicketType.DoesNotExist:
            raise serializers.ValidationError({
                'ticket_type_id': 'Ticket type not found for this event'
            })

        # Validate ticket type is available
        if not ticket_type.is_available:
            if ticket_type.tickets_remaining <= 0:
                raise serializers.ValidationError({
                    'ticket_type_id': 'This ticket type is sold out',
                    'tickets_remaining': 0
                })
            else:
                raise serializers.ValidationError({
                    'ticket_type_id': 'Ticket sales for this type have ended',
                    'available_until': ticket_type.available_until
                })

        # Validate quantity
        quantity = data['quantity']
        if quantity < ticket_type.min_purchase:
            raise serializers.ValidationError({
                'quantity': f'Minimum purchase for this ticket type is {ticket_type.min_purchase}',
                'min_purchase': ticket_type.min_purchase,
                'requested_quantity': quantity
            })

        if quantity > ticket_type.max_purchase:
            raise serializers.ValidationError({
                'quantity': f'Maximum purchase for this ticket type is {ticket_type.max_purchase}',
                'max_purchase': ticket_type.max_purchase,
                'requested_quantity': quantity
            })

        if quantity > ticket_type.tickets_remaining:
            raise serializers.ValidationError({
                'quantity': f'Only {ticket_type.tickets_remaining} ticket(s) remaining for this ticket type',
                'available_quantity': ticket_type.tickets_remaining,
                'requested_quantity': quantity
            })

        # Add validated objects to data
        data['event'] = event
        data['ticket_type'] = ticket_type

        return data


class PurchaseResponseSerializer(serializers.Serializer):
    """Serializer for purchase initiation response"""
    message = serializers.CharField()
    purchase_id = serializers.CharField()
    tickets = serializers.ListField()
    pricing = serializers.DictField()
    payment = serializers.DictField()
    reservation = serializers.DictField()


# ============================================================================
# TICKET SERIALIZERS
# ============================================================================

class TicketSerializer(serializers.ModelSerializer):
    """Serializer for individual tickets"""
    event = EventListSerializer(read_only=True)
    ticket_type = TicketTypeSerializer(read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'ticket_id',
            'event',
            'ticket_type',
            'attendee_name',
            'attendee_email',
            'attendee_phone',
            'status',
            'qr_code',
            'qr_code_url',
            'download_url',
            'is_checked_in',
            'checked_in_at',
            'created_at',
        ]

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
        return None

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/v1/tickets/{obj.ticket_id}/download/')
        return f'/api/v1/tickets/{obj.ticket_id}/download/'


# ============================================================================
# PAYMENT SERIALIZERS
# ============================================================================

class PaymentStatusSerializer(serializers.Serializer):
    """Serializer for payment status response"""
    payment_id = serializers.CharField()
    purchase_id = serializers.CharField(required=False)
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    payment_method = serializers.CharField(required=False)
    provider = serializers.CharField()
    reference = serializers.CharField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    failed_at = serializers.DateTimeField(required=False, allow_null=True)
    failure_reason = serializers.CharField(required=False, allow_null=True)
    message = serializers.CharField(required=False)

    # For completed payments
    event = serializers.DictField(required=False)
    tickets = serializers.ListField(required=False)
    receipt = serializers.DictField(required=False)


# ============================================================================
# CHECK-IN SERIALIZERS
# ============================================================================

class CheckInSerializer(serializers.Serializer):
    """Serializer for ticket check-in"""
    ticket_id = serializers.CharField(required=True)

    def validate_ticket_id(self, value):
        """Validate ticket exists"""
        try:
            Ticket.objects.get(ticket_id=value)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Invalid ticket ID")
        return value


class CheckInResponseSerializer(serializers.Serializer):
    """Serializer for check-in response"""
    message = serializers.CharField()
    ticket = serializers.DictField()
    event_stats = serializers.DictField()
