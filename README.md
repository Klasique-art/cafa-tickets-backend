# Cafa Tickets - Complete Event Ticketing System

A comprehensive Django REST API backend for event ticketing and management.

## Features

### Event Management
- Create and manage events with detailed information
- Event categories and venues
- Event status tracking (draft, published, cancelled, completed)
- Public and private events
- Featured events
- Event reviews and ratings
- Event analytics and statistics

### Ticketing System
- Multiple ticket types per event (VIP, Regular, Early Bird, etc.)
- Inventory management with real-time availability
- Min/max purchase limits per ticket type
- Ticket sales scheduling (start/end dates)
- QR code generation for ticket validation
- Ticket check-in system

### Order Processing
- Complete order management system
- Service fee calculation (2.5% default)
- Order status tracking
- Order cancellation with inventory restoration
- Email confirmations

### Payment Integration
- Multiple payment gateway support:
  - Paystack (Ghana, Nigeria)
  - Stripe (International)
  - Flutterwave (Africa)
- Webhook handling for payment verification
- Cash and bank transfer options

### User Features
- JWT authentication
- User profiles
- User dashboard (my events, orders, tickets)
- Email notifications
- Event organizer dashboard with analytics

### Admin Features
- Comprehensive Django admin interface
- Color-coded status badges
- Advanced filtering and search
- Inline editing
- QR code preview
- Sales statistics

## Technology Stack

- **Framework**: Django 5.2.9
- **API**: Django REST Framework 3.16.1
- **Authentication**: JWT (Simple JWT 5.5.1)
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **Image Handling**: Pillow 12.0.0
- **QR Codes**: qrcode 8.2
- **CORS**: django-cors-headers 4.9.0
- **User Auth**: Djoser 2.3.3

## Installation

### Prerequisites
- Python 3.11+
- pip
- virtualenv (recommended)

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd cafa-ticket
```

2. **Create virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment variables**
```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your settings
# IMPORTANT: Add your payment gateway keys
```

5. **Run migrations**
```bash
python manage.py migrate
```

6. **Create superuser**
```bash
python manage.py createsuperuser
```

7. **Create sample data (optional)**
```bash
python manage.py test_system
```

8. **Run development server**
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/v1/`
Admin panel at `http://localhost:8000/admin/`

## Project Structure

```
cafa-ticket/
├── cafa_ticket/          # Project settings
│   ├── settings.py       # Django settings
│   ├── urls.py          # Main URL configuration
│   └── wsgi.py          # WSGI config
├── users/               # User management app
│   ├── models.py        # Custom user model
│   ├── serializers.py   # User serializers
│   ├── views.py         # Auth views
│   └── backends.py      # Email authentication
├── tickets/             # Main ticketing app
│   ├── models.py        # Event, Ticket, Order models
│   ├── serializers.py   # API serializers
│   ├── views.py         # API views
│   ├── admin.py         # Admin configuration
│   ├── urls.py          # URL routing
│   ├── utils.py         # Helper functions
│   ├── permissions.py   # Custom permissions
│   ├── signals.py       # Signal handlers
│   └── management/
│       └── commands/
│           └── test_system.py  # System test command
├── media/               # User uploaded files
├── staticfiles/         # Static files
├── requirements.txt     # Python dependencies
├── .env                # Environment variables
├── .env.example        # Example env file
├── API_DOCUMENTATION.md # Complete API docs
└── README.md           # This file
```

## Models Overview

### Event System
- **Venue**: Event locations with geolocation
- **EventCategory**: Event categorization
- **Event**: Main event model with full details
- **TicketType**: Different ticket tiers per event

### Ticketing
- **Order**: Customer orders with payment info
- **Ticket**: Individual tickets with QR codes
- **Payment**: Payment transactions

### Reviews
- **EventReview**: Event ratings and reviews

## API Endpoints

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete API documentation.

### Quick Reference

**Authentication**
- `POST /api/v1/auth/users/` - Register
- `POST /api/v1/auth/login/` - Login
- `GET /api/v1/auth/profile/` - Get profile

**Events**
- `GET /api/v1/events/` - List events
- `POST /api/v1/events/` - Create event
- `GET /api/v1/events/{slug}/` - Event details
- `GET /api/v1/featured/` - Featured events
- `GET /api/v1/upcoming/` - Upcoming events

**Orders**
- `POST /api/v1/orders/create/` - Create order
- `GET /api/v1/orders/` - List orders
- `POST /api/v1/orders/{id}/cancel/` - Cancel order

**Tickets**
- `GET /api/v1/tickets/` - List tickets
- `POST /api/v1/tickets/check-in/` - Check-in ticket

## Configuration

### Email Settings
Configure in `.env`:
```env
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

### Payment Gateways

**Paystack** (Recommended for Ghana/Nigeria)
```env
PAYSTACK_SECRET_KEY=sk_test_your_secret_key
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key
```

**Stripe** (International)
```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLIC_KEY=pk_test_your_public_key
```

**Flutterwave** (Africa)
```env
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your_secret_key
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your_public_key
```

## Testing

Run the system test:
```bash
python manage.py test_system
```

This will:
- Check all models are accessible
- Verify user system is working
- Create sample categories and venues
- Display system statistics

## Development

### Creating Sample Events

1. Login to admin panel: `http://localhost:8000/admin/`
2. Create event categories and venues
3. Create events with ticket types
4. Test order creation via API

### Running in Development

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run server
python manage.py runserver

# Run with different port
python manage.py runserver 8001
```

## Production Deployment

### Checklist

1. **Environment Variables**
   - Set `DEBUG=False`
   - Generate new `SECRET_KEY`
   - Configure `ALLOWED_HOSTS`
   - Add production payment keys

2. **Database**
   - Switch to PostgreSQL
   - Run migrations
   - Create superuser

3. **Static Files**
   ```bash
   python manage.py collectstatic
   ```

4. **Security Settings**
   - Enable HTTPS
   - Set SECURE_SSL_REDIRECT=True
   - Set SESSION_COOKIE_SECURE=True
   - Set CSRF_COOKIE_SECURE=True

5. **Media Files**
   - Configure cloud storage (AWS S3, Cloudinary)
   - Or set up nginx to serve media files

## Management Commands

### test_system
Test the entire system and create sample data:
```bash
python manage.py test_system
```

## Troubleshooting

### Common Issues

**Migration errors**
```bash
python manage.py migrate --run-syncdb
```

**Port already in use**
```bash
python manage.py runserver 8001
```

**Media files not loading**
- Check MEDIA_URL and MEDIA_ROOT in settings
- Ensure DEBUG=True for development

**Payment webhook not working**
- Use ngrok for local testing
- Verify webhook URLs in payment gateway dashboard

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Email: support@cafaticket.com

## License

This project is proprietary software. All rights reserved.

## Acknowledgments

- Django and Django REST Framework communities
- Payment gateway providers
- All contributors

---

**Built with ❤️ for event organizers in Ghana and Africa**
