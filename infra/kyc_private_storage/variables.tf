variable "project_id" { type = string }
variable "region" { type = string }
variable "location" { type = string }
variable "kyc_bucket_name" { type = string }
variable "profile_bucket_name" { type = string }
variable "kyc_kms_key_name" { type = string }
variable "profile_kms_key_name" { type = string }
variable "runtime_service_account" { type = string }
variable "upload_allowed_origins" {
  type = list(string)
  validation {
    condition = length(var.upload_allowed_origins) > 0 && alltrue([
      for origin in var.upload_allowed_origins : origin != "*"
    ])
    error_message = "KYC upload CORS origins must be explicit and may not contain a wildcard."
  }
}

variable "kyc_retention_days" {
  type = number
  validation {
    condition     = var.kyc_retention_days > 0
    error_message = "KYC retention requires an explicit positive legal/DPO-approved value."
  }
}
