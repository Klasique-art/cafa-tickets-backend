"""
Custom error views for handling 404 and 500 errors
"""
from django.http import JsonResponse
from django.views.defaults import page_not_found, server_error


def custom_404_view(request, exception=None):
    """
    Custom 404 error handler
    Returns JSON for API requests, otherwise delegates to default handler
    """
    if request.path.startswith('/api/'):
        return JsonResponse({
            "error": "Not Found",
            "message": "The requested endpoint was not found",
            "path": request.path,
            "status_code": 404
        }, status=404)

    # For non-API requests, use default Django 404 page
    return page_not_found(request, exception)


def custom_500_view(request):
    """
    Custom 500 error handler
    Returns JSON for API requests, otherwise delegates to default handler
    """
    if request.path.startswith('/api/'):
        return JsonResponse({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "status_code": 500
        }, status=500)

    # For non-API requests, use default Django 500 page
    return server_error(request)


def custom_403_view(request, exception=None):
    """
    Custom 403 error handler for permission denied
    """
    if request.path.startswith('/api/'):
        return JsonResponse({
            "error": "Permission Denied",
            "message": "You don't have permission to access this resource",
            "status_code": 403
        }, status=403)

    from django.views.defaults import permission_denied
    return permission_denied(request, exception)


def custom_400_view(request, exception=None):
    """
    Custom 400 error handler for bad requests
    """
    if request.path.startswith('/api/'):
        return JsonResponse({
            "error": "Bad Request",
            "message": "The request could not be understood or was missing required parameters",
            "status_code": 400
        }, status=400)

    from django.views.defaults import bad_request
    return bad_request(request, exception)
