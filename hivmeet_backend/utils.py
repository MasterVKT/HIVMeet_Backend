"""
Utility functions for HIVMeet backend.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger('hivmeet')

def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Log the error
        logger.error(
            f"API Error: {exc.__class__.__name__} - {str(exc)} - "
            f"Path: {context['request'].path} - Method: {context['request'].method}"
        )
        
        # Customize the response format
        custom_response_data = {
            'error': True,
            'message': str(exc),
            'details': response.data if hasattr(response, 'data') else {},
            'status_code': response.status_code
        }
        
        # Add error code if available
        if hasattr(exc, 'default_code'):
            custom_response_data['error_code'] = exc.default_code
            
        response.data = custom_response_data
    
    return response