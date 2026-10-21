"""
Authentication middleware for Firebase integration.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

from .authentication import EmailNotVerified, VerifiedEmailJWTAuthentication

logger = logging.getLogger('hivmeet.auth')
User = get_user_model()


class FirebaseAuthenticationMiddleware:
    """
    Middleware to authenticate users using Firebase ID tokens.
    Falls back to JWT authentication if Firebase token is not present.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = VerifiedEmailJWTAuthentication()
    
    def __call__(self, request):
        request.user = SimpleLazyObject(
            lambda: self._get_user(request)
        )
        response = self.get_response(request)
        return response
    
    def _get_user(self, request):
        """
        Get user from Firebase token or JWT token.
        """
        # Try Firebase token first
        firebase_token = self._get_firebase_token(request)
        if firebase_token:
            user = self._authenticate_firebase(firebase_token)
            if user:
                return user
        
        # Try JWT token. The same guard used by DRF rejects old tokens when
        # the local Firebase-verification projection has been withdrawn.
        jwt_token = self._get_jwt_token(request)
        if not jwt_token:
            return AnonymousUser()
        try:
            validated_token = self.jwt_auth.get_validated_token(jwt_token)
            return self.jwt_auth.get_user(validated_token)
        except (InvalidToken, TokenError, EmailNotVerified):
            return AnonymousUser()

    
    def _get_firebase_token(self, request):
        """Extract Firebase token from request headers."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Firebase '):
            return auth_header.split(' ')[1]
        return None
    
    def _get_jwt_token(self, request):
        """Extract JWT token from request headers."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        return None
    
    def _authenticate_firebase(self, token):
        """
        Authenticate user with Firebase token.
        """
        try:
            from hivmeet_backend.firebase_service import firebase_service
            # Verify the Firebase ID token
            decoded_token = firebase_service.verify_id_token(token)
            firebase_uid = decoded_token.get('uid')
            firebase_email = str(decoded_token.get('email', '')).strip().lower()
            if not firebase_uid or not firebase_email:
                return None
            if decoded_token.get('email_verified') is not True:
                return None
            
            # Firebase identity can only authenticate an existing matching
            # account. This middleware must never provision a local user.
            try:
                user = User.objects.get(firebase_uid=firebase_uid)
                if not user.email_verified or user.email.lower() != firebase_email:
                    return None
                logger.info('Firebase middleware authentication completed')
                return user
            except User.DoesNotExist:
                logger.warning('Firebase middleware identity is not registered')
                return None
                
        except Exception:
            logger.error('Firebase middleware authentication failed')
            return None
