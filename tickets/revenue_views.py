from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal

from .models import OrganizerRevenue, WithdrawalRequest
from .revenue_serializers import (
    OrganizerRevenueSerializer,
    WithdrawalRequestSerializer,
    RevenueStatsSerializer
)


class RevenueViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing organizer revenue"""
    serializer_class = OrganizerRevenueSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return revenue records for current user only"""
        return OrganizerRevenue.objects.filter(
            organizer=self.request.user
        ).select_related('event', 'purchase')
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get revenue statistics for the organizer"""
        user = request.user
        
        # Calculate statistics
        revenue_queryset = OrganizerRevenue.objects.filter(organizer=user)
        
        total_revenue = revenue_queryset.aggregate(
            total=Sum('organizer_earnings')
        )['total'] or Decimal('0.00')
        
        available_balance = revenue_queryset.filter(
            status='available',
            is_withdrawn=False
        ).aggregate(
            total=Sum('organizer_earnings')
        )['total'] or Decimal('0.00')
        
        pending_revenue = revenue_queryset.filter(
            status='pending'
        ).aggregate(
            total=Sum('organizer_earnings')
        )['total'] or Decimal('0.00')
        
        withdrawn_amount = revenue_queryset.filter(
            is_withdrawn=True
        ).aggregate(
            total=Sum('organizer_earnings')
        )['total'] or Decimal('0.00')
        
        total_events = revenue_queryset.values('event').distinct().count()
        
        # Withdrawal stats
        pending_withdrawals = WithdrawalRequest.objects.filter(
            organizer=user,
            status__in=['pending', 'approved', 'processing']
        ).count()
        
        completed_withdrawals = WithdrawalRequest.objects.filter(
            organizer=user,
            status='completed'
        ).count()
        
        stats_data = {
            'total_revenue': total_revenue,
            'available_balance': available_balance,
            'pending_revenue': pending_revenue,
            'withdrawn_amount': withdrawn_amount,
            'total_events': total_events,
            'pending_withdrawals': pending_withdrawals,
            'completed_withdrawals': completed_withdrawals,
        }
        
        serializer = RevenueStatsSerializer(stats_data)
        return Response(serializer.data)


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing withdrawal requests"""
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']  # No PUT/PATCH allowed
    
    def get_queryset(self):
        """Return withdrawal requests for current user only"""
        return WithdrawalRequest.objects.filter(
            organizer=self.request.user
        ).select_related('payment_profile', 'organizer')
    
    def create(self, request, *args, **kwargs):
        """Create a new withdrawal request"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user has any pending withdrawals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            organizer=request.user,
            status__in=['pending', 'approved', 'processing']
        ).count()
        
        if pending_withdrawals > 0:
            return Response(
                {
                    'error': 'You already have a pending withdrawal request. '
                            'Please wait for it to be processed before creating a new one.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        withdrawal = serializer.save()
        
        # Mark revenue as being withdrawn (reserve it)
        self._reserve_revenue_for_withdrawal(withdrawal)
        
        return Response(
            {
                'message': 'Withdrawal request created successfully',
                'withdrawal': WithdrawalRequestSerializer(withdrawal).data
            },
            status=status.HTTP_201_CREATED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Cancel a withdrawal request (only if pending)"""
        withdrawal = self.get_object()
        
        if withdrawal.status != 'pending':
            return Response(
                {'error': 'Only pending withdrawal requests can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Release reserved revenue
        OrganizerRevenue.objects.filter(withdrawal=withdrawal).update(
            withdrawal=None,
            status='available'
        )
        
        withdrawal.delete()
        
        return Response(
            {'message': 'Withdrawal request cancelled successfully'},
            status=status.HTTP_200_OK
        )
    
    def _reserve_revenue_for_withdrawal(self, withdrawal):
        """Reserve revenue items for this withdrawal"""
        from django.db.models import Sum
        
        # Get available revenue items for this organizer
        available_revenue = OrganizerRevenue.objects.filter(
            organizer=withdrawal.organizer,
            status='available',
            is_withdrawn=False,
            withdrawal__isnull=True
        ).order_by('created_at')
        
        # Reserve revenue items until we reach the requested amount
        amount_reserved = Decimal('0.00')
        for revenue_item in available_revenue:
            if amount_reserved >= withdrawal.requested_amount:
                break
            
            revenue_item.withdrawal = withdrawal
            revenue_item.status = 'on_hold'
            revenue_item.save()
            
            amount_reserved += revenue_item.organizer_earnings