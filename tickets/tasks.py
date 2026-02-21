from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.mail import send_mail
from django.conf import settings
from .models import Event, Ticket, EventNotification

@shared_task
def check_and_send_event_notifications():
    """
    Periodic task to check all upcoming events and send notifications
    Runs every 30 minutes via Celery Beat
    """
    now = timezone.now()
    
    # Get all published events
    events = Event.objects.filter(is_published=True)
    
    for event in events:
        # Skip if event doesn't have required date/time fields
        if not event.start_date or not event.start_time:
            continue
            
        # Combine date and time to get full datetime
        event_start_naive = datetime.combine(event.start_date, event.start_time)
        event_start = timezone.make_aware(event_start_naive)
        
        # Handle end time
        if event.end_date and event.end_time:
            event_end_naive = datetime.combine(event.end_date, event.end_time)
            event_end = timezone.make_aware(event_end_naive)
        else:
            event_end = event_start
        
        # Calculate time differences
        time_until_start = event_start - now
        time_since_end = now - event_end
        
        # Check which notification window we're in and send
        # Using time ranges with buffer (30 min window since task runs every 30 min)
        
        # Event ended (within 1 hour after end)
        if timedelta(minutes=0) < time_since_end < timedelta(hours=1):
            send_notification_to_attendees(event, 'ended')
        
        # 1 hour before (55 min to 1 hour 5 min window)
        elif timedelta(minutes=55) < time_until_start <= timedelta(hours=1, minutes=5):
            send_notification_to_attendees(event, '1_hour')
        
        # 12 hours before (11h 30m to 12h 30m window)
        elif timedelta(hours=11, minutes=30) < time_until_start <= timedelta(hours=12, minutes=30):
            send_notification_to_attendees(event, '12_hours')
        
        # 1 day before (23h 30m to 24h 30m window)
        elif timedelta(hours=23, minutes=30) < time_until_start <= timedelta(days=1, minutes=30):
            send_notification_to_attendees(event, '1_day')
        
        # 3 days before
        elif timedelta(days=2, hours=23, minutes=30) < time_until_start <= timedelta(days=3, minutes=30):
            send_notification_to_attendees(event, '3_days')
        
        # 7 days before
        elif timedelta(days=6, hours=23, minutes=30) < time_until_start <= timedelta(days=7, minutes=30):
            send_notification_to_attendees(event, '7_days')
        
        # Event starting now (within 5 minutes of start)
        elif abs(time_until_start.total_seconds()) < 300:
            send_notification_to_attendees(event, 'starting')


def send_notification_to_attendees(event, notification_type):
    """
    Send email notification to all ticket holders of an event
    """
    # Get all paid tickets for this event
    tickets = Ticket.objects.filter(event=event, status='paid').select_related('purchase__user')
    
    # Get unique users (in case someone bought multiple tickets)
    user_emails = set()
    users_to_notify = []
    
    for ticket in tickets:
        user = ticket.purchase.user
        if user.email not in user_emails:
            user_emails.add(user.email)
            users_to_notify.append(user)
    
    # Send notification to each unique user
    for user in users_to_notify:
        # Check if this notification was already sent
        already_sent = EventNotification.objects.filter(
            event=event,
            user=user,
            notification_type=notification_type,
            channel='email',
            is_sent=True
        ).exists()
        
        if not already_sent:
            # Send the email asynchronously
            send_event_notification_email.delay(event.id, user.id, notification_type)
            
            # Mark as sent to prevent duplicates
            EventNotification.objects.create(
                event=event,
                user=user,
                notification_type=notification_type,
                channel='email',
                is_sent=True
            )


@shared_task
def send_event_notification_email(event_id, user_id, notification_type):
    """
    Send email notification to user about their event
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
        
        # Create different messages for each notification type
        messages = {
            '7_days': f"Reminder: {event.title} is coming up in 7 days!",
            '3_days': f"Just 3 days until {event.title}!",
            '1_day': f"Tomorrow is the big day! {event.title} starts in 24 hours.",
            '12_hours': f"Getting close! {event.title} starts in 12 hours.",
            '1_hour': f"Almost time! {event.title} starts in 1 hour.",
            'starting': f"{event.title} is starting now!",
            'ended': f"Thank you for attending {event.title}!",
        }
        
        subject = messages.get(notification_type, f"Update about {event.title}")
        
        # Format the event date nicely
        event_datetime = timezone.datetime.combine(event.start_date, event.start_time)
        if timezone.is_naive(event_datetime):
            event_datetime = timezone.make_aware(event_datetime)
        
        message = f"""
Hello {user.first_name or user.email},

{messages.get(notification_type)}

Event Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Event: {event.title}
🗓️ Date: {event_datetime.strftime('%A, %B %d, %Y')}
🕐 Time: {event_datetime.strftime('%I:%M %p')}
📍 Location: {event.venue_name or event.venue_address or 'See event details'}

We look forward to seeing you there!

Best regards,
Cafa Tickets Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f"✓ Email sent to {user.email} for {notification_type}"
        
    except Event.DoesNotExist:
        return f"✗ Event {event_id} not found"
    except User.DoesNotExist:
        return f"✗ User {user_id} not found"
    except Exception as e:
        return f"✗ Error sending notification: {str(e)}"


@shared_task
def check_and_send_inactive_user_emails():
    """
    Check for users who haven't logged in for a specified period
    and send re-engagement emails
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Define inactivity period (30 minutes for testing)
    inactivity_minutes = 30
    cutoff_time = timezone.now() - timedelta(minutes=inactivity_minutes)
    
    # Get users who:
    # 1. Haven't logged in for 30+ minutes
    # 2. Are active accounts
    # 3. Not staff or superuser
    inactive_users = User.objects.filter(
        last_login__lt=cutoff_time,
        is_active=True,
        is_staff=False,
        is_superuser=False
    )
    
    for user in inactive_users:
        # Check if we already sent a re-engagement email recently (in last 24 hours for testing)
        last_email_sent = check_last_reengagement_email(user)
        
        if not last_email_sent:
            send_reengagement_email.delay(user.id)


def check_last_reengagement_email(user):
    """Check if we sent a re-engagement email in the last 24 hours"""
    from .models import UserReengagementEmail
    
    one_day_ago = timezone.now() - timedelta(hours=24)
    
    recent_email = UserReengagementEmail.objects.filter(
        user=user,
        sent_at__gte=one_day_ago
    ).exists()
    
    return recent_email


@shared_task
def send_reengagement_email(user_id):
    """Send re-engagement email to inactive user"""
    from django.contrib.auth import get_user_model
    from .models import UserReengagementEmail
    
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        
        subject = "We Miss You at Cafa Tickets! 🎉"
        
        message = f"""
Hello {user.first_name or user.email},

We noticed you haven't visited Cafa Tickets in a while, and we miss you!

A lot has been happening:
✨ New exciting events have been added
🎫 Special promotions and discounts
⚡ Improved booking experience

Come back and check out what's new: https://cafatickets.com

We'd love to see you again!

Best regards,
The Cafa Tickets Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        # Record that we sent this email
        UserReengagementEmail.objects.create(user=user)
        
        return f"✓ Re-engagement email sent to {user.email}"
        
    except User.DoesNotExist:
        return f"✗ User {user_id} not found"
    except Exception as e:
        return f"✗ Error sending email: {str(e)}"