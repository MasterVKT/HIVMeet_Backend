"""
Custom authentication backends for HIVMeet.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that uses email instead of username.
    """
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate user by email and password.
        """
        if email is None:
            email = kwargs.get(User.USERNAME_FIELD)
            
        if email is None or password is None:
            return None
        
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user
            User().set_password(password)
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None