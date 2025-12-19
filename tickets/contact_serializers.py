from rest_framework import serializers
from .models import ContactMessage, NewsletterSubscription


class ContactMessageSerializer(serializers.ModelSerializer):
    """Serializer for contact form submissions"""
    
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_email(self, value):
        """Validate email format"""
        if '@' not in value:
            raise serializers.ValidationError("Please enter a valid email address")
        return value.lower()
    
    def validate_message(self, value):
        """Ensure message is not too short"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long")
        return value.strip()


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for newsletter subscriptions"""
    
    class Meta:
        model = NewsletterSubscription
        fields = ['id', 'email', 'source', 'subscribed_at']
        read_only_fields = ['id', 'subscribed_at']
    
    def validate_email(self, value):
        """Validate email format and check for existing subscription"""
        if '@' not in value:
            raise serializers.ValidationError("Please enter a valid email address")
        
        email = value.lower()
        
        # Check if already subscribed and active
        existing = NewsletterSubscription.objects.filter(
            email=email,
            is_active=True
        ).first()
        
        if existing:
            raise serializers.ValidationError("This email is already subscribed to our newsletter")
        
        return email