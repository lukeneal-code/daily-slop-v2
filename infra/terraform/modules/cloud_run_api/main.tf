variable "project_id" { type = string }
variable "region" { type = string }
variable "service_name" {
  type    = string
  default = "api"
}
variable "image" { type = string }
variable "scheduler_sa_email" { type = string }
variable "api_url" { type = string }
variable "cors_origins" {
  type    = list(string)
  default = ["https://dailyslop.co.uk"]
}
variable "database_url" { type = string }
variable "database_url_sync" { type = string }
variable "images_bucket" { type = string }
variable "images_public_base_url" { type = string }
variable "secret_anthropic" { type = string }
variable "secret_openai" { type = string }
variable "secret_xai" { type = string }
variable "vpc_connector" {
  type    = string
  default = ""
}
variable "extra_audiences" {
  type        = string
  description = "Comma-separated extra OIDC audiences to accept (e.g. the Cloud Run service URL pre-DNS)."
  default     = ""
}

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "api-runtime"
  display_name = "Cloud Run API runtime"
}

# Grant the runtime SA read access to each secret it references via secret_key_ref.
resource "google_secret_manager_secret_iam_member" "api_secret_access" {
  for_each = toset([
    var.secret_anthropic,
    var.secret_openai,
    var.secret_xai,
  ])
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  project             = var.project_id
  location            = var.region
  name                = var.service_name
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    dynamic "vpc_access" {
      for_each = var.vpc_connector == "" ? [] : [1]
      content {
        connector = var.vpc_connector
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }

    containers {
      image = var.image

      env {
        name  = "ENV"
        value = "prod"
      }
      env {
        name  = "API_URL"
        value = var.api_url
      }
      env {
        name  = "CORS_ORIGINS"
        value = jsonencode(var.cors_origins)
      }
      env {
        name  = "SCHEDULER_SA_EMAIL"
        value = var.scheduler_sa_email
      }
      env {
        name  = "EXTRA_AUDIENCES"
        value = var.extra_audiences
      }
      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "DATABASE_URL_SYNC"
        value = var.database_url_sync
      }
      env {
        name  = "IMAGES_BUCKET"
        value = var.images_bucket
      }
      env {
        name  = "IMAGES_PUBLIC_BASE_URL"
        value = var.images_public_base_url
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_anthropic
            version = "latest"
          }
        }
      }
      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_openai
            version = "latest"
          }
        }
      }
      env {
        name = "XAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_xai
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = true
      }

      ports {
        container_port = 8000
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }

    timeout = "900s"
  }
}

# Allow Cloud Scheduler to invoke the api service.
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_sa_email}"
}

output "service_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "runtime_sa_email" {
  value = google_service_account.api.email
}
