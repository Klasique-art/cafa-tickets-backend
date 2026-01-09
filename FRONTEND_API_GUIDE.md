# Cafa Tickets API - Frontend Integration Guide

**Base URL:** `http://localhost:8000/api/v1/`  
**Production URL:** `https://api.cafaticket.com/api/v1/`

---

## Quick Start

### Authentication Header
```javascript
headers: {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
}
```

---

## 1. AUTHENTICATION

### 1.1 Register
`POST /auth/users/`
```json
Request:
{
  "email": "user@example.com",
  "username": "username",
  "password": "SecurePass123!",
  "re_password": "SecurePass123!",
  "full_name": "John Doe"
}
```

### 1.2 Login
`POST /auth/login/`
```json
Request:
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response:
{
  "user": {...},
  "tokens": {
    "access": "...",
    "refresh": "..."
  }
}
```

### 1.3 Refresh Token
`POST /auth/jwt/refresh/`

---

## 2. USER PROFILE

### 2.1 Get Profile
`GET /auth/profile/` 🔒

### 2.2 Update Profile
`PATCH /auth/profile/` 🔒
- Supports multipart/form-data for profile image

### 2.3 Get User Stats
`GET /auth/users/stats/` 🔒
Returns:
- Tickets purchased
- Events organized  
- Total spent/revenue
- Active tickets

---

## 3. EVENT CATEGORIES

### 3.1 List Categories
`GET /event-categories/`
Returns all categories with event counts and icons (for react-icons).

---

## 4. EVENTS

### 4.1 Browse Events
`GET /events/`

**Query Params:**
- `category=music` - Filter by slug
- `search=concert` - Search term
- `city=Accra` - Filter by city
- `date_from=2025-07-01` - Date range start
- `date_to=2025-07-31` - Date range end
- `price_min=50` - Min price filter
- `price_max=200` - Max price filter
- `ordering=-start_date` - Sort (start_date, -start_date, price, -price)
- `status=upcoming` - upcoming | ongoing | all
- `page=1&page_size=20` - Pagination

### 4.2 Past Events
`GET /events/past/`
Same query params as above (except status).

### 4.3 Event Details
`GET /events/{slug}/` or `GET /events/{id}/`
Returns full event details with ticket types, organizer info, similar events.

### 4.4 Create Event
`POST /events/create/` 🔒
Content-Type: multipart/form-data

Required fields:
- title, category_id, description, short_description
- venue_name, venue_city, start_date, start_time
- max_attendees, payment_profile_id, featured_image
- ticket_types (JSON array)

### 4.5 Update Event
`PATCH /events/{id}/update/` 🔒

### 4.6 My Events
`GET /events/my-events/` 🔒
Query: `status=upcoming|ongoing|past|all`

### 4.7 My Event Details
`GET /events/my-events/{slug_or_id}/` 🔒
Returns detailed event with analytics.

---

## 5. TICKET PURCHASE

### 5.1 Initiate Purchase
`POST /tickets/purchase/` 🔒

```json
{
  "event_id": 1,
  "ticket_type_id": 1,
  "quantity": 2,
  "attendee_info": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+233241234567"
  },
  "payment_method": "card"
}
```

**Response includes:**
- purchase_id
- tickets (reserved for 10 min)
- payment object with payment_url
- pricing breakdown

**Next Step:** Redirect user to `payment.payment_url`

### 5.2 Check Payment Status
`GET /payments/{payment_id}/status/` 🔒

**Poll every 3 seconds** after payment redirect.

Statuses:
- `completed` - Success! Show tickets
- `pending` - Still processing, keep polling
- `failed` - Payment failed

### 5.3 Cancel Purchase
`POST /tickets/purchase/{purchase_id}/cancel/` 🔒

### 5.4 Resend Tickets Email
`POST /payments/{payment_id}/resend-tickets/` 🔒

---

## 6. TICKET MANAGEMENT

