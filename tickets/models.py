from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
import uuid
from decimal import Decimal
from datetime import timedelta

User = get_user_model()


class Venue(models.Model):
    """Legacy venue model - kept for backwards compatibility but not used in new events"""
    name = models.CharField(max_length=255, help_text="Name of the venue")
    address = models.TextField(help_text="Full address of the venue")
    city = models.CharField(max_length=100, help_text="City where venue is located")
    country = models.CharField(max_length=100, default="Ghana", help_text="Country")
    capacity = models.PositiveIntegerField(
        null=True, blank=True, help_text="Maximum capacity of the venue"
    )
    description = models.TextField(blank=True, help_text="Description of the venue")
    image = models.ImageField(
        upload_to="venues/%Y/%m/",
        blank=True,
        null=True,
        help_text="Venue image"
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Venue"
        verbose_name_plural = "Venues"
        indexes = [
            models.Index(fields=["city"], name="idx_venue_city"),
            models.Index(fields=["country"], name="idx_venue_country"),
        ]

    def __str__(self):
        return f"{self.name} - {self.city}"


class EventCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Category name")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, help_text="Category description")
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name/class for the category (e.g., FaMusic)"
    )
    is_active = models.BooleanField(default=True, help_text="Is category active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Event Category"
        verbose_name_plural = "Event Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_event_count(self):
        """Get count of published events in this category"""
        return self.events.filter(is_published=True).count()


class Event(models.Model):
    """Event model matching the document specification"""

    CHECK_IN_POLICY_CHOICES = [
        ("single_entry", "Single Entry"),
        ("multiple_entry", "Multiple Entry"),
        ("daily_entry", "Daily Entry"),
    ]

    # Basic Information
    title = models.CharField(
        max_length=200,
        help_text="Event title (5-200 characters)"
    )
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(
        help_text="Full event description with markdown support (min 50 chars)"
    )
    short_description = models.CharField(
        max_length=300,
        help_text="Short description for previews (20-300 characters)"
    )

    # Category and Organizer
    category = models.ForeignKey(
        EventCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="events",
        help_text="Event category"
    )
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_events",
        help_text="Event organizer"
    )

    # Payment Profile
    payment_profile = models.ForeignKey(
        "users.PaymentProfile",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
        help_text="Payment profile for receiving event revenue"
    )

    # Venue Information (stored directly on event)
    venue_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Name of the venue"
    )
    venue_address = models.TextField(
        blank=True,
        default="",
        help_text="Full venue address"
    )
    venue_city = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="City where event is located"
    )
    venue_country = models.CharField(
        max_length=100,
        default="Ghana",
        help_text="Country"
    )
    venue_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    venue_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )

    # Images
    featured_image = models.ImageField( 
        upload_to="events/featured/%Y/%m/",
        blank=True,
        null=True,
        help_text="Featured event image (required, max 5MB)"
    )
    additional_images = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional event images (max 5 images)"
    )

    # Date and Time
    start_date = models.DateField(null=True, blank=True, help_text="Event start date")
    end_date = models.DateField(null=True, blank=True, help_text="Event end date")
    start_time = models.TimeField(null=True, blank=True, help_text="Event start time")
    end_time = models.TimeField(null=True, blank=True, help_text="Event end time")

    # Recurring Events
    is_recurring = models.BooleanField(
        default=False,
        help_text="Whether the event repeats on multiple days"
    )
    recurrence_pattern = models.JSONField(
        null=True,
        blank=True,
        help_text="Recurrence pattern (frequency, interval, end_date)"
    )

    # Event Settings
    check_in_policy = models.CharField(
        max_length=20,
        choices=CHECK_IN_POLICY_CHOICES,
        default="single_entry",
        help_text="Check-in policy for tickets"
    )
    max_attendees = models.PositiveIntegerField(
        help_text="Maximum number of attendees"
    )

    # Status
    is_published = models.BooleanField(
        default=True,
        help_text="Whether event is published and visible"
    )

    # Tracking
    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times event was viewed"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Event"
        verbose_name_plural = "Events"
        indexes = [
            models.Index(fields=["slug"], name="idx_event_slug_v2"),
            models.Index(fields=["start_date"], name="idx_event_start_v2"),
            models.Index(fields=["category"], name="idx_event_category_v2"),
            models.Index(fields=["organizer"], name="idx_event_organizer_v2"),
            models.Index(fields=["is_published"], name="idx_event_published"),
            models.Index(fields=["venue_city"], name="idx_event_city"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def status(self):
        """Calculate event status based on dates"""
        if not self.start_date or not self.end_date or not self.start_time or not self.end_time:
            return "upcoming"

        now = timezone.now()
        event_start = timezone.datetime.combine(self.start_date, self.start_time)
        event_end = timezone.datetime.combine(self.end_date, self.end_time)

        # Make timezone aware if needed
        if timezone.is_naive(event_start):
            event_start = timezone.make_aware(event_start)
        if timezone.is_naive(event_end):
            event_end = timezone.make_aware(event_end)

        if now < event_start:
            return "upcoming"
        elif event_start <= now <= event_end:
            return "ongoing"
        else:
            return "past"

    @property
    def is_upcoming(self):
        return self.status == "upcoming"

    @property
    def is_ongoing(self):
        return self.status == "ongoing"

    @property
    def is_past(self):
        return self.status == "past"

    @property
    def tickets_sold(self):
        """Count of tickets that are paid"""
        return self.tickets.filter(status="paid").count()

    @property
    def tickets_available(self):
        return self.max_attendees - self.tickets_sold

    @property
    def is_sold_out(self):
        return self.tickets_sold >= self.max_attendees

    @property
    def lowest_price(self):
        """Get lowest ticket price"""
        ticket_type = self.ticket_types.order_by("price").first()
        return ticket_type.price if ticket_type else Decimal("0.00")

    @property
    def highest_price(self):
        """Get highest ticket price"""
        ticket_type = self.ticket_types.order_by("-price").first()
        return ticket_type.price if ticket_type else Decimal("0.00")

    @property
    def revenue_generated(self):
        """Calculate total revenue generated from ticket sales"""
        from django.db.models import Sum
        total = Purchase.objects.filter(
            event=self,
            status="completed"
        ).aggregate(total=Sum("subtotal"))["total"]
        return total or Decimal("0.00")


class TicketType(models.Model):
    """Ticket types for events"""
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_types",
        help_text="Associated event"
    )
    name = models.CharField(
        max_length=100,
        help_text="Ticket type name (e.g., VIP, Regular, Early Bird)"
    )
    description = models.TextField(
        blank=True,
        help_text="Ticket type description"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("10.00"))],
        help_text="Ticket price (minimum 10.00 GHS)"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1000000)],
        help_text="Total number of tickets available"
    )
    tickets_sold = models.PositiveIntegerField(
        default=0,
        help_text="Number of tickets sold"
    )
    min_purchase = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Minimum tickets per purchase"
    )
    max_purchase = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Maximum tickets per purchase"
    )
    available_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this ticket type becomes available"
    )
    available_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this ticket type stops being available"
    )
    sold_out_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When tickets sold out"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price"]
        verbose_name = "Ticket Type"
        verbose_name_plural = "Ticket Types"
        unique_together = ["event", "name"]

    def __str__(self):
        return f"{self.event.title} - {self.name}"

    @property
    def tickets_remaining(self):
        return self.quantity - self.tickets_sold

    @property
    def is_available(self):
        """Check if ticket type is available for purchase"""
        now = timezone.now()

        # Check if sold out
        if self.tickets_remaining <= 0:
            return False

        # Check availability window
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False

        return True

    @property
    def is_sold_out(self):
        """Check if ticket type is sold out"""
        return self.tickets_remaining <= 0

    @property
    def is_on_sale(self):
        """Check if ticket type is currently on sale"""
        return self.is_available

    @property
    def quantity_remaining(self):
        """Alias for tickets_remaining for backward compatibility"""
        return self.tickets_remaining

    def save(self, *args, **kwargs):
        # Mark as sold out if tickets_remaining hits zero
        if self.tickets_remaining <= 0 and not self.sold_out_at:
            self.sold_out_at = timezone.now()
        super().save(*args, **kwargs)


