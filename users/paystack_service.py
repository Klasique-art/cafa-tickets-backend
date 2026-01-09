"""
Paystack Transfer Service
Handles automated payouts to organizers
"""
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import logging
import uuid

logger = logging.getLogger(__name__)

PAYSTACK_SECRET_KEY = settings.PAYSTACK_SECRET_KEY
PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackTransferService:
    """Service for handling Paystack transfers (payouts)"""
    
    @staticmethod
    def create_transfer_recipient(payment_profile):
        """
        Create a transfer recipient in Paystack
        This saves the bank account details to Paystack
        
        Args:
            payment_profile: PaymentProfile instance
            
        Returns:
            dict: {'success': bool, 'recipient_code': str, 'message': str}
        """
        url = f"{PAYSTACK_BASE_URL}/transferrecipient"
        
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        # Handle both bank transfer and mobile money
        if payment_profile.method == 'bank_transfer':
            payload = {
                "type": "nuban",
                "name": payment_profile.account_name,
                "account_number": payment_profile.account_number,
                "bank_code": payment_profile.bank_code,
                "currency": "GHS"
            }
        elif payment_profile.method == 'mobile_money':
            payload = {
                "type": "mobile_money",
                "name": payment_profile.account_name,
                "account_number": payment_profile.account_number,
                "bank_code": payment_profile.bank_code,  # Mobile money provider code
                "currency": "GHS"
            }
        else:
            return {
                'success': False,
                'recipient_code': None,
                'message': 'Unsupported payment method'
            }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            if response.status_code == 201 and data.get('status'):
                recipient_code = data['data']['recipient_code']
                
                logger.info(f"Paystack recipient created: {recipient_code}")
                
                return {
                    'success': True,
                    'recipient_code': recipient_code,
                    'message': 'Recipient created successfully'
                }
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Failed to create recipient: {error_msg}")
                
                return {
                    'success': False,
                    'recipient_code': None,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.error(f"Exception creating recipient: {str(e)}")
            return {
                'success': False,
                'recipient_code': None,
                'message': str(e)
            }
    
    @staticmethod
    def initiate_transfer(withdrawal_request):
        """
        Initiate a transfer (payout) to organizer's bank account
        
        Args:
            withdrawal_request: WithdrawalRequest instance
            
        Returns:
            dict: {'success': bool, 'transfer_code': str, 'message': str}
        """
        payment_profile = withdrawal_request.payment_profile
        
        # Create recipient if doesn't exist
        if not payment_profile.paystack_recipient_code:
            result = PaystackTransferService.create_transfer_recipient(payment_profile)
            
            if not result['success']:
                return result
            
            # Save recipient code
            payment_profile.paystack_recipient_code = result['recipient_code']
            payment_profile.save(update_fields=['paystack_recipient_code'])
        
        # Initiate transfer
        url = f"{PAYSTACK_BASE_URL}/transfer"
        
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        # Convert to pesewas (GHS cents) - Paystack uses smallest currency unit
        amount_in_pesewas = int(withdrawal_request.final_amount * 100)
        
        payload = {
            "source": "balance",  # From your Paystack balance
            "reason": f"Withdrawal: {withdrawal_request.withdrawal_id}",
            "amount": amount_in_pesewas,
            "recipient": payment_profile.paystack_recipient_code,
            "reference": withdrawal_request.withdrawal_id  # Use our withdrawal ID
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            if response.status_code == 200 and data.get('status'):
                transfer_code = data['data']['transfer_code']
                transfer_reference = data['data'].get('reference', withdrawal_request.withdrawal_id)
                
                # Update withdrawal request
                withdrawal_request.transfer_code = transfer_code
                withdrawal_request.transfer_reference = transfer_reference
                withdrawal_request.transfer_response = data
                withdrawal_request.status = 'processing'
                withdrawal_request.save()
                
                logger.info(f"Transfer initiated: {transfer_code}")
                
                return {
                    'success': True,
                    'transfer_code': transfer_code,
                    'message': 'Transfer initiated successfully'
                }
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Failed to initiate transfer: {error_msg}")
                
                # Update withdrawal to failed
                withdrawal_request.status = 'failed'
                withdrawal_request.rejection_reason = error_msg
                withdrawal_request.save()
                
                return {
                    'success': False,
                    'transfer_code': None,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.error(f"Exception initiating transfer: {str(e)}")
            
            withdrawal_request.status = 'failed'
            withdrawal_request.rejection_reason = str(e)
            withdrawal_request.save()
            
            return {
                'success': False,
                'transfer_code': None,
                'message': str(e)
            }
    
    @staticmethod
    def verify_transfer(transfer_code):
        """
        Verify transfer status from Paystack
        
        Args:
            transfer_code: Paystack transfer code
            
        Returns:
            dict: Transfer details from Paystack
        """
        url = f"{PAYSTACK_BASE_URL}/transfer/{transfer_code}"
        
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            
            if response.status_code == 200 and data.get('status'):
                return {
                    'success': True,
                    'data': data['data']
                }
            else:
                return {
                    'success': False,
                    'message': data.get('message', 'Failed to verify transfer')
                }
                
        except Exception as e:
            logger.error(f"Exception verifying transfer: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    @staticmethod
    def resolve_account_number(account_number, bank_code):
        """
        Resolve account number to get account name
        This helps verify the account exists and belongs to the right person
        
        Args:
            account_number: Bank account number
            bank_code: Bank code
            
        Returns:
            dict: {'success': bool, 'account_name': str, 'account_number': str}
        """
        url = f"{PAYSTACK_BASE_URL}/bank/resolve"
        
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
        }
        
        params = {
            "account_number": account_number,
            "bank_code": bank_code
        }
        
        try:
            response = requests.get(url, params=params, headers=headers)
            data = response.json()
            
            if response.status_code == 200 and data.get('status'):
                account_name = data['data']['account_name']
                account_number = data['data']['account_number']
                
                logger.info(f"Account resolved: {account_name}")
                
                return {
                    'success': True,
                    'account_name': account_name,
                    'account_number': account_number,
                    'message': 'Account resolved successfully'
                }
            else:
                error_msg = data.get('message', 'Failed to resolve account')
                logger.error(f"Account resolution failed: {error_msg}")
                
                return {
                    'success': False,
                    'account_name': None,
                    'account_number': None,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.error(f"Exception resolving account: {str(e)}")
            return {
                'success': False,
                'account_name': None,
                'account_number': None,
                'message': str(e)
            }
    
    @staticmethod
    def verify_bank_account(payment_profile, is_retry=False):
        """
        Verify bank account by resolving account number
        Retries up to 5 times if verification fails
        
        Args:
            payment_profile: PaymentProfile instance
            is_retry: Whether this is a retry attempt
            
        Returns:
            dict: {'success': bool, 'message': str, 'reference': str, 'should_retry': bool}
        """
        # Only verify bank transfers (not mobile money)
        if payment_profile.method != 'bank_transfer':
            # Auto-verify mobile money for now
            payment_profile.status = 'verified'
            payment_profile.is_verified = True
            payment_profile.verified_at = timezone.now()
            payment_profile.save()
            
            return {
                'success': True,
                'message': 'Mobile money account verified',
                'reference': None,
                'should_retry': False
            }
        
        # Check retry limit (max 5 attempts)
        MAX_ATTEMPTS = 5
        
        if not is_retry:
            # First attempt - reset counter
            payment_profile.verification_attempts = 0
        
        payment_profile.verification_attempts += 1
        payment_profile.last_verification_attempt = timezone.now()
        
        # Resolve account number to verify it exists
        resolve_result = PaystackTransferService.resolve_account_number(
            payment_profile.account_number,
            payment_profile.bank_code
        )
        
        if not resolve_result['success']:
            # Check if we should retry
            should_retry = payment_profile.verification_attempts < MAX_ATTEMPTS
            
            if should_retry:
                # Still has attempts left - keep status as pending
                payment_profile.status = 'pending_verification'
                payment_profile.failure_reason = f"Attempt {payment_profile.verification_attempts}/{MAX_ATTEMPTS}: {resolve_result['message']}"
                payment_profile.save()
                
                logger.warning(
                    f"Verification attempt {payment_profile.verification_attempts}/{MAX_ATTEMPTS} failed: "
                    f"{resolve_result['message']}"
                )
                
                return {
                    'success': False,
                    'message': f"Verification failed. Retrying... (Attempt {payment_profile.verification_attempts}/{MAX_ATTEMPTS})",
                    'reference': None,
                    'should_retry': True,
                    'attempts_remaining': MAX_ATTEMPTS - payment_profile.verification_attempts
                }
            else:
                # Max attempts reached - mark as failed
                payment_profile.status = 'verification_failed'
                payment_profile.failure_reason = f"Failed after {MAX_ATTEMPTS} attempts: {resolve_result['message']}"
                payment_profile.save()
                
                logger.error(
                    f"Verification failed after {MAX_ATTEMPTS} attempts: "
                    f"{resolve_result['message']}"
                )
                
                return {
                    'success': False,
                    'message': f"Verification failed after {MAX_ATTEMPTS} attempts. Please check your account details.",
                    'reference': None,
                    'should_retry': False
                }
        
        # Account resolved successfully - mark as verified
        resolved_name = resolve_result['account_name']
        provided_name = payment_profile.account_name
        
        # Log name comparison (for manual review if needed)
        if resolved_name.lower() != provided_name.lower():
            logger.warning(
                f"Account name mismatch: "
                f"Provided='{provided_name}' vs Resolved='{resolved_name}'"
            )
        
        # Mark as verified
        payment_profile.status = 'verified'
        payment_profile.is_verified = True
        payment_profile.verified_at = timezone.now()
        payment_profile.verification_initiated_at = timezone.now()
        payment_profile.save()
        
        reference = f"VER-{uuid.uuid4().hex[:12].upper()}"
        
        logger.info(f"Account verified successfully after {payment_profile.verification_attempts} attempt(s)")
        
        return {
            'success': True,
            'message': f'Bank account verified. Account name: {resolved_name}',
            'reference': reference,
            'resolved_name': resolved_name,
            'should_retry': False
        }
