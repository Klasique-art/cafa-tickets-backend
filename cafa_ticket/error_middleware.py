"""
Global Error Handling Middleware
Catches errors that occur outside of DRF views
"""
import logging
import json
from django.http import JsonResponse
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    ObjectDoesNotExist,
    SuspiciousOperation,
    DisallowedHost,
)
from django.http import Http404
from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """
    Middleware to handle errors globally and return consistent JSON responses
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """
        Process exceptions that occur during request handling
        """
        # Log the exception
        logger.error(
            f"Middleware caught exception: {exception.__class__.__name__}: {str(exception)}",
            exc_info=True,
            extra={'request': request}
        )

        # Only handle JSON requests or API endpoints
        if not self._should_handle_as_json(request):
            return None

        # Handle specific exceptions
        if isinstance(exception, Http404):
            return self._json_response(
                error="Not Found",
                message="The requested resource was not found",
                status=404
            )

        if isinstance(exception, PermissionDenied):
            return self._json_response(
                error="Permission Denied",
                message=str(exception) or "You don't have permission to access this resource",
                status=403
            )

        if isinstance(exception, ValidationError):
            return self._json_response(
                error="Validation Error",
                message="The data provided is invalid",
                details=exception.message_dict if hasattr(exception, 'message_dict') else {"non_field_errors": exception.messages},
                status=400
            )

        if isinstance(exception, ObjectDoesNotExist):
            return self._json_response(
                error="Not Found",
                message=str(exception) or "The requested object was not found",
                status=404
            )

        if isinstance(exception, SuspiciousOperation):
            return self._json_response(
                error="Bad Request",
                message="The request could not be completed",
                status=400
            )

        if isinstance(exception, DisallowedHost):
            return self._json_response(
                error="Bad Request",
                message="Invalid host header",
                status=400
            )

        # Handle unexpected exceptions
        error_data = {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "status_code": 500
        }

        # In DEBUG mode, include the actual error
        if settings.DEBUG:
            error_data["debug_message"] = str(exception)
            error_data["debug_type"] = exception.__class__.__name__

        return JsonResponse(error_data, status=500)

    def _should_handle_as_json(self, request):
        """
        Determine if the request should be handled with JSON response
        """
        # Check if it's an API request
        if request.path.startswith('/api/'):
            return True

        # Check Accept header
        accept_header = request.META.get('HTTP_ACCEPT', '')
        if 'application/json' in accept_header:
            return True

        # Check Content-Type header
        content_type = request.META.get('CONTENT_TYPE', '')
        if 'application/json' in content_type:
            return True

        return False

    def _json_response(self, error, message, status, details=None):
        """
        Create a JSON error response
        """
        data = {
            "error": error,
            "message": message,
            "status_code": status
        }

        if details:
            data["details"] = details

        return JsonResponse(data, status=status)


class RequestLoggingMiddleware:
    """
    Middleware to log all requests and responses
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log request
        if settings.DEBUG and request.path.startswith('/api/'):
            logger.debug(
                f"Request: {request.method} {request.path}",
                extra={
                    'method': request.method,
                    'path': request.path,
                    'user': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                }
            )

        response = self.get_response(request)

        # Log response
        if settings.DEBUG and request.path.startswith('/api/'):
            logger.debug(
                f"Response: {request.method} {request.path} - {response.status_code}",
                extra={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                }
            )

        return response


class DatabaseErrorHandlingMiddleware:
    """
    Middleware to handle database-related errors
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """
        Handle database exceptions
        """
        from django.db import DatabaseError, IntegrityError, OperationalError

        # Only handle JSON requests
        if not request.path.startswith('/api/'):
            return None

        if isinstance(exception, IntegrityError):
            logger.error(f"Database integrity error: {str(exception)}", exc_info=True)
            return JsonResponse({
                "error": "Data Integrity Error",
                "message": "The operation could not be completed due to a data constraint violation. Please check your input and try again.",
                "status_code": 400
            }, status=400)

        if isinstance(exception, OperationalError):
            logger.error(f"Database operational error: {str(exception)}", exc_info=True)
            return JsonResponse({
                "error": "Database Error",
                "message": "A database error occurred. Please try again later.",
                "status_code": 503
            }, status=503)

        if isinstance(exception, DatabaseError):
            logger.error(f"Database error: {str(exception)}", exc_info=True)
            return JsonResponse({
                "error": "Database Error",
                "message": "A database error occurred. Please try again later.",
                "status_code": 500
            }, status=500)

        return None
