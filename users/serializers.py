from rest_framework import serializers
from djoser.serializers import UserSerializer as BaseUserSerializer
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from .models import User


class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ("id", "username", "email", "password")


class UserSerializer(BaseUserSerializer):
    settings = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    is_email_verified = serializers.BooleanField(source="is_active", read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)

    class Meta(BaseUserSerializer.Meta):
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "phone_number",
            "is_organizer",
            "profile_image",
            "bio",
            "city",
            "country",
            "is_email_verified",
            "date_joined",
            "last_login",
            "settings",
            "stats",
        )
        read_only_fields = (
            "id",
            "email",
            "is_email_verified",
            "date_joined",
            "last_login",
        )

    def get_settings(self, obj):
        return {
            "marketing_emails": obj.marketing_emails,
            "event_reminders": obj.event_reminders,
            "email_notifications": obj.email_notifications,
            "sms_notifications": obj.sms_notifications,
        }

    def get_stats(self, obj):
        return obj.get_stats()


class CurrentUserSerializer(UserSerializer):
    pass


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "full_name",
            "phone_number",
            "profile_image",
            "bio",
            "city",
            "country",
        )

    def validate_profile_image(self, value):
        """
        Validate profile image size and format
        """
        if value:
            # Check file size (5MB limit)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Profile image must be under 5MB.")

            valid_formats = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
            if value.content_type not in valid_formats:
                raise serializers.ValidationError(
                    "Profile image must be JPG, PNG, or WebP format."
                )

        return value


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user notification settings
    Matches: PATCH /api/v1/users/settings/
    """

    class Meta:
        model = User
        fields = (
            "marketing_emails",
            "event_reminders",
            "email_notifications",
            "sms_notifications",
        )

    def update(self, instance, validated_data):
        """
        Update settings and return formatted response
        """
        return instance.update_settings(**validated_data)

class IDUploadSerializer(serializers.Serializer):
    """Serializer for ID document upload"""
    id_document = serializers.ImageField(
        required=True,
        help_text="Government-issued ID (PNG, JPG, max 10MB)"
    )
    
    def validate_id_document(self, value):
        # Validate file size (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("ID document must be less than 10MB")
        
        # Validate file type
        valid_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if value.content_type not in valid_types:
            raise serializers.ValidationError("ID document must be JPG, PNG, or WebP")
        
        return value


class SelfieUploadSerializer(serializers.Serializer):
    """Serializer for selfie upload"""
    selfie_image = serializers.ImageField(
        required=True,
        help_text="Selfie photo (PNG, JPG, max 10MB)"
    )
    
    def validate_selfie_image(self, value):
        # Validate file size (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Selfie must be less than 10MB")
        
        # Validate file type
        valid_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if value.content_type not in valid_types:
            raise serializers.ValidationError("Selfie must be JPG, PNG, or WebP")
        
        return value


class VerificationStatusSerializer(serializers.ModelSerializer):
    """Serializer for verification status response"""
    class Meta:
        model = User
        fields = [
            'verification_status',
            'verification_submitted_at',
            'verified_at',
            'verification_notes',
            'is_organizer',
            'id_document',
            'selfie_image'
        ]
        read_only_fields = fields