"""
URLs for matching app.
"""
from django.urls import path, include

app_name = 'matching'

urlpatterns = [
    # Discovery endpoints
    path('discovery/', include('matching.urls_discovery')),
    
    # Matches endpoints  
    path('matches/', include('matching.urls_matches')),
]
