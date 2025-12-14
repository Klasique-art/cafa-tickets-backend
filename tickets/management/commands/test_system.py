from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tickets.models import (
    Venue,
    EventCategory,
    Event,
    TicketType,
    Order,
    Ticket,
    Payment,
)
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the ticket system functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Cafa Tickets System...'))

        # Test 1: Check models are accessible
        self.stdout.write('\n1. Checking models...')
        try:
            models = [Venue, EventCategory, Event, TicketType, Order, Ticket, Payment]
            for model in models:
                count = model.objects.count()
                self.stdout.write(f'   - {model.__name__}: {count} records')
            self.stdout.write(self.style.SUCCESS('   [OK] All models accessible'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   [FAIL] Model check failed: {e}'))
            return

        # Test 2: Check user model
        self.stdout.write('\n2. Checking users...')
        try:
            user_count = User.objects.count()
            superuser_count = User.objects.filter(is_superuser=True).count()
            self.stdout.write(f'   - Total users: {user_count}')
            self.stdout.write(f'   - Superusers: {superuser_count}')
            self.stdout.write(self.style.SUCCESS('   [OK] User model working'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   [FAIL] User check failed: {e}'))

        # Test 3: Create sample data if none exists
        self.stdout.write('\n3. Checking sample data...')
        try:
            if EventCategory.objects.count() == 0:
                self.stdout.write('   Creating sample categories...')
                categories = ['Concert', 'Conference', 'Workshop', 'Sports', 'Festival']
                for cat_name in categories:
                    EventCategory.objects.create(
                        name=cat_name,
                        description=f'{cat_name} events'
                    )
                self.stdout.write(self.style.SUCCESS('   [OK] Created 5 event categories'))
            else:
                self.stdout.write(f'   - {EventCategory.objects.count()} categories already exist')

            if Venue.objects.count() == 0:
                self.stdout.write('   Creating sample venues...')
                Venue.objects.create(
                    name='Accra International Conference Centre',
                    address='Accra, Ghana',
                    city='Accra',
                    country='Ghana',
                    capacity=5000
                )
                Venue.objects.create(
                    name='National Theatre of Ghana',
                    address='Accra, Ghana',
                    city='Accra',
                    country='Ghana',
                    capacity=1500
                )
                self.stdout.write(self.style.SUCCESS('   [OK] Created 2 venues'))
            else:
                self.stdout.write(f'   - {Venue.objects.count()} venues already exist')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   [FAIL] Sample data creation failed: {e}'))

        # Test 4: Check API configurations
        self.stdout.write('\n4. Checking configurations...')
        from django.conf import settings

        configs = {
            'DEBUG': settings.DEBUG,
            'INSTALLED_APPS includes tickets': 'tickets' in settings.INSTALLED_APPS,
            'INSTALLED_APPS includes corsheaders': 'corsheaders' in settings.INSTALLED_APPS,
            'MEDIA_URL configured': hasattr(settings, 'MEDIA_URL'),
            'MEDIA_ROOT configured': hasattr(settings, 'MEDIA_ROOT'),
            'AUTH_USER_MODEL': settings.AUTH_USER_MODEL,
        }

        for key, value in configs.items():
            status = '[OK]' if value else '[FAIL]'
            style = self.style.SUCCESS if value else self.style.ERROR
            self.stdout.write(style(f'   {status} {key}: {value}'))

        # Test 5: Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SYSTEM CHECK COMPLETE'))
        self.stdout.write('='*60)

        stats = {
            'Events': Event.objects.count(),
            'Categories': EventCategory.objects.count(),
            'Venues': Venue.objects.count(),
            'Ticket Types': TicketType.objects.count(),
            'Orders': Order.objects.count(),
            'Tickets': Ticket.objects.count(),
            'Payments': Payment.objects.count(),
        }

        self.stdout.write('\nDatabase Statistics:')
        for key, value in stats.items():
            self.stdout.write(f'  - {key}: {value}')

        self.stdout.write('\n' + self.style.SUCCESS('System is ready to use!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  1. Access admin at: http://localhost:8000/admin/')
        self.stdout.write('  2. API endpoints at: http://localhost:8000/api/v1/')
        self.stdout.write('  3. Create events and start selling tickets!')
