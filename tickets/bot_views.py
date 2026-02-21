from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from openai import OpenAI
from django.conf import settings
import logging

from tickets.bot_assistant_serializers import BotAssistantPromptSerializer

logger = logging.getLogger(__name__)


class BotAssistantView(APIView):
    """
    Cafa Tickets Bot Assistant - Handles customer inquiries and support.
    """
    permission_classes = [IsAuthenticated]  # Remove if you want it public
    
    SYSTEM_PROMPT = """You are the Cafa Tickets customer support assistant, a helpful and professional bot for a global event ticketing platform.

**About Cafa Tickets:**
- Global event ticketing platform serving customers worldwide
- Secure QR code-based ticket verification
- Multiple payment gateway integrations (Paystack, Stripe, and more)
- Face verification for enhanced security
- Support for multiple ticket types (Regular, VIP, VVIP, Early Bird, Group, Student)
- Automated email and SMS notifications
- Real-time event updates and notifications
- Multi-currency support
- Mobile app and web platform access

**Your Role:**
- Assist customers with ticket purchases and event inquiries
- Explain payment processes and ticket delivery
- Help troubleshoot issues with QR codes or ticket access
- Provide information about events, venues, and ticket types
- Guide users through account registration and profile management
- Address refund and cancellation policies
- Ensure customers have a smooth experience
- Support customers across different time zones and regions

**Tone & Style:**
- Professional yet friendly and approachable
- Clear and concise responses
- Patient and understanding with technical issues
- Culturally aware and respectful of global diversity
- Empathetic to customer concerns
- Available in multiple languages (when applicable)

**Key Information:**
- Payment Methods: Credit/Debit Cards, PayPal, Paystack, Mobile Money, Bank Transfer (region-dependent)
- Ticket Delivery: Instant email delivery with QR code (check spam/junk folder)
- Event Time: Displayed in local event timezone and customer timezone
- Support Hours: 24/7 automated support
- Contact: support@cafatickets.com
- Platform: Web (cafatickets.com) and Mobile Apps (iOS/Android)

**Common Issues to Address:**
1. Payment failures, pending transactions, or currency questions
2. QR code not received, not scanning, or damaged
3. Event date/time/venue changes and timezone confusion
4. Ticket transfers, resales, and refunds
5. Account access problems and password resets
6. Multiple ticket purchases and group bookings
7. Face verification questions and privacy concerns
8. Regional payment method availability
9. International transactions and fees
10. Mobile app sync issues

**Refund Policy:**
- Event cancellations: Full refund within 14 days
- Customer cancellations: Based on event organizer's policy
- Request refunds through your account dashboard or contact support

**Security & Privacy:**
- All transactions are encrypted and secure
- Face verification is optional and privacy-protected
- Personal data is never shared with third parties
- QR codes are unique and non-transferable (unless ticket transfer is enabled)

**Important Guidelines:**
- Always verify customer identity for sensitive account issues
- Escalate payment disputes to human support immediately
- Respect data privacy and never ask for payment credentials
- Provide clear timezone information for international events
- Acknowledge regional differences in payment methods
- Be sensitive to different cultural contexts

Always prioritize customer satisfaction and security. If an issue requires human intervention (payment disputes, account verification, technical bugs, or complex refunds), politely inform the customer to contact support@cafatickets.com with their ticket reference number."""

    def post(self, request):
        """
        Send a customer inquiry to the bot assistant.
        """
        serializer = BotAssistantPromptSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prompt = serializer.validated_data['prompt']
        context = serializer.validated_data.get('context', {})
        
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self._build_system_message(context)}
            ]
            
            # Add user prompt
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for customer support
                messages=messages,
                temperature=0.7,  # Balanced creativity and consistency
                max_tokens=800,
            )
            
            # Extract response
            assistant_message = response.choices[0].message.content
            
            return Response({
                "success": True,
                "response": assistant_message,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return Response(
                {
                    "error": "Failed to get response from bot assistant",
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _build_system_message(self, context):
        """
        Enhance system prompt with dynamic context.
        """
        enhanced_prompt = self.SYSTEM_PROMPT
        
        if context and isinstance(context, dict):
            # Add user-specific context
            context_additions = []
            
            if 'user_name' in context:
                context_additions.append(f"Customer Name: {context['user_name']}")
            
            if 'user_email' in context:
                context_additions.append(f"Customer Email: {context['user_email']}")
            
            if 'user_country' in context:
                context_additions.append(f"Customer Location: {context['user_country']}")
            
            if 'user_timezone' in context:
                context_additions.append(f"Customer Timezone: {context['user_timezone']}")
            
            if 'ticket_id' in context:
                context_additions.append(f"Ticket Reference: {context['ticket_id']}")
            
            if 'event_name' in context:
                context_additions.append(f"Event: {context['event_name']}")
            
            if 'event_location' in context:
                context_additions.append(f"Event Location: {context['event_location']}")
            
            if 'event_date' in context:
                context_additions.append(f"Event Date: {context['event_date']}")
            
            if 'payment_status' in context:
                context_additions.append(f"Payment Status: {context['payment_status']}")
            
            if 'payment_method' in context:
                context_additions.append(f"Payment Method: {context['payment_method']}")
            
            if 'currency' in context:
                context_additions.append(f"Currency: {context['currency']}")
            
            if 'issue_type' in context:
                context_additions.append(f"Issue Type: {context['issue_type']}")
            
            if 'language_preference' in context:
                context_additions.append(f"Preferred Language: {context['language_preference']}")
            
            if context_additions:
                enhanced_prompt += "\n\n**Current Customer Context:**\n" + "\n".join(context_additions)
        
        return enhanced_prompt


class BotAssistantStreamView(APIView):
    """
    Streaming endpoint for real-time bot responses.
    """
    permission_classes = [IsAuthenticated]
    
    SYSTEM_PROMPT = BotAssistantView.SYSTEM_PROMPT
    
    def post(self, request):
        """
        Stream responses from the bot assistant.
        """
        from django.http import StreamingHttpResponse
        import json
        
        serializer = BotAssistantPromptSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prompt = serializer.validated_data['prompt']
        context = serializer.validated_data.get('context', {})
        
        def generate():
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                
                messages = [
                    {"role": "system", "content": self._build_system_message(context)},
                    {"role": "user", "content": prompt}
                ]
                
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800,
                    stream=True,
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        # Send as SSE format
                        yield f"data: {json.dumps({'content': content})}\n\n"
                
                # Send done signal
                yield f"data: {json.dumps({'done': True})}\n\n"
                        
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
    
    def _build_system_message(self, context):
        """Enhance system prompt with dynamic context."""
        enhanced_prompt = self.SYSTEM_PROMPT
        
        if context and isinstance(context, dict):
            context_additions = []
            
            if 'user_name' in context:
                context_additions.append(f"Customer Name: {context['user_name']}")
            if 'user_email' in context:
                context_additions.append(f"Customer Email: {context['user_email']}")
            if 'user_country' in context:
                context_additions.append(f"Customer Location: {context['user_country']}")
            if 'ticket_id' in context:
                context_additions.append(f"Ticket Reference: {context['ticket_id']}")
            if 'event_name' in context:
                context_additions.append(f"Event: {context['event_name']}")
            if 'event_location' in context:
                context_additions.append(f"Event Location: {context['event_location']}")
            if 'payment_status' in context:
                context_additions.append(f"Payment Status: {context['payment_status']}")
            if 'currency' in context:
                context_additions.append(f"Currency: {context['currency']}")
            
            if context_additions:
                enhanced_prompt += "\n\n**Current Customer Context:**\n" + "\n".join(context_additions)
        
        return enhanced_prompt


class BotConversationView(APIView):
    """
    Multi-turn conversation endpoint with history.
    """
    permission_classes = [IsAuthenticated]
    
    SYSTEM_PROMPT = BotAssistantView.SYSTEM_PROMPT
    
    def post(self, request):
        """
        Handle conversation with message history.
        """
        serializer = BotAssistantPromptSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prompt = serializer.validated_data['prompt']
        context = serializer.validated_data.get('context', {})
        
        # Get or initialize conversation history
        session_key = f"bot_conversation_{request.user.id}"
        conversation_history = request.session.get(session_key, [])
        
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Build messages
            if not conversation_history:
                messages = [
                    {"role": "system", "content": self._build_system_message(context)}
                ]
            else:
                messages = conversation_history.copy()
            
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=800,
            )
            
            assistant_message = response.choices[0].message.content
            
            # Update conversation history (keep last 20 messages)
            messages.append({"role": "assistant", "content": assistant_message})
            request.session[session_key] = messages[-20:]
            
            return Response({
                "success": True,
                "response": assistant_message,
                "conversation_length": len(messages),
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Conversation error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request):
        """
        Clear conversation history.
        """
        session_key = f"bot_conversation_{request.user.id}"
        if session_key in request.session:
            del request.session[session_key]
        
        return Response({
            "success": True,
            "message": "Conversation history cleared"
        }, status=status.HTTP_200_OK)
    
    def _build_system_message(self, context):
        """Enhance system prompt with dynamic context."""
        enhanced_prompt = self.SYSTEM_PROMPT
        
        if context and isinstance(context, dict):
            context_additions = []
            
            if 'user_name' in context:
                context_additions.append(f"Customer Name: {context['user_name']}")
            if 'user_email' in context:
                context_additions.append(f"Customer Email: {context['user_email']}")
            if 'user_country' in context:
                context_additions.append(f"Customer Location: {context['user_country']}")
            if 'ticket_id' in context:
                context_additions.append(f"Ticket Reference: {context['ticket_id']}")
            if 'event_name' in context:
                context_additions.append(f"Event: {context['event_name']}")
            if 'event_location' in context:
                context_additions.append(f"Event Location: {context['event_location']}")
            
            if context_additions:
                enhanced_prompt += "\n\n**Current Customer Context:**\n" + "\n".join(context_additions)
        
        return enhanced_prompt
    