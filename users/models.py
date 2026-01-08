from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
from .managers import UserManager


class User(AbstractUser):
    email = models.EmailField(
        unique=True, db_index=True, help_text="Email address used for login"
    )
    full_name = models.CharField(
        max_length=255, blank=True, help_text="Full name of the user"
    )

    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be in E.164 format. Example: +233241234567",
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        help_text="International phone number format",
    )

    profile_image = models.ImageField(
        upload_to="profiles/%Y/%m/",
        blank=True,
        null=True,
        help_text="Profile picture - Max 5MB, JPG/PNG/WebP",
    )
    bio = models.TextField(
        max_length=500, blank=True, help_text="Short bio about the user"
    )
    city = models.CharField(max_length=100, blank=True, help_text="City of residence")
    country = models.CharField(
        max_length=100, blank=True, default="Ghana", help_text="Country of residence"
    )

    is_profile_completed = models.BooleanField(
        default=False, help_text="Indicates if user completed profile setup"
    )

    is_organizer = models.BooleanField(default=False, help_text="Indicates if user has created at least one event (for verification purposes)")

    username_last_changed = models.DateTimeField(
        null=True, blank=True, help_text="Last time username was changed"
    )

    marketing_emails = models.BooleanField(
        default=True, help_text="Receive marketing and promotional emails"
    )
    event_reminders = models.BooleanField(
        default=True, help_text="Receive reminders about upcoming events"
    )
    email_notifications = models.BooleanField(
        default=True, help_text="Receive email notifications"
    )
    sms_notifications = models.BooleanField(
        default=False, help_text="Receive SMS notifications"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when user registered"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date and time of last profile update"
    )


    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["email"], name="idx_user_email"),
            models.Index(fields=["username"], name="idx_user_username"),
            models.Index(fields=["is_active"], name="idx_user_active"),
            models.Index(fields=["created_at"], name="idx_user_created"),
        ]

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<User: {self.email} (ID: {self.id})>"

    @property
    def can_change_username(self):
        if not self.username_last_changed:
            return True
        return timezone.now() >= self.username_last_changed + timedelta(days=30)

    @property
    def next_username_change_date(self):
        if not self.username_last_changed:
            return None
        return self.username_last_changed + timedelta(days=30)

    @property
    def display_name(self):
        return self.full_name if self.full_name else self.username

    def get_settings(self):
        return {
            "marketing_emails": self.marketing_emails,
            "event_reminders": self.event_reminders,
            "email_notifications": self.email_notifications,
            "sms_notifications": self.sms_notifications,
        }

    def update_settings(self, **kwargs):
        """
        Update user notification settings

        Args:
            **kwargs: Settings to update (marketing_emails, event_reminders, etc.)

        Returns:
            dict: Updated settings
        """
        valid_settings = [
            "marketing_emails",
            "event_reminders",
            "email_notifications",
            "sms_notifications",
        ]

        for key, value in kwargs.items():
            if key in valid_settings and isinstance(value, bool):
                setattr(self, key, value)

        self.save(update_fields=valid_settings)
        return self.get_settings()

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_user = User.objects.get(pk=self.pk)
                if old_user.username != self.username:
                    self.username_last_changed = timezone.now()
            except User.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    def get_stats(self):
        """Return user statistics"""
        from tickets.models import Ticket, Event, Purchase

        tickets_purchased = Ticket.objects.filter(
            purchase__user=self,
            purchase__status="completed"
        ).count()

        events_organized = Event.objects.filter(organizer=self).count()

        from django.db.models import Sum
        total_spent = Purchase.objects.filter(
            user=self,
            status="completed"
        ).aggregate(total=Sum("total"))["total"] or 0

        return {
            "total_tickets_purchased": tickets_purchased,
            "total_events_attended": 0,  # TODO: Based on checked-in tickets
            "events_organized": events_organized,
            "total_spent": float(total_spent),
            "account_age_days": (timezone.now() - self.date_joined).days,
        }


class PaymentProfile(models.Model):
    """Payment profile for event organizers to receive revenue"""

    PAYMENT_METHOD_CHOICES = [
        ("mobile_money", "Mobile Money"),
        ("bank_transfer", "Bank Transfer"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("pending_verification", "Pending Verification"),
        ("verified", "Verified"),
        ("verification_failed", "Verification Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=None, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payment_profiles",
        help_text="User who owns this payment profile"
    )
    method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        help_text="Payment method type"
    )
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this payment profile"
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        help_text="Description of this payment profile"
    )
    account_details = models.JSONField(
        help_text="Account details (mobile number, account number, etc.)"
    )
    fee_percentage = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.5,
        help_text="Transaction fee percentage for this payment method"
    )
    status = models.CharField(
        max_length=25,
        choices=VERIFICATION_STATUS_CHOICES,
        default="pending_verification",
        help_text="Verification status"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this payment profile has been verified"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the payment profile was verified"
    )
    verification_initiated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verification was initiated"
    )
    verification_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of verification attempts"
    )
    last_verification_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last verification attempt time"
    )
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for verification failure"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default payment profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Payment Profile"
        verbose_name_plural = "Payment Profiles"
        indexes = [
            models.Index(fields=["user"], name="idx_payment_profile_user"),
            models.Index(fields=["status"], name="idx_payment_profile_status"),
            models.Index(fields=["is_verified"], name="idx_payment_profile_verified"),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.name}"

    def save(self, *args, **kwargs):
        import uuid
        if not self.id:
            self.id = uuid.uuid4()

        # Set fee percentage based on method
        if self.method == "mobile_money":
            self.fee_percentage = 1.5
        elif self.method == "bank_transfer":
            self.fee_percentage = 2.0

        # If this is set as default, unset other defaults
        if self.is_default:
            PaymentProfile.objects.filter(user=self.user, is_default=True).exclude(
                id=self.id
            ).update(is_default=False)

        super().save(*args, **kwargs)

    def get_masked_account_details(self):
        """Return masked account details for security"""
        details = self.account_details.copy()

        if self.method == "mobile_money" and "mobile_number" in details:
            number = details["mobile_number"]
            if len(number) > 7:
                details["mobile_number"] = number[:4] + "***" + number[-4:]

        if self.method == "bank_transfer" and "account_number" in details:
            account = details["account_number"]
            if len(account) > 6:
                details["account_number"] = "******" + account[-4:]

        return details
