from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket, Order, Payment
from .utils import generate_ticket_qr_code, send_order_confirmation_email, send_ticket_email


@receiver(post_save, sender=Ticket)
def create_ticket_qr_code(sender, instance, created, **kwargs):
    """Generate QR code when ticket is created"""
    if created and not instance.qr_code:
        try:
            generate_ticket_qr_code(instance)
        except Exception as e:
            print(f"Error generating QR code for ticket {instance.ticket_number}: {e}")


@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, update_fields, **kwargs):
    """Send order confirmation email when order is completed"""
    if not created and instance.status == "completed":
        if update_fields and "status" in update_fields:
            try:
                send_order_confirmation_email(instance)

                for ticket in instance.tickets.all():
                    send_ticket_email(ticket)
            except Exception as e:
                print(f"Error sending order confirmation for {instance.order_id}: {e}")


@receiver(post_save, sender=Payment)
def update_order_on_payment_completion(sender, instance, created, **kwargs):
    """Update order status when payment is completed"""
    if not created and instance.status == "completed":
        order = instance.order
        if order.status != "completed":
            order.status = "completed"
            order.payment_method = instance.gateway
            order.payment_reference = instance.gateway_reference
            from django.utils import timezone
            order.completed_at = timezone.now()
            order.save(update_fields=["status", "payment_method", "payment_reference", "completed_at"])
