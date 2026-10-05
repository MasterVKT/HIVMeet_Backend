"""
Views for profiles app.
"""
from rest_framework import generics, status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
import logging

from .catalog import normalize_catalog_search
from .models import GeoCity, GeoCountry, Profile, ProfilePhoto
from .serializers import (
    ProfileSerializer,
    ProfileCreateUpdateSerializer,
    PublicProfileSerializer,
    ProfilePhotoSerializer,
    PhotoUploadSerializer,
    GeoCitySerializer,
    GeoCountrySerializer,
    PhotoReorderSerializer,
    ProfileLocationUpdateSerializer,
    KycStartSerializer,
    KycUploadIntentRequestSerializer,
    KycUploadCompleteSerializer,
    KycSubmitRequestSerializer,
)
from hivmeet_backend.utils import api_error_response
from .photo_storage import (
    profile_photo_delivery_url,
    profile_photo_storage,
    ProfilePhotoStorageUnavailable,
)
# Kept as a test/import compatibility alias for legacy integrations.  New
# profile media is handled exclusively by profile_photo_storage above.
from hivmeet_backend.storage.manager import storage_manager
from .kyc import (
    KycLegacyEndpointDeprecated,
    KycRequired,
    has_active_kyc,
    issue_kyc_upload_intent,
    mark_kyc_upload_complete,
    serialize_kyc_upload_intent,
    serialize_safe_kyc_status,
    start_or_resume_kyc_attempt,
    submit_kyc_attempt,
)
from subscriptions.utils import is_premium_user

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


def _kyc_private_response(payload, *, response_status=status.HTTP_200_OK):
    """Return KYC state without allowing a browser or proxy to retain it.

    The start response contains the one-use selfie challenge and the upload
    intent response contains a transient signed PUT URL. Applying the same
    policy to all KYC state responses prevents future payload changes from
    accidentally becoming cacheable.
    """
    response = Response(payload, status=response_status)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class MyProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update the current user's profile.
    
    GET /api/v1/user-profiles/me
    PUT/PATCH /api/v1/user-profiles/me
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProfileCreateUpdateSerializer
        return ProfileSerializer
    
    def get_object(self):
        """Get or create profile for current user."""
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        if created:
            logger.info("Profile created")
        return profile
    
    def perform_update(self, serializer):
        """Update profile and log the action."""
        serializer.save()
        logger.info("Profile updated")

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
            gender_errors = exc.detail.get('gender', [])
            if any(getattr(error, 'code', None) == 'gender_immutable' for error in gender_errors):
                response.data = {
                    'code': 'gender_immutable',
                    'message': _('Gender cannot be changed.'),
                    'details': response.data,
                }
        return response


class UserProfileView(generics.RetrieveAPIView):
    """
    Get another user's public profile.
    
    GET /api/v1/user-profiles/{user_id}
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PublicProfileSerializer
    lookup_field = 'user__id'
    lookup_url_kwarg = 'user_id'
    
    def get_queryset(self):
        """Get public profiles plus an active match participant's profile."""
        from matching.models import Match

        user = self.request.user
        active_match = (
            Q(
                user__matches_as_user1__user2=user,
                user__matches_as_user1__status=Match.ACTIVE,
            )
            | Q(
                user__matches_as_user2__user1=user,
                user__matches_as_user2__status=Match.ACTIVE,
            )
        )
        public_profile = Q(is_hidden=False, allow_profile_in_discovery=True)
        return (
            Profile.objects.filter(user__is_active=True)
            .filter(public_profile | active_match)
            .select_related('user')
            .prefetch_related('photos')
            .distinct()
        )
    
    def get_object(self):
        """Get profile and check permissions."""
        queryset = self.get_queryset()
        
        # Get the profile
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_url_kwarg]}
        profile = get_object_or_404(queryset, **filter_kwargs)
        
        # Check if user is blocked
        if self.request.user in profile.user.blocked_users.all():
            raise PermissionDenied(_("You cannot view this profile."))
        
        # Check if current user is blocked by this user
        if profile.user in self.request.user.blocked_users.all():
            raise PermissionDenied(_("You cannot view this profile."))

        # Enforce the locked Free-Free policy for deep links too.  The Match
        # list itself only contains a minimal card in that state.
        from matching.free_access import FreeMatchAccessService
        from matching.models import Match

        match = Match.get_match_between(self.request.user, profile.user)
        if match and not FreeMatchAccessService.state_for(
            match, self.request.user
        )['can_view_profile']:
            raise PermissionDenied(
                {'code': 'free_match_locked', 'message': _(
                    'This Free match is locked until both monthly accesses are available.'
                )}
            )

        # Increment view count
        profile.increment_views()
        
        return profile


class GeoCatalogPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 300


class GeoCountryListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GeoCountrySerializer
    pagination_class = GeoCatalogPagination

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        queryset = GeoCountry.objects.all()
        if query:
            normalized = normalize_catalog_search(query)
            queryset = queryset.filter(
                Q(code__icontains=query) | Q(name__icontains=query) |
                Q(name_fr__icontains=query) | Q(search_name__contains=normalized)
            )
        return queryset


class GeoCityListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GeoCitySerializer
    pagination_class = GeoCatalogPagination

    def get_queryset(self):
        country = self.request.query_params.get('country', '').strip().upper()
        if len(country) != 2:
            return GeoCity.objects.none()
        query = self.request.query_params.get('q', '').strip()
        queryset = GeoCity.objects.filter(country_id=country).select_related('country')
        if query:
            queryset = queryset.filter(
                Q(search_name__contains=normalize_catalog_search(query)) |
                Q(name__icontains=query) | Q(ascii_name__icontains=query)
            )
        return queryset


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_profile_location_view(request):
    """Store a manual catalog city or a fresh foreground device reading."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    serializer = ProfileLocationUpdateSerializer(
        profile, data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    profile = serializer.save()
    return Response(ProfileSerializer(profile, context={'request': request}).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_profile_and_location_view(request):
    """Apply profile and location updates in one database transaction.

    Payload is additive: ``profile`` uses the normal profile fields and
    ``location`` uses the dedicated privacy-safe location contract.  When a
    location is included, a failed location validation leaves profile data
    untouched.
    """
    if not isinstance(request.data.get('profile'), dict):
        return Response(
            {'code': 'profile_required', 'message': _('A profile object is required.')},
            status=status.HTTP_400_BAD_REQUEST,
        )
    location_data = request.data.get('location')
    if location_data is not None and not isinstance(location_data, dict):
        return Response(
            {'code': 'invalid_location', 'message': _('Location must be an object.')},
            status=status.HTTP_400_BAD_REQUEST,
        )
    with transaction.atomic():
        profile, _ = Profile.objects.select_for_update().get_or_create(user=request.user)
        profile_serializer = ProfileCreateUpdateSerializer(
            profile, data=request.data['profile'], partial=request.method == 'PATCH',
            context={'request': request},
        )
        profile_serializer.is_valid(raise_exception=True)
        location_serializer = None
        if location_data is not None:
            location_serializer = ProfileLocationUpdateSerializer(
                profile, data=location_data, context={'request': request},
            )
            location_serializer.is_valid(raise_exception=True)
        profile = profile_serializer.save()
        if location_serializer is not None:
            profile = location_serializer.update(profile, location_serializer.validated_data)
    return Response(ProfileSerializer(profile, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_photo_view(request):
    """
    Upload a profile photo.
    
    POST /api/v1/user-profiles/me/photos
    """
    serializer = PhotoUploadSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    upload_result = None
    try:
        profile = request.user.profile
        
        # Check photo limit
        photo_count = profile.photos.count()
        max_photos = 6 if is_premium_user(request.user) else 1
        
        if photo_count >= max_photos:
            return Response({
                'error': True,
                'message': _('Photo limit reached. %(max)d photos allowed.') % {'max': max_photos}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Development uses local media storage. Production uses the configured
        # object-storage provider and never falls back to local files.
        file = serializer.validated_data['file']
        upload_result = profile_photo_storage.upload_image(
            image_data=file.read(),
            owner_id=str(request.user.id),
        )
        
        # Create photo record
        with transaction.atomic():
            photo = ProfilePhoto.objects.create(
                profile=profile,
                photo_url='',
                thumbnail_url='',
                storage_key=upload_result['storage_key'],
                thumbnail_storage_key=upload_result['thumbnail_storage_key'],
                storage_state=ProfilePhoto.PRIVATE,
                private_migrated_at=timezone.now(),
                is_main=serializer.validated_data.get('is_main', False) or photo_count == 0,
                caption=serializer.validated_data.get('caption', ''),
                order=photo_count
        )

        logger.info("Profile photo uploaded")

        return Response(_photo_payload(photo, request), status=status.HTTP_201_CREATED)

    except ProfilePhotoStorageUnavailable:
        logger.warning("Profile photo storage unavailable")
        return api_error_response(
            'photo_storage_unavailable',
            _('Photo storage is temporarily unavailable.'),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        if upload_result:
            _delete_uploaded_photo(upload_result)
        # Do not attach exception traces: object-store providers can embed
        # object keys or request URLs in their exception text.
        logger.error("Profile photo upload failed")
        return Response({
            'error': True,
            'message': _('Failed to upload photo. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def set_main_photo_view(request, photo_id):
    """
    Set a photo as the main profile photo.
    
    PUT /api/v1/user-profiles/me/photos/{photo_id}/set-main
    """
    try:
        with transaction.atomic():
            photo = ProfilePhoto.objects.select_for_update().get(
                id=photo_id,
                profile__user=request.user,
            )
            # Evaluating the queryset is required for select_for_update() to
            # hold a row lock while the main-photo invariant is changed.
            photos = list(
                ProfilePhoto.objects.select_for_update().filter(
                    profile=photo.profile
                )
            )
            for item in photos:
                if item.id != photo.id and item.is_main:
                    item.is_main = False
                    item.save(update_fields=['is_main'])
            photo.is_main = True
            photo.save(update_fields=['is_main'])
        
        logger.info("Profile main photo updated")
        
        return Response({
            'message': _('Main photo updated successfully.')
        }, status=status.HTTP_200_OK)
        
    except ProfilePhoto.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Photo not found.')
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def delete_photo_view(request, photo_id):
    """
    Delete a profile photo.

    DELETE /api/v1/user-profiles/me/photos/{photo_id}
    """
    if request.method == 'PUT':
        return _replace_photo(request, photo_id)

    try:
        with transaction.atomic():
            photo = ProfilePhoto.objects.select_for_update().get(
                id=photo_id,
                profile__user=request.user,
            )
            profile = Profile.objects.select_for_update().get(pk=photo.profile_id)
            photos = list(ProfilePhoto.objects.select_for_update().filter(profile=profile))
            was_main = photo.is_main
            if was_main and len(photos) == 1:
                return Response({
                    'error': True,
                    'message': _('Cannot delete the only photo.')
                }, status=status.HTTP_400_BAD_REQUEST)
            # Ensure no other photo temporarily becomes main while we delete.
            if was_main:
                # Promote the next photo (by order) before deleting.
                next_photo = next(
                    (item for item in sorted(photos, key=lambda value: (value.order, value.uploaded_at))
                     if item.id != photo.id),
                    None,
                )
                if next_photo:
                    # Reset all other photos' main flag, then promote the chosen one.
                    ProfilePhoto.objects.filter(profile=profile).exclude(id=next_photo.id).update(is_main=False)
                    ProfilePhoto.objects.filter(id=next_photo.id).update(is_main=True)

            original_references = _photo_references(photo)
            photo.delete()

            remaining = list(profile.photos.order_by('order', 'uploaded_at'))
            changed = []
            for index, item in enumerate(remaining):
                if item.order != index:
                    item.order = index
                    changed.append(item)
            if changed:
                ProfilePhoto.objects.bulk_update(changed, ['order'])
            transaction.on_commit(
                lambda references=original_references: _delete_photo_references(references)
            )

        logger.info("Profile photo deleted")

        return Response(status=status.HTTP_204_NO_CONTENT)

    except ProfilePhoto.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Photo not found.')
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def reorder_photos_view(request):
    """Atomically reorder the exact current photo set for Premium users."""
    if not is_premium_user(request.user):
        return Response(
            {'error': 'premium_required', 'message': _('Premium is required to reorder photos.')},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = PhotoReorderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    requested_ids = serializer.validated_data['photo_ids']
    if len(set(requested_ids)) != len(requested_ids):
        return Response(
            {'error': 'duplicate_photo_id', 'message': _('Each photo can appear only once.')},
            status=status.HTTP_400_BAD_REQUEST,
        )
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        photos = list(ProfilePhoto.objects.select_for_update().filter(profile=profile))
        current_ids = {photo.id for photo in photos}
        if set(requested_ids) != current_ids:
            return Response(
                {'error': 'photo_set_changed', 'message': _('Photos changed. Refresh and try again.')},
                status=status.HTTP_409_CONFLICT,
            )
        order_by_id = {photo_id: index for index, photo_id in enumerate(requested_ids)}
        for photo in photos:
            photo.order = order_by_id[photo.id]
        ProfilePhoto.objects.bulk_update(photos, ['order'])
    ordered = ProfilePhoto.objects.filter(profile=profile).order_by('order', 'uploaded_at')
    return Response(ProfilePhotoSerializer(ordered, many=True, context={'request': request}).data)


def _photo_references(photo):
    return {
        'profile_user_id': photo.profile.user_id,
        'storage_key': photo.storage_key,
        'thumbnail_storage_key': photo.thumbnail_storage_key,
        'photo_url': photo.photo_url,
        'thumbnail_url': photo.thumbnail_url,
        'legacy_source_verified': photo.legacy_source_verified,
    }


def _delete_photo_references(references):
    for key_name in ('storage_key', 'thumbnail_storage_key'):
        if references.get(key_name):
            profile_photo_storage.delete_private_key(references[key_name])
    # Only the controlled cutover may authorise deletion of a historical
    # reference. A raw value written after the cutover is neither delivered
    # nor used as a deletion target.
    if references.get('legacy_source_verified') and references.get('profile_user_id'):
        profile_photo_storage.delete_legacy_reference(
            references.get('photo_url'),
            owner_id=references['profile_user_id'],
        )
        profile_photo_storage.delete_legacy_reference(
            references.get('thumbnail_url'),
            owner_id=references['profile_user_id'],
        )


def _delete_uploaded_photo(upload_result):
    _delete_photo_references({
        'storage_key': upload_result.get('storage_key'),
        'thumbnail_storage_key': upload_result.get('thumbnail_storage_key'),
    })


def _replace_photo(request, photo_id):
    """Replace a photo without changing its id, order or main-photo status."""
    serializer = PhotoUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        ProfilePhoto.objects.get(id=photo_id, profile__user=request.user)
    except ProfilePhoto.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Photo not found.'),
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        upload_result = profile_photo_storage.upload_image(
            image_data=serializer.validated_data['file'].read(),
            owner_id=str(request.user.id),
        )
    except ProfilePhotoStorageUnavailable:
        logger.warning("Profile photo storage unavailable")
        return api_error_response(
            'photo_storage_unavailable',
            _('Photo storage is temporarily unavailable.'),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        with transaction.atomic():
            photo = ProfilePhoto.objects.select_for_update().get(
                id=photo_id,
                profile__user=request.user,
            )
            previous_references = _photo_references(photo)
            photo.photo_url = ''
            photo.thumbnail_url = ''
            photo.storage_key = upload_result['storage_key']
            photo.thumbnail_storage_key = upload_result['thumbnail_storage_key']
            photo.storage_state = ProfilePhoto.PRIVATE
            photo.legacy_source_verified = False
            photo.private_migrated_at = timezone.now()
            update_fields = [
                'photo_url', 'thumbnail_url', 'storage_key',
                'thumbnail_storage_key', 'storage_state',
                'legacy_source_verified', 'private_migrated_at',
            ]
            if 'caption' in serializer.validated_data:
                photo.caption = serializer.validated_data['caption']
                update_fields.append('caption')
            photo.save(update_fields=update_fields)
            transaction.on_commit(
                lambda references=previous_references: _delete_photo_references(references)
            )
    except Exception:
        _delete_uploaded_photo(upload_result)
        # Do not attach exception traces: object-store providers can embed
        # object keys or request URLs in their exception text.
        logger.error("Profile photo replacement failed")
        return Response({
            'error': True,
            'message': _('Failed to replace photo. Please try again.'),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(_photo_payload(photo, request), status=status.HTTP_200_OK)


def _photo_payload(photo, request):
    return {
        'photo_id': str(photo.id),
        'url': profile_photo_delivery_url(photo, request),
        'thumbnail_url': profile_photo_delivery_url(photo, request, thumbnail=True),
        'is_main': photo.is_main,
        'caption': photo.caption,
        'uploaded_at': photo.uploaded_at,
    }


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def profile_photo_media_view(request, photo_id, variant):
    """Serve private profile media after checking authorisation on every read."""
    if variant not in {'main', 'thumbnail'}:
        raise NotFound()
    photo = get_object_or_404(
        ProfilePhoto.objects.select_related('profile__user'),
        id=photo_id,
    )
    if request.user.id != photo.profile.user_id and not has_active_kyc(request.user):
        raise KycRequired()
    if photo.storage_state not in {ProfilePhoto.PRIVATE, ProfilePhoto.MIGRATION_COPIED}:
        raise NotFound()
    key = photo.thumbnail_storage_key if variant == 'thumbnail' else photo.storage_key
    if not key:
        raise NotFound()
    try:
        from .private_storage import (
            PrivateObjectIntegrityError,
            PrivateObjectNotFound,
            PrivateStorageUnavailable,
            private_object_storage,
        )

        metadata = private_object_storage.metadata(scope='profile', key=key)
        content = private_object_storage.download(scope='profile', key=key)
    except (PrivateObjectIntegrityError, PrivateObjectNotFound):
        raise NotFound()
    except PrivateStorageUnavailable:
        return api_error_response(
            'photo_storage_unavailable',
            _('Photo storage is temporarily unavailable.'),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    response = HttpResponse(content, content_type=metadata.content_type or 'image/jpeg')
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class VerificationStatusView(generics.GenericAPIView):
    """Read safe KYC state without creating records or challenges."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return _kyc_private_response(serialize_safe_kyc_status(user=request.user))


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def start_kyc_attempt_view(request):
    """Start or replay an idempotent KYC attempt."""
    serializer = KycStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    attempt, challenge_code, replay = start_or_resume_kyc_attempt(
        user=request.user,
        consent_version=serializer.validated_data['consent_version'],
        idempotency_key=serializer.validated_data['idempotency_key'],
    )
    return _kyc_private_response(
        {
            'attempt_id': str(attempt.id),
            'status': attempt.status,
            'selfie_challenge': {
                'code': challenge_code,
                'expires_at': attempt.challenge_expires_at,
            },
            'idempotent_replay': replay,
        },
        response_status=status.HTTP_200_OK if replay else status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_kyc_upload_intent_view(request):
    """Issue a transient constrained PUT URL for an opaque private object."""
    serializer = KycUploadIntentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    intent, replay = issue_kyc_upload_intent(
        user=request.user,
        values=serializer.validated_data,
    )
    payload = serialize_kyc_upload_intent(intent, replay=replay)
    return _kyc_private_response(
        payload,
        response_status=status.HTTP_200_OK if replay else status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def complete_kyc_upload_view(request):
    """Schedule one idempotent technical validation after the direct PUT."""
    serializer = KycUploadCompleteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    intent, replay = mark_kyc_upload_complete(
        user=request.user,
        upload_id=serializer.validated_data['upload_id'],
    )
    if not replay:
        from profiles.tasks import verify_kyc_upload

        transaction.on_commit(lambda: verify_kyc_upload.delay(str(intent.id)))
    return _kyc_private_response(
        {
            'upload_id': str(intent.id),
            'state': 'processing',
            'idempotent_replay': replay,
        },
        response_status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_kyc_attempt_view(request):
    """Submit server-owned accepted intents for human review."""
    serializer = KycSubmitRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    attempt, replay = submit_kyc_attempt(
        user=request.user,
        attempt_id=values['attempt_id'],
        upload_ids={
            'identity_upload_id': values['identity_upload_id'],
            'medical_upload_id': values['medical_upload_id'],
            'selfie_upload_id': values['selfie_upload_id'],
        },
        selfie_challenge_code=values['selfie_challenge_code'],
        idempotency_key=values['idempotency_key'],
    )
    return _kyc_private_response(
        {
            'attempt_id': str(attempt.id),
            'status': attempt.status,
            'idempotent_replay': replay,
        },
        response_status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_upload_url_view(request):
    """Block the unsafe historical signed-upload contract."""
    raise KycLegacyEndpointDeprecated()


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_verification_documents_view(request):
    """Block the unsafe historical client-supplied storage-path contract."""
    raise KycLegacyEndpointDeprecated()
