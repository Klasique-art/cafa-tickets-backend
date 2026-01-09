"""
Payment Profile Serializers
Matches the API specification for payment profile management
"""
from rest_framework import serializers
from .models import PaymentProfile, User
from django.utils import timezone


class PaymentProfileSerializer(serializers.ModelSerializer):
    """Serializer for payment profile list/detail views"""
    account_details = serializers.SerializerMethodField()

    class Meta:
        model = PaymentProfile
        fields = [
            'id',
            'method',
            'name',
            'description',
            'account_details',
            'fee_percentage',
            'status',
            'is_verified',
            'verified_at',
            'is_default',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'fee_percentage',
            'status',
            'is_verified',
            'verified_at',
            'created_at',
        ]

    def get_account_details(self, obj):
        """Return masked account details for security"""
        return obj.get_masked_account_details()


class PaymentProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment profiles"""

    class Meta:
        model = PaymentProfile
        fields = [
            'method',
            'name',
            'description',
            'account_details',
        ]

    def validate_method(self, value):
        """Validate payment method"""
        valid_methods = ['mobile_money', 'bank_transfer']
        if value not in valid_methods:
            raise serializers.ValidationError(
                f"Method must be one of: {', '.join(valid_methods)}"
            )
        return value

    def validate_name(self, value):
        """Validate name length"""
        if len(value) < 3 or len(value) > 100:
            raise serializers.ValidationError(
                "Name must be between 3 and 100 characters"
            )
        return value

    def validate_description(self, value):
        """Validate description length"""
        if value and len(value) > 500:
            raise serializers.ValidationError(
                "Description must not exceed 500 characters"
            )
        return value

    def validate_account_details(self, value):
        """Validate account details based on payment method"""
        method = self.initial_data.get('method')

        if method == 'mobile_money':
            # Validate mobile money details
            if 'mobile_number' not in value:
                raise serializers.ValidationError(
                    "mobile_number is required for mobile money"
                )
            if 'network' not in value:
                raise serializers.ValidationError(
                    "network is required for mobile money"
                )
            if 'account_name' not in value:
                raise serializers.ValidationError(
                    "account_name is required"
                )

            # Validate mobile number format (Ghanaian format)
            mobile = value['mobile_number']
            if not mobile.startswith('+233') or len(mobile) != 13:
                raise serializers.ValidationError(
                    "Invalid mobile number format. Must be in format: +233XXXXXXXXX"
                )

            # Validate network
            valid_networks = ['MTN', 'Vodafone', 'AirtelTigo']
            if value['network'] not in valid_networks:
                raise serializers.ValidationError(
                    f"Network must be one of: {', '.join(valid_networks)}"
                )

        elif method == 'bank_transfer':
            # Validate bank transfer details
            required_fields = ['account_number', 'account_name', 'bank_name', 'bank_code']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(
                        f"{field} is required for bank transfer"
                    )

            # Validate account number (10 digits)
            account_number = value['account_number']
            if not account_number.isdigit():
                raise serializers.ValidationError(
                    "Account number must contain only digits"
                )
            if not (8 <= len(account_number) <= 17):
                raise serializers.ValidationError(
                    "Account number must be between 8 and 17 digits"
                )

        return value

    def validate(self, data):
        """Cross-field validation"""
        # Check for duplicate payment profile
        user = self.context['request'].user

        if data['method'] == 'mobile_money':
            mobile_number = data['account_details']['mobile_number']
            if PaymentProfile.objects.filter(
                user=user,
                method='mobile_money',
                account_details__mobile_number=mobile_number
            ).exists():
                raise serializers.ValidationError({
                    'account_details': 'This mobile money account is already registered.'
                })

        elif data['method'] == 'bank_transfer':
            account_number = data['account_details']['account_number']
            if PaymentProfile.objects.filter(
                user=user,
                method='bank_transfer',
                account_details__account_number=account_number
            ).exists():
                raise serializers.ValidationError({
                    'account_details': 'This bank account is already registered.'
                })

        return data

    def create(self, validated_data):
        """Create payment profile and initiate verification"""
        user = self.context['request'].user

        # Create payment profile
        payment_profile = PaymentProfile.objects.create(
            user=user,
            **validated_data
        )

        # Initiate verification (1 GHS deduction)
        payment_profile.verification_initiated_at = timezone.now()
        payment_profile.status = 'pending_verification'
        payment_profile.save()

        # TODO: Integrate with Paystack to deduct 1 GHS for verification
        # For now, we'll mark it as pending

        return payment_profile


class PaymentProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating payment profiles"""

    class Meta:
        model = PaymentProfile
        fields = ['name', 'description', 'is_default']

    def validate_name(self, value):
        """Validate name length"""
        if value and (len(value) < 3 or len(value) > 100):
            raise serializers.ValidationError(
                "Name must be between 3 and 100 characters"
            )
        return value

    def update(self, instance, validated_data):
        """Update payment profile"""
        # Update fields
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance


class VerificationStatusSerializer(serializers.Serializer):
    """Serializer for verification status response"""
    status = serializers.CharField()
    is_verified = serializers.BooleanField()
    verified_at = serializers.DateTimeField(required=False, allow_null=True)
    verification_initiated_at = serializers.DateTimeField(required=False, allow_null=True)
    message = serializers.CharField()
    failure_reason = serializers.CharField(required=False, allow_null=True)
    can_retry = serializers.BooleanField(required=False)


class RetryVerificationSerializer(serializers.Serializer):
    """Serializer for retry verification request"""
    confirm = serializers.BooleanField(required=True)

    def validate_confirm(self, value):
        """Ensure user confirms retry"""
        if not value:
            raise serializers.ValidationError(
                "You must confirm retry by setting confirm to true"
            )
        return value
