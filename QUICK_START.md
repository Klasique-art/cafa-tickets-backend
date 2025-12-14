# Quick Start Guide - Cafa Tickets

Get up and running in 5 minutes!

## 1. Environment Setup (Already Done ✅)

The system is already set up and configured. Here's what's ready:

- ✅ Virtual environment activated
- ✅ All dependencies installed
- ✅ Database migrations applied
- ✅ Sample data created (5 categories, 2 venues)
- ✅ Superuser exists (eritten2@gmail.com / admin)

## 2. Start the Server

```bash
python manage.py runserver
```

The server will start at `http://localhost:8000`

## 3. Access the System

### Admin Panel
```
URL: http://localhost:8000/admin/
Username: admin
Email: eritten2@gmail.com
Password: [your password]
```

### API Base URL
```
http://localhost:8000/api/v1/
```

## 4. Test the API

### Get JWT Token (Login)
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "eritten2@gmail.com",
    "password": "your-password"
  }'
```

Response:
```json
{
  "message": "Login successful",
  "user": {...},
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

### List Events
```bash
curl http://localhost:8000/api/v1/events/
```

### List Categories
```bash
curl http://localhost:8000/api/v1/categories/
```

### List Venues
```bash
curl http://localhost:8000/api/v1/venues/
```

## 5. Create Your First Event

### Step 1: Login to Admin
1. Go to `http://localhost:8000/admin/`
2. Login with your credentials
3. Navigate to "Events" → "Add Event"

### Step 2: Fill Event Details
- **Title**: My First Concert
- **Description**: An amazing music event
- **Category**: Select from dropdown (e.g., Concert)
- **Venue**: Select from dropdown (e.g., Accra International Conference Centre)
- **Banner Image**: Upload an image
- **Start Date**: Select future date/time
- **End Date**: Select future date/time (after start)
- **Status**: Published
- **Privacy**: Public

### Step 3: Add Ticket Types
Scroll down to "Ticket types" section and add:
- **Name**: VIP
- **Price**: 500.00
- **Quantity**: 50
- **Is active**: ✓

Click "Save"

## 6. Test Order Creation (API)

### Create an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/create/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
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
            "email": "john@example.com"
          },
          {
            "name": "Jane Doe",
            "email": "jane@example.com"
          }
        ]
      }
    ]
  }'
```

## 7. View Your Data

### In Admin Panel
- **Dashboard**: See all events, orders, tickets
- **Events**: Manage events and ticket types
- **Orders**: View all orders and their status
- **Tickets**: See individual tickets with QR codes

### Via API
```bash
# List my orders
curl http://localhost:8000/api/v1/my/orders/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# List my tickets
curl http://localhost:8000/api/v1/my/tickets/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# List my events (as organizer)
curl http://localhost:8000/api/v1/my/events/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 8. Test Ticket Check-in

```bash
curl -X POST http://localhost:8000/api/v1/tickets/check-in/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "ticket_number": "TKT-ABC123456789"
  }'
```

## 9. Configure Payment Gateways

### Edit .env file
```env
# Paystack (Ghana/Nigeria)
PAYSTACK_SECRET_KEY=sk_test_your_secret_key
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key

# Get keys from: https://dashboard.paystack.com/settings/developer
```

### Stripe (International)
```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLIC_KEY=pk_test_your_public_key

# Get keys from: https://dashboard.stripe.com/test/apikeys
```

### Flutterwave (Africa)
```env
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your_secret_key
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your_public_key

# Get keys from: https://dashboard.flutterwave.com/settings/apis
```

## 10. Common Commands

### Run System Test
```bash
python manage.py test_system
```

### Create Superuser
```bash
python manage.py createsuperuser
```

### Make Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Collect Static Files
```bash
python manage.py collectstatic
```

### Run on Different Port
```bash
python manage.py runserver 8001
```

## 11. Explore the API

Full API documentation: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)

### Key Endpoints:
- 🔐 **Auth**: `/api/v1/auth/`
- 🎫 **Events**: `/api/v1/events/`
- 🎟️ **Tickets**: `/api/v1/tickets/`
- 📦 **Orders**: `/api/v1/orders/`
- 📍 **Venues**: `/api/v1/venues/`
- 🏷️ **Categories**: `/api/v1/categories/`

## 12. Frontend Integration

### CORS is Already Configured
The API accepts requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

Add more origins in `cafa_ticket/settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://your-frontend-domain.com",
]
```

### Example Frontend Request (JavaScript)
```javascript
// Login
const response = await fetch('http://localhost:8000/api/v1/auth/login/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password123'
  })
});

const data = await response.json();
const accessToken = data.tokens.access;

// Get Events
const eventsResponse = await fetch('http://localhost:8000/api/v1/events/', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});

const events = await eventsResponse.json();
```

## 🎉 You're All Set!

The system is fully operational and ready for:
- ✅ Creating events
- ✅ Selling tickets
- ✅ Processing orders
- ✅ Managing check-ins
- ✅ Generating revenue

## 📚 Need More Help?

- **Full Documentation**: [README.md](./README.md)
- **API Reference**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

---

**Happy Ticketing! 🎫**
