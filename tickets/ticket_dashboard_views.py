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

from .models import Ticket, Event, Purchase
from .purchase_serializers import TicketSerializer, CheckInSerializer


class MyTicketsView(generics.ListAPIView):
    """
    GET /api/v1/tickets/my-tickets/
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = Ticket.objects.filter(purchase__user=self.request.user)

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

        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(event__category_id=category_id)

        return queryset.order_by('-created_at')


class TicketDetailView(APIView):
    """
    GET /api/v1/tickets/{ticket_id}/
    """
    permissions_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(
            Ticket,
            ticket_id=ticket_id,
            purchase__user=request.user
        )

        serializer = TicketSerializer(ticket, context={'request': request})
        return Response(serializer.data)


class CheckInTicketView(APIView):
    """
    POST /api/v1/events/{id}/checkin/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        event = get_object_or_404(Event, id=id, organizer=request.user)

        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ticket_id = serializer.validated_data['ticket_id']
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)

        # Validate ticket belongs to this event
        if ticket.event.id != event.id:
            return Response({
                'error': 'Wrong event',
                'message': f"This ticket is for '{ticket.event.title}', not '{event.title}'"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if already checked in
        if ticket.is_checked_in and event.check_in_policy == 'single_entry':
            return Response({
                'error': 'Already checked in',
                'message': f'This ticket was already used at {ticket.checked_in_at}',
                'ticket': {
                    'ticket_id': ticket.ticket_id,
                    'attendee_name': ticket.attendee_name,
                    'checked_in_at': ticket.checked_in_at,
                    'checked_in_by': ticket.checked_in_by.username if ticket.checked_in_by else None
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
                    'full_name': request.user.full_name
                }
            },
            'event_stats': {
                'total_checked_in': total_checked_in,
                'total_attendees': total_attendees,
                'check_in_percentage': round((total_checked_in / total_attendees * 100) if total_attendees > 0 else 0, 2)
            }
        })


class EventAttendeesView(generics.ListAPIView):
    """
    GET /api/v1/events/{id}/attendees/
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination

    def get(self, request, id):
        event = get_object_or_404(Event, id=id, organizer=request.user)

        queryset = Ticket.objects.filter(event=event, status='paid')

        # Filters
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(attendee_name__icontains=search) |
                Q(attendee_email__icontains=search) |
                Q(ticket_id__icontains=search)
            )

        ticket_type_id = request.query_params.get('ticket_type_id')
        if ticket_type_id:
            queryset = queryset.filter(ticket_type_id=ticket_type_id)

        check_in_status = request.query_params.get('check_in_status', 'all')
        if check_in_status == 'checked_in':
            queryset = queryset.filter(is_checked_in=True)
        elif check_in_status == 'not_checked_in':
            queryset = queryset.filter(is_checked_in=False)

        # Summary
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
            summary['check_in_percentage'] = 0

        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        results = [{
            'ticket_id': ticket.ticket_id,
            'attendee_name': ticket.attendee_name,
            'attendee_email': ticket.attendee_email,
            'attendee_phone': ticket.attendee_phone,
            'ticket_type': {
                'id': ticket.ticket_type.id,
                'name': ticket.ticket_type.name,
                'price': str(ticket.ticket_type.price)
            },
            'purchase_date': ticket.purchase.created_at,
            'payment_status': 'paid',
            'payment_reference': ticket.purchase.payment.reference if hasattr(ticket.purchase, 'payment') else None,
            'amount_paid': str(ticket.ticket_type.price),
            'is_checked_in': ticket.is_checked_in,
            'checked_in_at': ticket.checked_in_at,
            'checked_in_by': ticket.checked_in_by.username if ticket.checked_in_by else None
        } for ticket in page]

        response = paginator.get_paginated_response(results)
        response.data['summary'] = summary
        return response


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
            tickets_sold=Count('tickets', filter=Q(tickets__status='paid'))
        ).order_by('-tickets_sold').first()

        if best_event_data:
            best_selling_event = {
                'id': best_event_data.id,
                'title': best_event_data.title,
                'tickets_sold': best_event_data.tickets_sold
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
    GET /api/v1/events/{id}/analytics/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        event = get_object_or_404(Event, id=id, organizer=request.user)

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
            }
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

        results = []
        for ticket in page:
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

        return self.get_paginated_response(results)


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