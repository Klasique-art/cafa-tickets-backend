"""
Ticket Management and Dashboard Views
"""
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from decimal import Decimal

from .models import Ticket, Event, Purchase
from .purchase_serializers import TicketSerializer, CheckInSerializer, TicketDetailSerializer


class MyTicketsView(generics.ListAPIView):
    """
    GET /api/v1/tickets/my-tickets/
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = Ticket.objects.filter(purchase__user=self.request.user).select_related(
            'event', 'event__category', 'ticket_type', 'purchase'
        )

        # Filter by status
        ticket_status = self.request.query_params.get('status', 'all')
        if ticket_status != 'all':
            queryset = queryset.filter(status=ticket_status)

        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(ticket_id__icontains=search) |
                Q(event__title__icontains=search)
            )

        # Filter by category slug
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(event__category__slug=category)

        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # If pagination is disabled, still return paginated structure
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': len(serializer.data),
            'next': None,
            'previous': None,
            'results': serializer.data
        })


class TicketDetailView(APIView):
    """
    GET /api/v1/tickets/{ticket_id}/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(
            Ticket,
            ticket_id=ticket_id,
            purchase__user=request.user
        )

        serializer = TicketDetailSerializer(ticket, context={'request': request})
        return Response(serializer.data)


class CheckInTicketView(APIView):
    """
    POST /api/v1/events/{slug_or_id}/checkin/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug_or_id):
        # Get event by slug or ID
        if slug_or_id.isdigit():
            event = get_object_or_404(Event, id=int(slug_or_id), organizer=request.user)
        else:
            event = get_object_or_404(Event, slug=slug_or_id, organizer=request.user)

        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ticket_id = serializer.validated_data['ticket_id']
        
        # ✅ Try to get ticket, return custom error if not found
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
        except Ticket.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Invalid ticket',
                'message': 'Ticket not found or not valid for this event'
            }, status=status.HTTP_404_NOT_FOUND)

        # Validate ticket belongs to this event
        if ticket.event.id != event.id:
            return Response({
                'success': False,
                'error': 'Wrong event',
                'message': f"This ticket is for '{ticket.event.title}', not '{event.title}'"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if already checked in
        if ticket.is_checked_in and event.check_in_policy == 'single_entry':
            return Response({
                'success': False,
                'error': 'Already checked in',
                'message': f'This ticket was already used at {ticket.checked_in_at}',
                'ticket': {
                    'ticket_id': ticket.ticket_id,
                    'attendee_name': ticket.attendee_name,
                    'checked_in_at': ticket.checked_in_at,
                    'checked_in_by': ticket.checked_in_by.full_name if ticket.checked_in_by and hasattr(ticket.checked_in_by, 'full_name') else (ticket.checked_in_by.username if ticket.checked_in_by else None)
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check in the ticket
        ticket.is_checked_in = True
        ticket.checked_in_at = timezone.now()
        ticket.checked_in_by = request.user
        ticket.status = 'used'
        ticket.save()

        # Get event stats
        total_checked_in = event.tickets.filter(is_checked_in=True).count()
        total_attendees = event.tickets.filter(status='paid').count()

        return Response({
            'success': True,
            'message': 'Ticket checked in successfully',
            'ticket': {
                'ticket_id': ticket.ticket_id,
                'attendee_name': ticket.attendee_name,
                'attendee_email': ticket.attendee_email,
                'ticket_type': {
                    'id': ticket.ticket_type.id,
                    'name': ticket.ticket_type.name,
                    'price': str(ticket.ticket_type.price)
                },
                'is_checked_in': ticket.is_checked_in,
                'checked_in_at': ticket.checked_in_at,
                'checked_in_by': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'full_name': request.user.full_name if hasattr(request.user, 'full_name') else request.user.username
                }
            },
            'event_stats': {
                'total_checked_in': total_checked_in,
                'total_attendees': total_attendees,
                'check_in_percentage': str(round((total_checked_in / total_attendees * 100) if total_attendees > 0 else 0, 2))
            }
        })
    
class CheckInHistoryView(APIView):
    """
    GET /api/v1/events/{slug_or_id}/checkin-history/
    Returns last 10 most recent check-ins for quick reference
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug_or_id):
        # Get event by slug or ID
        if slug_or_id.isdigit():
            event = get_object_or_404(Event, id=int(slug_or_id), organizer=request.user)
        else:
            event = get_object_or_404(Event, slug=slug_or_id, organizer=request.user)

        # Get last 10 checked-in tickets
        recent_checkins = Ticket.objects.filter(
            event=event,
            is_checked_in=True
        ).select_related('ticket_type', 'checked_in_by').order_by('-checked_in_at')[:10]

        # Build response
        results = []
        for ticket in recent_checkins:
            results.append({
                'ticket_id': ticket.ticket_id,
                'attendee_name': ticket.attendee_name,
                'attendee_email': ticket.attendee_email,
                'ticket_type': {
                    'id': ticket.ticket_type.id,
                    'name': ticket.ticket_type.name,
                    'price': str(ticket.ticket_type.price)
                },
                'checked_in_at': ticket.checked_in_at,
                'checked_in_by': {
                    'id': ticket.checked_in_by.id,
                    'username': ticket.checked_in_by.username,
                    'full_name': ticket.checked_in_by.full_name if hasattr(ticket.checked_in_by, 'full_name') else ticket.checked_in_by.username
                } if ticket.checked_in_by else None
            })

        return Response(results, status=status.HTTP_200_OK)
    

