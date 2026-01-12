from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from .models import User
from .serializers import (
    IDUploadSerializer, 
    SelfieUploadSerializer, 
    VerificationStatusSerializer
)
import random
import logging

logger = logging.getLogger(__name__)


class UploadIDView(APIView):
    """
    POST /api/v1/auth/verification/upload-id/
    Upload government-issued ID document
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        serializer = IDUploadSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            
            # Check if already verified
            if user.verification_status == 'verified':
                return Response(
                    {
                        'success': False,
                        'message': 'You are already verified',
                        'data': {
                            'verification_status': user.verification_status,
                            'is_organizer': user.is_organizer
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save ID document
            user.id_document = serializer.validated_data['id_document']
            user.verification_status = 'id_uploaded'
            user.save(update_fields=['id_document', 'verification_status'])
            
            logger.info(f"User {user.email} uploaded ID document")
            
            return Response(
                {
                    'success': True,
                    'message': 'ID document uploaded successfully. Please upload your selfie next.',
                    'data': {
                        'verification_status': user.verification_status,
                        'id_document_url': request.build_absolute_uri(user.id_document.url) if user.id_document else None,
                        'next_step': 'upload_selfie'
                    }
                },
                status=status.HTTP_200_OK
            )
        
        return Response(
            {
                'success': False,
                'message': 'Invalid ID document',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class UploadSelfieView(APIView):
    """
    POST /api/v1/auth/verification/upload-selfie/
    Upload selfie and trigger verification process
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        serializer = SelfieUploadSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            
            # Check if ID was uploaded first
            if not user.id_document:
                return Response(
                    {
                        'success': False,
                        'message': 'Please upload your ID document first',
                        'data': {
                            'verification_status': user.verification_status,
                            'next_step': 'upload_id'
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ REMOVED: Already verified check - allows re-verification
            # This enables using the same endpoint for face matching features
            
            # Remember if user was already an organizer (to preserve status if verification fails)
            was_already_organizer = user.is_organizer
            
            # Save selfie
            user.selfie_image = serializer.validated_data['selfie_image']
            user.verification_status = 'pending'
            user.verification_submitted_at = timezone.now()
            user.save(update_fields=['selfie_image', 'verification_status', 'verification_submitted_at'])
            
            logger.info(f"User {user.email} uploaded selfie, starting verification")
            
            # Simulate verification process (instant for now)
            verification_result = self._simulate_verification(user, was_already_organizer)
            
            return Response(
                {
                    'success': True,
                    'message': verification_result['message'],
                    'data': verification_result['data']
                },
                status=status.HTTP_200_OK
            )
        
        return Response(
            {
                'success': False,
                'message': 'Invalid selfie image',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def _simulate_verification(self, user, was_already_organizer):
        """
        Simulate face verification process
        In production, this would call a 3rd party API like:
        - AWS Rekognition
        - Azure Face API
        - Face++
        - CompareFaces
        
        Args:
            user: User instance
            was_already_organizer: Boolean - whether user was already an organizer
        """
        
        # Simulate 90% success rate (you can adjust this)
        is_match = random.random() < 0.9
        
        if is_match:
            # Verification successful
            user.verification_status = 'verified'
            user.is_organizer = True  # Grant or maintain organizer access
            user.verified_at = timezone.now()
            user.verification_notes = 'Automated verification successful'
            user.save(update_fields=[
                'verification_status', 
                'is_organizer', 
                'verified_at', 
                'verification_notes'
            ])
            
            logger.info(f"User {user.email} verification SUCCESSFUL")
            
            return {
                'message': 'Verification successful! You can now create events.' if not was_already_organizer else 'Face verification successful!',
                'data': {
                    'verification_status': 'verified',
                    'is_organizer': True,
                    'verified_at': user.verified_at,
                    'can_create_events': True
                }
            }
        else:
            # Verification failed
            user.verification_status = 'rejected'
            user.verification_notes = 'Face does not match ID document. Please try again with clearer photos.'
            
            # 🔥 CRITICAL: Preserve organizer status if user was already verified
            if not was_already_organizer:
                user.is_organizer = False  # Only revoke if this was first-time verification
            
            user.save(update_fields=['verification_status', 'verification_notes', 'is_organizer'])
            
            logger.warning(f"User {user.email} verification FAILED (organizer status preserved: {was_already_organizer})")
            
            return {
                'message': 'Verification failed. Please ensure your selfie clearly shows your face and matches your ID.',
                'data': {
                    'verification_status': 'rejected',
                    'is_organizer': user.is_organizer,  # Will be True if was already organizer
                    'rejection_reason': user.verification_notes,
                    'can_retry': True,
                    'organizer_status_preserved': was_already_organizer
                }
            }

class UserVerificationStatusView(APIView):
    """
    GET /api/v1/auth/verification/status/
    Get current user verification status
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        serializer = VerificationStatusSerializer(user)
        
        # Determine next steps
        next_step = None
        can_create_events = user.is_organizer and user.verification_status == 'verified'
        
        if user.verification_status == 'not_started':
            next_step = 'upload_id'
        elif user.verification_status == 'id_uploaded':
            next_step = 'upload_selfie'
        elif user.verification_status == 'rejected':
            next_step = 'resubmit'
        
        return Response(
            {
                'success': True,
                'data': {
                    **serializer.data,
                    'next_step': next_step,
                    'can_create_events': can_create_events
                }
            },
            status=status.HTTP_200_OK
        )


class UserRetryVerificationView(APIView):
    """
    POST /api/v1/auth/verification/retry/
    Retry user verification after rejection (resets status)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.verification_status != 'rejected':
            return Response(
                {
                    'success': False,
                    'message': 'You can only retry after rejection',
                    'data': {
                        'verification_status': user.verification_status
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset verification
        user.verification_status = 'not_started'
        user.id_document = None
        user.selfie_image = None
        user.verification_notes = ''
        user.save(update_fields=[
            'verification_status', 
            'id_document', 
            'selfie_image', 
            'verification_notes'
        ])
        
        logger.info(f"User {user.email} reset verification for retry")
        
        return Response(
            {
                'success': True,
                'message': 'Verification reset. Please upload your ID and selfie again.',
                'data': {
                    'verification_status': user.verification_status,
                    'next_step': 'upload_id'
                }
            },
            status=status.HTTP_200_OK
        )