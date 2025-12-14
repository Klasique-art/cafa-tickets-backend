from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Venue,
    EventCategory,
    Event,
    TicketType,
    Order,
    Ticket,
    Payment,
    EventReview,
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
    prepopulated_fields = {"slug": ("name",)}

    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = "Events"


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ["name", "price", "quantity", "quantity_sold", "is_active"]
    readonly_fields = ["quantity_sold"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "organizer",
        "start_date",
        "status",
        "is_featured",
        "tickets_sold_count",
        "views_count",
    ]
    list_filter = [
        "status",
        "privacy",
        "is_featured",
        "is_free",
        "category",
        "created_at",
        "start_date",
    ]
    search_fields = ["title", "description", "tags"]
    readonly_fields = [
        "slug",
        "views_count",
        "created_at",
        "updated_at",
        "tickets_sold_count",
        "revenue_display",
    ]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TicketTypeInline]
    date_hierarchy = "start_date"

    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "slug", "description", "short_description", "tags")
        }),
        ("Categorization", {
            "fields": ("category", "venue", "organizer")
        }),
        ("Images", {
            "fields": ("banner_image", "thumbnail_image")
        }),
        ("Schedule", {
            "fields": ("start_date", "end_date")
        }),
        ("Settings", {
            "fields": ("status", "privacy", "is_featured", "is_free", "max_attendees")
        }),
        ("Additional", {
            "fields": ("external_url", "terms_and_conditions"),
            "classes": ("collapse",)
        }),
        ("Statistics", {
            "fields": ("views_count", "tickets_sold_count", "revenue_display"),
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

    def revenue_display(self, obj):
        return f"GHS {obj.revenue_generated}"
    revenue_display.short_description = "Revenue"


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "event",
        "price",
        "quantity",
        "quantity_sold",
        "quantity_remaining_display",
        "is_active",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "event__title"]
    readonly_fields = ["quantity_sold", "created_at", "updated_at"]

    def quantity_remaining_display(self, obj):
        remaining = obj.quantity_remaining
        if remaining <= 0:
            return format_html('<span style="color: red;">SOLD OUT</span>')
        elif remaining < 10:
            return format_html('<span style="color: orange;">{}</span>', remaining)
        return remaining
    quantity_remaining_display.short_description = "Remaining"


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = [
        "ticket_number",
        "attendee_name",
        "ticket_type",
        "price_paid",
        "status",
    ]
    can_delete = False
    fields = [
        "ticket_number",
        "attendee_name",
        "ticket_type",
        "price_paid",
        "status",
    ]


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
    inlines = [TicketInline]
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
        return f"GHS {obj.grand_total}"
    grand_total_display.short_description = "Grand Total"

    def total_tickets_count(self, obj):
        return obj.total_tickets
    total_tickets_count.short_description = "Tickets"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_number",
        "event",
        "attendee_name",
        "status_badge",
        "price_paid",
        "checked_in_display",
        "created_at",
    ]
    list_filter = ["status", "created_at", "checked_in_at", "event"]
    search_fields = ["ticket_number", "attendee_name", "attendee_email", "order__order_id"]
    readonly_fields = [
        "ticket_number",
        "qr_code_display",
        "created_at",
        "updated_at",
        "checked_in_at",
        "checked_in_by",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Ticket Information", {
            "fields": ("ticket_number", "order", "event", "ticket_type", "status")
        }),
        ("Attendee Details", {
            "fields": ("attendee_name", "attendee_email", "attendee_phone")
        }),
        ("Payment", {
            "fields": ("price_paid",)
        }),
        ("QR Code", {
            "fields": ("qr_code", "qr_code_display"),
            "classes": ("collapse",)
        }),
        ("Check-in", {
            "fields": ("checked_in_at", "checked_in_by"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "valid": "green",
            "used": "blue",
            "cancelled": "red",
            "refunded": "orange",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def checked_in_display(self, obj):
        if obj.checked_in_at:
            return format_html('<span style="color: green;">✓ {}</span>', obj.checked_in_at)
        return format_html('<span style="color: gray;">Not checked in</span>')
    checked_in_display.short_description = "Checked In"

    def qr_code_display(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="150" height="150" />', obj.qr_code.url)
        return "No QR Code"
    qr_code_display.short_description = "QR Code Preview"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "payment_id",
        "order",
        "amount",
        "gateway",
        "status_badge",
        "created_at",
    ]
    list_filter = ["status", "gateway", "created_at"]
    search_fields = ["payment_id", "order__order_id", "gateway_reference"]
    readonly_fields = [
        "payment_id",
        "gateway_response",
        "created_at",
        "updated_at",
        "completed_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Payment Information", {
            "fields": ("payment_id", "order", "amount", "gateway", "status")
        }),
        ("Gateway Details", {
            "fields": ("gateway_reference", "gateway_response"),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("metadata", "ip_address"),
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
            "failed": "red",
            "refunded": "purple",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"


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
