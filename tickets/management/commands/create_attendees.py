from django.core.management.base import BaseCommand
from tickets.models import Event, Purchase, Ticket
from users.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create mock attendees for an event'

    def add_arguments(self, parser):
        parser.add_argument('event_slug', type=str, help='Event slug')
        parser.add_argument('--count', type=int, default=10, help='Number of attendees to create')
        parser.add_argument('--email', type=str, default='feboapong@gmail.com', help='User email')

    def handle(self, *args, **kwargs):
        event_slug = kwargs['event_slug']
        count = kwargs['count']
        user_email = kwargs['email']

        # Get user
        user = User.objects.filter(email=user_email).first()
        if not user:
            self.stdout.write(self.style.ERROR(f'User with email {user_email} not found!'))
            return

        # Get event
        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Event with slug "{event_slug}" not found!'))
            return

        # Get ticket type
        ticket_type = event.ticket_types.first()
        if not ticket_type:
            self.stdout.write(self.style.ERROR('No ticket types found for this event!'))
            return

        # Attendee names pool
        attendees = [
            {"name": "Kwame Mensah", "email": "kwame.mensah@example.com", "phone": "+233241234560"},
            {"name": "Ama Serwaa", "email": "ama.serwaa@example.com", "phone": "+233241234561"},
            {"name": "Kofi Adjei", "email": "kofi.adjei@example.com", "phone": "+233241234562"},
            {"name": "Akosua Boateng", "email": "akosua.boateng@example.com", "phone": "+233241234563"},
            {"name": "Yaw Owusu", "email": "yaw.owusu@example.com", "phone": "+233241234564"},
            {"name": "Abena Asante", "email": "abena.asante@example.com", "phone": "+233241234565"},
            {"name": "Kojo Darko", "email": "kojo.darko@example.com", "phone": "+233241234566"},
            {"name": "Efua Addo", "email": "efua.addo@example.com", "phone": "+233241234567"},
            {"name": "Kwabena Tetteh", "email": "kwabena.tetteh@example.com", "phone": "+233241234568"},
            {"name": "Afia Osei", "email": "afia.osei@example.com", "phone": "+233241234569"},
            {"name": "Nana Appiah", "email": "nana.appiah@example.com", "phone": "+233241234570"},
            {"name": "Esi Antwi", "email": "esi.antwi@example.com", "phone": "+233241234571"},
            {"name": "Kwesi Boakye", "email": "kwesi.boakye@example.com", "phone": "+233241234572"},
            {"name": "Adjoa Frimpong", "email": "adjoa.frimpong@example.com", "phone": "+233241234573"},
            {"name": "Fiifi Hayford", "email": "fiifi.hayford@example.com", "phone": "+233241234574"},
            {"name": "Maame Gyasi", "email": "maame.gyasi@example.com", "phone": "+233241234575"},
            {"name": "Koo Asiedu", "email": "koo.asiedu@example.com", "phone": "+233241234576"},
            {"name": "Adwoa Konadu", "email": "adwoa.konadu@example.com", "phone": "+233241234577"},
            {"name": "Kwaku Sarpong", "email": "kwaku.sarpong@example.com", "phone": "+233241234578"},
            {"name": "Akua Manu", "email": "akua.manu@example.com", "phone": "+233241234579"},
            {"name": "Kwame Asiedu", "email": "kwame.asiedu@example.com", "phone": "+233241234580"},
        ]

        # Limit to available names or requested count
        attendees_to_create = attendees[:min(count, len(attendees))]

        # Create attendees
        for attendee in attendees_to_create:
            ticket_price = Decimal(ticket_type.price)
            quantity = 1
            subtotal = ticket_price * quantity
            service_fee = subtotal * Decimal('0.05')
            total = subtotal + service_fee

            purchase = Purchase.objects.create(
                user=user,
                event=event,
                ticket_type=ticket_type,
                quantity=quantity,
                buyer_name=attendee['name'],
                buyer_email=attendee['email'],
                buyer_phone=attendee['phone'],
                ticket_price=ticket_price,
                subtotal=subtotal,
                service_fee=service_fee,
                total=total,
                status='completed'
            )

            ticket = Ticket.objects.create(
                event=event,
                ticket_type=ticket_type,
                purchase=purchase,
                attendee_name=attendee['name'],
                attendee_email=attendee['email'],
                attendee_phone=attendee['phone'],
                status='paid'
            )

            self.stdout.write(self.style.SUCCESS(f'✓ Created ticket: {ticket.ticket_id} for {attendee["name"]}'))

        self.stdout.write(self.style.SUCCESS(f'\n🎉 Successfully created {len(attendees_to_create)} attendees for "{event.title}"!'))