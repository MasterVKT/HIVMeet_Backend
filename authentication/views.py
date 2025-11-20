"""
Authentication views for HIVMeet API.
"""
from datetime import timedelta
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    TokenRefreshSerializer,
    EmailVerificationSerializer,
    FCMTokenSerializer
)
from .utils import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email
)
from hivmeet_backend.firebase_service import firebase_service
from firebase_admin import auth

import logging
import secrets
import hashlib
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import auth as firebase_auth
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

logger = logging.getLogger('hivmeet.auth')
User = get_user_model()


def generate_tokens(user, remember_me=False):
    """
    Generate access and refresh tokens for a user.
    """
    refresh = RefreshToken.for_user(user)
    
    # Extend refresh token lifetime if remember_me is True
    if remember_me:
        refresh.set_exp(lifetime=timedelta(days=30))
    
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }


def generate_verification_token():
    """
    Generate a secure verification token.
    """
    return secrets.token_urlsafe(32)


class FirebaseLoginView(APIView):
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def post(self, request):
        # Conserver logs et validation existante
        logger.info("🔄 Tentative d'échange token Firebase...")
        
        # Accepte id_token (préféré) ou firebase_token pour compatibilité
        id_token = request.data.get('id_token') or request.data.get('firebase_token')
        if not id_token:
            logger.warning("🚫 ID token missing in request")
            return Response({'error': 'ID token requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
            uid = decoded_token['uid']
            email = decoded_token.get('email')
            # Conserver extraction existante (name, email_verified)
            name = decoded_token.get('name', '')
            email_verified = decoded_token.get('email_verified', False)
            
            if not email:
                logger.warning(f"🚫 Email manquant dans token pour UID: {uid}")
                return Response({'error': 'Email requis'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Conserver création/maj user existante (plus détaillée)
            User = get_user_model()
            try:
                user = User.objects.get(email=email)
                created = False
                if not user.firebase_uid:
                    user.firebase_uid = uid
                    user.save()
            except User.DoesNotExist:
                try:
                    user = User.objects.get(firebase_uid=uid)
                    created = False
                    if user.email != email:
                        user.email = email
                        user.save()
                except User.DoesNotExist:
                    from datetime import date
                    default_birth_date = date(1990, 1, 1)
                    user = User.objects.create(
                        email=email,
                        firebase_uid=uid,
                        display_name=name.split(' ')[0] if name else email.split('@')[0],
                        email_verified=email_verified,
                        birth_date=default_birth_date,
                        is_active=True
                    )
                    created = True
            
            if not created and user.firebase_uid != uid:
                return Response({'error': 'UID mismatch'}, status=status.HTTP_400_BAD_REQUEST)
            
            if email_verified and not user.email_verified:
                user.email_verified = True
                user.save()
            
            user.update_last_active()
            
            # Générer JWT comme instructions
            refresh = RefreshToken.for_user(user)
            logger.info(f"🎯 Tokens générés pour ID: {user.id}")
            
            return Response({
                # Clés standardisées
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                # Alias pour rétrocompatibilité avec divers clients
                'token': str(refresh.access_token),
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {  # Conserver réponse user existante
                    'id': user.id,
                    'email': user.email,
                    'display_name': user.display_name,
                    'firebase_uid': uid,
                    'email_verified': user.email_verified
                }
            }, status=status.HTTP_200_OK)
        
        except firebase_auth.InvalidIdTokenError:
            return Response({'error': 'Token invalide'}, status=status.HTTP_400_BAD_REQUEST)
        except firebase_auth.ExpiredIdTokenError:
            return Response({'error': 'Token expiré'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"💥 Erreur: {str(e)}")
            return Response({'error': f'Erreur serveur: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def register_view(request):
    """
    Register a new user.
    
    POST /api/v1/auth/register
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create user in Django
        user = serializer.save()
        
        # Create user in Firebase
        firebase_user = firebase_service.create_user(
            email=user.email,
            password=request.data.get('password'),
            display_name=user.display_name
        )
        
        # Update user with Firebase UID
        user.firebase_uid = firebase_user.uid
        user.save()
        
        # Generate email verification token
        verification_token = generate_verification_token()
        cache_key = f"email_verify_{verification_token}"
        cache.set(cache_key, user.id, timeout=86400)  # 24 hours
        
        # Send verification email
        verification_link = f"{settings.FRONTEND_URL}/verify-email/{verification_token}"
        send_verification_email(user, verification_link)
        
        logger.info(f"New user registered: {user.email}")
        
        return Response({
            'user_id': str(user.id),
            'email': user.email,
            'display_name': user.display_name,
            'message': _('Registration successful. Please verify your email.')
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({
            'error': True,
            'message': _('Registration failed. Please try again.'),
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email_view(request, verification_token):
    """
    Verify user's email address.
    
    GET /api/v1/auth/verify-email/{verification_token}
    """
    cache_key = f"email_verify_{verification_token}"
    user_id = cache.get(cache_key)
    
    if not user_id:
        return Response({
            'error': True,
            'message': _('Invalid or expired verification token.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        
        if user.email_verified:
            return Response({
                'message': _('Email already verified.')
            }, status=status.HTTP_200_OK)
        
        # Verify email
        user.email_verified = True
        user.save()
        
        # Update Firebase user
        firebase_service.update_user(
            user.firebase_uid,
            email_verified=True
        )
        
        # Delete cache key
        cache.delete(cache_key)
        
        # Send welcome email
        send_welcome_email(user)
        
        logger.info(f"Email verified for user: {user.email}")
        
        return Response({
            'message': _('Email verified successfully. You can now log in.')
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return Response({
            'error': True,
            'message': _('Verification failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Authenticate user and return JWT tokens.
    
    POST /api/v1/auth/login
    """
    serializer = LoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    remember_me = serializer.validated_data.get('remember_me', False)
    
    try:
        # Authenticate user
        user = authenticate(request, email=email, password=password)
        
        if not user:
            return Response({
                'error': True,
                'message': _('Invalid credentials.')
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({
                'error': True,
                'message': _('Account is disabled.')
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not user.email_verified:
            return Response({
                'error': True,
                'message': _('Please verify your email before logging in.')
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update last login
        user.last_login = timezone.now()
        user.update_last_active()
        
        # Generate tokens
        tokens = generate_tokens(user, remember_me)
        
        # Serialize user data
        user_data = UserSerializer(user).data
        
        logger.info(f"User logged in: {user.email}")
        
        return Response({
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'user': user_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': True,
            'message': _('Login failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """
    Request password reset.
    
    POST /api/v1/auth/forgot-password
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    # Always return success to prevent email enumeration
    try:
        user = User.objects.get(email=email)
        
        # Generate reset token
        reset_token = generate_verification_token()
        cache_key = f"password_reset_{reset_token}"
        cache.set(cache_key, user.id, timeout=3600)  # 1 hour
        
        # Send password reset email
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
        send_password_reset_email(user, reset_link)
        
        logger.info(f"Password reset requested for: {email}")
        
    except User.DoesNotExist:
        # Don't reveal that the email doesn't exist
        logger.warning(f"Password reset requested for non-existent email: {email}")
    
    return Response({
        'message': _('If an account with this email exists, a password reset link has been sent.')
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_view(request):
    """
    Reset password with token.
    
    POST /api/v1/auth/reset-password
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    token = serializer.validated_data['token']
    new_password = serializer.validated_data['new_password']
    
    cache_key = f"password_reset_{token}"
    user_id = cache.get(cache_key)
    
    if not user_id:
        return Response({
            'error': True,
            'message': _('Invalid or expired reset token.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Update Firebase user
        firebase_service.update_user(
            user.firebase_uid,
            password=new_password
        )
        
        # Delete cache key
        cache.delete(cache_key)
        
        logger.info(f"Password reset successful for: {user.email}")
        
        return Response({
            'message': _('Password reset successfully. You can now log in with your new password.')
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return Response({
            'error': True,
            'message': _('Password reset failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """
    Refresh access token.
    
    POST /api/v1/auth/refresh-token
    """
    serializer = TokenRefreshSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    refresh_token = serializer.validated_data['refresh_token']
    
    try:
        # Verify and refresh token
        refresh = RefreshToken(refresh_token)
        
        # Get new tokens
        new_access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)  # Rotates the refresh token
        
        return Response({
            # Clés standardisées
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
            # Alias pour compatibilité
            'token': new_access_token,
            'access': new_access_token,
            'refresh': new_refresh_token
        }, status=status.HTTP_200_OK)
        
    except TokenError as e:
        return Response({
            'error': True,
            'message': _('Invalid or expired refresh token.')
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user (invalidate refresh token).
    
    POST /api/v1/auth/logout
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        logger.info(f"User logged out: {request.user.email}")
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        # Even if token blacklisting fails, consider logout successful
        logger.warning(f"Logout error: {str(e)}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterFCMTokenView(generics.CreateAPIView):
    """
    Register FCM token for push notifications.
    
    POST /api/v1/auth/fcm-token
    """
    serializer_class = FCMTokenSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        fcm_token = serializer.validated_data['fcm_token']
        device_id = serializer.validated_data.get('device_id')
        platform = serializer.validated_data.get('platform')
        
        # Add FCM token to user
        user.add_fcm_token(fcm_token, device_id, platform)
        
        logger.info(f"FCM token registered for user: {user.email}")
        
        return Response({
            'message': _('FCM token registered successfully.')
        }, status=status.HTTP_200_OK)