### 6.1 My Tickets
`GET /tickets/my-tickets/` 🔒

Query Params:
- `status=active|used|expired|all`
- `search=event name`
- `category_id=1`

### 6.2 Ticket Details
`GET /tickets/{ticket_id}/` 🔒

### 6.3 Download Ticket PDF
`GET /tickets/{ticket_id}/download/` 🔒
Returns PDF file.

### 6.4 Attended Events
`GET /tickets/attended-events/` 🔒
Shows checked-in events.

---

## 7. PAYMENT PROFILES (Organizers)

### 7.1 Create Profile
`POST /auth/users/payment-profile/` 🔒


**Bank Transfer:**
```json
{
  "method": "bank_transfer",
  "name": "Cal Bank",
  "description": "Secondary",
  "account_details": {
    "account_number": "1234567890",
    "account_name": "John Doe",
    "bank_name": "CAL Bank",
    "bank_code": "140100"
  }
}
```

**Verification:** 1 GHS is deducted for verification (1-2 mins).

### 7.2 List Profiles
`GET /auth/users/payment-profile/` 🔒

### 7.3 Update Profile
`PATCH /auth/users/payment-profile/{id}/` 🔒

### 7.4 Delete Profile
`DELETE /auth/users/payment-profile/{id}/` 🔒

### 7.5 Set Default
`POST /auth/users/payment-profile/{id}/set-default/` 🔒

### 7.6 Check Verification Status
`GET /auth/users/payment-profile/{id}/verification-status/` 🔒

**Poll every 5 seconds** after profile creation.

### 7.7 Retry Verification
`POST /auth/users/payment-profile/{id}/retry-verification/` 🔒
Costs another 1 GHS.

---

## 8. ANALYTICS (Organizers)

### 8.1 Event Analytics
`GET /events/{id}/analytics/` 🔒
Returns sales metrics, revenue, check-in stats.

### 8.2 Event Attendees
`GET /events/{id}/attendees/` 🔒

Query Params:
- `search=name`
- `ticket_type_id=1`
- `check_in_status=checked_in|not_checked_in|all`

### 8.3 Check-in Attendee
`POST /events/{id}/checkin/` 🔒

```json
{
  "ticket_id": "TKT-UUID-001"
}
```

---

## IMPLEMENTATION EXAMPLES

### Payment Flow
```javascript
// 1. Initiate purchase
const response = await fetch('/api/v1/tickets/purchase/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(purchaseData)
});

const data = await response.json();

// 2. Store payment_id
sessionStorage.setItem('payment_id', data.payment.payment_id);

// 3. Redirect to Paystack
window.location.href = data.payment.payment_url;

// 4. On callback page, poll status
const checkPayment = setInterval(async () => {
  const status = await fetch(`/api/v1/payments/${paymentId}/status/`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const result = await status.json();
  
  if (result.status === 'completed') {
    clearInterval(checkPayment);
    // Show success + tickets
  }
}, 3000);
```

### File Upload
```javascript
const formData = new FormData();
formData.append('title', 'Event Title');
formData.append('featured_image', fileInput.files[0]);
formData.append('ticket_types', JSON.stringify([...]));

fetch('/api/v1/events/create/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
    // Don't set Content-Type for FormData
  },
  body: formData
});
```

---

## ERROR RESPONSES

All errors follow this format:
```json
{
  "error": "Error type",
  "message": "Human-readable message",
  "details": {
    "field": ["Error details"]
  }
}
```

**Status Codes:**
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limited
- `500` - Server Error

---

## NOTES

1. **Currency:** All prices are in GHS (Ghanaian Cedis)
2. **Image URLs:** Returned URLs are relative - prepend base URL
3. **Pagination:** Standard format with count, next, previous, results
4. **Slug vs ID:** Most endpoints support both
5. **Reserved Tickets:** Expire after 10 minutes

🔒 = Requires Authentication

---

**Last Updated:** December 2025  
**API Version:** 1.0
