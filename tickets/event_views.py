"""
Event Views
Handles all event-related endpoints
"""
from rest_framework import status, generics, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count

from .models import Event, EventCategory, TicketType
from .new_serializers import (
    EventCategorySerializer,
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    TicketTypeCreateSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EventCategoryListView(generics.ListAPIView):
    """
    GET /api/v1/event-categories/
    """
    queryset = EventCategory.objects.filter(is_active=True)
    serializer_class = EventCategorySerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response({
            'count': queryset.count(),
            'categories': serializer.data
        })


class EventListView(generics.ListAPIView):
    """
    GET /api/v1/events/
    Browse all upcoming and ongoing events with filters
    """
    serializer_class = EventListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_date', 'created_at', '-start_date', '-created_at']

    def get_queryset(self):
        queryset = Event.objects.filter(is_published=True)

        # Filter by status (default: upcoming)
        event_status = self.request.query_params.get('status', 'upcoming')
        now = timezone.now().date()

        if event_status == 'upcoming':
            queryset = queryset.filter(start_date__gt=now)
        elif event_status == 'ongoing':
            queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
        elif event_status == 'all':
            queryset = queryset.filter(Q(start_date__gte=now) | Q(start_date__lte=now, end_date__gte=now))

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Filter by city
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(venue_city__iexact=city)

        # Date range filters
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)

        # Price range filters
        price_min = self.request.query_params.get('price_min')
        price_max = self.request.query_params.get('price_max')

        if price_min or price_max:
            # Get events with tickets in price range
            ticket_filter = Q()
            if price_min:
                ticket_filter &= Q(ticket_types__price__gte=price_min)
            if price_max:
                ticket_filter &= Q(ticket_types__price__lte=price_max)
            queryset = queryset.filter(ticket_filter).distinct()

        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(venue_name__icontains=search) |
                Q(venue_city__icontains=search)
            )

        # Ordering
        ordering = self.request.query_params.get('ordering', '-start_date')

        # Map ordering options
        ordering_map = {
            'start_date': 'start_date',
            '-start_date': '-start_date',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'price': 'ticket_types__price',
            '-price': '-ticket_types__price',
        }

        if ordering in ordering_map:
            queryset = queryset.order_by(ordering_map[ordering])

        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Get filters applied
        filters_applied = {
            'category': request.query_params.get('category'),
            'search': request.query_params.get('search'),
            'city': request.query_params.get('city'),
            'status': request.query_params.get('status', 'upcoming'),
        }

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self.get_paginated_response(serializer.data)
            result.data['filters_applied'] = filters_applied
            return result

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'filters_applied': filters_applied
        })


class PastEventsListView(generics.ListAPIView):
    """
    GET /api/v1/events/past/
    Browse past events
    """
    serializer_class = EventListSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Event.objects.filter(
            is_published=True,
            end_date__lt=timezone.now().date()
        )

        # Apply same filters as EventListView
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(venue_city__iexact=city)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(venue_name__icontains=search)
            )

        return queryset.order_by('-end_date')


class EventDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/events/{id}/ or /api/v1/events/{slug}/
    """
    serializer_class = EventDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Event.objects.filter(is_published=True)

    def get_object(self):
        """Support both ID and slug lookup"""
        lookup_value = self.kwargs.get(self.lookup_field)

        # Try slug first
        try:
            obj = self.get_queryset().get(slug=lookup_value)
        except Event.DoesNotExist:
            # Try ID
            try:
                obj = self.get_queryset().get(id=lookup_value)
            except (Event.DoesNotExist, ValueError):
                raise Event.DoesNotExist

        # Increment view count
        obj.views_count += 1
        obj.save(update_fields=['views_count'])

        return obj

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found',
                'message': "The event you're looking for does not exist or has been deleted."
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class EventCreateView(generics.CreateAPIView):
    """
    POST /api/v1/events/
    """
    serializer_class = EventCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()

        return Response({
            'message': 'Event created successfully',
            'event': {
                'id': event.id,
                'title': event.title,
                'slug': event.slug,
                'is_published': event.is_published,
                'created_at': event.created_at,
                'ticket_types_created': event.ticket_types.count()
            }
        }, status=status.HTTP_201_CREATED)


class EventUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/v1/events/{id}/
    """
    serializer_class = EventCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Check if event has already started
        if instance.status in ['ongoing', 'past']:
            return Response({
                'error': 'Cannot update event',
                'message': 'This event has already started. Major changes are not allowed.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()

        return Response({
            'message': 'Event updated successfully',
            'event': {
                'id': event.id,
                'title': event.title,
                'slug': event.slug,
                'updated_at': event.updated_at
            }
        })


class MyEventsView(generics.ListAPIView):
    """
    GET /api/v1/events/my-events/
    List events created by the authenticated user
    """
    serializer_class = EventListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        from django.db.models import Count, Sum, Q
        queryset = Event.objects.filter(organizer=self.request.user)

        # Filter by status
        event_status = self.request.query_params.get('status', 'all')
        now = timezone.now().date()

        if event_status == 'upcoming':
            queryset = queryset.filter(start_date__gt=now)
        elif event_status == 'ongoing':
            queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
        elif event_status == 'past':
            queryset = queryset.filter(end_date__lt=now)

        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |           # OR title contains search
                Q(venue_name__icontains=search) |      # OR venue name contains search
                Q(venue_city__icontains=search)        # OR venue city contains search
            )
        
        # Filter by category slug
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Sorting with annotations
        sort_by = self.request.query_params.get('sort_by', '-start_date')

        # For tickets_sold and revenue, we need to add calculated fields
        if sort_by in ['-tickets_sold', 'tickets_sold', '-revenue', 'revenue']:
            queryset = queryset.annotate(
                # Count tickets where status is 'paid'
                calculated_tickets_sold=Count('tickets', filter=Q(tickets__status='paid')),
                # Sum revenue from completed purchases
                calculated_revenue=Sum('purchases__subtotal', filter=Q(purchases__status='completed'))
            )

        # Map frontend sort_by to Django ordering
        sort_map = {
            '-start_date': '-start_date',
            'start_date': 'start_date',
            '-created_at': '-created_at',
            'created_at': 'created_at',
            '-tickets_sold': '-calculated_tickets_sold',
            'tickets_sold': 'calculated_tickets_sold',
            '-revenue': '-calculated_revenue',
            'revenue': 'calculated_revenue',
        }

        # Apply sorting
        ordering = sort_map.get(sort_by, '-start_date')  # Default to -start_date
        return queryset.order_by(ordering)

    def list(self, request, *args, **kwargs):
        from django.db.models import Sum, Count, Q
        from .models import Purchase
        
        queryset = self.get_queryset()
        now = timezone.now()

        # Calculate summary with revenue and tickets sold
        total_revenue = Purchase.objects.filter(
            event__organizer=request.user,
            status='completed'
        ).aggregate(total=Sum('subtotal'))['total'] or 0

        total_tickets_sold = queryset.aggregate(
            total=Count('tickets', filter=Q(tickets__status='paid'))
        )['total'] or 0

        summary = {
            'total_events': queryset.count(),
            'upcoming_events': queryset.filter(start_date__gt=now.date()).count(),
            'ongoing_events': queryset.filter(
                start_date__lte=now.date(),
                end_date__gte=now.date()
            ).count(),
            'past_events': queryset.filter(end_date__lt=now.date()).count(),
            'total_revenue': str(total_revenue),
            'total_tickets_sold': total_tickets_sold
        }

        # Paginate
        page = self.paginate_queryset(queryset)
        events_to_process = page if page is not None else queryset

        # Build results with analytics and ticket types
        results = []
        for event in events_to_process:
            # Use serializer for basic event data
            event_data = EventListSerializer(event, context={'request': request}).data
            
            # Add analytics
            tickets_sold = event.tickets.filter(status='paid').count()
            tickets_checked_in = event.tickets.filter(is_checked_in=True).count()
            total_tickets = event.max_attendees
            
            event_purchases = Purchase.objects.filter(event=event, status='completed')
            gross_revenue = event_purchases.aggregate(total=Sum('subtotal'))['total'] or 0
            platform_fee = event_purchases.aggregate(total=Sum('service_fee'))['total'] or 0
            net_revenue = gross_revenue
            
            last_sale = event_purchases.order_by('-created_at').first()
            
            event_data['analytics'] = {
                'total_tickets': total_tickets,
                'tickets_sold': tickets_sold,
                'tickets_remaining': total_tickets - tickets_sold,
                'tickets_checked_in': tickets_checked_in,
                'sales_percentage': round((tickets_sold / total_tickets * 100) if total_tickets > 0 else 0, 2),
                'gross_revenue': str(gross_revenue),
                'net_revenue': str(net_revenue),
                'platform_fee': str(platform_fee),
                'page_views': event.views_count,
                'unique_visitors': event.views_count,
                'conversion_rate': round((tickets_sold / event.views_count * 100) if event.views_count > 0 else 0, 2),
                'last_sale_date': last_sale.created_at if last_sale else None,
            }
            
            # Add ticket types
            ticket_types_data = []
            for tt in event.ticket_types.all():
                tickets_sold_for_type = tt.tickets_sold
                revenue = tickets_sold_for_type * tt.price
                sales_percentage = round((tickets_sold_for_type / tt.quantity * 100) if tt.quantity > 0 else 0, 2)
                
                status_value = 'active'
                if tt.available_until and now > tt.available_until:
                    status_value = 'expired'
                elif tt.tickets_remaining <= 0:
                    status_value = 'sold_out'
                elif not tt.is_available:
                    status_value = 'inactive'
                
                ticket_type_obj = {
                    'id': tt.id,
                    'name': tt.name,
                    'price': str(tt.price),
                    'quantity': tt.quantity,
                    'tickets_sold': tickets_sold_for_type,
                    'tickets_remaining': tt.tickets_remaining,
                    'revenue': str(revenue),
                    'sales_percentage': sales_percentage,
                }
                
                if tt.available_from:
                    ticket_type_obj['available_from'] = tt.available_from
                if tt.available_until:
                    ticket_type_obj['available_until'] = tt.available_until
                if status_value != 'active':
                    ticket_type_obj['status'] = status_value
                
                ticket_types_data.append(ticket_type_obj)
            
            event_data['ticket_types'] = ticket_types_data
            results.append(event_data)

        # Return response
        if page is not None:
            return Response({
                'count': self.paginator.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'summary': summary,
                'results': results
            })

        return Response({
            'count': len(results),
            'next': None,
            'previous': None,
            'summary': summary,
            'results': results
        })

    def get_next_link(self):
        if not self.paginator.page.has_next():
            return None
        page_number = self.paginator.page.next_page_number()
        return self.request.build_absolute_uri(f'?page={page_number}')

    def get_previous_link(self):
        if not self.paginator.page.has_previous():
            return None
        page_number = self.paginator.page.previous_page_number()
        return self.request.build_absolute_uri(f'?page={page_number}')


class CreateTicketTypeView(generics.CreateAPIView):
    """
    POST /api/v1/events/{event_id}/tickets/
    """
    serializer_class = TicketTypeCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, event_id):
        # Get event
        event = get_object_or_404(Event, id=event_id, organizer=request.user)

        # Validate data
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check capacity
        current_total = event.ticket_types.aggregate(
            total=Count('quantity')
        )['total'] or 0
        new_quantity = serializer.validated_data['quantity']

        if current_total + new_quantity > event.max_attendees:
            return Response({
                'error': 'Capacity exceeded',
                'message': f'Adding this ticket type would exceed event maximum attendees ({event.max_attendees}). Current total: {current_total}, Attempting to add: {new_quantity}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create ticket type
        ticket_type = serializer.save(event=event)

        return Response({
            'message': 'Ticket type created successfully',
            'ticket_type': TicketTypeCreateSerializer(ticket_type).data
        }, status=status.HTTP_201_CREATED)


class MyEventDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/events/my-events/{slug_or_id}/
    Get detailed information about a specific event created by the user
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)

    def get_object(self):
        """Support both ID and slug lookup"""
        lookup_value = self.kwargs.get('slug_or_id')

        # Try slug first
        try:
            obj = self.get_queryset().get(slug=lookup_value)
        except Event.DoesNotExist:
            # Try ID
            try:
                obj = self.get_queryset().get(id=lookup_value)
            except (Event.DoesNotExist, ValueError):
                raise Event.DoesNotExist

        return obj

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found',
                'message': "This event does not exist or you don't have permission to view it."
            }, status=status.HTTP_404_NOT_FOUND)

        # Build detailed response
        from .new_serializers import EventCategorySerializer
        from users.models import User

        # Calculate analytics
        total_tickets_sold = instance.tickets.filter(status='paid').count()
        total_revenue = 0
        from tickets.models import Purchase
        from django.db.models import Sum
        purchases = Purchase.objects.filter(event=instance, status='completed')
        if purchases.exists():
            total_revenue = purchases.aggregate(total=Sum('subtotal'))['total'] or 0

        # Ticket types with analytics
        ticket_types_data = []
        for tt in instance.ticket_types.all():
            tickets_sold = tt.tickets_sold
            revenue = tickets_sold * tt.price
            sales_percentage = round((tickets_sold / tt.quantity * 100) if tt.quantity > 0 else 0, 2)

            ticket_types_data.append({
                'id': tt.id,
                'name': tt.name,
                'description': tt.description,
                'price': str(tt.price),
                'quantity': tt.quantity,
                'tickets_sold': tickets_sold,
                'tickets_remaining': tt.tickets_remaining,
                'revenue': str(revenue),
                'sales_percentage': sales_percentage,
                'min_purchase': tt.min_purchase,
                'max_purchase': tt.max_purchase,
                'available_from': tt.available_from,
                'available_until': tt.available_until,
                'status': 'expired' if (tt.available_until and timezone.now() > tt.available_until) else ('active' if tt.is_available else 'inactive')
            })

        response_data = {
            'id': instance.id,
            'title': instance.title,
            'slug': instance.slug,
            'featured_image': request.build_absolute_uri(instance.featured_image.url) if instance.featured_image else None,
            'additional_images': instance.additional_images,
            'category': EventCategorySerializer(instance.category).data if instance.category else None,
            'short_description': instance.short_description,
            'description': instance.description,
            'venue_name': instance.venue_name,
            'venue_address': instance.venue_address,
            'venue_city': instance.venue_city,
            'venue_country': instance.venue_country,
            'venue_location': {
                'latitude': str(instance.venue_latitude) if instance.venue_latitude else None,
                'longitude': str(instance.venue_longitude) if instance.venue_longitude else None
            } if instance.venue_latitude and instance.venue_longitude else None,
            'start_date': instance.start_date,
            'start_time': instance.start_time,
            'end_date': instance.end_date,
            'end_time': instance.end_time,
            'status': instance.status,
            'is_published': instance.is_published,
            'is_recurring': instance.is_recurring,
            'recurrence_pattern': instance.recurrence_pattern,
            'check_in_policy': instance.check_in_policy,
            'max_attendees': instance.max_attendees,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
            'organizer': {
                'id': instance.organizer.id,
                'username': instance.organizer.username,
                'full_name': instance.organizer.full_name,
                'email': instance.organizer.email,
                'phone': instance.organizer.phone_number,
                'profile_image': request.build_absolute_uri(instance.organizer.profile_image.url) if instance.organizer.profile_image else None
            },
            'ticket_types': ticket_types_data
        }

        return Response(response_data)
