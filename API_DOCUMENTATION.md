# Cafa Tickets API Documentation

## Base URL
```
http://localhost:8000/api/v1/
```

## Authentication
Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

## Authentication Endpoints

### Register
```http
POST /api/v1/auth/users/
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "username",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

### Login
```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}

Response:
{
  "message": "Login successful",
  "user": {...},
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

### Get User Profile
```http
GET /api/v1/auth/profile/
Authorization: Bearer <token>
```

## Event Endpoints

### List Events
```http
GET /api/v1/events/

Query Parameters:
- category: Filter by category slug
- status: Filter by status (draft, published, cancelled, completed)
- featured: true/false
- free: true/false
- time: upcoming/ongoing/past
- city: Filter by city
- search: Search in title, description, tags
```

### Get Single Event
```http
GET /api/v1/events/{slug}/
```

### Create Event (Authenticated)
```http
POST /api/v1/events/
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Amazing Concert 2025",
  "description": "Full event description",
  "short_description": "Brief description",
  "category_id": 1,
  "venue_id": 1,
  "banner_image": <file>,
  "start_date": "2025-12-31T20:00:00Z",
  "end_date": "2025-12-31T23:59:00Z",
  "status": "published",
  "privacy": "public",
  "is_free": false,
  "max_attendees": 1000,
  "tags": "concert,music,live"
}
```

### Update Event
```http
PATCH /api/v1/events/{slug}/
Authorization: Bearer <token>
```

### Get Event Ticket Types
```http
GET /api/v1/events/{slug}/ticket_types/
```

### Add Ticket Type to Event
```http
POST /api/v1/events/{slug}/add_ticket_type/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "VIP",
  "description": "VIP access with backstage pass",
  "price": "500.00",
  "quantity": 100,
  "min_purchase": 1,
  "max_purchase": 5,
  "is_active": true
}
```

### Get Event Stats (Organizer only)
```http
GET /api/v1/events/{slug}/stats/
Authorization: Bearer <token>
```

### Get Event Reviews
```http
GET /api/v1/events/{slug}/reviews/
```

### Add Review
```http
POST /api/v1/events/{slug}/add_review/
Authorization: Bearer <token>
Content-Type: application/json

{
  "rating": 5,
  "comment": "Amazing event!"
}
```

## Event Discovery

### Featured Events
```http
GET /api/v1/featured/
```

### Upcoming Events
```http
GET /api/v1/upcoming/
```

### Search Events
```http
GET /api/v1/search/?q=concert
```

## Category Endpoints

### List Categories
```http
GET /api/v1/categories/
```

### Get Single Category
```http
GET /api/v1/categories/{slug}/
```

## Venue Endpoints

### List Venues
```http
GET /api/v1/venues/
```

### Get Single Venue
```http
GET /api/v1/venues/{id}/
```

## Order Endpoints

### Create Order
```http
POST /api/v1/orders/create/
Authorization: Bearer <token>
Content-Type: application/json

{
  "event_id": 1,
  "buyer_name": "John Doe",
  "buyer_email": "john@example.com",
  "buyer_phone": "+233241234567",
  "payment_gateway": "paystack",
  "items": [
    {
      "ticket_type_id": 1,
      "quantity": 2,
      "attendees": [
        {
          "name": "John Doe",
          "email": "john@example.com",
          "phone": "+233241234567"
        },
        {
          "name": "Jane Doe",
          "email": "jane@example.com",
          "phone": "+233241234568"
        }
      ]
    }
  ],
  "notes": "Special seating request"
}

Response:
{
  "message": "Order created successfully",
  "order": {...},
  "payment": {
    "payment_id": "PAY-ABC123",
    "amount": 1025.00,
    "gateway": "paystack"
  }
}
```

### List My Orders
```http
GET /api/v1/orders/
Authorization: Bearer <token>
```

### Get Order Details
```http
GET /api/v1/orders/{id}/
Authorization: Bearer <token>
```

### Cancel Order
```http
POST /api/v1/orders/{id}/cancel/
Authorization: Bearer <token>
```

## Ticket Endpoints

### List My Tickets
```http
GET /api/v1/tickets/
Authorization: Bearer <token>
```

### Get Ticket Details
```http
GET /api/v1/tickets/{id}/
Authorization: Bearer <token>
```

### Download Ticket
```http
GET /api/v1/tickets/{id}/download/
Authorization: Bearer <token>
```

## Check-in Endpoint

### Check-in Ticket
```http
POST /api/v1/tickets/check-in/
Authorization: Bearer <token>
Content-Type: application/json

{
  "ticket_number": "TKT-ABC123456789"
}

Response:
{
  "message": "Ticket checked in successfully",
  "ticket": {...}
}
```

## User Dashboard

### My Events (Organizer)
```http
GET /api/v1/my/events/
Authorization: Bearer <token>
```

### My Orders
```http
GET /api/v1/my/orders/
Authorization: Bearer <token>
```

### My Tickets
```http
GET /api/v1/my/tickets/
Authorization: Bearer <token>
```

## Payment Webhook

### Payment Webhook (Paystack/Stripe/Flutterwave)
```http
POST /api/v1/payments/webhook/
Content-Type: application/json

{
  "gateway": "paystack",
  "reference": "PAY-ABC123",
  "status": "success",
  ...
}
```

## Response Formats

### Success Response
```json
{
  "message": "Operation successful",
  "data": {...}
}
```

### Error Response
```json
{
  "error": "Error type",
  "message": "Detailed error message",
  "details": {...}
}
```

## Status Codes

- `200 OK` - Successful GET request
- `201 Created` - Successful POST request creating a resource
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Event Status Values

- `draft` - Event is being created
- `published` - Event is live and accepting ticket purchases
- `cancelled` - Event has been cancelled
- `completed` - Event has ended

## Order Status Values

- `pending` - Order created, awaiting payment
- `processing` - Payment being processed
- `completed` - Payment successful, tickets issued
- `cancelled` - Order cancelled
- `refunded` - Order refunded

## Ticket Status Values

- `valid` - Ticket is valid and can be used
- `used` - Ticket has been checked in
- `cancelled` - Ticket cancelled
- `refunded` - Ticket refunded

## Payment Gateways

- `paystack` - Paystack (Ghana, Nigeria)
- `stripe` - Stripe (International)
- `flutterwave` - Flutterwave (Africa)
- `cash` - Cash payment
- `bank_transfer` - Bank transfer
