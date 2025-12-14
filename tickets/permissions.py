from rest_framework import permissions


class IsOrganizerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.organizer == request.user or request.user.is_staff


class IsOrderOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.is_staff


class IsTicketOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.order.user == request.user or request.user.is_staff
