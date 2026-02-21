#!/usr/bin/env python
"""
Check all events and their revenue calculations
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cafa_ticket.settings')
django.setup()

from tickets.models import Purchase, Ticket, Event
from django.db.models import Count, Sum

def check_all_events():
    print("=" * 80)
    print("ALL EVENTS REVENUE REPORT")
    print("=" * 80)
    
    events = Event.objects.all().order_by('-created_at')
    
    if not events.exists():
        print("No events found in database")
        return
    
    print(f"\nTotal Events: {events.count()}\n")
    
    for event in events:
        print("=" * 80)
        print(f"EVENT ID: {event.id}")
        print(f"TITLE: {event.title}")
        print(f"SLUG: {event.slug}")
        print(f"STATUS: {event.status}")
        print(f"MAX ATTENDEES: {event.max_attendees}")
        print("-" * 80)
        
        # Ticket Types Info
        print("\nTICKET TYPES:")
        for tt in event.ticket_types.all():
            print(f"  - {tt.name}:")
            print(f"      Price: {tt.price}")
            print(f"      Quantity: {tt.quantity}")
            print(f"      Tickets Sold (field): {tt.tickets_sold}")
            actual_sold = tt.tickets.filter(status='paid').count()
            print(f"      Tickets Sold (actual paid): {actual_sold}")
            print(f"      Revenue (tickets_sold * price): {tt.tickets_sold * tt.price}")
        
        # Purchases Info
        print("\nPURCHASES:")
        purchases = Purchase.objects.filter(event=event)
        if purchases.exists():
            for p in purchases:
                print(f"  - Purchase {p.id}:")
                print(f"      Status: {p.status}")
                print(f"      Subtotal: {p.subtotal}")
                print(f"      Tickets in purchase: {p.tickets.count()}")
        else:
            print("  No purchases")
        
        # Tickets Info
        print("\nTICKETS:")
        tickets = Ticket.objects.filter(event=event)
        if tickets.exists():
            paid_tickets = tickets.filter(status='paid')
            print(f"  Total tickets: {tickets.count()}")
            print(f"  Paid tickets: {paid_tickets.count()}")
            for t in paid_tickets[:5]:  # Show first 5 paid tickets
                print(f"    - {t.ticket_id}: {t.status}, Price: {t.price}")
        else:
            print("  No tickets")
        
        # Revenue Calculations
        print("\nREVENUE CALCULATIONS:")
        
        # Method 1: From completed purchases (current backend)
        completed_revenue = Purchase.objects.filter(
            event=event,
            status='completed'
        ).aggregate(total=Sum('subtotal'))['total'] or 0
        print(f"  1. Completed Purchases Revenue: {completed_revenue}")
        
        # Method 2: From all purchases
        all_revenue = Purchase.objects.filter(
            event=event
        ).aggregate(total=Sum('subtotal'))['total'] or 0
        print(f"  2. All Purchases Revenue: {all_revenue}")
        
        # Method 3: From paid tickets
        paid_tickets = Ticket.objects.filter(event=event, status='paid')
        paid_revenue = sum(t.price for t in paid_tickets)
        print(f"  3. Paid Tickets Revenue: {paid_revenue}")
        
        # Method 4: From ticket_types.tickets_sold field
        ticket_types_revenue = sum(tt.tickets_sold * tt.price for tt in event.ticket_types.all())
        print(f"  4. Ticket Types Field Revenue: {ticket_types_revenue}")
        
        # What the API currently returns
        print(f"\n  >> CURRENT API RETURNS: {completed_revenue} (WRONG!)")
        print(f"  >> SHOULD RETURN: {paid_revenue} (Method 3 - Paid Tickets)")
        
        print()

if __name__ == '__main__':
    check_all_events()