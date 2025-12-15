# Error Handling Quick Reference Guide

## For Frontend Developers

### Standard Error Response Format
All API errors return this consistent structure:

```javascript
{
    "error": "Error Title",           // Short error category
    "message": "Detailed message",    // User-friendly description
    "details": {},                    // Optional: field-level errors
    "status_code": 400               // HTTP status code
}
```

### How to Handle Errors in Frontend

```javascript
// Example using fetch
try {
    const response = await fetch('/api/v1/events/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(eventData)
    });

    const data = await response.json();

    if (!response.ok) {
        // Handle error
        console.error(`${data.error}: ${data.message}`);

        // Show field-level errors if present
        if (data.details) {
            Object.keys(data.details).forEach(field => {
                console.error(`${field}: ${data.details[field]}`);
            });
        }

        return;
    }

    // Success - handle data
    console.log('Success:', data);

} catch (error) {
    console.error('Network error:', error);
}
```

### Common Error Status Codes

| Code | Error Type | Meaning |
|------|-----------|---------|
| 400 | Bad Request | Invalid data or missing required fields |
| 401 | Unauthorized | Not authenticated or invalid credentials |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |

---

## For Backend Developers

### How to Raise Errors in Views

```python
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

# Validation Error
if not data.get('email'):
    raise ValidationError({
        'email': 'This field is required'
    })

# Not Found
event = Event.objects.filter(id=event_id).first()
if not event:
    raise NotFound('Event not found')

# Permission Denied
if event.organizer != request.user:
    raise PermissionDenied('You do not have permission to edit this event')

# Custom error response
return Response({
    'error': 'Payment Failed',
    'message': 'The payment gateway returned an error',
    'details': {'gateway_error': payment_error}
}, status=status.HTTP_402_PAYMENT_REQUIRED)
```

### Custom Exception Classes

Create custom exceptions for domain-specific errors:

```python
# tickets/exceptions.py
from rest_framework.exceptions import APIException

class TicketSoldOutException(APIException):
    status_code = 400
    default_detail = 'Tickets are sold out'
    default_code = 'ticket_sold_out'

class PaymentFailedException(APIException):
    status_code = 402
    default_detail = 'Payment failed'
    default_code = 'payment_failed'

# Usage in views
from .exceptions import TicketSoldOutException

if ticket_type.is_sold_out:
    raise TicketSoldOutException('This ticket type is sold out')
```

### Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

# Log errors
logger.error(f"Payment failed for order {order.id}", exc_info=True)

# Log warnings
logger.warning(f"Low ticket inventory for event {event.id}")

# Log info
logger.info(f"Ticket purchased: {ticket.ticket_id}")

# Log debug
logger.debug(f"Payment gateway response: {response.json()}")
```

### Transaction Handling with Error Recovery

```python
from django.db import transaction

@transaction.atomic
def create_order(request):
    try:
        # Create order
        order = Order.objects.create(...)

        # Create tickets
        tickets = []
        for item in items:
            ticket = Ticket.objects.create(...)
            tickets.append(ticket)

        # Process payment
        payment = process_payment(order)

        if not payment.success:
            # Rollback will happen automatically
            raise PaymentFailedException(payment.error_message)

        return Response({'order': order.id})

    except Exception as e:
        # Transaction automatically rolled back
        logger.error(f"Order creation failed: {str(e)}", exc_info=True)
        raise
```

---

## Testing Error Scenarios

### Using cURL

```bash
# Test 404
curl http://localhost:8000/api/v1/events/nonexistent-slug/

# Test 401 (No auth token)
curl http://localhost:8000/api/v1/tickets/my-tickets/

# Test 400 (Invalid data)
curl -X POST http://localhost:8000/api/v1/tickets/purchase/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"invalid": "data"}'

# Test 403 (Permission denied)
curl -X PATCH http://localhost:8000/api/v1/events/1/update/ \
  -H "Authorization: Bearer ANOTHER_USER_TOKEN"
```

### Using Python Requests

```python
import requests

# Test validation error
response = requests.post(
    'http://localhost:8000/api/v1/events/',
    json={'title': 'Too short'},  # Title needs 5+ chars
    headers={'Authorization': f'Bearer {token}'}
)

print(response.json())
# {
#     "error": "Validation Error",
#     "message": "The data provided is invalid",
#     "details": {
#         "title": ["Title must be between 5 and 200 characters"]
#     },
#     "status_code": 400
# }
```

---

## Monitoring and Debugging

### View Logs

```bash
# View error logs
tail -f logs/error.log

# View debug logs (development only)
tail -f logs/debug.log

# Search for specific errors
grep "Payment failed" logs/error.log

# View last 100 lines
tail -100 logs/error.log
```

### Log Rotation

Logs automatically rotate when they reach 10MB:
- Error logs keep 5 backup files
- Debug logs keep 3 backup files

---

## Common Error Scenarios

### 1. Event Creation Validation

```json
// Missing required fields
{
    "error": "Validation Error",
    "message": "The data provided is invalid",
    "details": {
        "title": ["This field is required"],
        "start_date": ["This field is required"],
        "payment_profile_id": ["This field is required"]
    },
    "status_code": 400
}
```

### 2. Ticket Purchase - Sold Out

```json
{
    "error": "Validation Error",
    "message": "The data provided is invalid",
    "details": {
        "ticket_type_id": ["This ticket type is sold out"],
        "tickets_remaining": 0
    },
    "status_code": 400
}
```

### 3. Payment Failed

```json
{
    "error": "Payment initialization failed",
    "message": "The payment gateway returned an error",
    "status_code": 500
}
```

### 4. Authentication Required

```json
{
    "error": "Authentication Failed",
    "message": "Authentication credentials were not provided or are invalid",
    "status_code": 401
}
```

### 5. Permission Denied

```json
{
    "error": "Permission Denied",
    "message": "You don't have permission to edit this event",
    "status_code": 403
}
```

---

## Best Practices

### For Frontend:
1. ✅ Always check `response.ok` before parsing JSON
2. ✅ Display `message` field to users
3. ✅ Show field-level errors from `details` near form fields
4. ✅ Handle network errors separately from API errors
5. ✅ Provide retry mechanisms for 500 errors
6. ✅ Store error logs for debugging

### For Backend:
1. ✅ Use appropriate HTTP status codes
2. ✅ Provide clear, actionable error messages
3. ✅ Use field-level validation errors in serializers
4. ✅ Log all exceptions with context
5. ✅ Use transactions for multi-step operations
6. ✅ Never expose sensitive information in errors
7. ✅ Return consistent error response format

---

## Configuration Files Reference

### Exception Handler
`cafa_ticket/exception_handlers.py`

### Middleware
`cafa_ticket/error_middleware.py`

### Error Views
`cafa_ticket/error_views.py`

### Settings
`cafa_ticket/settings.py`
- `REST_FRAMEWORK['EXCEPTION_HANDLER']`
- `MIDDLEWARE`
- `LOGGING`

### URLs
`cafa_ticket/urls.py`
- `handler404`, `handler500`, `handler403`, `handler400`

---

## Support

For issues or questions about error handling:
1. Check logs in `logs/error.log`
2. Enable DEBUG mode for detailed error messages
3. Review `ERROR_FIXES_AND_IMPROVEMENTS.md` for detailed documentation
4. Check Django docs: https://docs.djangoproject.com/en/stable/
5. Check DRF docs: https://www.django-rest-framework.org/
