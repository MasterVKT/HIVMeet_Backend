variable "project_id" { type = string }
variable "region" { type = string }
variable "location" { type = string }
variable "kyc_bucket_name" { type = string }
variable "profile_bucket_name" { type = string }
variable "kyc_kms_key_name" { type = string }
variable "profile_kms_key_name" { type = string }
variable "runtime_service_account" { type = string }
variable "upload_allowed_origins" {
  type        = list(string)
  description = "Exact HTTPS browser origins permitted to PUT synthetic KYC uploads."

  validation {
    condition = length(var.upload_allowed_origins) > 0 && alltrue([
      # Keep Terraform's bucket CORS input compatible with the backend
      # deployment gate. A CORS origin is scheme + authority only: no path,
      # query, fragment, credentials or wildcard can broaden the PUT scope.
      for origin in var.upload_allowed_origins : can(
        regex("^https://[^/:?#@]+(:[0-9]+)?$", origin)
      )
    ])
    error_message = "KYC upload CORS origins must be exact HTTPS origins without a path, credentials, query, fragment or wildcard."
  }
}

variable "kyc_retention_days" {
  type = number
  validation {
    condition     = var.kyc_retention_days > 0
    error_message = "KYC retention requires an explicit positive legal/DPO-approved value."
  }
}
