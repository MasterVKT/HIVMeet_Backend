"""
Security middleware and utilities for HIVMeet.
File: hivmeet_backend/security.py
"""
import hashlib
import time
import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import re

logger = logging.getLogger('hivmeet.security')
User = get_user_model()


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware to prevent abuse."""
    
    # Rate limits per endpoint pattern
    RATE_LIMITS = {
        'auth/register': (5, 3600),        # 5 per hour
        'auth/login': (10, 600),           # 10 per 10 minutes
        'auth/password-reset': (3, 3600),  # 3 per hour
        'profiles/.*?/like': (100, 3600),  # 100 likes per hour
        'conversations/.*/messages': (60, 60),  # 60 messages per minute
        'subscriptions/purchase': (5, 3600),    # 5 attempts per hour
    }
    
    def process_request(self, request):
        """Check rate limits for the request."""
        if not self.should_rate_limit(request):
            return None
        
        # Get client identifier
        client_id = self.get_client_id(request)
        path = request.path.lstrip('/api/v1/')
        
        # Check each rate limit pattern
        for pattern, (limit, window) in self.RATE_LIMITS.items():
            if re.match(pattern, path):
                cache_key = f'rate_limit:{pattern}:{client_id}'
                
                # Get current count
                current = cache.get(cache_key, 0)
                
                if current >= limit:
                    logger.warning(f"Rate limit exceeded for {client_id} on {pattern}")
                    return JsonResponse({
                        'error': 'rate_limit_exceeded',
                        'message': f'Too many requests. Please try again later.',
                        'retry_after': window
                    }, status=429)
                
                # Increment counter
                cache.set(cache_key, current + 1, window)
                
        return None
    
    def should_rate_limit(self, request):
        """Determine if request should be rate limited."""
        # Skip rate limiting for internal IPs in debug mode
        if settings.DEBUG and request.META.get('REMOTE_ADDR') in ['127.0.0.1', 'localhost']:
            return False
        
        # Skip for authenticated admin users
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
            return False
        
        return True
    
    def get_client_id(self, request):
        """Get unique client identifier."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f'user:{request.user.id}'
        
        # Use IP + User-Agent for anonymous users
        ip = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return hashlib.md5(f'{ip}:{user_agent}'.encode()).hexdigest()


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses."""
    
    def process_response(self, request, response):
        """Add security headers."""
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.mycoolpay.com; "
            "frame-ancestors 'none';"
        )
        
        # Other security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(self), camera=(), microphone=()'
        
        # HSTS for production
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


class AuditLogMiddleware(MiddlewareMixin):
    """Log sensitive operations for audit trail."""
    
    SENSITIVE_OPERATIONS = [
        ('POST', 'auth/login'),
        ('POST', 'auth/register'),
        ('DELETE', 'auth/delete-account'),
        ('POST', 'profiles/.*/verification/submit'),
        ('POST', 'subscriptions/purchase'),
        ('POST', 'subscriptions/.*/cancel'),
    ]
    
    def process_response(self, request, response):
        """Log sensitive operations."""
        if self.should_log(request, response):
            self.log_operation(request, response)
        
        return response
    
    def should_log(self, request, response):
        """Determine if operation should be logged."""
        path = request.path.lstrip('/api/v1/')
        
        for method, pattern in self.SENSITIVE_OPERATIONS:
            if request.method == method and re.match(pattern, path):
                return True
        
        # Log all admin operations
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Log failed authentication attempts
        if response.status_code == 401:
            return True
        
        return False
    
    def log_operation(self, request, response):
        """Log the operation details."""
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
            'ip_address': request.META.get('REMOTE_ADDR'),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'user_agent': request.META.get('HTTP_USER_AGENT'),
        }
        
        # Log sensitive operations to separate audit log
        logger.info(f"AUDIT: {log_data}")


class SuspiciousBehaviorDetector:
    """Detect and prevent suspicious behavior patterns."""
    
    @staticmethod
    def check_rapid_swipes(user):
        """Check for unnaturally rapid swiping."""
        cache_key = f'swipe_rate:{user.id}'
        swipe_times = cache.get(cache_key, [])
        current_time = time.time()
        
        # Keep only swipes from last minute
        swipe_times = [t for t in swipe_times if current_time - t < 60]
        swipe_times.append(current_time)
        
        cache.set(cache_key, swipe_times, 60)
        
        # Flag if more than 60 swipes per minute
        if len(swipe_times) > 60:
            logger.warning(f"Suspicious swiping rate detected for user {user.id}")
            return True
        
        return False
    
    @staticmethod
    def check_message_patterns(user, message_content):
        """Check for spam/scam message patterns."""
        spam_patterns = [
            r'click.*(here|link)',
            r'(wire|send).*(money|cash|bitcoin)',
            r'(viagra|cialis|porn)',
            r'(prize|winner|congratulations).*claim',
            r'https?://[^\s]+\.(tk|ml|ga|cf)',  # Suspicious domains
        ]
        
        content_lower = message_content.lower()
        
        for pattern in spam_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                logger.warning(f"Spam pattern detected from user {user.id}: {pattern}")
                return True
        
        # Check for repeated messages
        cache_key = f'message_history:{user.id}'
        message_history = cache.get(cache_key, [])
        
        if message_content in message_history[-5:]:
            logger.warning(f"Repeated message detected from user {user.id}")
            return True
        
        message_history.append(message_content)
        cache.set(cache_key, message_history[-10:], 3600)  # Keep last 10 messages
        
        return False
    
    @staticmethod
    def check_profile_changes(user, changes):
        """Check for suspicious profile changes."""
        cache_key = f'profile_changes:{user.id}'
        change_history = cache.get(cache_key, [])
        current_time = time.time()
        
        # Keep changes from last hour
        change_history = [c for c in change_history if current_time - c['time'] < 3600]
        change_history.append({'time': current_time, 'changes': list(changes.keys())})
        
        cache.set(cache_key, change_history, 3600)
        
        # Flag if too many changes
        if len(change_history) > 10:
            logger.warning(f"Excessive profile changes detected for user {user.id}")
            return True
        
        return False


class DataEncryption:
    """Utilities for encrypting sensitive data."""
    
    @staticmethod
    def encrypt_pii(data):
        """Encrypt personally identifiable information."""
        from cryptography.fernet import Fernet
        
        # Get or generate encryption key
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key:
            raise ValueError("ENCRYPTION_KEY not configured")
        
        f = Fernet(key.encode() if isinstance(key, str) else key)
        
        if isinstance(data, str):
            return f.encrypt(data.encode()).decode()
        elif isinstance(data, dict):
            encrypted = {}
            for k, v in data.items():
                if k in ['ssn', 'medical_id', 'real_name']:
                    encrypted[k] = f.encrypt(str(v).encode()).decode()
                else:
                    encrypted[k] = v
            return encrypted
        
        return data
    
    @staticmethod
    def decrypt_pii(encrypted_data):
        """Decrypt personally identifiable information."""
        from cryptography.fernet import Fernet
        
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key:
            raise ValueError("ENCRYPTION_KEY not configured")
        
        f = Fernet(key.encode() if isinstance(key, str) else key)
        
        if isinstance(encrypted_data, str):
            return f.decrypt(encrypted_data.encode()).decode()
        elif isinstance(encrypted_data, dict):
            decrypted = {}
            for k, v in encrypted_data.items():
                if k in ['ssn', 'medical_id', 'real_name'] and v:
                    try:
                        decrypted[k] = f.decrypt(v.encode()).decode()
                    except:
                        decrypted[k] = v  # Return as-is if decryption fails
                else:
                    decrypted[k] = v
            return decrypted
        
        return encrypted_data