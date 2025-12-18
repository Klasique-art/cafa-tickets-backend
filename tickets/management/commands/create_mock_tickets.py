from django.core.management.base import BaseCommand
from tickets.models import Event, Purchase, Ticket
from users.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create mock tickets for testing'

    def handle(self, *args, **kwargs):
        # Get user
        user = User.objects.filter(email='feboapong@gmail.com').first()
        
        if not user:
            self.stdout.write(self.style.ERROR('User not found!'))
            return
        
        # Get multiple events (up to 5)
        events = Event.objects.filter(is_published=True)[:5]
        
        if not events:
            self.stdout.write(self.style.ERROR('No events found!'))
            return
        
        # Create one ticket for each event
        for i, event in enumerate(events):
            ticket_type = event.ticket_types.first()
            
            if not ticket_type:
                self.stdout.write(self.style.WARNING(f'No ticket types for {event.title}, skipping...'))
                continue
            
            ticket_price = Decimal(ticket_type.price)
            quantity = 1
            subtotal = ticket_price * quantity
            service_fee = subtotal * Decimal('0.05')  # 5% fee
            total = subtotal + service_fee
            
            purchase = Purchase.objects.create(
                user=user,
                event=event,
                ticket_type=ticket_type,
                quantity=quantity,
                buyer_name="Klasique",
                buyer_email="feboapong@gmail.com",
                buyer_phone=f"+23324123456{i}",
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
                attendee_name="Klasique",
                attendee_email="feboapong@gmail.com",
                attendee_phone=f"+23324123456{i}",
                status='active'
            )
            
            self.stdout.write(self.style.SUCCESS(f'Created ticket for {event.title}: {ticket.ticket_id}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(events)} mock tickets!'))