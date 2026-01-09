"""
Paystack Webhook Handlers
"""
import hmac
import hashlib
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
import logging

from tickets.models import WithdrawalRequest, OrganizerRevenue

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def paystack_transfer_webhook(request):
    """
    Handle Paystack transfer webhooks
    POST /api/v1/webhooks/paystack/transfer/
    """
    
    # Verify webhook signature
    paystack_signature = request.headers.get('x-paystack-signature', '')
    
    if not verify_paystack_signature(request.body, paystack_signature):
        logger.warning("Invalid Paystack webhook signature")
        return HttpResponse(status=400)
    
    try:
        payload = json.loads(request.body)
        event = payload.get('event')
        data = payload.get('data', {})
        
        logger.info(f"Paystack webhook received: {event}")
        
        if event == 'transfer.success':
            handle_transfer_success(data)
        elif event == 'transfer.failed':
            handle_transfer_failed(data)
        elif event == 'transfer.reversed':
            handle_transfer_reversed(data)
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)


def verify_paystack_signature(payload, signature):
    """Verify Paystack webhook signature"""
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    hash_obj = hmac.new(secret, payload, hashlib.sha512)
    expected_signature = hash_obj.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def handle_transfer_success(data):
    """Handle successful transfer"""
    reference = data.get('reference')
    transfer_code = data.get('transfer_code')
    
    try:
        withdrawal = WithdrawalRequest.objects.get(
            withdrawal_id=reference
        )
        
        withdrawal.status = 'completed'
        withdrawal.completed_at = timezone.now()
        withdrawal.transfer_response = data
        withdrawal.save()
        
        # Mark revenue as withdrawn
        OrganizerRevenue.objects.filter(
            withdrawal=withdrawal
        ).update(is_withdrawn=True)
        
        logger.info(f"Transfer completed: {reference}")
        
    except WithdrawalRequest.DoesNotExist:
        logger.error(f"Withdrawal not found: {reference}")


def handle_transfer_failed(data):
    """Handle failed transfer"""
    reference = data.get('reference')
    
    try:
        withdrawal = WithdrawalRequest.objects.get(
            withdrawal_id=reference
        )
        
        withdrawal.status = 'failed'
        withdrawal.rejection_reason = data.get('reason', 'Transfer failed')
        withdrawal.transfer_response = data
        withdrawal.save()
        
        # Release reserved revenue
        OrganizerRevenue.objects.filter(
            withdrawal=withdrawal
        ).update(
            withdrawal=None,
            status='available'
        )
        
        logger.warning(f"Transfer failed: {reference}")
        
    except WithdrawalRequest.DoesNotExist:
        logger.error(f"Withdrawal not found: {reference}")


def handle_transfer_reversed(data):
    """Handle reversed transfer"""
    reference = data.get('reference')
    
    try:
        withdrawal = WithdrawalRequest.objects.get(
            withdrawal_id=reference
        )
        
        withdrawal.status = 'failed'
        withdrawal.rejection_reason = 'Transfer was reversed'
        withdrawal.transfer_response = data
        withdrawal.save()
        
        # Release reserved revenue
        OrganizerRevenue.objects.filter(
            withdrawal=withdrawal,
            is_withdrawn=True
        ).update(is_withdrawn=False)
        
        logger.warning(f"Transfer reversed: {reference}")
        
    except WithdrawalRequest.DoesNotExist:
        logger.error(f"Withdrawal not found: {reference}")