"""
Public Views
Endpoints that don't require authentication
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import Event, Ticket, Purchase
from users.models import User


"""
Public Views
Endpoints that don't require authentication
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import Event, Ticket, Purchase
from users.models import User


class PublicStatsView(APIView):
    """
    GET /api/v1/public/stats/
    Get public platform statistics for homepage
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()

        # Total Upcoming Events (filter by date, not status property)
        upcoming_events_count = Event.objects.filter(
            is_published=True,
            start_date__gt=now  # ✅ Use date comparison instead of status
        ).count()

        # Total Tickets Sold (paid tickets only)
        total_tickets_sold = Ticket.objects.filter(
            status='paid'
        ).count()

        # Total Event Organizers (users who have published at least one event)
        total_organizers = User.objects.filter(
            organized_events__is_published=True
        ).distinct().count()

        # Total Attendees (successfully checked in)
        total_attendees = Ticket.objects.filter(
            is_checked_in=True
        ).values('attendee_email').distinct().count()

        # Total Events Ever Published
        total_events_published = Event.objects.filter(
            is_published=True
        ).count()

        # Active Events (ongoing right now) - between start and end date
        active_events_count = Event.objects.filter(
            is_published=True,
            start_date__lte=now,  # ✅ Started already
            end_date__gte=now     # ✅ Hasn't ended yet
        ).count()

        # Total Revenue Generated (completed purchases)
        total_revenue = Purchase.objects.filter(
            status='completed'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Most Popular Event (by tickets sold)
        most_popular_event = None
        popular_event = Event.objects.filter(
            is_published=True
        ).annotate(
            tickets_count=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-tickets_count').first()

        if popular_event:
            most_popular_event = {
                'id': popular_event.id,
                'slug': popular_event.slug,
                'title': popular_event.title,
                'tickets_sold': popular_event.tickets_count,
                'category': popular_event.category.name if popular_event.category else None
            }

        # Events This Month
        first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        events_this_month = Event.objects.filter(
            is_published=True,
            start_date__gte=first_day_this_month,
            start_date__month=now.month
        ).count()

        # New Organizers This Month
        new_organizers_this_month = User.objects.filter(
            organized_events__is_published=True,
            organized_events__created_at__gte=first_day_this_month
        ).distinct().count()

        return Response({
            'success': True,
            'data': {
                'overview': {
                    'total_upcoming_events': upcoming_events_count,
                    'total_tickets_sold': total_tickets_sold,
                    'total_organizers': total_organizers,
                    'total_attendees_checked_in': total_attendees,
                    'total_events_published': total_events_published,
                    'active_events_now': active_events_count
                },
                'revenue': {
                    'total_revenue': str(total_revenue),
                    'currency': 'GHS'
                },
                'highlights': {
                    'most_popular_event': most_popular_event,
                    'events_this_month': events_this_month,
                    'new_organizers_this_month': new_organizers_this_month
                },
                'last_updated': now.isoformat()
            }
        })
