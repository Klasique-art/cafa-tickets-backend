"""
Contact and Newsletter Views
Public endpoints for contact form and newsletter subscription
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ContactMessage, NewsletterSubscription
from .contact_serializers import ContactMessageSerializer, NewsletterSubscriptionSerializer


class ContactMessageView(APIView):
    """
    POST /api/v1/contact/
    Submit a contact form message
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid data provided',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save contact message
        contact = serializer.save()
        
        # TODO: Send email notification to admin
        # send_contact_notification_email(contact)
        
        # TODO: Send confirmation email to user
        # send_contact_confirmation_email(contact)
        
        return Response({
            'success': True,
            'message': 'Thank you for contacting us! We will get back to you soon.',
            'data': {
                'id': contact.id,
                'reference': f"MSG-{contact.id:06d}",
                'created_at': contact.created_at.isoformat()
            }
        }, status=status.HTTP_201_CREATED)


class NewsletterSubscribeView(APIView):
    """
    POST /api/v1/newsletter/subscribe/
    Subscribe to newsletter
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = NewsletterSubscriptionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid email address',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if email was previously unsubscribed
        email = serializer.validated_data['email']
        existing = NewsletterSubscription.objects.filter(email=email).first()
        
        if existing and not existing.is_active:
            # Reactivate subscription
            existing.is_active = True
            existing.save()
            subscription = existing
        else:
            # Create new subscription
            subscription = serializer.save()
        
        # TODO: Send welcome email
        # send_newsletter_welcome_email(subscription)
        
        return Response({
            'success': True,
            'message': 'Successfully subscribed to our newsletter!',
            'data': {
                'email': subscription.email,
                'subscribed_at': subscription.subscribed_at.isoformat()
            }
        }, status=status.HTTP_201_CREATED)


class NewsletterUnsubscribeView(APIView):
    """
    POST /api/v1/newsletter/unsubscribe/
    Unsubscribe from newsletter
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower()
        
        if not email:
            return Response({
                'success': False,
                'message': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription = NewsletterSubscription.objects.get(
                email=email,
                is_active=True
            )
            subscription.is_active = False
            subscription.save()
            
            return Response({
                'success': True,
                'message': 'Successfully unsubscribed from our newsletter'
            })
            
        except NewsletterSubscription.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Email not found in our subscriber list'
            }, status=status.HTTP_404_NOT_FOUND)