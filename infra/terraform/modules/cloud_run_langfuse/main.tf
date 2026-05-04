variable "project_id" { type = string }
variable "region" { type = string }
variable "service_name" {
  type    = string
  default = "langfuse-web"
}
variable "image" {
  type    = string
  default = "langfuse/langfuse:2"
}
variable "vpc_connector" { type = string }
variable "database_url" {
  type      = string
  sensitive = true
}
variable "secret_nextauth" { type = string }
variable "secret_salt" { type = string }
variable "secret_encryption_key" { type = string }

resource "google_service_account" "langfuse" {
  project      = var.project_id
  account_id   = "langfuse-runtime"
  display_name = "LangFuse Cloud Run runtime"
}

# Grant the runtime SA read access to each secret it references via secret_key_ref.
resource "google_secret_manager_secret_iam_member" "langfuse_secret_access" {
  for_each = toset([
    var.secret_nextauth,
    var.secret_salt,
    var.secret_encryption_key,
  ])
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.langfuse.email}"
}

resource "google_cloud_run_v2_service" "langfuse" {
  project             = var.project_id
  location            = var.region
  name                = var.service_name
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.langfuse.email

    vpc_access {
      connector = var.vpc_connector
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.image

      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "TELEMETRY_ENABLED"
        value = "false"
      }
      env {
        name = "NEXTAUTH_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.secret_nextauth
            version = "latest"
          }
        }
      }
      env {
        name = "SALT"
        value_source {
          secret_key_ref {
            secret  = var.secret_salt
            version = "latest"
          }
        }
      }
      env {
        name = "ENCRYPTION_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_encryption_key
            version = "latest"
          }
        }
      }

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }
}

# LangFuse is intended for the operator, not the public — restrict to invoker IAM.
# (Open it up via `gcloud run services add-iam-policy-binding ... allUsers` if you
# want to expose the UI; we leave it locked by default.)

output "service_url" {
  value = google_cloud_run_v2_service.langfuse.uri
}