class Purchase(models.Model):
    """Purchase tracking - represents ticket purchase attempt"""
    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("pending", "Pending Payment"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    purchase_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Unique purchase identifier (PUR-XXXXXX)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="purchases",
        help_text="User who made the purchase"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="purchases",
        help_text="Event for this purchase"
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.CASCADE,
        related_name="purchases",
        help_text="Ticket type purchased"
    )
    quantity = models.PositiveIntegerField(help_text="Number of tickets")

    # Buyer Information
    buyer_name = models.CharField(max_length=255, help_text="Buyer's full name")
    buyer_email = models.EmailField(help_text="Buyer's email address")
    buyer_phone = models.CharField(max_length=20, help_text="Buyer's phone number")

    # Pricing
    ticket_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per ticket at time of purchase"
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Subtotal (price × quantity)"
    )
    service_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Service fee (5%)"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount to pay"
    )

    # Status and Timing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="reserved",
        help_text="Purchase status"
    )
    reserved_at = models.DateTimeField(auto_now_add=True)
    reservation_expires_at = models.DateTimeField(
        help_text="When reservation expires (10 minutes from creation)"
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Purchase"
        verbose_name_plural = "Purchases"
        indexes = [
            models.Index(fields=["purchase_id"], name="idx_purchase_id"),
            models.Index(fields=["user"], name="idx_purchase_user"),
            models.Index(fields=["status"], name="idx_purchase_status"),
        ]

    def __str__(self):
        return f"Purchase {self.purchase_id} - {self.buyer_name}"

    def save(self, *args, **kwargs):
        if not self.purchase_id:
            self.purchase_id = f"PUR-{uuid.uuid4().hex[:10].upper()}"

        # Set reservation expiry (10 minutes from now)
        if not self.reservation_expires_at:
            self.reservation_expires_at = timezone.now() + timedelta(minutes=10)

        # Track if this is a status change to completed
        is_new_completion = False
        if self.pk:
            try:
                old_purchase = Purchase.objects.get(pk=self.pk)
                if old_purchase.status != "completed" and self.status == "completed":
                    is_new_completion = True
            except Purchase.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Create revenue record when purchase is completed
        if is_new_completion:
            self._create_revenue_record()

    def _create_revenue_record(self):
        """Create revenue record for the organizer when purchase is completed"""
        from decimal import Decimal
        
        # Calculate platform commission (5%)
        platform_commission_rate = Decimal('0.05')  # 5%
        platform_fee = self.subtotal * platform_commission_rate
        
        # Organizer gets 95% of subtotal (subtotal - 5% commission)
        organizer_earnings = self.subtotal - platform_fee
        
        # Create revenue record
        OrganizerRevenue.objects.create(
            organizer=self.event.organizer,
            event=self.event,
            purchase=self,
            ticket_sales_amount=self.subtotal,
            platform_fee=platform_fee,
            organizer_earnings=organizer_earnings,
            status='pending'  # Will become 'available' after 7 days
        )

    @property
    def is_expired(self):
        """Check if reservation has expired"""
        return timezone.now() > self.reservation_expires_at and self.status == "reserved"


class Payment(models.Model):
    """Payment tracking for purchases"""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    PROVIDER_CHOICES = [
        ("paystack", "Paystack"),
    ]

    payment_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Unique payment identifier (PAY-XXXXXX)"
    )
    purchase = models.OneToOneField(
        Purchase,
        on_delete=models.CASCADE,
        related_name="payment",
        help_text="Associated purchase"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Payment amount"
    )
    currency = models.CharField(
        max_length=3,
        default="GHS",
        help_text="Currency code"
    )
    payment_method = models.CharField(
        max_length=50,
        default="card",
        help_text="Payment method used (card, mobile_money, bank_transfer)"
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default="paystack",
        help_text="Payment gateway provider"
    )
    reference = models.CharField(
        max_length=255,
        unique=True,
        help_text="Payment gateway reference (e.g., PSK-XYZ123)"
    )
    payment_url = models.URLField(
        blank=True,
        help_text="Payment gateway URL for customer"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Payment status"
    )
    provider_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full provider response data"
    )
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for payment failure"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=["payment_id"], name="idx_payment_id_v2"),
            models.Index(fields=["reference"], name="idx_payment_reference"),
            models.Index(fields=["status"], name="idx_payment_status_v2"),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} - {self.provider}"

    def save(self, *args, **kwargs):
        if not self.payment_id:
            self.payment_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)


