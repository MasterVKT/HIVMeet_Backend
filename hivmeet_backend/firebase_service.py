"""
Firebase service initialization and utilities for HIVMeet backend.
"""
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from django.conf import settings
import logging
import os

logger = logging.getLogger('hivmeet.firebase')

class FirebaseService:
    """
    Singleton service for Firebase operations.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            self._initialized = True
    
    def _initialize_firebase(self):
        """
        Initialize Firebase Admin SDK.
        """
        try:
            if not firebase_admin._apps:
                # Check if credentials path is configured
                if not settings.FIREBASE_CREDENTIALS_PATH:
                    raise ValueError("FIREBASE_CREDENTIALS_PATH not configured in settings")
                
                # Check if credentials file exists
                if not os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                    raise FileNotFoundError(f"Firebase credentials file not found at {settings.FIREBASE_CREDENTIALS_PATH}")
                
                # Initialize Firebase Admin SDK
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': settings.FIREBASE_STORAGE_BUCKET
                })
            
            # Initialize services
            self._auth = auth
            self._db = firestore.client()
            self._bucket = storage.bucket()
            
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    @property
    def auth(self):
        """Get Firebase Auth instance."""
        return self._auth
    
    @property
    def db(self):
        """Get Firestore client instance."""
        return self._db
    
    @property
    def bucket(self):
        """Get Firebase Storage bucket instance."""
        return self._bucket
    
    def verify_id_token(self, id_token):
        """
        Verify a Firebase ID token.
        
        Args:
            id_token (str): The Firebase ID token to verify
            
        Returns:
            dict: Decoded token claims if valid
            
        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            decoded_token = self._auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}")
    
    def create_custom_token(self, uid, additional_claims=None):
        """
        Create a custom token for a user.
        
        Args:
            uid (str): The user's Firebase UID
            additional_claims (dict): Additional claims to include in the token
            
        Returns:
            bytes: The custom token
        """
        try:
            return self._auth.create_custom_token(uid, additional_claims)
        except Exception as e:
            logger.error(f"Failed to create custom token: {str(e)}")
            raise
    
    def get_user(self, uid):
        """
        Get a Firebase user by UID.
        
        Args:
            uid (str): The user's Firebase UID
            
        Returns:
            firebase_admin.auth.UserRecord: The user record
        """
        try:
            return self._auth.get_user(uid)
        except Exception as e:
            logger.error(f"Failed to get user: {str(e)}")
            raise
    
    def get_user_by_email(self, email):
        """
        Get a Firebase user by email.
        
        Args:
            email (str): The user's email
            
        Returns:
            firebase_admin.auth.UserRecord: The user record
        """
        try:
            return self._auth.get_user_by_email(email)
        except Exception as e:
            logger.error(f"Failed to get user by email: {str(e)}")
            raise
    
    def create_user(self, email, password, **kwargs):
        """
        Create a new Firebase user.
        
        Args:
            email (str): User's email
            password (str): User's password
            **kwargs: Additional user properties
            
        Returns:
            firebase_admin.auth.UserRecord: The created user record
        """
        try:
            user = self._auth.create_user(
                email=email,
                password=password,
                **kwargs
            )
            logger.info(f"Created Firebase user with UID: {user.uid}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            raise
    
    def update_user(self, uid, **kwargs):
        """
        Update a Firebase user.
        
        Args:
            uid (str): The user's Firebase UID
            **kwargs: Properties to update
            
        Returns:
            firebase_admin.auth.UserRecord: The updated user record
        """
        try:
            user = self._auth.update_user(uid, **kwargs)
            logger.info(f"Updated Firebase user with UID: {uid}")
            return user
        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}")
            raise
    
    def delete_user(self, uid):
        """
        Delete a Firebase user.
        
        Args:
            uid (str): The user's Firebase UID
        """
        try:
            self._auth.delete_user(uid)
            logger.info(f"Deleted Firebase user with UID: {uid}")
        except Exception as e:
            logger.error(f"Failed to delete user: {str(e)}")
            raise
    
    def send_email_verification(self, email, action_code_settings=None):
        """
        Send email verification to a user.
        
        Args:
            email (str): User's email
            action_code_settings: Optional action code settings
            
        Returns:
            str: The verification link
        """
        try:
            link = self._auth.generate_email_verification_link(
                email, 
                action_code_settings
            )
            logger.info(f"Generated email verification link for: {email}")
            return link
        except Exception as e:
            logger.error(f"Failed to send email verification: {str(e)}")
            raise
    
    def send_password_reset_email(self, email, action_code_settings=None):
        """
        Send password reset email to a user.
        
        Args:
            email (str): User's email
            action_code_settings: Optional action code settings
            
        Returns:
            str: The password reset link
        """
        try:
            link = self._auth.generate_password_reset_link(
                email,
                action_code_settings
            )
            logger.info(f"Generated password reset link for: {email}")
            return link
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            raise

# Global instance
firebase_service = FirebaseService()