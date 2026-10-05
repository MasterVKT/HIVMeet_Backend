terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_storage_bucket" "kyc" {
  name                        = var.kyc_bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  encryption {
    default_kms_key_name = var.kyc_kms_key_name
  }

  versioning {
    # A KYC purge must remove the bytes, not merely create a noncurrent
    # version. Backup/retention requirements are governed separately by the
    # approved legal schedule and must never turn this bucket public.
    enabled = false
  }

  lifecycle_rule {
    action { type = "Delete" }
    condition { age = var.kyc_retention_days }
  }

  cors {
    origin          = var.upload_allowed_origins
    method          = ["PUT"]
    response_header = ["Content-Type", "x-goog-generation"]
    max_age_seconds = 600
  }

  lifecycle {
    prevent_destroy = true

    precondition {
      condition     = var.kyc_bucket_name != var.profile_bucket_name
      error_message = "KYC evidence and profile media must use distinct buckets."
    }
    precondition {
      condition     = var.kyc_kms_key_name != var.profile_kms_key_name
      error_message = "KYC evidence and profile media must use distinct CMEK keys."
    }
  }
}

resource "google_storage_bucket" "profile_media" {
  name                        = var.profile_bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  encryption {
    default_kms_key_name = var.profile_kms_key_name
  }

  versioning {
    # Profile media is recreated privately; preserving deleted public-era
    # versions would defeat the verified migration/purge procedure.
    enabled = false
  }

  lifecycle {
    prevent_destroy = true
  }

}

# No allUsers/allAuthenticatedUsers binding is allowed. The runtime account is
# the sole object reader/writer and KYC PUT URL signer; grant it through
# workload identity rather than a checked-in credential. Profile-media reads
# are proxied by the authenticated API rather than signed directly.
resource "google_storage_bucket_iam_member" "kyc_runtime_object_admin" {
  bucket = google_storage_bucket.kyc.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.runtime_service_account}"
}

resource "google_storage_bucket_iam_member" "profile_runtime_object_admin" {
  bucket = google_storage_bucket.profile_media.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.runtime_service_account}"
}

# Bucket-default CMEK is performed by the Cloud Storage service agent, not by
# the application process. Grant the agent only encrypt/decrypt on the two
# approved keys; do not give the runtime account broad KMS administration.
resource "google_kms_crypto_key_iam_member" "kyc_storage_service_agent" {
  crypto_key_id = var.kyc_kms_key_name
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

resource "google_kms_crypto_key_iam_member" "profile_storage_service_agent" {
  crypto_key_id = var.profile_kms_key_name
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# Workload identity signs V4 URLs through IAM; no JSON private key is created
# or stored in the repository. This grant is intentionally scoped to the
# runtime service account itself and must be reviewed by Platform/Security.
resource "google_service_account_iam_member" "runtime_v4_url_signer" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.runtime_service_account}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.runtime_service_account}"
}