class Ticket(models.Model):
    """Individual ticket issued after successful payment"""
    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
        ("used", "Used"),
        ("expired", "Expired"),
    ]

    ticket_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Unique ticket identifier (TKT-UUID-XXX)"
    )
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="tickets",
        help_text="Associated purchase"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="tickets",
        help_text="Event this ticket is for"
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="tickets",
        help_text="Type of ticket"
    )

    # Attendee Information
    attendee_name = models.CharField(
        max_length=255,
        help_text="Name of the ticket holder"
    )
    attendee_email = models.EmailField(
        help_text="Email of the ticket holder"
    )
    attendee_phone = models.CharField(
        max_length=20,
        help_text="Phone of the ticket holder"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price paid for this ticket",
        default=Decimal('0.00')
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="reserved",
        help_text="Ticket status"
    )

    # QR Code
    qr_code = models.ImageField(
        upload_to="tickets/qr_codes/%Y/%m/",
        blank=True,
        null=True,
        help_text="QR code for ticket validation"
    )

    # Check-in
    is_checked_in = models.BooleanField(
        default=False,
        help_text="Whether ticket has been checked in"
    )
    checked_in_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was checked in"
    )
    checked_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_in_tickets",
        help_text="Staff who checked in this ticket"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        indexes = [
            models.Index(fields=["ticket_id"], name="idx_ticket_id_v2"),
            models.Index(fields=["event"], name="idx_ticket_event_v2"),
            models.Index(fields=["status"], name="idx_ticket_status_v2"),
            models.Index(fields=["purchase"], name="idx_ticket_purchase"),
        ]

    def __str__(self):
        return f"Ticket {self.ticket_id} - {self.attendee_name}"

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TKT-{uuid.uuid4().hex.upper()}"
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Check if ticket is valid for entry"""
        return self.status == "paid" and not self.is_checked_in

    @property
    def can_check_in(self):
        """Check if ticket can be checked in"""
        if self.status != "paid":
            return False
        if self.is_checked_in:
            return False
        return True

    @property
    def ticket_number(self):
        """Alias for ticket_id for backward compatibility"""
        return self.ticket_id

    def generate_qr_code(self):
        """Generate QR code for ticket"""
        import qrcode
        from io import BytesIO
        from django.core.files import File
        import json
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # QR code contains ticket information
        qr_data = {
            'ticket_id': self.ticket_id,
            'event_id': str(self.event.id),
            'attendee_name': self.attendee_name,
        }
        
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Save to model
        filename = f"ticket_{self.ticket_id}.png"
        self.qr_code.save(filename, File(buffer), save=True)
        
        return self.qr_code


# Legacy models kept for backwards compatibility
class Order(models.Model):
    """Legacy order model - kept for backwards compatibility"""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    order_id = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="Unique order identifier"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
        help_text="User who placed the order"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="orders",
        help_text="Event for this order"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total order amount"
    )
    service_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Service fee"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Order status"
    )
    buyer_email = models.EmailField(help_text="Buyer's email address")
    buyer_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Buyer's phone number"
    )
    buyer_name = models.CharField(max_length=255, help_text="Buyer's full name")
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment method used"
    )
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="External payment reference"
    )
    notes = models.TextField(blank=True, help_text="Additional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order was completed"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["order_id"], name="idx_order_id"),
            models.Index(fields=["user"], name="idx_order_user"),
            models.Index(fields=["event"], name="idx_order_event"),
            models.Index(fields=["status"], name="idx_order_status"),
            models.Index(fields=["created_at"], name="idx_order_created"),
        ]

    def __str__(self):
        return f"Order {self.order_id} - {self.buyer_name}"

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_tickets(self):
        return self.tickets.count()

    @property
    def grand_total(self):
        total = self.total_amount or Decimal("0.00")
        fee = self.service_fee or Decimal("0.00")
        return total + fee


class EventReview(models.Model):
    """Event reviews"""
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="reviews",
        help_text="Event being reviewed"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="event_reviews",
        help_text="User who wrote the review"
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5"
    )
    comment = models.TextField(blank=True, help_text="Review comment")
    is_verified_purchase = models.BooleanField(
        default=False,
        help_text="User attended the event"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Event Review"
        verbose_name_plural = "Event Reviews"
        unique_together = ["event", "user"]

    def __str__(self):
        return f"{self.user.email} - {self.event.title} ({self.rating}/5)"

class ContactMessage(models.Model):
    """Contact form submissions"""
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed')
        ],
        default='new'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(blank=True, null=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
    
    def __str__(self):
        return f"{self.name} - {self.subject}"


class NewsletterSubscription(models.Model):
    """Newsletter email subscriptions"""
    email = models.EmailField(unique=True)
    
    # Subscription details
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    
    # Tracking
    confirmation_token = models.CharField(max_length=100, blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    
    # Source tracking
    source = models.CharField(
        max_length=50,
        choices=[
            ('homepage', 'Homepage'),
            ('footer', 'Footer'),
            ('event_page', 'Event Page'),
            ('checkout', 'Checkout'),
            ('other', 'Other')
        ],
        default='homepage'
    )
    
    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = 'Newsletter Subscription'
        verbose_name_plural = 'Newsletter Subscriptions'
    
    def __str__(self):
        return self.email

class OrganizerRevenue(models.Model):
    """Track revenue earned by event organizers"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="revenue_records",
        help_text="Event organizer"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="revenue_records",
        help_text="Event that generated this revenue"
    )
    purchase = models.ForeignKey(
        'Purchase',
        on_delete=models.CASCADE,
        related_name="revenue_record",
        help_text="Purchase that generated this revenue"
    )
    
    # Revenue breakdown
    ticket_sales_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total from ticket sales (subtotal)"
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Platform service fee deducted"
    )
    organizer_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Net earnings for organizer (ticket_sales - platform_fee)"
    )
    
    # Withdrawal tracking
    is_withdrawn = models.BooleanField(
        default=False,
        help_text="Whether this revenue has been withdrawn"
    )
    withdrawal = models.ForeignKey(
        'WithdrawalRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenue_items",
        help_text="Withdrawal request this revenue is part of"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('available', 'Available for Withdrawal'),
            ('withdrawn', 'Withdrawn'),
            ('on_hold', 'On Hold'),
        ],
        default='pending',
        help_text="Revenue status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    available_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When revenue becomes available for withdrawal (e.g., 7 days after purchase)"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organizer Revenue'
        verbose_name_plural = 'Organizer Revenue'
        indexes = [
            models.Index(fields=['organizer'], name='idx_revenue_organizer'),
            models.Index(fields=['event'], name='idx_revenue_event'),
            models.Index(fields=['status'], name='idx_revenue_status'),
            models.Index(fields=['is_withdrawn'], name='idx_revenue_withdrawn'),
        ]
    
    def __str__(self):
        return f"{self.organizer.email} - {self.event.title} - GHS {self.organizer_earnings}"
    
    def save(self, *args, **kwargs):
        # Set available_at to 7 days from creation (configurable)
        if not self.available_at:
            from datetime import timedelta
            self.available_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)


class WithdrawalRequest(models.Model):
    """Withdrawal requests from organizers"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    withdrawal_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Unique withdrawal identifier (WDR-XXXXXX)"
    )
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="withdrawal_requests",
        help_text="Organizer requesting withdrawal"
    )
    payment_profile = models.ForeignKey(
        'users.PaymentProfile',
        on_delete=models.PROTECT,
        related_name="withdrawals",
        help_text="Bank account to receive funds"
    )
    
    # Amount
    requested_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount requested by organizer"
    )
    transfer_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Bank transfer fee (deducted from requested amount)"
    )
    final_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final amount to be transferred (requested_amount - transfer_fee)"
    )
    
    # Status and processing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Withdrawal status"
    )
    
    # Paystack transfer details
    transfer_code = models.CharField(
        max_length=255,
        blank=True,
        help_text="Paystack transfer code"
    )
    transfer_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Paystack transfer reference"
    )
    transfer_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full Paystack response"
    )
    
    # Admin review
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_withdrawals",
        help_text="Admin who reviewed this request"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was reviewed"
    )
    admin_notes = models.TextField(
        blank=True,
        help_text="Admin notes about this withdrawal"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if rejected)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When withdrawal was completed"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Withdrawal Request'
        verbose_name_plural = 'Withdrawal Requests'
        indexes = [
            models.Index(fields=['withdrawal_id'], name='idx_withdrawal_id'),
            models.Index(fields=['organizer'], name='idx_withdrawal_organizer'),
            models.Index(fields=['status'], name='idx_withdrawal_status'),
        ]
    
    def __str__(self):
        return f"{self.withdrawal_id} - {self.organizer.email} - GHS {self.requested_amount}"
    
    def save(self, *args, **kwargs):
        if not self.withdrawal_id:
            self.withdrawal_id = f"WDR-{uuid.uuid4().hex[:10].upper()}"
        
        # Calculate final amount
        self.final_amount = self.requested_amount - self.transfer_fee
        
        super().save(*args, **kwargs)
    
    def calculate_transfer_fee(self):
        """Calculate Paystack transfer fee for bank transfers"""
        # Paystack Ghana charges:
        # - Free for transfers below GHS 5,000
        # - GHS 10 flat fee for transfers GHS 5,000 and above
        
        if self.requested_amount >= Decimal('5000.00'):
            return Decimal('10.00')
        else:
            return Decimal('0.00')  # Free for amounts below GHS 5,000
    
    def can_approve(self):
        """Check if withdrawal can be approved"""
        return self.status == 'pending'
    
    def can_reject(self):
        """Check if withdrawal can be rejected"""
        return self.status in ['pending', 'approved']
    
    def can_process(self):
        """Check if withdrawal can be processed"""
        return self.status == 'approved'