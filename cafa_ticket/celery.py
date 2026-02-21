import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cafa_ticket.settings')

app = Celery('cafa_tickets')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'check-upcoming-events': {
        'task': 'tickets.tasks.check_and_send_event_notifications',
        'schedule': crontab(minute='*/2'),  # Run every 2 minutes
    },
    'check-inactive-users': {
        'task': 'tickets.tasks.check_and_send_inactive_user_emails',
        'schedule': crontab(minute='*/5'),
    },
}