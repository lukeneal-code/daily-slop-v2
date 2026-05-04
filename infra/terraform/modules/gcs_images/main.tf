variable "project_id" { type = string }
variable "location" { type = string }
variable "bucket_name" { type = string }

resource "google_storage_bucket" "images" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "inherited"
  force_destroy               = false

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

# Public read so the CDN can cache without signed URLs.
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.images.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

output "bucket_name" { value = google_storage_bucket.images.name }
output "self_link" { value = google_storage_bucket.images.self_link }