class EventAttendeesView(generics.ListAPIView):
    """
    GET /api/v1/events/{slug_or_id}/attendees/
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def get(self, request, slug_or_id):
        # Get event by slug or ID
        if slug_or_id.isdigit():
            event = get_object_or_404(Event, id=int(slug_or_id), organizer=request.user)
        else:
            event = get_object_or_404(Event, slug=slug_or_id, organizer=request.user)

        queryset = Ticket.objects.filter(event=event).select_related(
            'ticket_type', 'purchase', 'checked_in_by'
        )

        # Filter by payment status
        payment_status = request.query_params.get('payment_status', 'all')
        if payment_status != 'all':
            queryset = queryset.filter(status=payment_status)
        else:
            # Default: show paid tickets only
            queryset = queryset.filter(status='paid')

        # Search (now includes phone)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(attendee_name__icontains=search) |
                Q(attendee_email__icontains=search) |
                Q(attendee_phone__icontains=search) |
                Q(ticket_id__icontains=search)
            )

        # Filter by ticket type
        ticket_type_id = request.query_params.get('ticket_type_id')
        if ticket_type_id:
            queryset = queryset.filter(ticket_type_id=ticket_type_id)

        # Filter by check-in status
        check_in_status = request.query_params.get('check_in_status', 'all')
        if check_in_status == 'checked_in':
            queryset = queryset.filter(is_checked_in=True)
        elif check_in_status == 'not_checked_in':
            queryset = queryset.filter(is_checked_in=False)

        # Sort by
        sort_by = request.query_params.get('sort_by', '-purchase_date')
        
        sort_mapping = {
            'purchase_date': 'purchase__created_at',
            '-purchase_date': '-purchase__created_at',
            'attendee_name': 'attendee_name',
            '-attendee_name': '-attendee_name',
            'ticket_type': 'ticket_type__name',
            '-ticket_type': '-ticket_type__name',
            'check_in_time': 'checked_in_at',
            '-check_in_time': '-checked_in_at',
        }
        
        order_by = sort_mapping.get(sort_by, '-purchase__created_at')
        queryset = queryset.order_by(order_by)

        # Summary (before pagination)
        summary = {
            'total_attendees': queryset.count(),
            'checked_in': queryset.filter(is_checked_in=True).count(),
            'not_checked_in': queryset.filter(is_checked_in=False).count(),
        }
        if summary['total_attendees'] > 0:
            summary['check_in_percentage'] = round(
                (summary['checked_in'] / summary['total_attendees'] * 100), 2
            )
        else:
            summary['check_in_percentage'] = 0.0

        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        # ✅ Handle case when page is None
        if page is not None:
            tickets = page
        else:
            tickets = queryset

        results = []
        for ticket in tickets:
            # Get payment reference
            payment_reference = None
            if ticket.purchase:
                if hasattr(ticket.purchase, 'payments') and ticket.purchase.payments.exists():
                    payment = ticket.purchase.payments.first()
                    payment_reference = payment.payment_reference if hasattr(payment, 'payment_reference') else payment.payment_id
                else:
                    payment_reference = ticket.purchase.purchase_id

            # Build checked_in_by object
            checked_in_by = None
            if ticket.checked_in_by:
                checked_in_by = {
                    'id': ticket.checked_in_by.id,
                    'username': ticket.checked_in_by.username,
                    'full_name': ticket.checked_in_by.full_name if hasattr(ticket.checked_in_by, 'full_name') else ticket.checked_in_by.username
                }

            results.append({
                'ticket_id': ticket.ticket_id,
                'attendee_name': ticket.attendee_name,
                'attendee_email': ticket.attendee_email,
                'attendee_phone': ticket.attendee_phone,
                'ticket_type': {
                    'id': ticket.ticket_type.id,
                    'name': ticket.ticket_type.name,
                    'price': str(ticket.ticket_type.price)
                },
                'purchase_date': ticket.purchase.created_at if ticket.purchase else ticket.created_at,
                'payment_status': ticket.status,
                'payment_reference': payment_reference,
                'amount_paid': str(ticket.ticket_type.price),
                'is_checked_in': ticket.is_checked_in,
                'checked_in_at': ticket.checked_in_at,
                'checked_in_by': checked_in_by
            })

        # ✅ Return paginated response if page exists, otherwise plain response
        if page is not None:
            response = paginator.get_paginated_response(results)
            response.data['summary'] = summary
            return response
        
        return Response({
            'count': len(results),
            'next': None,
            'previous': None,
            'summary': summary,
            'results': results
        })
    
    
class UserDashboardStatsView(APIView):
    """
    GET /api/v1/auth/stats/
    Comprehensive user statistics including purchasing, organizing, and activity data
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # Purchasing stats - tickets the user bought
        tickets = Ticket.objects.filter(purchase__user=user, status='paid')
        total_spent = Purchase.objects.filter(
            user=user,
            status='completed'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Events attended (checked in)
        events_attended = tickets.filter(is_checked_in=True).values('event').distinct().count()

        # Organizing stats - events the user created
        events_created = Event.objects.filter(organizer=user)
        total_revenue = Purchase.objects.filter(
            event__organizer=user,
            status='completed'
        ).aggregate(total=Sum('total'))['total'] or 0

        total_tickets_sold = Ticket.objects.filter(
            event__organizer=user,
            status='paid'
        ).count()

        # Tickets by category breakdown
        tickets_by_category = []
        category_stats = tickets.values(
            'event__category__name'
        ).annotate(
            count=Count('id'),
            total_spent=Sum('ticket_type__price')
        ).order_by('-count')

        for stat in category_stats:
            if stat['event__category__name']:
                tickets_by_category.append({
                    'category': stat['event__category__name'],
                    'count': stat['count'],
                    'total_spent': str(stat['total_spent'] or 0)
                })

        # Upcoming and past events for user (as attendee)
        upcoming_events = tickets.filter(event__start_date__gte=now.date()).values('event').distinct().count()
        past_events = tickets.filter(event__start_date__lt=now.date()).values('event').distinct().count()

        # Best selling event
        best_selling_event = None
        best_event_data = events_created.annotate(
            sold_count=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-sold_count').first()

        if best_event_data:
            best_selling_event = {
                'id': best_event_data.id,
                'title': best_event_data.title,
                'tickets_sold': best_event_data.sold_count
            }

        # Revenue by month (last 6 months)
        from datetime import timedelta
        from django.db.models.functions import TruncMonth
        
        six_months_ago = now - timedelta(days=180)
        revenue_by_month = []
        
        monthly_revenue = Purchase.objects.filter(
            event__organizer=user,
            status='completed',
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            revenue=Sum('total'),
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-month')

        for month_data in monthly_revenue:
            revenue_by_month.append({
                'month': month_data['month'].strftime('%Y-%m'),
                'revenue': str(month_data['revenue'] or 0),
                'tickets_sold': month_data['tickets_sold']
            })

        # Recent activity (last 10 activities)
        recent_activity = []
        
        # Recent ticket purchases
        recent_purchases = Purchase.objects.filter(
            user=user,
            status='completed'
        ).order_by('-created_at')[:5]
        
        for purchase in recent_purchases:
            recent_activity.append({
                'type': 'ticket_purchase',
                'event_title': purchase.event.title,
                'date': purchase.created_at.isoformat(),
                'amount': str(purchase.total)
            })

        # Recent events created
        recent_events_created = events_created.order_by('-created_at')[:3]
        for event in recent_events_created:
            recent_activity.append({
                'type': 'event_created',
                'event_title': event.title,
                'date': event.created_at.isoformat()
            })

        # Recent ticket sales (for organizer)
        recent_sales = Purchase.objects.filter(
            event__organizer=user,
            status='completed'
        ).order_by('-created_at')[:3]
        
        for sale in recent_sales:
            recent_activity.append({
                'type': 'ticket_sale',
                'event_title': sale.event.title,
                'date': sale.created_at.isoformat(),
                'amount': str(sale.total)
            })

        # Sort by date and limit to 10
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        recent_activity = recent_activity[:10]

        # Calculate average tickets per event
        avg_tickets_per_event = 0
        if events_created.count() > 0:
            avg_tickets_per_event = round(total_tickets_sold / events_created.count(), 1)

        # Total attendees (unique checked-in tickets)
        total_attendees = Ticket.objects.filter(
            event__organizer=user,
            status='paid',
            is_checked_in=True
        ).count()

        account_age = now - user.date_joined
        account_age_days = account_age.days

        # If less than 1 day old, calculate hours
        if account_age_days == 0:
            account_age_hours = int(account_age.total_seconds() / 3600)
            account_age_display = f"{account_age_hours}h" if account_age_hours > 0 else "Just now"
        else:
            account_age_display = f"{account_age_days}d"

        return Response({
            'user_id': user.id,
            'username': user.username,
            'overview': {
                'tickets_purchased': tickets.count(),
                'events_organized': events_created.count(),
                'events_attended': events_attended,
                'total_spent': str(total_spent),
                'total_revenue': str(total_revenue),
                'account_age_days': account_age_days,
                'account_age_display': account_age_display
            },
            'purchasing_stats': {
                'active_tickets': tickets.filter(event__start_date__gte=now.date()).count(),
                'used_tickets': tickets.filter(is_checked_in=True).count(),
                'total_spent': str(total_spent),
                'tickets_by_category': tickets_by_category,
                'upcoming_events': upcoming_events,
                'past_events': past_events
            },
            'organizing_stats': {
                'total_events_created': events_created.count(),
                'active_events': events_created.filter(is_published=True, start_date__gte=now.date()).count(),
                'past_events': events_created.filter(start_date__lt=now.date()).count(),
                'total_tickets_sold': total_tickets_sold,
                'total_revenue': str(total_revenue),
                'total_attendees': total_attendees,
                'average_tickets_per_event': avg_tickets_per_event,
                'best_selling_event': best_selling_event,
                'revenue_by_month': revenue_by_month
            },
            'recent_activity': recent_activity
        })


class EventAnalyticsView(APIView):
    """
    GET /api/v1/events/{slug_or_id}/analytics/
    Get comprehensive analytics for an event (supports both slug and ID)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug_or_id):
        # Try to get event by slug first, then by ID
        try:
            event = Event.objects.get(slug=slug_or_id, organizer=request.user)
        except Event.DoesNotExist:
            try:
                event = Event.objects.get(id=slug_or_id, organizer=request.user)
            except (Event.DoesNotExist, ValueError):
                return Response({
                    'error': 'Event not found',
                    'message': "This event does not exist or you don't have permission to view it."
                }, status=status.HTTP_404_NOT_FOUND)

        # Calculate metrics
        total_tickets = event.max_attendees
        tickets_sold = event.tickets.filter(status='paid').count()
        tickets_checked_in = event.tickets.filter(is_checked_in=True).count()

        gross_revenue = Purchase.objects.filter(
            event=event,
            status='completed'
        ).aggregate(total=Sum('subtotal'))['total'] or 0

        platform_fee = Purchase.objects.filter(
            event=event,
            status='completed'
        ).aggregate(total=Sum('service_fee'))['total'] or 0

        net_revenue = gross_revenue

        # Calculate average ticket price
        average_ticket_price = round(gross_revenue / tickets_sold, 2) if tickets_sold > 0 else 0

        # Calculate projected revenue (if all tickets sell)
        total_possible_revenue = 0
        for ticket_type in event.ticket_types.all():
            total_possible_revenue += ticket_type.price * ticket_type.quantity
        projected_revenue = total_possible_revenue

        # Sales by ticket type
        sales_by_ticket_type = []
        for ticket_type in event.ticket_types.all():
            sold_count = ticket_type.tickets.filter(status='paid').count()
            revenue = sold_count * ticket_type.price
            
            percentage_of_total_sales = round((sold_count / tickets_sold * 100) if tickets_sold > 0 else 0, 2)
            percentage_of_quantity_sold = round((sold_count / ticket_type.quantity * 100) if ticket_type.quantity > 0 else 0, 2)
            
            sales_by_ticket_type.append({
                'ticket_type_id': ticket_type.id,
                'ticket_type': ticket_type.name,
                'price': str(ticket_type.price),
                'tickets_sold': sold_count,
                'total_quantity': ticket_type.quantity,
                'revenue': str(revenue),
                'percentage_of_total_sales': percentage_of_total_sales,
                'percentage_of_quantity_sold': percentage_of_quantity_sold
            })

        # Sales timeline (daily sales)
        from django.db.models.functions import TruncDate
        
        daily_sales = Purchase.objects.filter(
            event=event,
            status='completed'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid')),
            revenue=Sum('subtotal')
        ).order_by('date')

        sales_timeline = []
        cumulative_tickets = 0
        cumulative_revenue = 0
        
        for day in daily_sales:
            cumulative_tickets += day['tickets_sold']
            cumulative_revenue += day['revenue'] or 0
            
            sales_timeline.append({
                'date': day['date'].strftime('%Y-%m-%d'),
                'tickets_sold': day['tickets_sold'],
                'revenue': str(day['revenue'] or 0),
                'cumulative_tickets': cumulative_tickets,
                'cumulative_revenue': str(cumulative_revenue)
            })

        # Sales by hour
        from django.db.models.functions import ExtractHour
        
        hourly_sales = Purchase.objects.filter(
            event=event,
            status='completed'
        ).annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid')),
            revenue=Sum('subtotal')
        ).order_by('hour')

        sales_by_hour = []
        for hour_data in hourly_sales:
            sales_by_hour.append({
                'hour': f"{hour_data['hour']:02d}:00",
                'tickets_sold': hour_data['tickets_sold'],
                'revenue': str(hour_data['revenue'] or 0)
            })

        # Traffic stats (placeholder - would need analytics integration)
        # For now, returning calculated values based on sales conversion
        # In production, this would come from Google Analytics, Mixpanel, etc.
        traffic = {
            'page_views': 0,  # Would come from analytics service
            'unique_visitors': 0,  # Would come from analytics service
            'conversion_rate': round((tickets_sold / 1) * 100, 2) if tickets_sold > 0 else 0.0  # Placeholder calculation
        }

        # Recent sales (last 10)
        recent_purchases = Purchase.objects.filter(
            event=event,
            status='completed'
        ).select_related('user').prefetch_related('tickets').order_by('-created_at')[:10]

        recent_sales = []
        for purchase in recent_purchases:
            # Get first ticket from this purchase
            first_ticket = purchase.tickets.first()
            if first_ticket:
                recent_sales.append({
                    'ticket_id': first_ticket.ticket_id,
                    'ticket_type': first_ticket.ticket_type.name if first_ticket.ticket_type else 'N/A',
                    'amount': str(purchase.subtotal),
                    'buyer_name': purchase.user.full_name or purchase.user.username,
                    'purchase_date': purchase.created_at.isoformat()
                })

        return Response({
            'event_id': event.id,
            'event_title': event.title,
            'event_status': event.status,
            'overview': {
                'total_tickets': total_tickets,
                'tickets_sold': tickets_sold,
                'tickets_remaining': total_tickets - tickets_sold,
                'tickets_checked_in': tickets_checked_in,
                'sales_percentage': round((tickets_sold / total_tickets * 100) if total_tickets > 0 else 0, 2),
                'check_in_percentage': round((tickets_checked_in / tickets_sold * 100) if tickets_sold > 0 else 0, 2),
                'gross_revenue': str(gross_revenue),
                'net_revenue': str(net_revenue),
                'platform_fee': str(platform_fee),
                'platform_fee_percentage': 5.0,
                'average_ticket_price': str(average_ticket_price),
                'projected_revenue': str(projected_revenue)
            },
            'sales_by_ticket_type': sales_by_ticket_type,
            'sales_timeline': sales_timeline,
            'sales_by_hour': sales_by_hour,
            'traffic': traffic,
            'recent_sales': recent_sales
        })

class AttendedEventsView(generics.ListAPIView):
    """
    GET /api/v1/tickets/attended-events/
    List events the user has attended (checked in)
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return Ticket.objects.filter(
            purchase__user=self.request.user,
            is_checked_in=True
        ).select_related('event', 'event__category', 'ticket_type').order_by('-checked_in_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        # ✅ Handle case when page is None (no results or pagination disabled)
        if page is not None:
            tickets = page
        else:
            tickets = queryset

        results = []
        for ticket in tickets:
            results.append({
                'event': {
                    'id': ticket.event.id,
                    'title': ticket.event.title,
                    'slug': ticket.event.slug,
                    'featured_image': request.build_absolute_uri(ticket.event.featured_image.url) if ticket.event.featured_image else None,
                    'category': ticket.event.category.name if ticket.event.category else None,
                    'venue_name': ticket.event.venue_name,
                    'event_date': ticket.event.start_date
                },
                'ticket_id': ticket.ticket_id,
                'ticket_type': ticket.ticket_type.name if ticket.ticket_type else None,
                'attended_date': ticket.checked_in_at,
                'amount_paid': str(ticket.ticket_type.price) if ticket.ticket_type else '0.00'
            })

        # ✅ ALWAYS return paginated response for consistency
        if page is not None:
            return self.get_paginated_response(results)
        
        # ✅ Return pagination structure even when page is None
        return Response({
            'count': len(results),
            'next': None,
            'previous': None,
            'results': results
        })


class DownloadTicketView(APIView):
    """
    GET /api/v1/tickets/{ticket_id}/download/
    Download ticket as PDF
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(
            Ticket,
            ticket_id=ticket_id,
            purchase__user=request.user
        )

        # Generate PDF ticket
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from io import BytesIO

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Add ticket information
        p.setFont("Helvetica-Bold", 24)
        p.drawString(100, height - 100, "Event Ticket")

        p.setFont("Helvetica", 12)
        y_position = height - 150

        # Event details
        p.drawString(100, y_position, f"Event: {ticket.event.title}")
        y_position -= 20
        p.drawString(100, y_position, f"Date: {ticket.event.start_date} at {ticket.event.start_time}")
        y_position -= 20
        p.drawString(100, y_position, f"Venue: {ticket.event.venue_name}, {ticket.event.venue_city}")
        y_position -= 40

        # Ticket details
        p.drawString(100, y_position, f"Ticket ID: {ticket.ticket_id}")
        y_position -= 20
        p.drawString(100, y_position, f"Ticket Type: {ticket.ticket_type.name if ticket.ticket_type else 'N/A'}")
        y_position -= 20
        p.drawString(100, y_position, f"Attendee: {ticket.attendee_name}")
        y_position -= 20
        p.drawString(100, y_position, f"Email: {ticket.attendee_email}")
        y_position -= 40

        # QR Code (if available)
        if ticket.qr_code:
            p.drawString(100, y_position, "QR Code: Scan at venue entrance")
            # TODO: Add actual QR code image to PDF

        y_position -= 40
        p.setFont("Helvetica", 10)
        p.drawString(100, y_position, f"Purchase Reference: {ticket.purchase.purchase_id}")
        y_position -= 15
        p.drawString(100, y_position, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")

        p.showPage()
        p.save()

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ticket-{ticket.ticket_id}.pdf"'
        return response

class OrganizerRevenueView(APIView):
    """
    GET /api/v1/organizers/revenue/
    Comprehensive revenue dashboard for event organizers
    Query params:
    - period: all_time (default), this_month, last_month, this_year
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # Get period filter
        period = request.query_params.get('period', 'all_time')
        
        # Calculate date range based on period
        if period == 'this_month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == 'last_month':
            from datetime import timedelta
            first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            start_date = last_day_last_month.replace(day=1)
            end_date = last_day_last_month.replace(hour=23, minute=59, second=59)
        elif period == 'this_year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:  # all_time
            start_date = None
            end_date = None

        # Base queryset for organizer's completed purchases
        purchases_query = Purchase.objects.filter(
            event__organizer=user,
            status='completed'
        )
        
        if start_date:
            purchases_query = purchases_query.filter(created_at__gte=start_date)
        if end_date:
            purchases_query = purchases_query.filter(created_at__lte=end_date)

        # Calculate summary
        gross_revenue = purchases_query.aggregate(total=Sum('subtotal'))['total'] or Decimal('0')
        platform_fee_percentage = Decimal('5.0')  # ✅ Define THEN convert to Decimal
        platform_fees = gross_revenue * (platform_fee_percentage / Decimal('100'))
        net_revenue = gross_revenue - platform_fees
        
        total_tickets_sold = Ticket.objects.filter(
            purchase__in=purchases_query,
            status='paid'
        ).count()
        
        total_events = Event.objects.filter(
            organizer=user,
            is_published=True
        ).count()
        
        average_ticket_price = round(gross_revenue / total_tickets_sold, 2) if total_tickets_sold > 0 else Decimal('0')

        # REAL PAYOUT STATUS (using actual revenue records)
        from .models import OrganizerRevenue

        # Get revenue records for this organizer
        revenue_queryset = OrganizerRevenue.objects.filter(organizer=user)

        # Filter by period if needed
        if start_date:
            revenue_queryset = revenue_queryset.filter(created_at__gte=start_date)
        if end_date:
            revenue_queryset = revenue_queryset.filter(created_at__lte=end_date)

        # Update any pending revenue that's now available (past 7-day holding period)
        OrganizerRevenue.objects.filter(
            status='pending',
            available_at__lte=now
        ).update(status='available')

        # Available balance (ready to withdraw)
        available_balance = revenue_queryset.filter(
            status='available',
            is_withdrawn=False
        ).aggregate(total=Sum('organizer_earnings'))['total'] or Decimal('0')

        # Pending balance (still in 7-day holding period)
        pending_balance = revenue_queryset.filter(
            status='pending'
        ).aggregate(total=Sum('organizer_earnings'))['total'] or Decimal('0')

        # Total paid out (already withdrawn)
        total_paid_out = revenue_queryset.filter(
            is_withdrawn=True
        ).aggregate(total=Sum('organizer_earnings'))['total'] or Decimal('0')
        
        # Calculate next payout date (mock: 15th of next month)
        from datetime import timedelta
        if now.day < 15:
            next_payout_date = now.replace(day=15).date()
        else:
            next_month = now.replace(day=1) + timedelta(days=32)
            next_payout_date = next_month.replace(day=15).date()

        # Revenue by event
        revenue_by_event = []
        event_revenue = purchases_query.values(
            'event__id',
            'event__title'
        ).annotate(
            gross_revenue=Sum('subtotal'),
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-gross_revenue')[:10]  # Top 10 events

        for event_data in event_revenue:
            event_gross = event_data['gross_revenue'] or Decimal('0')
            event_platform_fee = event_gross * (platform_fee_percentage / Decimal('100'))
            event_net = event_gross - event_platform_fee
            
            revenue_by_event.append({
                'event_id': event_data['event__id'],
                'event_title': event_data['event__title'],
                'gross_revenue': str(event_gross),
                'net_revenue': str(event_net),
                'platform_fee': str(event_platform_fee),
                'tickets_sold': event_data['tickets_sold']
            })

        # Revenue by month (last 12 months)
        from django.db.models.functions import TruncMonth
        from datetime import timedelta
        
        twelve_months_ago = now - timedelta(days=365)
        revenue_by_month = []
        
        monthly_revenue = Purchase.objects.filter(
            event__organizer=user,
            status='completed',
            created_at__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            gross_revenue=Sum('subtotal'),
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-month')

        for month_data in monthly_revenue:
            month_gross = month_data['gross_revenue'] or Decimal('0')
            month_platform_fee = month_gross * (platform_fee_percentage / Decimal('100'))
            month_net = month_gross - month_platform_fee
            
            revenue_by_month.append({
                'month': month_data['month'].strftime('%Y-%m'),
                'gross_revenue': str(month_gross),
                'net_revenue': str(month_net),
                'platform_fee': str(month_platform_fee),
                'tickets_sold': month_data['tickets_sold']
            })

        # Recent transactions (last 20)
        recent_purchases = purchases_query.select_related(
            'event',
            'user'
        ).prefetch_related('tickets__ticket_type').order_by('-created_at')[:20]

        recent_transactions = []
        for purchase in recent_purchases:
            first_ticket = purchase.tickets.first()
            if first_ticket:
                ticket_price = purchase.subtotal
                transaction_platform_fee = ticket_price * (platform_fee_percentage / Decimal('100'))
                transaction_net = ticket_price - transaction_platform_fee
                
                recent_transactions.append({
                    'date': purchase.created_at.isoformat(),
                    'event_title': purchase.event.title,
                    'ticket_type': first_ticket.ticket_type.name if first_ticket.ticket_type else 'N/A',
                    'amount': str(ticket_price),
                    'platform_fee': str(transaction_platform_fee),
                    'net_amount': str(transaction_net)
                })

        return Response({
            'period': period,
            'summary': {
                'gross_revenue': str(gross_revenue),
                'platform_fees': str(platform_fees),
                'net_revenue': str(net_revenue),
                'total_tickets_sold': total_tickets_sold,
                'total_events': total_events,
                'average_ticket_price': str(average_ticket_price)
            },
            'payout_status': {
                'available_balance': str(available_balance),
                'pending_balance': str(pending_balance),
                'total_paid_out': str(total_paid_out),
                'next_payout_date': next_payout_date.isoformat()
            },
            'revenue_by_event': revenue_by_event,
            'revenue_by_month': revenue_by_month,
            'recent_transactions': recent_transactions
        })


