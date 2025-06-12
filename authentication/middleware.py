"""
Authentication middleware for Firebase integration.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from hivmeet_backend.firebase_service import firebase_service
import logging

logger = logging.getLogger('hivmeet.auth')
User = get_user_model()


class FirebaseAuthenticationMiddleware:
    """
    Middleware to authenticate users using Firebase ID tokens.
    Falls back to JWT authentication if Firebase token is not present.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()
    
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
        
        # Try JWT token
        try:
            validated_token = self.jwt_auth.get_validated_token(
                self._get_jwt_token(request)
            )
            return self.jwt_auth.get_user(validated_token)
        except (InvalidToken, TokenError):
            pass
        
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
            # Verify the Firebase ID token
            decoded_token = firebase_service.verify_id_token(token)
            firebase_uid = decoded_token['uid']
            
            # Get or create user
            try:
                user = User.objects.get(firebase_uid=firebase_uid)
                logger.info(f"Firebase user authenticated: {user.email}")
                return user
            except User.DoesNotExist:
                # User exists in Firebase but not in Django
                # This shouldn't happen in normal flow
                logger.warning(
                    f"Firebase user {firebase_uid} not found in Django database"
                )
                return None
                
        except Exception as e:
            logger.error(f"Firebase authentication error: {str(e)}")
            return None