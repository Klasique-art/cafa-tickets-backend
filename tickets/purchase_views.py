"""
Purchase and Payment Views
Handles ticket purchase flow with Paystack integration
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import requests
import hmac
import hashlib

from .models import Purchase, Payment, Ticket, Event, TicketType
from .purchase_serializers import (
    PurchaseInitiateSerializer,
    PaymentStatusSerializer,
)


class InitiatePurchaseView(APIView):
    """
    POST /api/v1/tickets/purchase/
    Initiate ticket purchase and create payment
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Validate request
        serializer = PurchaseInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        event = validated_data['event']
        ticket_type = validated_data['ticket_type']
        quantity = validated_data['quantity']
        attendee_info = validated_data['attendee_info']
        payment_method = validated_data['payment_method']

        # Calculate pricing
        ticket_price = ticket_type.price
        subtotal = ticket_price * quantity
        service_fee = subtotal * Decimal('0.05')  # 5% service fee
        total = subtotal + service_fee

        # Create purchase
        purchase = Purchase.objects.create(
            user=request.user,
            event=event,
            ticket_type=ticket_type,
            quantity=quantity,
            buyer_name=attendee_info['name'],
            buyer_email=attendee_info['email'],
            buyer_phone=attendee_info['phone'],
            ticket_price=ticket_price,
            subtotal=subtotal,
            service_fee=service_fee,
            total=total,
            status='reserved'
        )

        # Create tickets in reserved state
        tickets = []
        for i in range(quantity):
            ticket = Ticket.objects.create(
                purchase=purchase,
                event=event,
                ticket_type=ticket_type,
                attendee_name=attendee_info['name'],
                attendee_email=attendee_info['email'],
                attendee_phone=attendee_info['phone'],
                status='reserved'
            )
            tickets.append(ticket)

        # Initialize Paystack payment
        paystack_response = self._initialize_paystack_payment(
            purchase, payment_method, request.user.email
        )

        if not paystack_response['success']:
            # Rollback purchase
            purchase.status = 'failed'
            purchase.save()
            for ticket in tickets:
                ticket.status = 'expired'
                ticket.save()

            return Response({
                'error': 'Payment initialization failed',
                'message': paystack_response['message']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Create payment record
        payment = Payment.objects.create(
            purchase=purchase,
            amount=total,
            currency='GHS',
            payment_method=payment_method,
            provider='paystack',
            reference=paystack_response['reference'],
            payment_url=paystack_response['authorization_url'],
            status='pending'
        )

        # Update purchase status
        purchase.status = 'pending'
        purchase.save()

        # Prepare response
        response_data = {
            'message': 'Tickets reserved. Please complete payment within 10 minutes.',
            'purchase_id': purchase.purchase_id,
            'tickets': [
                {
                    'ticket_id': ticket.ticket_id,
                    'event_title': event.title,
                    'event_slug': event.slug,
                    'ticket_type_name': ticket_type.name,
                    'attendee_name': attendee_info['name'],
                    'attendee_email': attendee_info['email'],
                    'attendee_phone': attendee_info['phone'],
                    'status': 'reserved'
                }
                for ticket in tickets
            ],
            'pricing': {
                'ticket_price': str(ticket_price),
                'quantity': quantity,
                'subtotal': str(subtotal),
                'service_fee': str(service_fee),
                'service_fee_percentage': 5.0,
                'total': str(total),
                'currency': 'GHS'
            },
            'payment': {
                'payment_id': payment.payment_id,
                'amount': str(total),
                'currency': 'GHS',
                'payment_method': payment_method,
                'provider': 'paystack',
                'payment_url': payment.payment_url,
                'reference': payment.reference,
                'expires_at': purchase.reservation_expires_at
            },
            'reservation': {
                'reserved_at': purchase.reserved_at,
                'expires_at': purchase.reservation_expires_at,
                'expires_in_seconds': int((purchase.reservation_expires_at - timezone.now()).total_seconds())
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    def _initialize_paystack_payment(self, purchase, payment_method, email):
        """Initialize payment with Paystack"""
        try:
            paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
            if not paystack_secret:
                return {
                    'success': False,
                    'message': 'Paystack not configured'
                }

            url = 'https://api.paystack.co/transaction/initialize'
            headers = {
                'Authorization': f'Bearer {paystack_secret}',
                'Content-Type': 'application/json'
            }

            # Convert to kobo (GHS to pesewas)
            amount_in_pesewas = int(purchase.total * 100)

            data = {
                'email': email,
                'amount': amount_in_pesewas,
                'currency': 'GHS',
                'reference': f'PUR-{purchase.purchase_id}',
                'callback_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:3000') + '/payment/callback',
                'metadata': {
                    'purchase_id': purchase.purchase_id,
                    'payment_method': payment_method,
                    'event_id': purchase.event.id,
                    'ticket_type_id': purchase.ticket_type.id,
                    'quantity': purchase.quantity
                }
            }

            response = requests.post(url, json=data, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status'):
                return {
                    'success': True,
                    'authorization_url': response_data['data']['authorization_url'],
                    'access_code': response_data['data']['access_code'],
                    'reference': response_data['data']['reference']
                }
            else:
                return {
                    'success': False,
                    'message': response_data.get('message', 'Payment initialization failed')
                }

        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }


class PaymentWebhookView(APIView):
    """
    POST /api/v1/payments/webhook/
    Paystack webhook endpoint
    """
    permission_classes = []  # Public endpoint, validated by signature

    def post(self, request):
        # Verify Paystack signature
        paystack_signature = request.headers.get('X-Paystack-Signature')
        if not self._verify_signature(request.body, paystack_signature):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

        # Get event data
        event_data = request.data
        event_type = event_data.get('event')

        if event_type == 'charge.success':
            return self._handle_successful_payment(event_data['data'])

        return Response({'message': 'Webhook received'})

    def _verify_signature(self, payload, signature):
        """Verify Paystack webhook signature"""
        paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        computed_signature = hmac.new(
            paystack_secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        return computed_signature == signature

    def _handle_successful_payment(self, payment_data):
        """Handle successful payment"""
        reference = payment_data.get('reference')
        metadata = payment_data.get('metadata', {})
        purchase_id = metadata.get('purchase_id')

        if not purchase_id:
            return Response({'error': 'Invalid metadata'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get purchase and payment
            purchase = Purchase.objects.get(purchase_id=purchase_id)
            payment = Payment.objects.get(purchase=purchase)

            # Update payment status
            payment.status = 'completed'
            payment.completed_at = timezone.now()
            payment.provider_response = payment_data
            payment.save()

            # Update purchase status
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.save()

            # Update tickets to paid and generate QR codes
            from .utils import generate_ticket_qr_code
            for ticket in purchase.tickets.all():
                ticket.status = 'paid'
                qr_code_file = generate_ticket_qr_code(ticket)
                ticket.qr_code.save(qr_code_file.name, qr_code_file, save=False)
                ticket.save()

            # Update ticket type sold count
            purchase.ticket_type.tickets_sold += purchase.quantity
            purchase.ticket_type.save()

            # TODO: Send confirmation email with tickets

            return Response({'message': 'Webhook processed successfully'})

        except Purchase.DoesNotExist:
            return Response({'error': 'Purchase not found'}, status=status.HTTP_404_NOT_FOUND)


class PaymentStatusView(APIView):
    """
    GET /api/v1/payments/{payment_id}/status/
    Check payment status
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(
            Payment,
            payment_id=payment_id,
            purchase__user=request.user
        )

        if payment.status == 'completed':
            # Return full details with tickets
            response_data = {
                'payment_id': payment.payment_id,
                'purchase_id': payment.purchase.purchase_id,
                'status': 'completed',
                'amount': str(payment.amount),
                'currency': payment.currency,
                'payment_method': payment.payment_method,
                'provider': payment.provider,
                'reference': payment.reference,
                'created_at': payment.created_at,
                'completed_at': payment.completed_at,
                'event': {
                    'id': payment.purchase.event.id,
                    'title': payment.purchase.event.title,
                    'slug': payment.purchase.event.slug,
                    'start_date': payment.purchase.event.start_date,
                    'venue_name': payment.purchase.event.venue_name
                },
                'tickets': [
                    {
                        'ticket_id': ticket.ticket_id,
                        'ticket_type': ticket.ticket_type.name,
                        'attendee_name': ticket.attendee_name,
                        'attendee_email': ticket.attendee_email,
                        'status': ticket.status,
                        'qr_code_url': request.build_absolute_uri(ticket.qr_code.url) if ticket.qr_code else None,
                        'download_url': f'/api/v1/tickets/{ticket.ticket_id}/download/'
                    }
                    for ticket in payment.purchase.tickets.all()
                ],
                'receipt': {
                    'subtotal': str(payment.purchase.subtotal),
                    'service_fee': str(payment.purchase.service_fee),
                    'total': str(payment.purchase.total),
                    'payment_method': payment.payment_method
                }
            }
        elif payment.status == 'pending':
            response_data = {
                'payment_id': payment.payment_id,
                'status': 'pending',
                'amount': str(payment.amount),
                'currency': payment.currency,
                'provider': payment.provider,
                'reference': payment.reference,
                'created_at': payment.created_at,
                'message': 'Payment is being processed. This usually takes a few seconds.'
            }
        else:  # failed
            response_data = {
                'payment_id': payment.payment_id,
                'status': 'failed',
                'amount': str(payment.amount),
                'currency': payment.currency,
                'provider': payment.provider,
                'reference': payment.reference,
                'created_at': payment.created_at,
                'failed_at': payment.failed_at,
                'failure_reason': payment.failure_reason or 'Payment failed',
                'message': 'Payment failed. Your tickets have been released.'
            }

        return Response(response_data)


class CancelPurchaseView(APIView):
    """
    POST /api/v1/tickets/purchase/{purchase_id}/cancel/
    Cancel a pending purchase
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, purchase_id):
        purchase = get_object_or_404(
            Purchase,
            purchase_id=purchase_id,
            user=request.user
        )

        # Check if purchase can be cancelled
        if purchase.status not in ['reserved', 'pending']:
            return Response({
                'error': 'Cannot cancel purchase',
                'message': 'This purchase has already been completed or expired.',
                'status': purchase.status
            }, status=status.HTTP_400_BAD_REQUEST)

        # Cancel purchase
        purchase.status = 'expired'
        purchase.save()

        # Update tickets to expired
        tickets_released = 0
        for ticket in purchase.tickets.all():
            if ticket.status in ['reserved', 'pending']:
                ticket.status = 'expired'
                ticket.save()
                tickets_released += 1

        # Release ticket type count
        if tickets_released > 0:
            purchase.ticket_type.tickets_sold = max(0, purchase.ticket_type.tickets_sold - tickets_released)
            purchase.ticket_type.save()

        return Response({
            'message': 'Purchase cancelled successfully. Tickets have been released.',
            'purchase_id': purchase.purchase_id,
            'tickets_released': tickets_released
        })


class ResendTicketsView(APIView):
    """
    POST /api/v1/payments/{payment_id}/resend-tickets/
    Resend ticket email
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, payment_id):
        payment = get_object_or_404(
            Payment,
            payment_id=payment_id,
            purchase__user=request.user
        )

        # Check if payment is completed
        if payment.status != 'completed':
            return Response({
                'error': 'Payment not completed',
                'message': 'Tickets can only be resent for completed payments.',
                'payment_status': payment.status
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get tickets
        tickets = payment.purchase.tickets.filter(status='paid')
        if not tickets.exists():
            return Response({
                'error': 'No tickets found',
                'message': 'No valid tickets found for this payment.'
            }, status=status.HTTP_404_NOT_FOUND)

        # TODO: Send email with tickets
        # from .utils import send_ticket_email
        # send_ticket_email(payment.purchase.buyer_email, tickets)

        return Response({
            'message': f'Tickets have been resent to {payment.purchase.buyer_email}',
            'email': payment.purchase.buyer_email,
            'tickets_count': tickets.count()
        })
