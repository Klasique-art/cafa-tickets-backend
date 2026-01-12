"""
Payment Profile Views
Handles payment profile CRUD operations and verification
"""
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta

from .models import PaymentProfile
from .payment_serializers import (
    PaymentProfileSerializer,
    PaymentProfileCreateSerializer,
    PaymentProfileUpdateSerializer,
    VerificationStatusSerializer,
    RetryVerificationSerializer,
)

from decimal import Decimal
from django.db.models import Sum
from tickets.models import OrganizerRevenue, WithdrawalRequest
from .paystack_service import PaystackTransferService

class PaymentProfileListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/users/payment-profile/
    POST /api/v1/users/payment-profile/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentProfileCreateSerializer
        return PaymentProfileSerializer

    def get_queryset(self):
        return PaymentProfile.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        """List all payment profiles for the user"""
        queryset = self.get_queryset()
        serializer = PaymentProfileSerializer(queryset, many=True)

        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })

    def create(self, request, *args, **kwargs):
        """Create a new payment profile"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_profile = serializer.save()

        # 🔥 AUTOMATICALLY VERIFY BANK ACCOUNT WITH RETRY LOGIC
        max_retries = 5
        retry_count = 0
        verification_result = None
        
        while retry_count < max_retries:
            verification_result = PaystackTransferService.verify_bank_account(
                payment_profile, 
                is_retry=(retry_count > 0)
            )
            
            if verification_result['success']:
                # Verification successful
                break
            
            if not verification_result.get('should_retry', False):
                # No more retries needed (either succeeded or max attempts reached)
                break
            
            retry_count += 1
            
            # Optional: Add a small delay between retries (0.5 seconds)
            import time
            time.sleep(0.5)

        # Return response with verification info
        response_serializer = PaymentProfileSerializer(payment_profile)

        if verification_result and verification_result['success']:
            return Response({
                'success': True,
                'message': 'Payment profile created and verified successfully.',
                'data': {
                    'payment_profile': response_serializer.data,
                    'verification': {
                        'status': 'verified',
                        'attempts': payment_profile.verification_attempts,
                        'resolved_name': verification_result.get('resolved_name')
                    }
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': f'Payment profile created but verification failed after {payment_profile.verification_attempts} attempts.',
                'data': {
                    'payment_profile': response_serializer.data,
                    'verification': {
                        'status': payment_profile.status,
                        'attempts': payment_profile.verification_attempts,
                        'failure_reason': payment_profile.failure_reason
                    }
                }
            }, status=status.HTTP_201_CREATED)


class PaymentProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/v1/users/payment-profile/{id}/
    PATCH /api/v1/users/payment-profile/{id}/
    DELETE /api/v1/users/payment-profile/{id}/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return PaymentProfileUpdateSerializer
        return PaymentProfileSerializer

    def get_queryset(self):
        return PaymentProfile.objects.filter(user=self.request.user)

    def get_object(self):
        """Get payment profile by ID"""
        profile_id = self.kwargs.get('pk')
        return get_object_or_404(
            PaymentProfile,
            id=profile_id,
            user=self.request.user
        )

    def update(self, request, *args, **kwargs):
        """Update payment profile"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payment_profile = serializer.save()

        response_serializer = PaymentProfileSerializer(payment_profile)

        return Response({
            'message': 'Payment profile updated successfully',
            'payment_profile': response_serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """Delete payment profile"""
        instance = self.get_object()

        # Check if profile is default
        if instance.is_default:
            return Response({
                'error': 'Cannot delete default profile',
                'message': 'Cannot delete your default payment profile. Please set another profile as default first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if profile is used by active events
        active_events = instance.events.filter(
            is_published=True,
            start_date__gte=timezone.now().date()
        )

        if active_events.exists():
            return Response({
                'error': 'Cannot delete payment profile',
                'message': f'This payment profile is currently used by {active_events.count()} active events. Please update those events first.',
                'active_events': [
                    {'id': event.id, 'title': event.title}
                    for event in active_events
                ]
            }, status=status.HTTP_400_BAD_REQUEST)

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SetDefaultPaymentProfileView(APIView):
    """
    POST /api/v1/users/payment-profile/{id}/set-default/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """Set payment profile as default"""
        payment_profile = get_object_or_404(
            PaymentProfile,
            id=pk,
            user=request.user
        )

        # Set as default
        payment_profile.is_default = True
        payment_profile.save()

        return Response({
            'message': 'Default payment profile updated successfully',
            'payment_profile': {
                'id': str(payment_profile.id),
                'name': payment_profile.name,
                'is_default': payment_profile.is_default
            }
        })


class VerificationStatusView(APIView):
    """
    GET /api/v1/users/payment-profile/{id}/verification-status/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        """Check verification status of payment profile"""
        payment_profile = get_object_or_404(
            PaymentProfile,
            id=pk,
            user=request.user
        )

        # Prepare response based on status
        if payment_profile.status == 'verified':
            response_data = {
                'status': 'verified',
                'is_verified': True,
                'verified_at': payment_profile.verified_at,
                'message': 'Payment profile verified successfully'
            }
        elif payment_profile.status == 'pending_verification':
            response_data = {
                'status': 'pending_verification',
                'is_verified': False,
                'message': 'Verification in progress. This usually takes 1-2 minutes.',
                'verification_initiated_at': payment_profile.verification_initiated_at
            }
        else:  # verification_failed
            response_data = {
                'status': 'verification_failed',
                'is_verified': False,
                'message': 'Verification failed. Please check your account details and try again.',
                'failure_reason': payment_profile.failure_reason or 'Unknown error',
                'can_retry': True
            }

        serializer = VerificationStatusSerializer(response_data)
        return Response(serializer.data)


class RetryVerificationView(APIView):
    """
    POST /api/v1/users/payment-profile/{id}/retry-verification/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """Retry verification for a failed payment profile"""
        payment_profile = get_object_or_404(
            PaymentProfile,
            id=pk,
            user=request.user
        )

        # Validate request
        serializer = RetryVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if already verified
        if payment_profile.status == 'verified':
            return Response({
                'error': 'Already verified',
                'message': 'This payment profile has already been verified.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if verification is in progress
        if payment_profile.status == 'pending_verification':
            return Response({
                'error': 'Verification in progress',
                'message': 'Please wait for the current verification attempt to complete before retrying.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check rate limiting (max 3 attempts per hour)
        if payment_profile.last_verification_attempt:
            time_since_last_attempt = timezone.now() - payment_profile.last_verification_attempt
            if time_since_last_attempt < timedelta(hours=1):
                attempts_in_last_hour = payment_profile.verification_attempts
                if attempts_in_last_hour >= 3:
                    retry_after = int((timedelta(hours=1) - time_since_last_attempt).total_seconds())
                    return Response({
                        'error': 'Rate limit exceeded',
                        'message': 'Too many verification attempts. Please try again in 1 hour.',
                        'retry_after': retry_after
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Reset verification status
        payment_profile.status = 'pending_verification'
        payment_profile.verification_initiated_at = timezone.now()
        payment_profile.last_verification_attempt = timezone.now()
        payment_profile.verification_attempts += 1
        payment_profile.failure_reason = ''
        payment_profile.save()

        # TODO: Integrate with Paystack to deduct 1 GHS for verification

        response_serializer = PaymentProfileSerializer(payment_profile)

        return Response({
            'message': 'Verification retry initiated. Another 1 GHS will be deducted from your account.',
            'payment_profile': response_serializer.data
        })

class CreateWithdrawalRequestView(APIView):
    """
    POST /api/v1/users/withdrawal/request/
    Create a new withdrawal request and automatically initiate transfer
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        requested_amount = request.data.get('amount')
        payment_profile_id = request.data.get('payment_profile_id')
        
        # Validate amount
        try:
            requested_amount = Decimal(str(requested_amount))
            if requested_amount <= 0:
                raise ValueError()
        except (ValueError, TypeError, decimal.InvalidOperation):
            return Response({
                'success': False,
                'message': 'Please enter a valid withdrawal amount'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Minimum withdrawal amount
        if requested_amount < Decimal('10.00'):
            return Response({
                'success': False,
                'message': 'Minimum withdrawal amount is GHS 10.00'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check available balance
        available_balance = OrganizerRevenue.objects.filter(
            organizer=user,
            status='available',
            is_withdrawn=False
        ).aggregate(total=Sum('organizer_earnings'))['total'] or Decimal('0')
        
        if requested_amount > available_balance:
            return Response({
                'success': False,
                'message': f'Insufficient balance. Available: GHS {available_balance}',
                'data': {
                    'requested_amount': str(requested_amount),
                    'available_balance': str(available_balance)
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for pending withdrawals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            organizer=user,
            status__in=['pending', 'processing']  # ← Remove 'approved'
        )
        
        if pending_withdrawals.exists():
            pending = pending_withdrawals.first()
            return Response({
                'success': False,
                'message': 'You already have a pending withdrawal request',
                'data': {
                    'pending_withdrawal_id': pending.withdrawal_id,
                    'pending_amount': str(pending.requested_amount),
                    'status': pending.status
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment profile
        if not payment_profile_id:
            # Try to get default payment profile
            payment_profile = PaymentProfile.objects.filter(
                user=user,
                is_default=True
            ).first()
            
            if not payment_profile:
                return Response({
                    'success': False,
                    'message': 'No payment profile found. Please add a bank account first.'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            payment_profile = get_object_or_404(
                PaymentProfile,
                id=payment_profile_id,
                user=user
            )
        
        # Check if payment profile is verified
        if payment_profile.status != 'verified':
            return Response({
                'success': False,
                'message': 'Payment profile must be verified before withdrawal',
                'data': {
                    'payment_profile_status': payment_profile.status,
                    'payment_profile_id': str(payment_profile.id)
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate transfer fee (Paystack Ghana charges)
        # Free for transfers below GHS 5,000
        # GHS 10 flat fee for transfers GHS 5,000 and above
        if requested_amount >= Decimal('5000.00'):
            transfer_fee = Decimal('10.00')
        else:
            transfer_fee = Decimal('0.00')
        
        final_amount = requested_amount - transfer_fee
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest.objects.create(
            organizer=user,
            payment_profile=payment_profile,
            requested_amount=requested_amount,
            transfer_fee=transfer_fee,
            final_amount=final_amount,
            status='pending'
        )
        
        # Reserve revenue for this withdrawal
        self._reserve_revenue(withdrawal, requested_amount)
        
        # 🔥 AUTOMATICALLY INITIATE TRANSFER
        transfer_result = PaystackTransferService.initiate_transfer(withdrawal)
        
        if transfer_result['success']:
            return Response({
                'success': True,
                'message': 'Withdrawal initiated successfully. Money will be sent to your bank account within 1-2 minutes.',
                'data': {
                    'withdrawal_id': withdrawal.withdrawal_id,
                    'requested_amount': str(requested_amount),
                    'transfer_fee': str(transfer_fee),
                    'final_amount': str(final_amount),
                    'status': withdrawal.status,
                    'transfer_code': transfer_result['transfer_code'],
                    'bank_account': {
                        'bank_name': payment_profile.bank_name,
                        'account_number': payment_profile.account_number,
                        'account_name': payment_profile.account_name
                    }
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': f'Failed to initiate transfer: {transfer_result["message"]}',
                'data': {
                    'withdrawal_id': withdrawal.withdrawal_id,
                    'status': withdrawal.status,
                    'error': transfer_result['message']
                }
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _reserve_revenue(self, withdrawal, amount):
        """Reserve available revenue for this withdrawal"""
        # Get available revenue items
        available_revenue = OrganizerRevenue.objects.filter(
            organizer=withdrawal.organizer,
            status='available',
            is_withdrawn=False,
            withdrawal__isnull=True
        ).order_by('created_at')
        
        # Reserve revenue items until we reach the requested amount
        amount_reserved = Decimal('0.00')
        for revenue_item in available_revenue:
            if amount_reserved >= amount:
                break
            
            revenue_item.withdrawal = withdrawal
            revenue_item.status = 'on_hold'
            revenue_item.save()
            
            amount_reserved += revenue_item.organizer_earnings


class WithdrawalHistoryView(APIView):
    """
    GET /api/v1/users/withdrawal/history/
    Get withdrawal history for the organizer
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        withdrawals = WithdrawalRequest.objects.filter(
            organizer=user
        ).select_related('payment_profile').order_by('-created_at')
        
        withdrawal_list = []
        for withdrawal in withdrawals:
            withdrawal_list.append({
                'withdrawal_id': withdrawal.withdrawal_id,
                'requested_amount': str(withdrawal.requested_amount),
                'transfer_fee': str(withdrawal.transfer_fee),
                'final_amount': str(withdrawal.final_amount),
                'status': withdrawal.status,
                'bank_account': {
                    'bank_name': withdrawal.payment_profile.bank_name,
                    'account_number': withdrawal.payment_profile.account_number,
                    'account_name': withdrawal.payment_profile.account_name
                },
                'created_at': withdrawal.created_at,
                'completed_at': withdrawal.completed_at,
                'rejection_reason': withdrawal.rejection_reason or None
            })
        
        return Response({
            'success': True,
            'count': len(withdrawal_list),
            'data': withdrawal_list
        })


class WithdrawalDetailView(APIView):
    """
    GET /api/v1/users/withdrawal/{withdrawal_id}/
    Get withdrawal details
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, withdrawal_id):
        user = request.user
        
        withdrawal = get_object_or_404(
            WithdrawalRequest,
            withdrawal_id=withdrawal_id,
            organizer=user
        )
        
        return Response({
            'success': True,
            'data': {
                'withdrawal_id': withdrawal.withdrawal_id,
                'requested_amount': str(withdrawal.requested_amount),
                'transfer_fee': str(withdrawal.transfer_fee),
                'final_amount': str(withdrawal.final_amount),
                'status': withdrawal.status,
                'bank_account': {
                    'bank_name': withdrawal.payment_profile.bank_name,
                    'account_number': withdrawal.payment_profile.account_number,
                    'account_name': withdrawal.payment_profile.account_name
                },
                'transfer_code': withdrawal.transfer_code or None,
                'transfer_reference': withdrawal.transfer_reference or None,
                'created_at': withdrawal.created_at,
                'completed_at': withdrawal.completed_at,
                'rejection_reason': withdrawal.rejection_reason or None,
                'admin_notes': withdrawal.admin_notes or None
            }
        })


class CancelWithdrawalView(APIView):
    """
    POST /api/v1/users/withdrawal/{withdrawal_id}/cancel/
    Cancel a pending withdrawal request
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, withdrawal_id):
        user = request.user
        
        withdrawal = get_object_or_404(
            WithdrawalRequest,
            withdrawal_id=withdrawal_id,
            organizer=user
        )
        
        # Can only cancel if pending
        if withdrawal.status != 'pending':
            return Response({
                'success': False,
                'message': f'Cannot cancel withdrawal with status: {withdrawal.status}',
                'data': {
                    'current_status': withdrawal.status,
                    'cancellable_statuses': ['pending']
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Release reserved revenue
        OrganizerRevenue.objects.filter(withdrawal=withdrawal).update(
            withdrawal=None,
            status='available'
        )
        
        # Delete withdrawal request
        withdrawal.delete()
        
        return Response({
            'success': True,
            'message': 'Withdrawal request cancelled successfully'
        })