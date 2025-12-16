"""
Django management command to load sample events for a specific user
Run with: python manage.py load_my_events --email YOUR_EMAIL
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tickets.models import Event, EventCategory, TicketType
from users.models import PaymentProfile
from datetime import datetime, timedelta
from django.utils import timezone
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = 'Load sample events for a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email of the user to create events for',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of events to create (default: 10)',
        )

    def handle(self, *args, **options):
        user_email = options['email']
        
        # Get user
        try:
            organizer = User.objects.get(email=user_email)
            self.stdout.write(self.style.SUCCESS(f'✓ Found user: {organizer.email}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ User with email "{user_email}" not found!'))
            self.stdout.write('Available users:')
            for user in User.objects.all():
                self.stdout.write(f'  - {user.email}')
            return

        # Check categories
        categories = EventCategory.objects.filter(is_active=True)
        if not categories.exists():
            self.stdout.write(self.style.ERROR('❌ No categories found! Run: python manage.py load_categories'))
            return

        # Get or create payment profile
        payment_profile = PaymentProfile.objects.filter(
            user=organizer,
            is_verified=True
        ).first()
        
        if not payment_profile:
            self.stdout.write(self.style.WARNING('Creating payment profile...'))
            payment_profile = PaymentProfile.objects.create(
                id=uuid.uuid4(),
                user=organizer,
                method='mobile_money',
                name='Default MTN Account',
                description='Auto-created payment profile',
                account_details={
                    'mobile_number': '+233241234567',
                    'network': 'MTN',
                    'account_name': organizer.full_name or organizer.username
                },
                status='verified',
                is_verified=True,
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created payment profile'))

        # Sample events data
        events_data = [
            # FUTURE EVENTS
            {
                "title": "Afrobeats Night Accra 2025",
                "category": "music",
                "short_description": "The biggest Afrobeats party in Accra with top DJs",
                "description": "Join us for an unforgettable night of Afrobeats music featuring the best DJs in Ghana. Dance the night away with the hottest tracks and enjoy premium drinks and VIP lounges.",
                "featured_image": "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=800",
                "venue_name": "National Theatre",
                "venue_city": "Accra",
                "venue_address": "Liberia Road, Accra",
                "start_date_offset": 30,
                "start_time": "20:00:00",
                "end_time": "02:00:00",
                "max_attendees": 500,
                "ticket_types": [
                    {"name": "Regular", "price": "50.00", "quantity": 300},
                    {"name": "VIP", "price": "100.00", "quantity": 150},
                    {"name": "VVIP", "price": "150.00", "quantity": 50},
                ]
            },
            {
                "title": "Tech Innovation Summit 2025",
                "category": "business-networking",
                "short_description": "Connect with tech leaders and innovators",
                "description": "A premier gathering of technology entrepreneurs, investors, and innovators. Network with industry leaders, attend keynote speeches, and discover the latest in African tech innovation.",
                "featured_image": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800",
                "venue_name": "Kempinski Hotel",
                "venue_city": "Accra",
                "venue_address": "Ridge, Accra",
                "start_date_offset": 60,
                "start_time": "08:00:00",
                "end_time": "17:00:00",
                "max_attendees": 300,
                "ticket_types": [
                    {"name": "Early Bird", "price": "150.00", "quantity": 100},
                    {"name": "Regular", "price": "200.00", "quantity": 150},
                    {"name": "VIP Pass", "price": "350.00", "quantity": 50},
                ]
            },
            {
                "title": "Ghana Premier League Final",
                "category": "sports",
                "short_description": "Watch the epic finale of Ghana Premier League",
                "description": "Experience the thrill of Ghana's biggest football event. Watch the top two teams battle for the championship title in this exciting finale.",
                "featured_image": "https://images.unsplash.com/photo-1459865264687-595d652de67e?w=800",
                "venue_name": "Baba Yara Stadium",
                "venue_city": "Kumasi",
                "venue_address": "Amakom, Kumasi",
                "start_date_offset": 45,
                "start_time": "16:00:00",
                "end_time": "19:00:00",
                "max_attendees": 2000,
                "ticket_types": [
                    {"name": "General Stand", "price": "20.00", "quantity": 1500},
                    {"name": "Covered Stand", "price": "50.00", "quantity": 400},
                    {"name": "VIP", "price": "100.00", "quantity": 100},
                ]
            },
            {
                "title": "Contemporary Art Exhibition",
                "category": "arts-culture",
                "short_description": "Explore modern African art from emerging artists",
                "description": "A showcase of contemporary African art featuring paintings, sculptures, and digital art from Ghana's most promising young artists.",
                "featured_image": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=800",
                "venue_name": "Nubuke Foundation",
                "venue_city": "Accra",
                "venue_address": "East Legon, Accra",
                "start_date_offset": 15,
                "start_time": "10:00:00",
                "end_time": "18:00:00",
                "max_attendees": 200,
                "ticket_types": [
                    {"name": "General Admission", "price": "30.00", "quantity": 150},
                    {"name": "VIP Tour", "price": "80.00", "quantity": 50},
                ]
            },
            {
                "title": "Accra Food Festival",
                "category": "food-drink",
                "short_description": "Taste the best of Ghanaian and international cuisine",
                "description": "A culinary celebration featuring Ghana's top chefs and restaurants. Sample traditional Ghanaian dishes and international cuisine.",
                "featured_image": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=800",
                "venue_name": "Accra Sports Stadium",
                "venue_city": "Accra",
                "venue_address": "Osu, Accra",
                "start_date_offset": 25,
                "start_time": "12:00:00",
                "end_time": "22:00:00",
                "max_attendees": 1000,
                "ticket_types": [
                    {"name": "General Entry", "price": "40.00", "quantity": 800},
                    {"name": "VIP Tasting", "price": "120.00", "quantity": 200},
                ]
            },
            {
                "title": "Stand-Up Comedy Night",
                "category": "comedy",
                "short_description": "Laugh out loud with Ghana's funniest comedians",
                "description": "An evening of non-stop laughter featuring Ghana's best stand-up comedians with special guest performances.",
                "featured_image": "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?w=800",
                "venue_name": "Alliance Française",
                "venue_city": "Accra",
                "venue_address": "Airport Residential, Accra",
                "start_date_offset": 20,
                "start_time": "19:00:00",
                "end_time": "22:00:00",
                "max_attendees": 250,
                "ticket_types": [
                    {"name": "Regular", "price": "60.00", "quantity": 200},
                    {"name": "VIP Front Row", "price": "100.00", "quantity": 50},
                ]
            },
            {
                "title": "Digital Marketing Masterclass",
                "category": "education-training",
                "short_description": "Learn advanced digital marketing strategies",
                "description": "Comprehensive workshop covering SEO, social media marketing, content creation, and analytics with industry experts.",
                "featured_image": "https://images.unsplash.com/photo-1432888622747-4eb9a8f2c293?w=800",
                "venue_name": "MEST Africa",
                "venue_city": "Accra",
                "venue_address": "East Legon, Accra",
                "start_date_offset": 35,
                "start_time": "09:00:00",
                "end_time": "16:00:00",
                "max_attendees": 100,
                "ticket_types": [
                    {"name": "Workshop Pass", "price": "250.00", "quantity": 80},
                    {"name": "Premium", "price": "350.00", "quantity": 20},
                ]
            },
            {
                "title": "Independence Day Celebration",
                "category": "other",
                "short_description": "Celebrate Ghana's independence with music and culture",
                "description": "Grand celebration featuring cultural performances, live music, traditional dance, and fireworks.",
                "featured_image": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?w=800",
                "venue_name": "Independence Square",
                "venue_city": "Accra",
                "venue_address": "High Street, Accra",
                "start_date_offset": 90,
                "start_time": "14:00:00",
                "end_time": "22:00:00",
                "max_attendees": 5000,
                "ticket_types": [
                    {"name": "General", "price": "10.00", "quantity": 4500},
                    {"name": "VIP", "price": "50.00", "quantity": 500},
                ]
            },
            # PAST EVENTS
            {
                "title": "Jazz Night at Alliance",
                "category": "music",
                "short_description": "An evening of smooth jazz classics",
                "description": "Experience an unforgettable night of smooth jazz featuring local and international artists.",
                "featured_image": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800",
                "venue_name": "Alliance Française",
                "venue_city": "Accra",
                "venue_address": "Airport Residential, Accra",
                "start_date_offset": -30,
                "start_time": "19:00:00",
                "end_time": "23:00:00",
                "max_attendees": 180,
                "ticket_types": [
                    {"name": "Regular", "price": "75.00", "quantity": 120},
                    {"name": "VIP", "price": "150.00", "quantity": 60},
                ]
            },
            {
                "title": "Tech Startup Pitch Competition",
                "category": "business-networking",
                "short_description": "Watch Ghana's brightest startups compete",
                "description": "Exciting pitch competition where startups presented their innovative solutions to investors.",
                "featured_image": "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=800",
                "venue_name": "MEST Africa",
                "venue_city": "Accra",
                "venue_address": "East Legon, Accra",
                "start_date_offset": -45,
                "start_time": "14:00:00",
                "end_time": "19:00:00",
                "max_attendees": 200,
                "ticket_types": [
                    {"name": "General", "price": "50.00", "quantity": 150},
                    {"name": "VIP", "price": "100.00", "quantity": 50},
                ]
            },
        ]

        # Create events
        self.stdout.write(self.style.SUCCESS('\nCreating events...'))
        created_count = 0
        
        count_to_create = min(options['count'], len(events_data))

        for event_data in events_data[:count_to_create]:
            try:
                # Get category
                category = categories.filter(slug=event_data['category']).first()
                if not category:
                    self.stdout.write(self.style.WARNING(f'⚠️  Category "{event_data["category"]}" not found, skipping'))
                    continue

                # Calculate dates
                start_date = timezone.now() + timedelta(days=event_data['start_date_offset'])
                end_date = start_date

                # Create event
                event = Event.objects.create(
                    title=event_data['title'],
                    category=category,
                    organizer=organizer,
                    payment_profile=payment_profile,
                    short_description=event_data['short_description'],
                    description=event_data['description'],
                    featured_image=event_data['featured_image'],
                    venue_name=event_data['venue_name'],
                    venue_city=event_data['venue_city'],
                    venue_address=event_data.get('venue_address', ''),
                    venue_country='Ghana',
                    start_date=start_date.date(),
                    end_date=end_date.date(),
                    start_time=event_data['start_time'],
                    end_time=event_data['end_time'],
                    max_attendees=event_data['max_attendees'],
                    is_published=True,
                )

                # Create ticket types
                for ticket_data in event_data['ticket_types']:
                    TicketType.objects.create(
                        event=event,
                        name=ticket_data['name'],
                        description=f"{ticket_data['name']} ticket",
                        price=ticket_data['price'],
                        quantity=ticket_data['quantity'],
                    )

                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {event.title}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {event_data["title"]} - {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ Done! Created {created_count} events'))
        self.stdout.write(f'💡 View at: http://localhost:8000/api/v1/events/my-events/')