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
    """Generate QR code for new ticket model"""
    import json

    qr_data = json.dumps({
        'ticket_id': ticket.ticket_id,
        'event_id': ticket.event.id,
        'verification_hash': ticket.ticket_id
    })

    qr_code_file = generate_qr_code(qr_data, f"ticket_{ticket.ticket_id}.png")
    return qr_code_file


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
            "email": payment.purchase.buyer_email,
            "amount": int(payment.amount * 100),
            "reference": payment.payment_id,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback",
            "metadata": {
                "order_id": payment.purchase.order_id,
                "event_name": payment.purchase.event.title,
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

def send_purchase_ticket_email(purchase):
    """Send ticket confirmation email to buyer for new Purchase model"""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    
    # Get tickets
    tickets = purchase.tickets.all()
    
    # Email subject
    subject = f'🎫 Your Tickets for {purchase.event.title}'
    
    # Email body (plain text)
    text_content = f"""
Hi {purchase.buyer_name},

Thank you for purchasing tickets for {purchase.event.title}!

ORDER DETAILS:
- Order ID: {purchase.purchase_id}
- Event: {purchase.event.title}
- Date: {purchase.event.start_date.strftime("%B %d, %Y")} at {purchase.event.start_time.strftime("%I:%M %p")}
- Venue: {purchase.event.venue_name}, {purchase.event.venue_city}
- Tickets: {purchase.quantity}
- Total Paid: GHS {purchase.total}

YOUR TICKETS:
"""
    
    for i, ticket in enumerate(tickets, 1):
        text_content += f"\n{i}. Ticket ID: {ticket.ticket_id}"
        text_content += f"\n   Type: {ticket.ticket_type.name}"
        text_content += f"\n   Price: GHS {ticket.price}"
    
    text_content += f"""

IMPORTANT INFORMATION:
- Please bring your ticket (QR code or ticket number) to the event
- Check-in starts 30 minutes before the event
- Tickets are non-refundable
- Check-in policy: {purchase.event.get_check_in_policy_display()}

View your tickets with QR codes: {settings.FRONTEND_URL}/dashboard/tickets

See you at the event! 🎉

Best regards,
Cafa Tickets Team
{settings.FRONTEND_URL}
    """
    
    # HTML version (looks professional)
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; 
            line-height: 1.6; 
            color: #1e293b; 
            background-color: #f8fafc;
            margin: 0;
            padding: 0;
        }}
        .email-container {{ 
            max-width: 600px; 
            margin: 20px auto; 
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white; 
            padding: 40px 30px; 
            text-align: center; 
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 700;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 16px;
            opacity: 0.9;
        }}
        .content {{ 
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            margin-bottom: 20px;
            color: #1e293b;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: #6366f1;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .info-grid {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 20px;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e2e8f0;
        }}
        .info-row:last-child {{
            border-bottom: none;
        }}
        .info-label {{
            color: #64748b;
            font-size: 14px;
        }}
        .info-value {{
            color: #1e293b;
            font-weight: 600;
            text-align: right;
        }}
        .ticket-card {{ 
            background: white;
            border: 2px solid #e2e8f0;
            padding: 20px;
            margin: 12px 0;
            border-radius: 10px;
            border-left: 4px solid #6366f1;
        }}
        .ticket-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .ticket-number {{
            font-family: 'Courier New', monospace;
            font-size: 14px;
            color: #6366f1;
            font-weight: 700;
        }}
        .ticket-badge {{
            background: #6366f1;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .ticket-details {{
            font-size: 14px;
            color: #64748b;
        }}
        .ticket-details div {{
            margin: 8px 0;
        }}
        .button {{ 
            display: inline-block;
            background: #6366f1;
            color: white !important;
            padding: 16px 32px;
            text-decoration: none;
            border-radius: 8px;
            margin: 20px 0;
            font-weight: 700;
            font-size: 16px;
            text-align: center;
            width: 100%;
            box-sizing: border-box;
        }}
        .button:hover {{
            background: #4f46e5;
        }}
        .important-box {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .important-title {{
            font-weight: 700;
            color: #92400e;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        .important-list {{
            margin: 0;
            padding-left: 20px;
            color: #78350f;
        }}
        .important-list li {{
            margin: 8px 0;
        }}
        .footer {{ 
            text-align: center;
            padding: 30px;
            background: #f8fafc;
            color: #64748b;
            font-size: 13px;
            border-top: 1px solid #e2e8f0;
        }}
        .footer a {{
            color: #6366f1;
            text-decoration: none;
        }}
        .emoji {{
            font-size: 24px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="emoji">🎉</div>
            <h1>Your Tickets are Ready!</h1>
            <p>Order confirmed for {purchase.event.title}</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Hi <strong>{purchase.buyer_name}</strong>,
            </div>
            <p style="color: #64748b; margin-bottom: 30px;">
                Thank you for your purchase! Your tickets have been confirmed and are ready to use.
            </p>
            
            <div class="section">
                <div class="section-title">📋 Order Summary</div>
                <div class="info-grid">
                    <div class="info-row">
                        <span class="info-label">Order ID</span>
                        <span class="info-value">{purchase.purchase_id}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Event</span>
                        <span class="info-value">{purchase.event.title}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Date</span>
                        <span class="info-value">{purchase.event.start_date.strftime("%B %d, %Y")}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Time</span>
                        <span class="info-value">{purchase.event.start_time.strftime("%I:%M %p")}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Venue</span>
                        <span class="info-value">{purchase.event.venue_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Location</span>
                        <span class="info-value">{purchase.event.venue_city}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tickets</span>
                        <span class="info-value">{purchase.quantity} Ticket{"s" if purchase.quantity > 1 else ""}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Total Paid</span>
                        <span class="info-value" style="color: #6366f1; font-size: 18px;">GHS {purchase.total}</span>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">🎫 Your Tickets</div>
"""
    
    for i, ticket in enumerate(tickets, 1):
        html_content += f"""
                <div class="ticket-card">
                    <div class="ticket-header">
                        <span class="ticket-badge">Ticket {i}</span>
                        <span class="ticket-number">{ticket.ticket_id}</span>
                    </div>
                    <div class="ticket-details">
                        <div><strong>Type:</strong> {ticket.ticket_type.name}</div>
                        <div><strong>Price:</strong> GHS {ticket.price}</div>
                        <div><strong>Attendee:</strong> {ticket.attendee_name}</div>
                    </div>
                </div>
"""
    
    html_content += f"""
            </div>
            
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/dashboard/tickets" class="button">
                    View Tickets with QR Codes →
                </a>
            </div>
            
            <div class="important-box">
                <div class="important-title">⚠️ Important Information</div>
                <ul class="important-list">
                    <li>Please bring your ticket (QR code or ticket number) to the event</li>
                    <li>Check-in starts 30 minutes before the event</li>
                    <li>Tickets are non-refundable</li>
                    <li>Check-in policy: {purchase.event.get_check_in_policy_display()}</li>
                    <li>Each ticket admits one person</li>
                </ul>
            </div>
            
            <p style="text-align: center; color: #64748b; margin-top: 30px;">
                Need help? Contact us at <a href="mailto:support@cafaticket.com" style="color: #6366f1;">support@cafaticket.com</a>
            </p>
        </div>
        
        <div class="footer">
            <p style="margin: 0 0 10px 0; font-weight: 600;">See you at the event! 🎊</p>
            <p style="margin: 0;">
                <strong>Cafa Tickets</strong><br>
                <a href="{settings.FRONTEND_URL}">{settings.FRONTEND_URL}</a>
            </p>
            <p style="margin-top: 20px; font-size: 11px; color: #94a3b8;">
                This email was sent to {purchase.buyer_email} because you purchased tickets on Cafa Tickets.
            </p>
        </div>
    </div>
</body>
</html>
    """
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[purchase.buyer_email],
    )
    
    # Attach HTML version
    email.attach_alternative(html_content, "text/html")
    
    # Send
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Failed to send ticket email: {e}")
        return False