from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, PaymentProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "full_name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser", "date_joined"]
    search_fields = ["username", "email", "full_name"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("full_name", "email", "phone_number", "bio", "profile_image", "city", "country")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Notification Settings", {"fields": ("marketing_emails", "event_reminders", "email_notifications", "sms_notifications")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "username_last_changed")}),
    )


@admin.register(PaymentProfile)
class PaymentProfileAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "method",
        "status_badge",
        "is_verified",
        "is_default",
        "created_at",
    ]
    list_filter = ["method", "status", "is_verified", "is_default", "created_at"]
    search_fields = ["name", "user__username", "user__email"]
    readonly_fields = [
        "id",
        "status",
        "is_verified",
        "verified_at",
        "verification_initiated_at",
        "verification_attempts",
        "last_verification_attempt",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Basic Information", {
            "fields": ("id", "user", "method", "name", "description")
        }),
        ("Account Details", {
            "fields": ("account_details",)
        }),
        ("Verification", {
            "fields": ("status", "is_verified", "verified_at", "verification_initiated_at",
                      "verification_attempts", "last_verification_attempt", "failure_reason")
        }),
        ("Settings", {
            "fields": ("is_default", "fee_percentage")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "pending_verification": "orange",
            "verified": "green",
            "verification_failed": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
