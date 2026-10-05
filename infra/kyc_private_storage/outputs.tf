output "kyc_bucket_name" {
  value = google_storage_bucket.kyc.name
}

output "profile_media_bucket_name" {
  value = google_storage_bucket.profile_media.name
}
