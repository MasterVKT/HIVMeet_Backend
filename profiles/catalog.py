"""Versioned, verified GeoNames catalogue import helpers."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable

from django.db import transaction

from .models import GeoCatalogRelease, GeoCity, GeoCountry

CATALOG_VERSION = 'geonames-2026-09'
GEONAMES_ATTRIBUTION_URL = 'https://www.geonames.org/about.html'
DATA_DIR = Path(__file__).resolve().parent / 'data'
COUNTRY_SOURCE = DATA_DIR / 'countryInfo.txt'
FRENCH_TERRITORIES_SOURCE = DATA_DIR / 'territories_fr.json'
CITY_SOURCE = DATA_DIR / 'cities500-geonames-2026-09.zip'


def normalize_catalog_search(value: str) -> str:
    """Case/diacritic-insensitive, indexable search representation."""
    decomposed = unicodedata.normalize('NFKD', value or '')
    return ''.join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()


def file_sha256(source_path: Path) -> str:
    digest = hashlib.sha256()
    with source_path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def iter_countries() -> Iterable[dict]:
    """Yield ISO country rows from the checked-in GeoNames country source."""
    french_names = {}
    if FRENCH_TERRITORIES_SOURCE.exists():
        with FRENCH_TERRITORIES_SOURCE.open(encoding='utf-8') as source:
            french_names = (json.load(source).get('main', {}).get('fr', {})
                .get('localeDisplayNames', {}).get('territories', {}))
    with COUNTRY_SOURCE.open(encoding='utf-8') as source:
        for row in csv.reader(source, delimiter='\t'):
            if not row or row[0].startswith('#') or len(row) < 17:
                continue
            code = row[0].strip().upper()
            if len(code) != 2:
                continue
            name = row[4].strip()
            name_fr = french_names.get(code, '')
            yield {
                'code': code,
                'geonames_id': int(row[16]) if row[16].isdigit() else None,
                'name': name,
                'name_fr': name_fr,
                'search_name': normalize_catalog_search(f'{code} {name} {name_fr}'),
            }


def sync_countries() -> int:
    rows = list(iter_countries())
    with transaction.atomic():
        for row in rows:
            GeoCountry.objects.update_or_create(
                code=row['code'], defaults={**row, 'catalog_version': CATALOG_VERSION},
            )
    return len(rows)


def iter_cities(source_path: Path = CITY_SOURCE) -> Iterable[dict]:
    """Stream populated-place entries only from a GeoNames archive."""
    with zipfile.ZipFile(source_path) as archive:
        member = next((name for name in archive.namelist() if name.endswith('.txt')), None)
        if member is None:
            raise ValueError('GeoNames archive contains no .txt data file.')
        with archive.open(member) as raw:
            for row in csv.reader(io.TextIOWrapper(raw, encoding='utf-8'), delimiter='\t'):
                if len(row) < 15 or row[6] != 'P' or not row[8]:
                    continue
                try:
                    name, ascii_name = row[1].strip(), row[2].strip()
                    yield {
                        'geonames_id': int(row[0]),
                        'country_id': row[8].upper(),
                        'name': name,
                        'ascii_name': ascii_name,
                        'search_name': normalize_catalog_search(f'{name} {ascii_name}'),
                        'latitude': row[4],
                        'longitude': row[5],
                        'population': int(row[14] or 0),
                        'catalog_version': CATALOG_VERSION,
                    }
                except (TypeError, ValueError):
                    continue


def sync_cities(source_path: Path = CITY_SOURCE, *, expected_sha256: str, batch_size: int = 2000) -> int:
    """Verify then upsert a complete catalogue, recording its release manifest."""
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    actual_sha256 = file_sha256(source_path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError('GeoNames archive checksum does not match --sha256.')
    known_countries = set(GeoCountry.objects.values_list('code', flat=True))
    batch: list[GeoCity] = []
    total = 0
    with transaction.atomic():
        for row in iter_cities(source_path):
            if row['country_id'] not in known_countries:
                continue
            batch.append(GeoCity(**row))
            if len(batch) >= batch_size:
                GeoCity.objects.bulk_create(batch, batch_size=batch_size, update_conflicts=True,
                    update_fields=['country', 'name', 'ascii_name', 'search_name', 'latitude', 'longitude', 'population', 'catalog_version'],
                    unique_fields=['geonames_id'])
                total += len(batch)
                batch.clear()
        if batch:
            GeoCity.objects.bulk_create(batch, batch_size=batch_size, update_conflicts=True,
                update_fields=['country', 'name', 'ascii_name', 'search_name', 'latitude', 'longitude', 'population', 'catalog_version'],
                unique_fields=['geonames_id'])
            total += len(batch)
        if total == 0:
            raise ValueError('GeoNames import has no populated places.')
        GeoCatalogRelease.objects.update_or_create(
            catalog_version=CATALOG_VERSION,
            defaults={'sha256': actual_sha256, 'city_count': total, 'attribution_url': GEONAMES_ATTRIBUTION_URL},
        )
    return total


def catalog_is_healthy() -> bool:
    return (GeoCity.objects.filter(catalog_version=CATALOG_VERSION).exists()
        and GeoCatalogRelease.objects.filter(catalog_version=CATALOG_VERSION, city_count__gt=0).exists())
