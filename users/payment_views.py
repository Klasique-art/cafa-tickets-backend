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

        # Return response with verification info
        response_serializer = PaymentProfileSerializer(payment_profile)

        return Response({
            'message': 'Payment profile created successfully. Verification in progress...',
            'payment_profile': response_serializer.data
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
