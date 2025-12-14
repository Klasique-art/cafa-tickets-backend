from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
import uuid
from decimal import Decimal

User = get_user_model()


class Venue(models.Model):
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
        help_text="Icon name/class for the category"
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


class Event(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    PRIVACY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
    ]

    title = models.CharField(max_length=255, help_text="Event title")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(help_text="Detailed event description")
    short_description = models.CharField(
        max_length=500,
        blank=True,
        help_text="Short description for previews"
    )

    category = models.ForeignKey(
        EventCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="events",
        help_text="Event category"
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        help_text="Event venue"
    )

    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_events",
        help_text="Event organizer"
    )

    banner_image = models.ImageField(
        upload_to="events/banners/%Y/%m/",
        help_text="Event banner image"
    )
    thumbnail_image = models.ImageField(
        upload_to="events/thumbnails/%Y/%m/",
        blank=True,
        null=True,
        help_text="Event thumbnail image"
    )

    start_date = models.DateTimeField(help_text="Event start date and time")
    end_date = models.DateTimeField(help_text="Event end date and time")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Event status"
    )
    privacy = models.CharField(
        max_length=20,
        choices=PRIVACY_CHOICES,
        default="public",
        help_text="Event privacy setting"
    )

    is_featured = models.BooleanField(
        default=False,
        help_text="Show event in featured section"
    )
    is_free = models.BooleanField(
        default=False,
        help_text="Is this a free event"
    )

    max_attendees = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of attendees (null = unlimited)"
    )

    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags for the event"
    )

    external_url = models.URLField(
        blank=True,
        help_text="External event URL (if applicable)"
    )

    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Event-specific terms and conditions"
    )

    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times event was viewed"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Event"
        verbose_name_plural = "Events"
        indexes = [
            models.Index(fields=["slug"], name="idx_event_slug"),
            models.Index(fields=["status"], name="idx_event_status"),
            models.Index(fields=["start_date"], name="idx_event_start"),
            models.Index(fields=["category"], name="idx_event_category"),
            models.Index(fields=["organizer"], name="idx_event_organizer"),
            models.Index(fields=["is_featured"], name="idx_event_featured"),
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
    def is_upcoming(self):
        return self.start_date > timezone.now()

    @property
    def is_ongoing(self):
        return self.start_date <= timezone.now() <= self.end_date

    @property
    def is_past(self):
        return self.end_date < timezone.now()

    @property
    def tickets_sold(self):
        return self.tickets.filter(
            order__status="completed"
        ).count()

    @property
    def tickets_available(self):
        if self.max_attendees:
            return self.max_attendees - self.tickets_sold
        return None

    @property
    def is_sold_out(self):
        if self.max_attendees:
            return self.tickets_sold >= self.max_attendees
        return False

    @property
    def revenue_generated(self):
        from django.db.models import Sum
        total = self.orders.filter(
            status="completed"
        ).aggregate(Sum("total_amount"))["total_amount__sum"]
        return total or Decimal("0.00")


class TicketType(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_types",
        help_text="Associated event"
    )
    name = models.CharField(max_length=100, help_text="Ticket type name (e.g., VIP, Regular)")
    description = models.TextField(blank=True, help_text="Ticket type description")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Ticket price"
    )
    quantity = models.PositiveIntegerField(help_text="Total number of tickets available")
    quantity_sold = models.PositiveIntegerField(
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
    sale_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket sales start"
    )
    sale_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket sales end"
    )
    is_active = models.BooleanField(default=True, help_text="Is ticket type available for sale")
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
    def quantity_remaining(self):
        return self.quantity - self.quantity_sold

    @property
    def is_sold_out(self):
        return self.quantity_sold >= self.quantity

    @property
    def is_on_sale(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.sale_start and now < self.sale_start:
            return False
        if self.sale_end and now > self.sale_end:
            return False
        return not self.is_sold_out


class Order(models.Model):
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
            self.order_id = self.generate_order_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_order_id():
        return f"ORD-{uuid.uuid4().hex[:12].upper()}"

    @property
    def total_tickets(self):
        return self.tickets.count()

    @property
    def grand_total(self):
        return self.total_amount + self.service_fee


class Ticket(models.Model):
    STATUS_CHOICES = [
        ("valid", "Valid"),
        ("used", "Used"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    ticket_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="Unique ticket identifier"
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="tickets",
        help_text="Associated order"
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

    attendee_name = models.CharField(
        max_length=255,
        help_text="Name of the ticket holder"
    )
    attendee_email = models.EmailField(
        blank=True,
        help_text="Email of the ticket holder"
    )
    attendee_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone of the ticket holder"
    )

    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price paid for this ticket"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="valid",
        help_text="Ticket status"
    )

    qr_code = models.ImageField(
        upload_to="tickets/qr_codes/%Y/%m/",
        blank=True,
        null=True,
        help_text="QR code for ticket validation"
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        indexes = [
            models.Index(fields=["ticket_number"], name="idx_ticket_number"),
            models.Index(fields=["order"], name="idx_ticket_order"),
            models.Index(fields=["event"], name="idx_ticket_event"),
            models.Index(fields=["status"], name="idx_ticket_status"),
        ]

    def __str__(self):
        return f"Ticket {self.ticket_number} - {self.attendee_name}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_ticket_number():
        return f"TKT-{uuid.uuid4().hex[:16].upper()}"

    @property
    def is_valid(self):
        return self.status == "valid" and not self.checked_in_at

    @property
    def can_check_in(self):
        if self.status != "valid":
            return False
        if self.checked_in_at:
            return False
        return self.event.start_date <= timezone.now() <= self.event.end_date


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    PAYMENT_GATEWAY_CHOICES = [
        ("paystack", "Paystack"),
        ("stripe", "Stripe"),
        ("flutterwave", "Flutterwave"),
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
    ]

    payment_id = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="Unique payment identifier"
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
        help_text="Associated order"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Payment amount"
    )

    gateway = models.CharField(
        max_length=50,
        choices=PAYMENT_GATEWAY_CHOICES,
        help_text="Payment gateway used"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Payment status"
    )

    gateway_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Gateway transaction reference"
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full gateway response data"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment metadata"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the payer"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was completed"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=["payment_id"], name="idx_payment_id"),
            models.Index(fields=["order"], name="idx_payment_order"),
            models.Index(fields=["status"], name="idx_payment_status"),
            models.Index(fields=["gateway"], name="idx_payment_gateway"),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} - {self.gateway}"

    def save(self, *args, **kwargs):
        if not self.payment_id:
            self.payment_id = self.generate_payment_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_payment_id():
        return f"PAY-{uuid.uuid4().hex[:12].upper()}"


class EventReview(models.Model):
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
