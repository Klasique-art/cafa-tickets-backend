"""
Event Ticketing Serializers
Matches the exact API specification from the documentation
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone

from .models import (
    EventCategory,
    Event,
    TicketType,
    Purchase,
    Payment,
    Ticket,
)
from users.models import PaymentProfile

User = get_user_model()


# ============================================================================
# CATEGORY SERIALIZERS
# ============================================================================

class EventCategorySerializer(serializers.ModelSerializer):
    """Serializer for event categories"""
    event_count = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'icon',
            'event_count',
        ]

    def get_event_count(self, obj):
        """Get count of published events in this category"""
        return obj.events.filter(is_published=True).count()


# ============================================================================
# USER/ORGANIZER SERIALIZERS
# ============================================================================

class OrganizerSerializer(serializers.ModelSerializer):
    """Serializer for event organizer information"""
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'profile_image']


class OrganizerDetailSerializer(serializers.ModelSerializer):
    """Detailed organizer information for event details"""
    member_since = serializers.DateTimeField(source='date_joined', read_only=True)
    events_organized = serializers.SerializerMethodField()
    total_tickets_sold = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'full_name',
            'profile_image',
            'bio',
            'events_organized',
            'total_tickets_sold',
            'member_since',
        ]

    def get_events_organized(self, obj):
        return obj.organized_events.filter(is_published=True).count()

    def get_total_tickets_sold(self, obj):
        return Ticket.objects.filter(
            event__organizer=obj,
            status='paid'
        ).count()


# ============================================================================
# TICKET TYPE SERIALIZERS
# ============================================================================

class TicketTypeSerializer(serializers.ModelSerializer):
    """Serializer for ticket types"""
    tickets_remaining = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = TicketType
        fields = [
            'id',
            'name',
            'description',
            'price',
            'quantity',
            'tickets_sold',
            'tickets_remaining',
            'min_purchase',
            'max_purchase',
            'available_from',
            'available_until',
            'is_available',
            'sold_out_at',
        ]


class TicketTypeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ticket types"""

    class Meta:
        model = TicketType
        fields = [
            'name',
            'description',
            'price',
            'quantity',
            'min_purchase',
            'max_purchase',
            'available_from',
            'available_until',
        ]

    def validate_price(self, value):
        if value < Decimal('10.00'):
            raise serializers.ValidationError("Price must be at least 10.00 GHS")
        return value

    def validate_quantity(self, value):
        if value < 1 or value > 1000000:
            raise serializers.ValidationError("Quantity must be between 1 and 1,000,000")
        return value

    def validate(self, data):
        """Cross-field validation"""
        if data.get('max_purchase', 10) < data.get('min_purchase', 1):
            raise serializers.ValidationError({
                'max_purchase': 'Max purchase must be greater than or equal to min purchase'
            })

        if data.get('available_until') and data.get('available_from'):
            if data['available_until'] <= data['available_from']:
                raise serializers.ValidationError({
                    'available_until': 'Available until must be after available from'
                })

        return data


# ============================================================================
# EVENT LIST SERIALIZERS
# ============================================================================

class EventListSerializer(serializers.ModelSerializer):
    """Serializer for event listing"""
    organizer = OrganizerSerializer(read_only=True)
    category = EventCategorySerializer(read_only=True)
    status = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    lowest_price = serializers.ReadOnlyField()
    highest_price = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'slug',
            'organizer',
            'category',
            'short_description',
            'featured_image',
            'venue_name',
            'venue_city',
            'venue_country',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'tickets_sold',
            'tickets_available',
            'max_attendees',
            'lowest_price',
            'highest_price',
            'status',
            'is_recurring',
            'created_at',
            'is_published',
            'updated_at', 
        ]


# ============================================================================
# EVENT DETAIL SERIALIZER
# ============================================================================

