variable "project_id" { type = string }
variable "region" { type = string }
variable "name" {
  type    = string
  default = "daily-slop-generate-prod"
}
variable "schedule" {
  type    = string
  default = "0 6 * * *"
}
variable "time_zone" {
  type    = string
  default = "Europe/London"
}
variable "target_url" { type = string }
variable "audience" {
  type        = string
  description = "OIDC audience the api validates against (typically the api host without path)."
}
variable "scheduler_sa_email" { type = string }

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "scheduler-invoker"
  display_name = "Cloud Scheduler invoker for daily generation"
}

resource "google_cloud_scheduler_job" "daily" {
  project   = var.project_id
  region    = var.region
  name      = var.name
  schedule  = var.schedule
  time_zone = var.time_zone

  http_target {
    http_method = "POST"
    uri         = var.target_url
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({}))

    oidc_token {
      service_account_email = var.scheduler_sa_email
      audience              = var.audience
    }
  }

  retry_config {
    retry_count          = 1
    min_backoff_duration = "60s"
    max_retry_duration   = "600s"
  }
}

output "service_account_email" {
  value = google_service_account.scheduler.email
}
