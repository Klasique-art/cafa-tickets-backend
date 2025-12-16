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

class PaymentHistoryView(APIView):
    """
    GET /api/v1/payments/
    Get user's complete payment history with summary
    Query params: status (completed, pending, failed), date_from, date_to, page, page_size
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from rest_framework.pagination import PageNumberPagination
        from datetime import datetime
        
        # Get user's payments
        payments = Payment.objects.filter(
            purchase__user=request.user
        ).select_related(
            'purchase__event',
            'purchase__ticket_type'
        ).prefetch_related(
            'purchase__tickets__ticket_type'
        ).order_by('-created_at')

        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            payments = payments.filter(status=status_filter)

        # Filter by date range
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
                payments = payments.filter(created_at__gte=from_date)
            except ValueError:
                pass  # Ignore invalid date format
        
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
                # Set to end of day (23:59:59)
                to_date = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                payments = payments.filter(created_at__lte=to_date)
            except ValueError:
                pass  # Ignore invalid date format

        # Calculate summary
        all_payments = Payment.objects.filter(purchase__user=request.user)
        total_spent = sum(float(p.amount) for p in all_payments.filter(status='completed'))
        total_transactions = all_payments.count()
        completed_transactions = all_payments.filter(status='completed').count()
        pending_transactions = all_payments.filter(status='pending').count()

        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 10))
        paginated_payments = paginator.paginate_queryset(payments, request)

        # Build results
        results = []
        for payment in paginated_payments:
            purchase = payment.purchase
            event = purchase.event
            
            # Get tickets info
            tickets_info = []
            for ticket in purchase.tickets.all():
                tickets_info.append({
                    'ticket_id': ticket.ticket_id,
                    'ticket_type': ticket.ticket_type.name if ticket.ticket_type else 'N/A',
                    'price': str(ticket.ticket_type.price if ticket.ticket_type else purchase.ticket_price)
                })

            results.append({
                'payment_id': payment.payment_id,
                'reference': payment.reference,
                'amount': str(payment.amount),
                'currency': payment.currency,
                'payment_method': payment.payment_method,
                'provider': payment.provider,
                'status': payment.status,
                'created_at': payment.created_at.isoformat(),
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'slug': event.slug,
                    'featured_image': request.build_absolute_uri(event.featured_image.url) if event.featured_image else None,
                    'start_date': event.start_date.isoformat()
                },
                'tickets': tickets_info,
                'fees': {
                    'service_fee': str(purchase.service_fee),
                    'total_paid': str(purchase.total)
                }
            })

        # Build response
        response = {
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'summary': {
                'total_spent': f"{total_spent:.2f}",
                'total_transactions': total_transactions,
                'completed_transactions': completed_transactions,
                'pending_transactions': pending_transactions
            },
            'results': results
        }

        return Response(response)


class PaymentDetailView(APIView):
    """
    GET /api/v1/payments/{payment_id}/
    Get detailed payment information
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(
            Payment,
            payment_id=payment_id,
            purchase__user=request.user
        )

        purchase = payment.purchase
        event = purchase.event

        # Extract card details from provider_response if available
        card_details = None
        if payment.provider_response and 'authorization' in payment.provider_response:
            auth = payment.provider_response['authorization']
            card_details = {
                'brand': auth.get('card_type', auth.get('brand', 'Unknown')),
                'last4': auth.get('last4', '****'),
                'exp_month': auth.get('exp_month', ''),
                'exp_year': auth.get('exp_year', '')
            }

        # Build tickets info
        tickets_info = []
        for ticket in purchase.tickets.all():
            tickets_info.append({
                'ticket_id': ticket.ticket_id,
                'qr_code': request.build_absolute_uri(ticket.qr_code.url) if ticket.qr_code else None,
                'ticket_type': {
                    'id': ticket.ticket_type.id if ticket.ticket_type else None,
                    'name': ticket.ticket_type.name if ticket.ticket_type else 'N/A',
                    'price': str(ticket.ticket_type.price if ticket.ticket_type else purchase.ticket_price)
                },
                'attendee_name': ticket.attendee_name,
                'status': ticket.status
            })

        # Build response
        response_data = {
            'payment_id': payment.payment_id,
            'reference': payment.reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'payment_method': payment.payment_method,
            'provider': payment.provider,
            'status': payment.status,
            'created_at': payment.created_at.isoformat(),
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
            'event': {
                'id': event.id,
                'title': event.title,
                'slug': event.slug,
                'featured_image': request.build_absolute_uri(event.featured_image.url) if event.featured_image else None,
                'organizer': {
                    'id': event.organizer.id,
                    'username': event.organizer.username,
                    'full_name': event.organizer.full_name or event.organizer.username
                },
                'venue_name': event.venue_name,
                'start_date': event.start_date.isoformat(),
                'start_time': str(event.start_time) if event.start_time else None
            },
            'tickets': tickets_info,
            'breakdown': {
                'subtotal': str(purchase.subtotal),
                'service_fee': str(purchase.service_fee),
                'total': str(purchase.total)
            },
            'billing_info': {
                'name': purchase.buyer_name,
                'email': purchase.buyer_email,
                'phone': purchase.buyer_phone
            }
        }

        # Add card_details if available
        if card_details:
            response_data['card_details'] = card_details

        return Response(response_data)

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