class EventDetailSerializer(serializers.ModelSerializer):
    """Detailed event serializer"""
    organizer = OrganizerDetailSerializer(read_only=True)
    category = EventCategorySerializer(read_only=True)
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    lowest_price = serializers.ReadOnlyField()
    highest_price = serializers.ReadOnlyField()
    venue = serializers.SerializerMethodField()
    share_urls = serializers.SerializerMethodField()
    similar_events = serializers.SerializerMethodField()
    recurrence_info = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'slug',
            'organizer',
            'category',
            'description',
            'short_description',
            'featured_image',
            'additional_images',
            'venue',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'timezone',
            'max_attendees',
            'tickets_sold',
            'tickets_available',
            'lowest_price',
            'highest_price',
            'status',
            'is_recurring',
            'recurrence_info',
            'check_in_policy',
            'is_published',
            'created_at',
            'updated_at',
            'ticket_types',
            'similar_events',
            'share_urls',
        ]

    def get_venue(self, obj):
        """Format venue information"""
        return {
            'name': obj.venue_name,
            'address': obj.venue_address,
            'city': obj.venue_city,
            'country': obj.venue_country,
            'latitude': str(obj.venue_latitude) if obj.venue_latitude else None,
            'longitude': str(obj.venue_longitude) if obj.venue_longitude else None,
            'google_maps_url': f"https://www.google.com/maps?q={obj.venue_latitude},{obj.venue_longitude}" if obj.venue_latitude and obj.venue_longitude else None
        }

    def get_timezone(self, obj):
        return "Africa/Accra"

    def get_recurrence_info(self, obj):
        """Return recurrence pattern if event is recurring"""
        if obj.is_recurring and obj.recurrence_pattern:
            return obj.recurrence_pattern
        return None

    def get_share_urls(self, obj):
        """Generate social share URLs"""
        event_url = f"https://cafatickets.com/events/{obj.slug}"
        return {
            'facebook': f"https://www.facebook.com/sharer/sharer.php?u={event_url}",
            'twitter': f"https://twitter.com/intent/tweet?url={event_url}&text=Check%20out%20{obj.title.replace(' ', '%20')}",
            'whatsapp': f"https://wa.me/?text=Check%20out%20{obj.title.replace(' ', '%20')}%20{event_url}",
            'email': f"mailto:?subject={obj.title.replace(' ', '%20')}&body=Check%20out%20this%20event:%20{event_url}"
        }

    def get_similar_events(self, obj):
        """Get similar events in the same category"""
        similar = Event.objects.filter(
            category=obj.category,
            is_published=True,
            start_date__gte=timezone.now().date()
        ).exclude(id=obj.id)[:3]

        return [{
            'id': event.id,
            'title': event.title,
            'slug': event.slug,
            'featured_image': event.featured_image.url if event.featured_image else None,
            'start_date': event.start_date,
            'venue_city': event.venue_city,
            'lowest_price': str(event.lowest_price),
        } for event in similar]


# ============================================================================
# EVENT CREATE/UPDATE SERIALIZERS
# ============================================================================

class EventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating events"""
    category_slug = serializers.CharField(required=True)
    payment_profile_id = serializers.UUIDField(required=True)
    ticket_types = serializers.CharField(required=True)
    additional_images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Event
        fields = [
            'title',
            'category_slug',
            'short_description',
            'description',
            'venue_name',
            'venue_address',
            'venue_city',
            'venue_country',
            'venue_latitude',
            'venue_longitude',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'is_recurring',
            'recurrence_pattern',
            'check_in_policy',
            'max_attendees',
            'payment_profile_id',
            'featured_image',
            'additional_images',
            'is_published',
            'ticket_types',
        ]

    def validate_title(self, value):
        if len(value) < 5 or len(value) > 200:
            raise serializers.ValidationError("Title must be between 5 and 200 characters")
        return value

    def validate_short_description(self, value):
        if len(value) < 20 or len(value) > 300:
            raise serializers.ValidationError("Short description must be between 20 and 300 characters")
        return value

    def validate_description(self, value):
        if len(value) < 50:
            raise serializers.ValidationError("Description must be at least 50 characters")
        return value

    def validate_payment_profile_id(self, value):
        """Validate payment profile exists and is verified"""
        request = self.context.get('request')
        try:
            profile = PaymentProfile.objects.get(id=value, user=request.user)
            if not profile.is_verified:
                raise serializers.ValidationError(
                    "Payment profile must be verified before creating events"
                )
        except PaymentProfile.DoesNotExist:
            raise serializers.ValidationError(
                "Payment profile not found or you don't have permission to use it"
            )
        return value

    def validate_ticket_types(self, value):
        """Validate ticket types - parse JSON string"""
        import json
        try:
            # Parse JSON string to list
            ticket_types = json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError:
            raise serializers.ValidationError("Invalid JSON format for ticket types")
        
        if not ticket_types:
            raise serializers.ValidationError("At least one ticket type is required")
        if len(ticket_types) > 10:
            raise serializers.ValidationError("Maximum 10 ticket types allowed")
        
        # Validate each ticket type
        for ticket_type in ticket_types:
            ticket_serializer = TicketTypeCreateSerializer(data=ticket_type)
            if not ticket_serializer.is_valid():
                raise serializers.ValidationError(ticket_serializer.errors)
        
        return ticket_types

    def validate(self, data):
        """Cross-field validation"""
        # Validate dates
        if data.get('start_date') and data.get('end_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after or equal to start date'
                })

        # Validate start date is not in past
        if data.get('start_date') and data['start_date'] < timezone.now().date():
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be in the past'
            })

        # Validate max attendees
        if data.get('ticket_types') and data.get('max_attendees'):
            total_tickets = sum(tt['quantity'] for tt in data['ticket_types'])
            if total_tickets > data['max_attendees']:
                raise serializers.ValidationError({
                    'max_attendees': f'Max attendees must be at least {total_tickets} (sum of ticket quantities)'
                })

        # Validate recurring pattern
        if data.get('is_recurring') and not data.get('recurrence_pattern'):
            raise serializers.ValidationError({
                'recurrence_pattern': 'Recurrence pattern is required for recurring events'
            })

        return data

    def create(self, validated_data):
        """Create event with ticket types"""
        ticket_types_data = validated_data.pop('ticket_types')
        category_slug = validated_data.pop('category_slug')
        payment_profile_id = validated_data.pop('payment_profile_id')
        
        # ✅ Pop file fields
        featured_image = validated_data.pop('featured_image', None)
        additional_images_files = validated_data.pop('additional_images', [])

        # Get category and payment profile
        category = EventCategory.objects.get(slug=category_slug)
        payment_profile = PaymentProfile.objects.get(id=payment_profile_id)

        # Create event
        event = Event.objects.create(
            category=category,
            payment_profile=payment_profile,
            organizer=self.context['request'].user,
            featured_image=featured_image,  # ImageField handles this fine
            **validated_data
        )
        
        # ✅ Save additional images and store their URLs
        additional_image_urls = []
        if additional_images_files:
            from django.core.files.storage import default_storage
            for i, img_file in enumerate(additional_images_files):
                # Save file and get URL
                file_path = f'events/additional/{event.id}/{i}_{img_file.name}'
                saved_path = default_storage.save(file_path, img_file)
                file_url = default_storage.url(saved_path)
                additional_image_urls.append(file_url)
            
            # Store URLs in JSONField
            event.additional_images = additional_image_urls
            event.save()

        # Create ticket types
        for ticket_type_data in ticket_types_data:
            TicketType.objects.create(event=event, **ticket_type_data)

        return event

    def update(self, instance, validated_data):
        """Update event"""
        ticket_types_data = validated_data.pop('ticket_types', None)
        category_slug = validated_data.pop('category_slug', None)
        payment_profile_id = validated_data.pop('payment_profile_id', None)

        # Update category if provided
        if category_slug:
            try:
                instance.category = EventCategory.objects.get(slug=category_slug)
            except EventCategory.DoesNotExist:
                raise serializers.ValidationError({
                    'category_slug': f'Category with slug "{category_slug}" does not exist'
                })

        # Update payment profile if provided
        if payment_profile_id:
            instance.payment_profile = PaymentProfile.objects.get(id=payment_profile_id)

        # Update other fields
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        # Update ticket types if provided
        if ticket_types_data is not None:
            # Remove old ticket types
            instance.ticket_types.all().delete()
            # Create new ones
            for ticket_type_data in ticket_types_data:
                TicketType.objects.create(event=instance, **ticket_type_data)

        return instance


# Add timezone field to EventDetailSerializer
EventDetailSerializer._declared_fields['timezone'] = serializers.SerializerMethodField()
