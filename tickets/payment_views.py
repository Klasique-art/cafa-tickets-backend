"""
Payment views for Paystack integration
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import requests
import uuid

from .models import Purchase, Payment, Ticket, TicketType, Event
from .serializers import TicketSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Initiate payment with Paystack
    
    Request body:
    {
        "event_slug": "my-event",
        "ticket_type_id": 1,
        "quantity": 2,
        "buyer_name": "John Doe",
        "buyer_email": "john@example.com",
        "buyer_phone": "+233241234567"
    }
    """
    try:
        # Extract request data
        event_slug = request.data.get('event_slug')
        ticket_type_id = request.data.get('ticket_type_id')
        quantity = request.data.get('quantity', 1)
        buyer_name = request.data.get('buyer_name')
        buyer_email = request.data.get('buyer_email')
        buyer_phone = request.data.get('buyer_phone')
        
        # Validate required fields
        if not all([event_slug, ticket_type_id, buyer_name, buyer_email, buyer_phone]):
            return Response(
                {'error': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid quantity. Must be a positive integer.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get event and ticket type
        try:
            event = Event.objects.get(slug=event_slug, is_published=True)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            ticket_type = TicketType.objects.get(id=ticket_type_id, event=event)
        except TicketType.DoesNotExist:
            return Response(
                {'error': 'Ticket type not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if ticket type is available
        if not ticket_type.is_available:
            return Response(
                {'error': 'This ticket type is not available for sale'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check ticket availability
        available = ticket_type.tickets_remaining
        if available < quantity:
            return Response(
                {
                    'error': f'Only {available} ticket(s) available. You requested {quantity}.',
                    'available_quantity': available
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check min/max purchase limits
        if quantity < ticket_type.min_purchase:
            return Response(
                {
                    'error': f'Minimum purchase is {ticket_type.min_purchase} ticket(s)',
                    'min_quantity': ticket_type.min_purchase
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity > ticket_type.max_purchase:
            return Response(
                {
                    'error': f'Maximum purchase is {ticket_type.max_purchase} ticket(s)',
                    'max_quantity': ticket_type.max_purchase
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate pricing
        ticket_price = ticket_type.price
        subtotal = ticket_price * quantity
        service_fee = subtotal * Decimal('0.05')  # 5% service fee
        total = subtotal + service_fee
        
        # Create purchase record with transaction
        with transaction.atomic():
            # Reserve tickets by incrementing tickets_sold
            ticket_type.tickets_sold += quantity
            ticket_type.save()
            
            # Create purchase
            purchase = Purchase.objects.create(
                user=request.user,
                event=event,
                ticket_type=ticket_type,
                quantity=quantity,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                buyer_phone=buyer_phone,
                ticket_price=ticket_price,
                subtotal=subtotal,
                service_fee=service_fee,
                total=total,
                status='pending'
            )
            
            # Generate unique reference for Paystack
            payment_reference = f"CAFA-{purchase.purchase_id}-{uuid.uuid4().hex[:6].upper()}"
            
            # Initialize payment with Paystack
            paystack_response = initialize_paystack_payment(
                email=buyer_email,
                amount=total,
                reference=payment_reference,
                metadata={
                    'purchase_id': purchase.purchase_id,
                    'event_title': event.title,
                    'ticket_type': ticket_type.name,
                    'quantity': quantity,
                    'buyer_name': buyer_name,
                    'buyer_phone': buyer_phone
                }
            )
            
            if not paystack_response['success']:
                # Rollback ticket reservation
                ticket_type.tickets_sold -= quantity
                ticket_type.save()
                purchase.delete()
                
                return Response(
                    {
                        'error': 'Failed to initialize payment',
                        'details': paystack_response.get('message', 'Unknown error')
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create payment record
            payment = Payment.objects.create(
                purchase=purchase,
                amount=total,
                currency='GHS',
                provider='paystack',
                reference=payment_reference,
                payment_url=paystack_response['data']['authorization_url'],
                provider_response=paystack_response['data'],
                status='pending'
            )
        
        # Return payment details
        return Response({
            'success': True,
            'purchase_id': purchase.purchase_id,
            'payment_reference': payment_reference,
            'authorization_url': payment.payment_url,
            'amount': float(total),
            'currency': 'GHS',
            'expires_at': purchase.reservation_expires_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_payment(request, reference):
    """
    Verify payment with Paystack
    
    URL: /payments/verify/{reference}/
    """
    import traceback
    
    try:
        print(f"\n{'='*50}")
        print(f"VERIFY PAYMENT - Reference: {reference}")
        print(f"{'='*50}\n")
        
        # Get payment record
        try:
            payment = Payment.objects.select_related(
                'purchase',
                'purchase__event',
                'purchase__ticket_type',
                'purchase__user'
            ).get(reference=reference)
            print(f"✅ Payment found: {payment.payment_id}")
        except Payment.DoesNotExist:
            print(f"❌ Payment not found for reference: {reference}")
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # If already completed, return success
        if payment.status == 'completed':
            print("⚠️ Payment already completed, returning existing tickets")
            try:
                tickets = Ticket.objects.filter(purchase=payment.purchase)
                print(f"Found {tickets.count()} tickets")
                
                print("Serializing tickets...")
                serializer = TicketSerializer(tickets, many=True, context={'request': request})
                print("✅ Tickets serialized successfully")
                
                return Response({
                    'success': True,
                    'status': 'completed',
                    'message': 'Payment already verified',
                    'purchase_id': payment.purchase.purchase_id,
                    'amount': float(payment.amount),
                    'tickets': serializer.data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                print(f"❌ ERROR serializing tickets: {str(e)}")
                print(traceback.format_exc())
                raise
        
        # Verify with Paystack
        print("🔍 Verifying with Paystack API...")
        verification_result = verify_paystack_payment(reference)
        
        if not verification_result['success']:
            print(f"❌ Paystack verification failed: {verification_result.get('message')}")
            # Update payment as failed
            payment.status = 'failed'
            payment.failure_reason = verification_result.get('message', 'Verification failed')
            payment.failed_at = timezone.now()
            payment.save()
            
            # Update purchase status
            payment.purchase.status = 'failed'
            payment.purchase.save()
            
            # Release reserved tickets
            ticket_type = payment.purchase.ticket_type
            ticket_type.tickets_sold -= payment.purchase.quantity
            ticket_type.save()
            
            return Response({
                'success': False,
                'status': 'failed',
                'message': verification_result.get('message', 'Payment verification failed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if payment was successful
        paystack_data = verification_result['data']
        print(f"Paystack status: {paystack_data.get('status')}")
        
        if paystack_data['status'] != 'success':
            print(f"⚠️ Payment not successful: {paystack_data['status']}")
            payment.status = 'failed'
            payment.failure_reason = f"Payment status: {paystack_data['status']}"
            payment.failed_at = timezone.now()
            payment.provider_response = paystack_data
            payment.save()
            
            payment.purchase.status = 'failed'
            payment.purchase.save()
            
            # Release reserved tickets
            ticket_type = payment.purchase.ticket_type
            ticket_type.tickets_sold -= payment.purchase.quantity
            ticket_type.save()
            
            return Response({
                'success': False,
                'status': 'failed',
                'message': 'Payment was not successful'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Payment successful - complete the purchase
        print("✅ Payment successful, creating tickets...")
        with transaction.atomic():
            # Update payment record
            payment.status = 'completed'
            payment.completed_at = timezone.now()
            payment.provider_response = paystack_data
            payment.payment_method = paystack_data.get('channel', 'card')
            payment.save()
            print("✅ Payment record updated")
            
            # Update purchase record
            purchase = payment.purchase
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.save()
            print("✅ Purchase record updated")
            
            # Generate tickets with QR codes
            tickets = []
            print(f"Generating {purchase.quantity} tickets...")
            for i in range(purchase.quantity):
                print(f"  Creating ticket {i+1}/{purchase.quantity}...")
                ticket = Ticket.objects.create(
                    purchase=purchase,
                    event=purchase.event,
                    ticket_type=purchase.ticket_type,
                    attendee_name=purchase.buyer_name,
                    attendee_email=purchase.buyer_email,
                    attendee_phone=purchase.buyer_phone,
                    price=purchase.ticket_price,
                    status='paid'
                )
                print(f"  ✅ Ticket created: {ticket.ticket_id}")
                
                # Generate QR code
                print(f"  Generating QR code...")
                ticket.generate_qr_code()
                print(f"  ✅ QR code generated")
                tickets.append(ticket)
            
            print(f"✅ All {len(tickets)} tickets created successfully")
            
            # Create revenue record for organizer
            print("Creating revenue record...")
            from decimal import Decimal
            platform_commission_rate = Decimal('0.05')  # 5%
            platform_fee = purchase.subtotal * platform_commission_rate
            organizer_earnings = purchase.subtotal - platform_fee
            
            from .models import OrganizerRevenue
            OrganizerRevenue.objects.create(
                organizer=purchase.event.organizer,
                event=purchase.event,
                purchase=purchase,
                ticket_sales_amount=purchase.subtotal,
                platform_fee=platform_fee,
                organizer_earnings=organizer_earnings,
                status='pending'  # Will become 'available' after 7 days
            )
            print("✅ Revenue record created")
            
            # Send ticket confirmation email
            print("Sending confirmation email...")
            try:
                from .utils import send_purchase_ticket_email
                send_purchase_ticket_email(purchase)
                print("✅ Email sent successfully")
            except Exception as e:
                print(f"⚠️ Failed to send email: {str(e)}")
                # Don't fail the whole transaction if email fails
        
        # Serialize tickets
        print("Serializing tickets for response...")
        try:
            serializer = TicketSerializer(tickets, many=True, context={'request': request})
            tickets_data = serializer.data
            print("✅ Tickets serialized successfully")
        except Exception as e:
            print(f"❌ ERROR serializing tickets: {str(e)}")
            print(traceback.format_exc())
            raise
        
        # Return success response
        print("✅ Returning success response")
        print(f"{'='*50}\n")
        return Response({
            'success': True,
            'status': 'completed',
            'message': 'Payment verified successfully',
            'purchase_id': purchase.purchase_id,
            'amount': float(payment.amount),
            'tickets': tickets_data,
            'ticket_count': len(tickets)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"\n{'!'*50}")
        print(f"❌❌❌ CRITICAL ERROR ❌❌❌")
        print(f"Error: {str(e)}")
        print(f"{'!'*50}")
        print(traceback.format_exc())
        print(f"{'!'*50}\n")
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

def initialize_paystack_payment(email, amount, reference, metadata=None):
    """
    Initialize payment with Paystack
    
    Args:
        email: Customer email
        amount: Amount in GHS
        reference: Unique payment reference
        metadata: Additional data (dict)
    
    Returns:
        dict: Response from Paystack
    """
    # Convert amount to kobo (Paystack uses smallest currency unit)
    # For GHS: 1 GHS = 100 pesewas
    amount_in_pesewas = int(amount * 100)
    
    url = "https://api.paystack.co/transaction/initialize"
    
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "email": email,
        "amount": amount_in_pesewas,
        "reference": reference,
        "currency": "GHS",
        "callback_url": "http://localhost:3000/payment-results",
        "metadata": metadata or {}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status'):
            return {
                'success': True,
                'data': response_data['data']
            }
        else:
            return {
                'success': False,
                'message': response_data.get('message', 'Unknown error'),
                'data': response_data
            }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'message': f'Network error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }


def verify_paystack_payment(reference):
    """
    Verify payment with Paystack
    
    Args:
        reference: Payment reference to verify
    
    Returns:
        dict: Verification result
    """
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status'):
            return {
                'success': True,
                'data': response_data['data']
            }
        else:
            return {
                'success': False,
                'message': response_data.get('message', 'Verification failed'),
                'data': response_data
            }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'message': f'Network error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }