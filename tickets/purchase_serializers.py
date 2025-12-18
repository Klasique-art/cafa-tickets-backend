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
        required=False,
        default='card')  # Default since Paystack will handle the actual method

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
    event = serializers.SerializerMethodField()
    ticket_type = serializers.SerializerMethodField()
    attendee_info = serializers.SerializerMethodField()
    purchase_date = serializers.DateTimeField(source='created_at', read_only=True)
    payment_reference = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'ticket_id',
            'qr_code',
            'event',
            'ticket_type',
            'attendee_info',
            'purchase_date',
            'payment_reference',
            'amount_paid',
            'status',
            'is_checked_in',
            'checked_in_at',
        ]

    def get_event(self, obj):
        """Return event info in expected format"""
        request = self.context.get('request')
        return {
            'id': obj.event.id,
            'title': obj.event.title,
            'slug': obj.event.slug,
            'featured_image': request.build_absolute_uri(obj.event.featured_image.url) if request and obj.event.featured_image else None,
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
        if obj.purchase and hasattr(obj.purchase, 'payments') and obj.purchase.payments.exists():
            payment = obj.purchase.payments.first()
            return payment.payment_reference if hasattr(payment, 'payment_reference') else payment.payment_id
        elif obj.purchase:
            return obj.purchase.purchase_id
        return None

    def get_amount_paid(self, obj):
        """Get amount paid (ticket price)"""
        return str(obj.ticket_type.price) if obj.ticket_type else '0.00'
    

# Ticket details
class TicketDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single ticket view"""
    event = serializers.SerializerMethodField()
    ticket_type = serializers.SerializerMethodField()
    attendee_info = serializers.SerializerMethodField()
    purchase_info = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'ticket_id',
            'qr_code',
            'event',
            'ticket_type',
            'attendee_info',
            'purchase_info',
            'status',
            'is_checked_in',
            'checked_in_at',
        ]

    def get_event(self, obj):
        """Return detailed event info"""
        request = self.context.get('request')
        return {
            'id': obj.event.id,
            'title': obj.event.title,
            'slug': obj.event.slug,
            'featured_image': request.build_absolute_uri(obj.event.featured_image.url) if request and obj.event.featured_image else None,
            'description': obj.event.description,
            'category': {
                'id': obj.event.category.id,
                'name': obj.event.category.name
            } if obj.event.category else None,
            'venue_name': obj.event.venue_name,
            'venue_address': obj.event.venue_address,
            'venue_city': obj.event.venue_city,
            'venue_country': obj.event.venue_country,
            'venue_location': {
                'latitude': str(obj.event.venue_latitude) if obj.event.venue_latitude else None,
                'longitude': str(obj.event.venue_longitude) if obj.event.venue_longitude else None
            },
            'start_date': obj.event.start_date,
            'start_time': obj.event.start_time,
            'end_date': obj.event.end_date,
            'end_time': obj.event.end_time,
            'organizer': {
                'id': obj.event.organizer.id,
                'username': obj.event.organizer.username,
                'full_name': obj.event.organizer.full_name if hasattr(obj.event.organizer, 'full_name') else obj.event.organizer.username,
                'profile_image': request.build_absolute_uri(obj.event.organizer.profile_image.url) if request and hasattr(obj.event.organizer, 'profile_image') and obj.event.organizer.profile_image else None
            }
        }

    def get_ticket_type(self, obj):
        """Return detailed ticket type info"""
        return {
            'id': obj.ticket_type.id,
            'name': obj.ticket_type.name,
            'description': obj.ticket_type.description,
            'price': str(obj.ticket_type.price)
        }

    def get_attendee_info(self, obj):
        """Return attendee info"""
        return {
            'name': obj.attendee_name,
            'email': obj.attendee_email,
            'phone': obj.attendee_phone
        }

    def get_purchase_info(self, obj):
        """Return purchase info"""
        purchase = obj.purchase
        payment = None
        
        if purchase and hasattr(purchase, 'payments') and purchase.payments.exists():
            payment = purchase.payments.first()
        
        return {
            'purchase_date': obj.created_at,
            'payment_reference': payment.payment_reference if payment and hasattr(payment, 'payment_reference') else (payment.payment_id if payment else purchase.purchase_id if purchase else None),
            'payment_method': payment.payment_method if payment and hasattr(payment, 'payment_method') else 'card',
            'amount_paid': str(obj.ticket_type.price) if obj.ticket_type else '0.00',
            'currency': payment.currency if payment and hasattr(payment, 'currency') else 'GHS',
            'payment_status': purchase.status if purchase else 'completed'
        }
    

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
