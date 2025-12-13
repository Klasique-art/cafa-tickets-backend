from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import User
from .serializers import UserSettingsSerializer, UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db.models import Q

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_user_settings(request):
    serializer = UserSettingsSerializer(request.user, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                "message": "Settings updated successfully",
                "settings": request.user.get_settings(),
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {"error": "Validation failed", "details": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = request.data.get("password")
    confirmation = request.data.get("confirmation")

    if not password or not request.user.check_password(password):
        return Response(
            {
                "error": "Invalid password",
                "message": "The password you entered is incorrect.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if confirmation != "DELETE MY ACCOUNT":
        return Response(
            {
                "error": "Invalid confirmation",
                "message": "Please type 'DELETE MY ACCOUNT' to confirm deletion.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    request.user.delete()

    return Response(
        {
            "message": "Your account has been permanently deleted. We're sorry to see you go."
        },
        status=status.HTTP_200_OK,
    )


User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    identifier = request.data.get("email")
    password = request.data.get("password")

    if not identifier or not password:
        return Response(
            {
                "error": "Validation failed",
                "details": {
                    "email": ["This field is required"] if not identifier else [],
                    "password": ["This field is required"] if not password else [],
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # it can be either email or username
        user = User.objects.filter(email=identifier).first() or User.objects.filter(username=identifier).first()
        if not user:
            raise User.DoesNotExist
    except User.DoesNotExist:
        return Response(
            {
                "error": "Invalid credentials",
                "message": "The email/username or password you entered is incorrect.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    if not user.check_password(password):
        return Response(
            {
                "error": "Invalid credentials",
                "message": "The email/username or password you entered is incorrect.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        return Response(
            {
                "error": "Account not verified",
                "message": "Please verify your email before logging in.",
                "resend_verification_url": "/api/v1/auth/users/resend_activation/",
            },
            status=status.HTTP_403_FORBIDDEN,
        )



    # Generate tokens
    refresh = RefreshToken.for_user(user)

    # Serialize user data
    user_serializer = UserSerializer(user)

    return Response(
        {
            "message": "Login successful",
            "user": user_serializer.data,
            "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
        },
        status=status.HTTP_200_OK,
    )
