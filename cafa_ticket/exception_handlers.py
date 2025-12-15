"""
Global Exception Handlers for Django REST Framework
Provides consistent error responses across the entire API
"""
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
    PermissionDenied,
    ObjectDoesNotExist
)
from django.http import Http404
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    NotFound,
    MethodNotAllowed,
    NotAcceptable,
    UnsupportedMediaType,
    Throttled,
    ParseError,
)
import logging
import traceback

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework
    Returns consistent error responses in the format:
    {
        "error": "Error Title",
        "message": "Detailed error message",
        "details": {} (optional),
        "status_code": 400
    }
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)

    # Get the request object
    request = context.get('view', None)
    if request:
        request = getattr(request, 'request', None)

    # Log the exception
    if response is None or (response and response.status_code >= 500):
        logger.error(
            f"Exception: {exc.__class__.__name__}: {str(exc)}",
            exc_info=True,
            extra={
                'request': request,
                'view': context.get('view'),
            }
        )

    # Handle DRF exceptions
    if response is not None:
        error_data = format_drf_exception(exc, response)
        return Response(error_data, status=response.status_code)

    # Handle Django exceptions
    if isinstance(exc, DjangoValidationError):
        error_data = {
            "error": "Validation Error",
            "message": "The data provided is invalid",
            "details": exc.message_dict if hasattr(exc, 'message_dict') else {"non_field_errors": exc.messages},
            "status_code": status.HTTP_400_BAD_REQUEST
        }
        return Response(error_data, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, ObjectDoesNotExist):
        error_data = {
            "error": "Not Found",
            "message": str(exc) or "The requested resource was not found",
            "status_code": status.HTTP_404_NOT_FOUND
        }
        return Response(error_data, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, PermissionDenied):
        error_data = {
            "error": "Permission Denied",
            "message": str(exc) or "You don't have permission to access this resource",
            "status_code": status.HTTP_403_FORBIDDEN
        }
        return Response(error_data, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, Http404):
        error_data = {
            "error": "Not Found",
            "message": "The requested resource was not found",
            "status_code": status.HTTP_404_NOT_FOUND
        }
        return Response(error_data, status=status.HTTP_404_NOT_FOUND)

    # Handle unexpected exceptions
    error_data = {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later.",
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
    }

    # In DEBUG mode, include the actual error message
    from django.conf import settings
    if settings.DEBUG:
        error_data["debug_message"] = str(exc)
        error_data["debug_traceback"] = traceback.format_exc()

    return Response(error_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def format_drf_exception(exc, response):
    """
    Format DRF exceptions into consistent error response format
    """
    error_data = {
        "status_code": response.status_code
    }

    # Handle ValidationError
    if isinstance(exc, ValidationError):
        error_data["error"] = "Validation Error"
        if isinstance(response.data, dict):
            # Check if it's field-level validation errors
            if any(key not in ['error', 'message', 'detail'] for key in response.data.keys()):
                error_data["message"] = "The data provided is invalid"
                error_data["details"] = response.data
            else:
                error_data["message"] = response.data.get('detail') or response.data.get('message') or "Validation failed"
                if 'details' in response.data:
                    error_data["details"] = response.data['details']
        elif isinstance(response.data, list):
            error_data["message"] = response.data[0] if response.data else "Validation failed"
        else:
            error_data["message"] = str(response.data)

    # Handle AuthenticationFailed and NotAuthenticated
    elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        error_data["error"] = "Authentication Failed"
        error_data["message"] = str(exc) or "Authentication credentials were not provided or are invalid"

    # Handle PermissionDenied
    elif isinstance(exc, DRFPermissionDenied):
        error_data["error"] = "Permission Denied"
        error_data["message"] = str(exc) or "You don't have permission to perform this action"

    # Handle NotFound
    elif isinstance(exc, NotFound):
        error_data["error"] = "Not Found"
        error_data["message"] = str(exc) or "The requested resource was not found"

    # Handle MethodNotAllowed
    elif isinstance(exc, MethodNotAllowed):
        error_data["error"] = "Method Not Allowed"
        error_data["message"] = f"Method '{exc.detail.code}' is not allowed for this endpoint"

    # Handle NotAcceptable
    elif isinstance(exc, NotAcceptable):
        error_data["error"] = "Not Acceptable"
        error_data["message"] = str(exc)

    # Handle UnsupportedMediaType
    elif isinstance(exc, UnsupportedMediaType):
        error_data["error"] = "Unsupported Media Type"
        error_data["message"] = str(exc)

    # Handle Throttled
    elif isinstance(exc, Throttled):
        error_data["error"] = "Too Many Requests"
        error_data["message"] = f"Request was throttled. Expected available in {exc.wait} seconds."
        error_data["retry_after"] = exc.wait

    # Handle ParseError
    elif isinstance(exc, ParseError):
        error_data["error"] = "Parse Error"
        error_data["message"] = str(exc) or "Malformed request data"

    # Handle other APIExceptions
    elif isinstance(exc, APIException):
        error_data["error"] = exc.default_detail
        error_data["message"] = str(exc)

    # Generic handler
    else:
        error_data["error"] = "Error"
        if isinstance(response.data, dict):
            error_data["message"] = response.data.get('detail') or response.data.get('message') or str(response.data)
        else:
            error_data["message"] = str(response.data)

    return error_data
