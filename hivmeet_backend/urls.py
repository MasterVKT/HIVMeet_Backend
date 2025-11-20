"""
URL configuration for HIVMeet backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from .health import health_check_view, simple_health_check_view, readiness_check_view, metrics_view

# API documentation schema
schema_view = get_schema_view(
    openapi.Info(
        title="HIVMeet API",
        default_version='v1',
        description="API documentation for HIVMeet dating application",
        terms_of_service="https://www.hivmeet.com/terms/",
        contact=openapi.Contact(email="contact@hivmeet.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Health check endpoints
    path('health/', health_check_view, name='health-check'),
    path('health/simple/', simple_health_check_view, name='simple-health-check'),
    path('health/ready/', readiness_check_view, name='readiness-check'),
    path('metrics/', metrics_view, name='metrics'),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API endpoints
    path('api/v1/', include('hivmeet_backend.api_urls')),
    path('api/v1/auth/', include('authentication.urls')),
]

# Internationalized admin
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),
)

# Debug toolbar
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    # Static and media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)