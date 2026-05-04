variable "project_id" { type = string }
variable "region" { type = string }
variable "repository_id" {
  type    = string
  default = "app"
}

resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Daily Slop application images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent-50"
    action = "KEEP"
    most_recent_versions {
      keep_count = 50
    }
  }
}

output "repo_path" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}
