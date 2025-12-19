from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Venue,
    EventCategory,
    Event,
    TicketType,
    Purchase,
    Payment,
    Ticket,
    Order,
    EventReview,
    ContactMessage, 
    NewsletterSubscription
)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "country", "capacity", "created_at"]
    list_filter = ["city", "country", "created_at"]
    search_fields = ["name", "city", "country", "address"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "description", "image")
        }),
        ("Location", {
            "fields": ("address", "city", "country", "latitude", "longitude")
        }),
        ("Details", {
            "fields": ("capacity",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "event_count", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["slug", "created_at", "updated_at"]

    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = "Events"


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ["name", "price", "quantity", "tickets_sold"]
    readonly_fields = ["tickets_sold"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "organizer",
        "start_date",
        "event_status",
        "is_published",
        "tickets_sold_count",
        "views_count",
    ]
    list_filter = [
        "is_published",
        "category",
        "created_at",
        "start_date",
    ]
    search_fields = ["title", "description"]
    readonly_fields = [
        "slug",
        "views_count",
        "created_at",
        "updated_at",
        "tickets_sold_count",
    ]
    inlines = [TicketTypeInline]
    date_hierarchy = "start_date"

    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "slug", "description", "short_description")
        }),
        ("Categorization", {
            "fields": ("category", "organizer", "payment_profile")
        }),
        ("Venue", {
            "fields": ("venue_name", "venue_address", "venue_city", "venue_country", "venue_latitude", "venue_longitude")
        }),
        ("Images", {
            "fields": ("featured_image", "additional_images")
        }),
        ("Schedule", {
            "fields": ("start_date", "end_date", "start_time", "end_time")
        }),
        ("Recurring Events", {
            "fields": ("is_recurring", "recurrence_pattern"),
            "classes": ("collapse",)
        }),
        ("Settings", {
            "fields": ("is_published", "check_in_policy", "max_attendees")
        }),
        ("Statistics", {
            "fields": ("views_count", "tickets_sold_count"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def tickets_sold_count(self, obj):
        return obj.tickets_sold
    tickets_sold_count.short_description = "Tickets Sold"

    def event_status(self, obj):
        return obj.status
    event_status.short_description = "Status"


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "event",
        "price",
        "quantity",
        "tickets_sold",
        "quantity_remaining_display",
    ]
    list_filter = ["created_at"]
    search_fields = ["name", "event__title"]
    readonly_fields = ["tickets_sold", "created_at", "updated_at", "sold_out_at"]

    def quantity_remaining_display(self, obj):
        remaining = obj.tickets_remaining
        if remaining <= 0:
            return format_html('<span style="color: red;">SOLD OUT</span>')
        elif remaining < 10:
            return format_html('<span style="color: orange;">{}</span>', remaining)
        return remaining
    quantity_remaining_display.short_description = "Remaining"


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "purchase_id",
        "buyer_name",
        "event",
        "quantity",
        "status_badge",
        "total",
        "created_at",
    ]
    list_filter = ["status", "created_at", "event"]
    search_fields = ["purchase_id", "buyer_name", "buyer_email"]
    readonly_fields = [
        "purchase_id",
        "created_at",
        "updated_at",
        "completed_at",
        "reservation_expires_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Purchase Information", {
            "fields": ("purchase_id", "user", "event", "ticket_type", "quantity", "status")
        }),
        ("Buyer Details", {
            "fields": ("buyer_name", "buyer_email", "buyer_phone")
        }),
        ("Financial", {
            "fields": ("ticket_price", "subtotal", "service_fee", "total")
        }),
        ("Timing", {
            "fields": ("reservation_expires_at", "completed_at")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.append("reserved_at")
        return readonly

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:
            fieldsets = (
                ("Purchase Information", {
                    "fields": ("purchase_id", "user", "event", "ticket_type", "quantity", "status")
                }),
                ("Buyer Details", {
                    "fields": ("buyer_name", "buyer_email", "buyer_phone")
                }),
                ("Financial", {
                    "fields": ("ticket_price", "subtotal", "service_fee", "total")
                }),
                ("Timing", {
                    "fields": ("reserved_at", "reservation_expires_at", "completed_at")
                }),
                ("Timestamps", {
                    "fields": ("created_at", "updated_at"),
                    "classes": ("collapse",)
                }),
            )
        return fieldsets

    def status_badge(self, obj):
        colors = {
            "reserved": "blue",
            "pending": "orange",
            "completed": "green",
            "failed": "red",
            "expired": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "payment_id",
        "purchase",
        "amount",
        "provider",
        "status_badge",
        "created_at",
    ]
    list_filter = ["status", "provider", "created_at"]
    search_fields = ["payment_id", "reference", "purchase__purchase_id"]
    readonly_fields = [
        "payment_id",
        "provider_response",
        "created_at",
        "completed_at",
        "failed_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Payment Information", {
            "fields": ("payment_id", "purchase", "amount", "currency", "provider", "status")
        }),
        ("Payment Method", {
            "fields": ("payment_method", "reference", "payment_url")
        }),
        ("Provider Details", {
            "fields": ("provider_response", "failure_reason"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "completed_at", "failed_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "pending": "orange",
            "completed": "green",
            "failed": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = [
        "ticket_id",
        "attendee_name",
        "ticket_type",
        "status",
    ]
    can_delete = False
    fields = [
        "ticket_id",
        "attendee_name",
        "ticket_type",
        "status",
    ]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_id",
        "event",
        "attendee_name",
        "status_badge",
        "checked_in_display",
        "created_at",
    ]
    list_filter = ["status", "is_checked_in", "created_at", "event"]
    search_fields = ["ticket_id", "attendee_name", "attendee_email", "purchase__purchase_id"]
    readonly_fields = [
        "ticket_id",
        "qr_code_display",
        "created_at",
        "updated_at",
        "checked_in_at",
        "checked_in_by",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Ticket Information", {
            "fields": ("ticket_id", "purchase", "event", "ticket_type", "status")
        }),
        ("Attendee Details", {
            "fields": ("attendee_name", "attendee_email", "attendee_phone")
        }),
        ("QR Code", {
            "fields": ("qr_code", "qr_code_display"),
            "classes": ("collapse",)
        }),
        ("Check-in", {
            "fields": ("is_checked_in", "checked_in_at", "checked_in_by"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "reserved": "blue",
            "paid": "green",
            "cancelled": "red",
            "used": "purple",
            "expired": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def checked_in_display(self, obj):
        if obj.is_checked_in:
            return format_html('<span style="color: green;">✓ {}</span>', obj.checked_in_at)
        return format_html('<span style="color: gray;">Not checked in</span>')
    checked_in_display.short_description = "Checked In"

    def qr_code_display(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="150" height="150" />', obj.qr_code.url)
        return "No QR Code"
    qr_code_display.short_description = "QR Code Preview"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_id",
        "buyer_name",
        "event",
        "status_badge",
        "grand_total_display",
        "total_tickets_count",
        "created_at",
    ]
    list_filter = ["status", "created_at", "event"]
    search_fields = ["order_id", "buyer_name", "buyer_email", "event__title"]
    readonly_fields = [
        "order_id",
        "grand_total_display",
        "created_at",
        "updated_at",
        "completed_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Order Information", {
            "fields": ("order_id", "user", "event", "status")
        }),
        ("Buyer Details", {
            "fields": ("buyer_name", "buyer_email", "buyer_phone")
        }),
        ("Financial", {
            "fields": ("total_amount", "service_fee", "grand_total_display")
        }),
        ("Payment", {
            "fields": ("payment_method", "payment_reference")
        }),
        ("Additional", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "completed_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "pending": "orange",
            "processing": "blue",
            "completed": "green",
            "cancelled": "red",
            "refunded": "purple",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def grand_total_display(self, obj):
        try:
            return f"GHS {obj.grand_total:.2f}"
        except (TypeError, AttributeError):
            return "GHS 0.00"
    grand_total_display.short_description = "Grand Total"

    def total_tickets_count(self, obj):
        return obj.total_tickets
    total_tickets_count.short_description = "Tickets"


@admin.register(EventReview)
class EventReviewAdmin(admin.ModelAdmin):
    list_display = [
        "event",
        "user",
        "rating_stars",
        "is_verified_purchase",
        "created_at",
    ]
    list_filter = ["rating", "is_verified_purchase", "created_at"]
    search_fields = ["event__title", "user__email", "comment"]
    readonly_fields = ["created_at", "updated_at"]

    def rating_stars(self, obj):
        stars = "⭐" * obj.rating
        return format_html('<span style="font-size: 16px;">{}</span>', stars)
    rating_stars.short_description = "Rating"

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'subject', 'message')
        }),
        ('Status', {
            'fields': ('status', 'admin_notes', 'responded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_active', 'is_confirmed', 'source', 'subscribed_at']
    list_filter = ['is_active', 'is_confirmed', 'source', 'subscribed_at']
    search_fields = ['email']
    readonly_fields = ['subscribed_at', 'unsubscribed_at', 'confirmed_at']
    
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        queryset.update(is_active=True)
    activate_subscriptions.short_description = "Activate selected subscriptions"
    
    def deactivate_subscriptions(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_subscriptions.short_description = "Deactivate selected subscriptions"