from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserProfileSerializer, UserSettingsSerializer

User = get_user_model()


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET: Retrieve user profile
    PATCH/PUT: Update profile (full_name, bio, phone, profile_image, etc.)
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return UserSerializer
        return UserProfileSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                "message": "Profile updated successfully",
                "user": UserSerializer(instance).data,
            },
            status=status.HTTP_200_OK,
        )


class UserSettingsView(generics.UpdateAPIView):
    """
    PATCH: Update user notification settings
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSettingsSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                "message": "Settings updated successfully",
                "settings": instance.get_settings(),
            },
            status=status.HTTP_200_OK,
        )


class DeleteAccountView(generics.DestroyAPIView):
    """
    DELETE: Permanently delete user account
    """

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def destroy(self, request, *args, **kwargs):
        password = request.data.get("password")
        confirmation = request.data.get("confirmation")
        instance = self.get_object()

        if not password or not instance.check_password(password):
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

        instance.delete()

        return Response(
            {
                "message": "Your account has been permanently deleted. We're sorry to see you go."
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    POST: Login with email/username and password
    """

    permission_classes = [AllowAny]

    def post(self, request):
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
            user = (
                User.objects.filter(email=identifier).first()
                or User.objects.filter(username=identifier).first()
            )
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
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )
