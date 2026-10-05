"""Private location updates and privacy-safe distance calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.utils import timezone

from .models import GeoCity, Profile


FRESH_LOCATION_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class ProfileDistance:
    km: int | None
    estimated: bool
    same_city: bool


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance without exposing the underlying coordinates."""
    lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))


def has_recent_precise_location(profile: Profile) -> bool:
    return bool(
        profile.latitude is not None
        and profile.longitude is not None
        and profile.location_updated_at is not None
        and profile.location_updated_at >= timezone.now() - FRESH_LOCATION_WINDOW
    )


def city_for_coordinates(latitude: Decimal | float, longitude: Decimal | float):
    """Return a nearby catalog city, if GeoNames data is installed.

    The bounding box limits the Python refinement and makes a missing catalogue
    a normal manual-selection fallback rather than an external geocoding call.
    """
    latitude = float(latitude)
    longitude = float(longitude)
    candidates = GeoCity.objects.filter(
        latitude__gte=latitude - 1,
        latitude__lte=latitude + 1,
        longitude__gte=longitude - 1,
        longitude__lte=longitude + 1,
    ).select_related('country')
    nearest = None
    nearest_distance = float('inf')
    for city in candidates.iterator():
        distance = haversine_km(latitude, longitude, city.latitude, city.longitude)
        if distance < nearest_distance:
            nearest = city
            nearest_distance = distance
    return nearest if nearest_distance <= 100 else None


def distance_between(viewer: Profile, target: Profile) -> ProfileDistance:
    """Return only a rounded distance and whether it was estimated."""
    if target.hide_exact_location:
        return ProfileDistance(km=None, estimated=False, same_city=False)
    if has_recent_precise_location(viewer) and has_recent_precise_location(target):
        return ProfileDistance(
            km=max(1, round(haversine_km(
                viewer.latitude, viewer.longitude, target.latitude, target.longitude,
            ))),
            estimated=False,
            same_city=False,
        )
    if viewer.geo_city_id and target.geo_city_id:
        if viewer.geo_city_id == target.geo_city_id:
            return ProfileDistance(km=None, estimated=True, same_city=True)
        return ProfileDistance(
            km=max(1, round(haversine_km(
                viewer.geo_city.latitude, viewer.geo_city.longitude,
                target.geo_city.latitude, target.geo_city.longitude,
            ))),
            estimated=True,
            same_city=False,
        )
    return ProfileDistance(km=None, estimated=True, same_city=False)
