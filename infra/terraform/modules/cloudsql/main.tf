variable "project_id" { type = string }
variable "region" { type = string }
variable "tier" {
  type    = string
  default = "db-f1-micro"
}
variable "network_self_link" { type = string }
variable "private_vpc_dependency" { type = string }
variable "langfuse_db_password_secret" { type = string }

resource "random_password" "app" {
  length  = 24
  special = false
}

resource "google_sql_database_instance" "main" {
  project          = var.project_id
  name             = "slop-pg"
  region           = var.region
  database_version = "POSTGRES_16"
  depends_on       = [var.private_vpc_dependency]

  settings {
    tier              = var.tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_size         = 10
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "04:00"
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_self_link
    }
  }

  deletion_protection = true
}

# App database.
resource "google_sql_database" "slop" {
  project  = var.project_id
  name     = "slop"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "slop" {
  project  = var.project_id
  name     = "slop"
  instance = google_sql_database_instance.main.name
  password = random_password.app.result
}

# LangFuse database on the same instance.
resource "google_sql_database" "langfuse" {
  project  = var.project_id
  name     = "langfuse"
  instance = google_sql_database_instance.main.name
}

data "google_secret_manager_secret_version" "langfuse_pw" {
  project = var.project_id
  secret  = var.langfuse_db_password_secret
}

resource "google_sql_user" "langfuse" {
  project  = var.project_id
  name     = "langfuse"
  instance = google_sql_database_instance.main.name
  password = data.google_secret_manager_secret_version.langfuse_pw.secret_data
}

output "instance_name" { value = google_sql_database_instance.main.name }
output "private_ip" { value = google_sql_database_instance.main.private_ip_address }
output "slop_user" { value = google_sql_user.slop.name }
output "slop_password" {
  value     = random_password.app.result
  sensitive = true
}
output "langfuse_user" { value = google_sql_user.langfuse.name }
