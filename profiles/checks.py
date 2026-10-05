"""Deployment checks for the versioned geographical catalogue."""
from django.conf import settings
from django.core.checks import Error, register
from django.db import OperationalError, ProgrammingError


@register(deploy=True)
def geonames_catalog_check(app_configs, **kwargs):
    if not getattr(settings, 'GEONAMES_CATALOG_REQUIRED', False):
        return []
    try:
        from .catalog import catalog_is_healthy
        healthy = catalog_is_healthy()
    except (OperationalError, ProgrammingError):
        # Schema setup runs checks before this migration in some deployment
        # environments.  The post-migration readiness command remains strict.
        return []
    if healthy:
        return []
    return [Error(
        'The verified GeoNames populated-place catalogue is unavailable.',
        hint='Run sync_geonames_catalog with the release SHA-256, then verify_geonames_catalog.',
        id='profiles.E001',
    )]
