"""Private profile-photo storage and authorisation-aware delivery URLs."""

from __future__ import annotations

import warnings
from io import BytesIO

from django.conf import settings
from django.urls import reverse
from PIL import Image, ImageOps

from .private_storage import (
    PrivateObjectIntegrityError,
    PrivateStorageUnavailable,
    delete_legacy_profile_object,
    legacy_profile_object_path,
    private_object_storage,
)


class ProfilePhotoStorageUnavailable(RuntimeError):
    """The private profile-media boundary cannot complete the requested action."""


class ProfilePhotoStorage:
    _main_size = (1920, 1920)
    _thumbnail_size = (200, 200)

    def upload_image(self, *, image_data: bytes, owner_id: str):
        """Store processed image bytes under random private keys.

        ``owner_id`` remains part of the public method for compatibility, but
        is intentionally never used in an object key.
        """
        del owner_id
        main_key = None
        thumbnail_key = None
        previous_limit = Image.MAX_IMAGE_PIXELS
        try:
            if len(image_data) > settings.PROFILE_MEDIA_MAX_UPLOAD_BYTES:
                raise ValueError('profile_image_byte_limit_exceeded')
            Image.MAX_IMAGE_PIXELS = settings.PROFILE_MEDIA_MAX_IMAGE_PIXELS
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                image = ImageOps.exif_transpose(Image.open(BytesIO(image_data)))
                image.load()
            if image.width * image.height > settings.PROFILE_MEDIA_MAX_IMAGE_PIXELS:
                raise ValueError('profile_image_pixel_limit_exceeded')
            if image.mode != 'RGB':
                image = image.convert('RGB')
            main_data = self._jpeg_bytes(image, self._main_size)
            thumbnail_data = self._jpeg_bytes(image, self._thumbnail_size)
            main_key = private_object_storage.new_key('profile')
            thumbnail_key = private_object_storage.new_key('profile')
            private_object_storage.put_bytes(
                scope='profile', key=main_key, data=main_data, content_type='image/jpeg',
            )
            private_object_storage.put_bytes(
                scope='profile', key=thumbnail_key, data=thumbnail_data, content_type='image/jpeg',
            )
            return {
                'storage_key': main_key,
                'thumbnail_storage_key': thumbnail_key,
            }
        except (
            PrivateStorageUnavailable,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            for key in (main_key, thumbnail_key):
                if key:
                    try:
                        self.delete_private_key(key)
                    except ProfilePhotoStorageUnavailable:
                        # The caller cannot link an incomplete upload to a
                        # profile row. Preserve the original safe failure;
                        # object-store lifecycle remains the final guard.
                        pass
            raise ProfilePhotoStorageUnavailable() from None
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit

    def _jpeg_bytes(self, image, size: tuple[int, int]) -> bytes:
        output = image.copy()
        output.thumbnail(size, Image.Resampling.LANCZOS)
        buffer = BytesIO()
        output.save(buffer, format='JPEG', quality=85, optimize=True)
        return buffer.getvalue()

    def delete_private_key(self, key: str | None):
        if not key:
            return
        try:
            private_object_storage.delete(scope='profile', key=key)
        except (PrivateObjectIntegrityError, PrivateStorageUnavailable):
            # Caller persists a retryable migration/purge state. Do not leak a
            # key in logs from a best-effort cleanup path.
            raise ProfilePhotoStorageUnavailable() from None

    def delete_photo(self, photo):
        """Delete private keys, or a recognised legacy object during migration."""
        if getattr(photo, 'storage_key', ''):
            self.delete_private_key(photo.storage_key)
        if getattr(photo, 'thumbnail_storage_key', ''):
            self.delete_private_key(photo.thumbnail_storage_key)
        # A row in ``migration_copied`` can temporarily own both the verified
        # private copy and its legacy source. Deleting the row must clean both.
        if getattr(photo, 'legacy_source_verified', False):
            owner_id = getattr(getattr(photo, 'profile', None), 'user_id', None)
            if owner_id is not None:
                self.delete_legacy_reference(
                    getattr(photo, 'photo_url', ''), owner_id=owner_id,
                )
                self.delete_legacy_reference(
                    getattr(photo, 'thumbnail_url', ''), owner_id=owner_id,
                )

    def delete_legacy_reference(self, value: str | None, *, owner_id):
        """Cleanup a verified historical source owned by this profile only."""
        if not value:
            return
        path = legacy_profile_object_path(value, owner_id=owner_id)
        if path:
            try:
                if not delete_legacy_profile_object(path):
                    raise PrivateStorageUnavailable()
            except PrivateStorageUnavailable:
                raise ProfilePhotoStorageUnavailable() from None

def profile_photo_delivery_url(photo, request, *, thumbnail=False):
    """Return an authenticated media endpoint only for current access rights."""
    if request is None or not getattr(request.user, 'is_authenticated', False):
        return None
    key = photo.thumbnail_storage_key if thumbnail else photo.storage_key
    if not key or photo.storage_state not in {photo.PRIVATE, photo.MIGRATION_COPIED}:
        return None
    owner_id = photo.profile.user_id
    if request.user.id != owner_id:
        from .kyc import has_active_kyc

        # Serializers may render several photos in one response. The decision
        # remains live for every HTTP request, while this per-request memo
        # avoids turning a media list into one KYC query per photo.
        if not hasattr(request, '_hivmeet_active_kyc_for_media'):
            request._hivmeet_active_kyc_for_media = has_active_kyc(request.user)
        if not request._hivmeet_active_kyc_for_media:
            return None
    variant = 'thumbnail' if thumbnail else 'main'
    return request.build_absolute_uri(reverse(
        'api:profiles:profile-photo-media',
        kwargs={'photo_id': photo.id, 'variant': variant},
    ))


profile_photo_storage = ProfilePhotoStorage()
