import qrcode
from io import BytesIO
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import requests
from decimal import Decimal


def generate_qr_code(data, filename="qr_code.png"):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return File(buffer, name=filename)


def generate_ticket_qr_code(ticket):
    qr_data = f"{settings.FRONTEND_URL}/verify-ticket/{ticket.ticket_number}"
    qr_code_file = generate_qr_code(qr_data, f"ticket_{ticket.ticket_number}.png")
    ticket.qr_code.save(f"ticket_{ticket.ticket_number}.png", qr_code_file, save=True)
    return ticket


def send_order_confirmation_email(order):
    subject = f"Order Confirmation - {order.event.title}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [order.buyer_email]

    context = {
        "order": order,
        "event": order.event,
        "tickets": order.tickets.all(),
        "frontend_url": settings.FRONTEND_URL,
    }

    html_content = f"""
    <html>
    <body>
        <h1>Order Confirmation</h1>
        <p>Dear {order.buyer_name},</p>
        <p>Thank you for your order! Your tickets for <strong>{order.event.title}</strong> have been confirmed.</p>

        <h2>Order Details</h2>
        <p><strong>Order ID:</strong> {order.order_id}</p>
        <p><strong>Event:</strong> {order.event.title}</p>
        <p><strong>Date:</strong> {order.event.start_date.strftime("%B %d, %Y at %I:%M %p")}</p>
        <p><strong>Venue:</strong> {order.event.venue.name if order.event.venue else 'TBA'}</p>

        <h2>Payment Summary</h2>
        <p><strong>Total Amount:</strong> GHS {order.total_amount}</p>
        <p><strong>Service Fee:</strong> GHS {order.service_fee}</p>
        <p><strong>Grand Total:</strong> GHS {order.grand_total}</p>

        <h2>Your Tickets</h2>
        <p>You can view and download your tickets by visiting: <a href="{settings.FRONTEND_URL}/orders/{order.order_id}">{settings.FRONTEND_URL}/orders/{order.order_id}</a></p>

        <p>See you at the event!</p>
        <p>Best regards,<br>The {settings.SITE_NAME} Team</p>
    </body>
    </html>
    """

    text_content = f"""
    Order Confirmation

    Dear {order.buyer_name},

    Thank you for your order! Your tickets for {order.event.title} have been confirmed.

    Order Details:
    - Order ID: {order.order_id}
    - Event: {order.event.title}
    - Date: {order.event.start_date.strftime("%B %d, %Y at %I:%M %p")}
    - Venue: {order.event.venue.name if order.event.venue else 'TBA'}

    Payment Summary:
    - Total Amount: GHS {order.total_amount}
    - Service Fee: GHS {order.service_fee}
    - Grand Total: GHS {order.grand_total}

    You can view your tickets at: {settings.FRONTEND_URL}/orders/{order.order_id}

    See you at the event!

    Best regards,
    The {settings.SITE_NAME} Team
    """

    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Error sending order confirmation email: {e}")
        return False


def send_ticket_email(ticket):
    subject = f"Your Ticket for {ticket.event.title}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [ticket.attendee_email or ticket.order.buyer_email]

    context = {
        "ticket": ticket,
        "event": ticket.event,
        "frontend_url": settings.FRONTEND_URL,
    }

    html_content = f"""
    <html>
    <body>
        <h1>Your Event Ticket</h1>
        <p>Dear {ticket.attendee_name},</p>
        <p>Here is your ticket for <strong>{ticket.event.title}</strong>.</p>

        <h2>Ticket Details</h2>
        <p><strong>Ticket Number:</strong> {ticket.ticket_number}</p>
        <p><strong>Event:</strong> {ticket.event.title}</p>
        <p><strong>Type:</strong> {ticket.ticket_type.name if ticket.ticket_type else 'General'}</p>
        <p><strong>Date:</strong> {ticket.event.start_date.strftime("%B %d, %Y at %I:%M %p")}</p>
        <p><strong>Venue:</strong> {ticket.event.venue.name if ticket.event.venue else 'TBA'}</p>

        <p>You can view and download your ticket by visiting: <a href="{settings.FRONTEND_URL}/tickets/{ticket.ticket_number}">{settings.FRONTEND_URL}/tickets/{ticket.ticket_number}</a></p>

        <p>Please present this ticket (digital or printed) at the event entrance.</p>

        <p>See you at the event!</p>
        <p>Best regards,<br>The {settings.SITE_NAME} Team</p>
    </body>
    </html>
    """

    msg = EmailMultiAlternatives(subject, "", from_email, to_email)
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Error sending ticket email: {e}")
        return False


class PaymentGateway:
    @staticmethod
    def initialize_paystack_payment(payment):
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        data = {
            "email": payment.order.buyer_email,
            "amount": int(payment.amount * 100),
            "reference": payment.payment_id,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback",
            "metadata": {
                "order_id": payment.order.order_id,
                "event_name": payment.order.event.title,
            },
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            response_data = response.json()

            if response_data.get("status"):
                payment.gateway_reference = response_data["data"]["reference"]
                payment.gateway_response = response_data
                payment.save()

                return {
                    "success": True,
                    "authorization_url": response_data["data"]["authorization_url"],
                    "access_code": response_data["data"]["access_code"],
                    "reference": response_data["data"]["reference"],
                }
            else:
                return {
                    "success": False,
                    "message": response_data.get("message", "Payment initialization failed"),
                }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def verify_paystack_payment(reference):
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }

        try:
            response = requests.get(url, headers=headers)
            response_data = response.json()

            if response_data.get("status"):
                return {
                    "success": True,
                    "data": response_data["data"],
                }
            else:
                return {
                    "success": False,
                    "message": response_data.get("message", "Payment verification failed"),
                }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def initialize_stripe_payment(payment):
        return {"success": False, "message": "Stripe integration to be implemented"}

    @staticmethod
    def initialize_flutterwave_payment(payment):
        return {
            "success": False,
            "message": "Flutterwave integration to be implemented",
        }


def calculate_service_fee(amount, percentage=Decimal("0.025")):
    return amount * percentage


def calculate_total_with_fee(amount, percentage=Decimal("0.025")):
    service_fee = calculate_service_fee(amount, percentage)
    return amount + service_fee
