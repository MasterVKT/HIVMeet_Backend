"""
Premium status middleware for HIVMeet.
"""
from subscriptions.utils import is_premium_user


class PremiumStatusMiddleware:
    """
    Add premium status to request.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.is_premium = is_premium_user(request.user)
        else:
            request.is_premium = False
        
        response = self.get_response(request)
        return response
