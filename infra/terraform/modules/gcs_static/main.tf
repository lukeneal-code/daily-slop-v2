variable "project_id" { type = string }
variable "location" { type = string }
variable "bucket_name" { type = string }

resource "google_storage_bucket" "frontend" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "inherited"
  force_destroy               = false

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html" # SPA fallback
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

output "bucket_name" { value = google_storage_bucket.frontend.name }
output "self_link" { value = google_storage_bucket.frontend.self_link }
