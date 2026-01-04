from rest_framework import serializers
from .models import OrganizerRevenue, WithdrawalRequest
from users.models import PaymentProfile
from django.contrib.auth import get_user_model

User = get_user_model()


class OrganizerRevenueSerializer(serializers.ModelSerializer):
    """Serializer for organizer revenue records"""
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_slug = serializers.CharField(source='event.slug', read_only=True)
    purchase_id = serializers.CharField(source='purchase.purchase_id', read_only=True)
    
    class Meta:
        model = OrganizerRevenue
        fields = [
            'id',
            'event_title',
            'event_slug',
            'purchase_id',
            'ticket_sales_amount',
            'platform_fee',
            'organizer_earnings',
            'is_withdrawn',
            'status',
            'created_at',
            'available_at',
        ]
        read_only_fields = fields


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Serializer for creating withdrawal requests"""
    payment_profile_details = serializers.SerializerMethodField(read_only=True)
    organizer_email = serializers.EmailField(source='organizer.email', read_only=True)
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id',
            'withdrawal_id',
            'organizer_email',
            'payment_profile',
            'payment_profile_details',
            'requested_amount',
            'transfer_fee',
            'final_amount',
            'status',
            'admin_notes',
            'rejection_reason',
            'created_at',
            'updated_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'withdrawal_id',
            'organizer_email',
            'payment_profile_details',
            'transfer_fee',
            'final_amount',
            'status',
            'admin_notes',
            'rejection_reason',
            'updated_at',
            'completed_at',
        ]
    
    def get_payment_profile_details(self, obj):
        """Get masked payment profile details"""
        if obj.payment_profile:
            return {
                'name': obj.payment_profile.name,
                'method': obj.payment_profile.method,
                'masked_details': obj.payment_profile.get_masked_account_details()
            }
        return None
    
    def validate_payment_profile(self, value):
        """Ensure payment profile belongs to user and is verified"""
        user = self.context['request'].user
        
        if value.user != user:
            raise serializers.ValidationError("This payment profile does not belong to you.")
        
        if not value.is_verified:
            raise serializers.ValidationError("Payment profile must be verified before withdrawal.")
        
        if value.method != 'bank_transfer':
            raise serializers.ValidationError("Only bank transfer profiles can be used for withdrawals.")
        
        return value
    
    def validate_requested_amount(self, value):
        """Ensure requested amount is valid"""
        user = self.context['request'].user
        
        # Get available balance
        from django.db.models import Sum
        from decimal import Decimal
        
        available_revenue = OrganizerRevenue.objects.filter(
            organizer=user,
            status='available',
            is_withdrawn=False
        ).aggregate(total=Sum('organizer_earnings'))['total'] or Decimal('0.00')
        
        if value <= 0:
            raise serializers.ValidationError("Withdrawal amount must be greater than zero.")
        
        if value > available_revenue:
            raise serializers.ValidationError(
                f"Requested amount (GHS {value}) exceeds available balance (GHS {available_revenue})."
            )
        
        # Minimum withdrawal amount (e.g., GHS 50)
        min_withdrawal = Decimal('50.00')
        if value < min_withdrawal:
            raise serializers.ValidationError(
                f"Minimum withdrawal amount is GHS {min_withdrawal}."
            )
        
        return value
    
    def create(self, validated_data):
        """Create withdrawal request and calculate fees"""
        user = self.context['request'].user
        withdrawal = WithdrawalRequest(
            organizer=user,
            **validated_data
        )
        
        # Calculate transfer fee
        withdrawal.transfer_fee = withdrawal.calculate_transfer_fee()
        withdrawal.save()
        
        return withdrawal


class RevenueStatsSerializer(serializers.Serializer):
    """Serializer for revenue statistics"""
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    withdrawn_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_events = serializers.IntegerField()
    pending_withdrawals = serializers.IntegerField()
    completed_withdrawals = serializers.IntegerField()