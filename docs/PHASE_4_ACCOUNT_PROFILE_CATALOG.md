# Phase 4 - Accounts, profiles and geographic catalogue

## Deployment order

1. Deploy the backend with `profiles.0008_phase4_registration_gender_catalog` and run `python manage.py migrate`.
2. Import a verified GeoNames `cities500` artifact:

   ```bash
   python manage.py sync_geonames_catalog --source /releases/geonames/cities500.zip --sha256 <published-sha256>
   python manage.py verify_geonames_catalog
   ```

   The import records its version, SHA-256, number of cities and GeoNames attribution: <https://www.geonames.org/about.html>. `check --deploy` fails when `GEONAMES_CATALOG_REQUIRED=True` and no verified catalogue is ready.
3. Deploy the Flutter application that sends `display_name`, `birth_date`, optional `phone_number` and `gender` (`male` or `female`) to `POST /api/v1/auth/register/` before Firebase sign-in.
4. Keep `HIVMEET_REQUIRE_EXPLICIT_REGISTRATION=False` only for the controlled legacy-client rollout. It creates a blank, non-discoverable confirmation profile for Firebase-only identities. Once the compatible Flutter release is available, remove that temporary setting (the secure default is `True`): the exchange never creates a local account and can only attach a Firebase UID to a pre-rollout local account with the same email and no existing UID.

## Migration and rollback

`profiles.0008_phase4_registration_gender_catalog` and `profiles.0009_normalize_sought_gender_single_choice` add an auditable catalogue release manifest, accent-insensitive search keys, and profile gender-confirmation state. Historical `city` and `country` strings remain available for legacy clients. Public profile DTOs never expose coordinates.

Existing `male` and `female` values remain unchanged. Every other legacy value is stored internally in `legacy_gender`, cleared, marked as requiring confirmation, and removed from Discovery. No value is inferred. Sought genders are normalized to `[]`, `['male']` or `['female']`; relationships are normalized to `friendship`, `long_term`, `short_term` and `casual`.

A schema rollback restores `legacy_gender` only for profiles that have not explicitly chosen again. The removal of unsupported legacy preferences is deliberate: export profiles before any data rollback if those original values must be retained externally.

## Contracts

- `POST /api/v1/auth/register/` requires `email`, `password`, `password_confirm`, `display_name`, `birth_date`, and `gender`; it accepts optional `phone_number`. Firebase is provisioned first and deleted if the Django transaction fails.
- `POST /api/v1/auth/firebase-exchange/` returns `409 registration_required` for an unknown Firebase identity when `HIVMEET_REQUIRE_EXPLICIT_REGISTRATION=True`. The temporary bridge is documented above and never assigns a gender or exposes the resulting profile in Discovery.
- `PUT|PATCH /api/v1/user-profiles/me/complete/` accepts `{ "profile": {...}, "location": {...} }`. If a location is supplied, both parts validate and persist in one transaction.
- `GET /api/v1/user-profiles/geo/countries/` and `geo/cities/?country=XX` provide paginated, case-insensitive and accent-insensitive catalogue search.
- Automatic coordinates may contain nine decimals on input and are quantized to seven decimals before storage. Manual location remains available and removes precise coordinates.

A chosen gender is immutable and returns the business code `gender_immutable` on attempted change. An unconfirmed profile is excluded from Discovery even if a stale legacy visibility flag exists.
