"""Fail-closed runtime gate for a production KYC rollout.

This module deliberately contains no model or storage import so settings can
validate the deployment posture before Django accepts traffic.
"""

from django.core.exceptions import ImproperlyConfigured


DEPLOYMENT_ENVIRONMENTS = frozenset({
    'development', 'test', 'preproduction', 'production',
})
KYC_ENFORCEMENT_MODES = frozenset({'disabled', 'preproduction', 'enforced'})


def validate_kyc_runtime_gate(*, deployment_environment, enforcement_mode,
                              legal_approval, legal_approval_reference):
    """Reject a production process unless the written legal gate is asserted.

    The reference is an operator-held approval identifier, never document
    evidence or a person’s data. It cannot prove legal authority by itself;
    it makes an unaudited, implicit production activation impossible.
    """
    if deployment_environment not in DEPLOYMENT_ENVIRONMENTS:
        raise ImproperlyConfigured('HIVMEET_DEPLOYMENT_ENVIRONMENT is invalid.')
    if enforcement_mode not in KYC_ENFORCEMENT_MODES:
        raise ImproperlyConfigured('KYC_SOCIAL_ACCESS_ENFORCEMENT is invalid.')
    if deployment_environment != 'production':
        return
    if enforcement_mode != 'enforced':
        raise ImproperlyConfigured(
            'Production must use KYC_SOCIAL_ACCESS_ENFORCEMENT=enforced.'
        )
    if not legal_approval or not legal_approval_reference:
        raise ImproperlyConfigured(
            'Written legal/DPO approval is required before KYC production activation.'
        )


def validate_private_storage_runtime_gate(
        *, deployment_environment, kyc_storage_backend,
        profile_media_storage_backend, kyc_bucket, profile_media_bucket,
        kyc_kms_key, profile_media_kms_key, runtime_service_account,
        kyc_document_retention_days, antivirus_backend,
        kyc_storage_upload_ttl_seconds, kyc_quarantine_retention_hours,
        kyc_scan_timeout_seconds, kyc_max_image_pixels, kyc_max_pdf_pages,
        kyc_max_pdf_objects, profile_media_max_upload_bytes,
        profile_media_max_image_pixels, kyc_clamav_binary):
    """Reject production KYC if its private-storage posture is incomplete.

    This deliberately validates configuration identifiers only. It never logs
    a bucket, a KMS resource, or a service-account identity, and it does not
    contact the cloud provider during Django startup. The deployment gate and
    the operational verifier remain responsible for proving the live policy.
    """
    if deployment_environment != 'production':
        return

    errors = []
    if kyc_storage_backend != 'gcs':
        errors.append('kyc_storage_backend')
    if profile_media_storage_backend != 'gcs':
        errors.append('profile_media_storage_backend')
    if not kyc_bucket:
        errors.append('kyc_bucket')
    if not profile_media_bucket:
        errors.append('profile_media_bucket')
    if kyc_bucket and kyc_bucket == profile_media_bucket:
        errors.append('distinct_buckets')
    if not kyc_kms_key:
        errors.append('kyc_kms_key')
    if not profile_media_kms_key:
        errors.append('profile_media_kms_key')
    if kyc_kms_key and kyc_kms_key == profile_media_kms_key:
        errors.append('distinct_kms_keys')
    if not runtime_service_account:
        errors.append('runtime_service_account')
    if kyc_document_retention_days <= 0:
        errors.append('kyc_document_retention_days')
    if kyc_storage_upload_ttl_seconds <= 0:
        errors.append('kyc_storage_upload_ttl_seconds')
    if kyc_quarantine_retention_hours <= 0:
        errors.append('kyc_quarantine_retention_hours')
    if kyc_scan_timeout_seconds <= 0:
        errors.append('kyc_scan_timeout_seconds')
    if kyc_max_image_pixels <= 0:
        errors.append('kyc_max_image_pixels')
    if kyc_max_pdf_pages <= 0:
        errors.append('kyc_max_pdf_pages')
    if kyc_max_pdf_objects <= 0:
        errors.append('kyc_max_pdf_objects')
    if profile_media_max_upload_bytes <= 0:
        errors.append('profile_media_max_upload_bytes')
    if profile_media_max_image_pixels <= 0:
        errors.append('profile_media_max_image_pixels')
    if antivirus_backend != 'clamav-cli':
        errors.append('antivirus_backend')
    if not isinstance(kyc_clamav_binary, str) or not kyc_clamav_binary.strip():
        errors.append('kyc_clamav_binary')

    if errors:
        raise ImproperlyConfigured(
            'Production KYC private storage configuration is incomplete: '
            + ','.join(errors)
        )
