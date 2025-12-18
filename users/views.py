from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserProfileSerializer, UserSettingsSerializer
from rest_framework import permissions

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

        # ✅ Check for active tickets
        from tickets.models import Ticket, Event
        from django.utils import timezone
        
        active_tickets = Ticket.objects.filter(
            purchase__user=instance,
            status='active',
            event__start_date__gte=timezone.now().date()
        ).count()

        # ✅ Check for upcoming events (as organizer)
        upcoming_events = Event.objects.filter(
            organizer=instance,
            start_date__gte=timezone.now().date()
        ).count()

        if active_tickets > 0 or upcoming_events > 0:
            return Response(
                {
                    "error": "Cannot delete account",
                    "message": f"Cannot delete account. You have {active_tickets} active tickets and {upcoming_events} upcoming events. Please cancel them first."
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

class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        # Validate all fields present
        if not all([current_password, new_password, confirm_password]):
            return Response({
                'error': 'Missing fields',
                'message': 'All fields are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check current password is correct
        if not request.user.check_password(current_password):
            return Response({
                'error': 'Invalid password',
                'message': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check new passwords match
        if new_password != confirm_password:
            return Response({
                'error': 'Password mismatch',
                'message': 'New password and confirmation do not match'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate password strength (Django's built-in validators)
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        
        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            return Response({
                'error': 'Invalid password',
                'message': ', '.join(e.messages)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Change password
        request.user.set_password(new_password)
        request.user.save()

        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
    

class ChangeUsernameView(APIView):
    """
    POST /api/v1/auth/username/
    Change username with password verification
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # Validate fields
        if not username or not password:
            return Response({
                'error': 'Missing fields',
                'message': 'Username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify password
        if not request.user.check_password(password):
            return Response({
                'error': 'Invalid password',
                'message': 'The password you entered is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if username is taken
        if User.objects.filter(username=username).exclude(id=request.user.id).exists():
            return Response({
                'error': 'Username taken',
                'message': 'This username is already in use'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate username format
        if len(username) < 3 or len(username) > 30:
            return Response({
                'error': 'Invalid username',
                'message': 'Username must be between 3 and 30 characters'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update username
        request.user.username = username
        request.user.save()

        return Response({
            'message': 'Username changed successfully',
            'username': username
        }, status=status.HTTP_200_OK)