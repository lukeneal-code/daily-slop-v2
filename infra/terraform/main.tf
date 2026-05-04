locals {
  project_apis = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudbuild.googleapis.com",
  ]

  domain                 = var.domain
  api_url                = "https://${var.domain}"
  images_bucket_name     = "${var.project_id}-images-prod"
  frontend_bucket_name   = "${var.project_id}-frontend-prod"
  images_public_base_url = "https://${var.domain}/images"
}

# ---------------------------------------------------------------------------
# Project APIs.
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each                   = toset(local.project_apis)
  project                    = var.project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}

# ---------------------------------------------------------------------------
# Read references to secrets that bootstrap.sh created.
# ---------------------------------------------------------------------------
data "google_secret_manager_secret" "secrets" {
  for_each   = toset(var.secret_names)
  project    = var.project_id
  secret_id  = each.key
  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Networking.
# ---------------------------------------------------------------------------
module "network" {
  source     = "./modules/network"
  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud SQL (single instance, two databases: slop + langfuse).
# ---------------------------------------------------------------------------
module "cloudsql" {
  source                      = "./modules/cloudsql"
  project_id                  = var.project_id
  region                      = var.region
  network_self_link           = module.network.network_self_link
  private_vpc_dependency      = module.network.private_vpc_dependency
  langfuse_db_password_secret = "langfuse-db-password"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Artifact Registry.
# ---------------------------------------------------------------------------
module "artifact_registry" {
  source        = "./modules/artifact_registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = "app"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# GCS buckets.
# ---------------------------------------------------------------------------
module "gcs_images" {
  source      = "./modules/gcs_images"
  project_id  = var.project_id
  location    = var.region
  bucket_name = local.images_bucket_name

  depends_on = [google_project_service.apis]
}

module "gcs_static" {
  source      = "./modules/gcs_static"
  project_id  = var.project_id
  location    = var.region
  bucket_name = local.frontend_bucket_name

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud Run — API service.
# ---------------------------------------------------------------------------
module "cloud_run_api" {
  source                 = "./modules/cloud_run_api"
  project_id             = var.project_id
  region                 = var.region
  service_name           = "api"
  image                  = "${module.artifact_registry.repo_path}/api:${var.api_image_tag}"
  scheduler_sa_email     = module.cloud_scheduler.service_account_email
  api_url                = local.api_url
  extra_audiences        = var.extra_audiences
  cors_origins           = ["https://${var.domain}"]
  images_bucket          = local.images_bucket_name
  images_public_base_url = local.images_public_base_url
  vpc_connector          = module.network.vpc_connector

  database_url = format(
    "postgresql+asyncpg://%s:%s@%s:5432/slop",
    module.cloudsql.slop_user,
    module.cloudsql.slop_password,
    module.cloudsql.private_ip,
  )
  database_url_sync = format(
    "postgresql+psycopg://%s:%s@%s:5432/slop",
    module.cloudsql.slop_user,
    module.cloudsql.slop_password,
    module.cloudsql.private_ip,
  )

  secret_anthropic = "anthropic-api-key"
  secret_openai    = "openai-api-key"
  secret_xai       = "xai-api-key"

  linkedin_org_urn = var.linkedin_org_urn
  site_url         = "https://${var.domain}"

  depends_on = [
    module.gcs_images,
    module.cloudsql,
    module.artifact_registry,
  ]
}

# Grant the api runtime SA permission to write to the images bucket.
resource "google_storage_bucket_iam_member" "api_images_writer" {
  bucket = module.gcs_images.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.cloud_run_api.runtime_sa_email}"
}

# ---------------------------------------------------------------------------
# Cloud Scheduler.
# ---------------------------------------------------------------------------
module "cloud_scheduler" {
  source             = "./modules/cloud_scheduler"
  project_id         = var.project_id
  region             = var.region
  schedule           = var.scheduler_cron
  time_zone          = var.scheduler_timezone
  target_url         = "${module.cloud_run_api.service_url}/admin/generate"
  audience           = module.cloud_run_api.service_url
  scheduler_sa_email = "scheduler-invoker@${var.project_id}.iam.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

# Second scheduler job: post the day's front-page picks to LinkedIn.
# Reuses the scheduler SA created by module.cloud_scheduler. Disabled when
# linkedin_org_urn is unset (the count-based no-op).
resource "google_cloud_scheduler_job" "linkedin_post" {
  count = var.linkedin_org_urn == "" ? 0 : 1

  project   = var.project_id
  region    = var.region
  name      = "daily-slop-linkedin-prod"
  schedule  = var.linkedin_scheduler_cron
  time_zone = var.scheduler_timezone

  http_target {
    http_method = "POST"
    uri         = "${module.cloud_run_api.service_url}/admin/post-linkedin"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({}))

    oidc_token {
      service_account_email = module.cloud_scheduler.service_account_email
      audience              = module.cloud_run_api.service_url
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "60s"
    max_retry_duration   = "600s"
  }

  depends_on = [module.cloud_scheduler, module.cloud_run_api]
}

# ---------------------------------------------------------------------------
# LangFuse self-host.
#
# LangFuse expects a single `DATABASE_URL` env var. Cloud Run secret refs only
# substitute whole values, so we read the LangFuse DB password here and assemble
# the URL. The password ends up in tfstate — that's acceptable because the
# tfstate bucket is private + versioned with no public access.
# ---------------------------------------------------------------------------
data "google_secret_manager_secret_version" "langfuse_db_password" {
  project = var.project_id
  secret  = "langfuse-db-password"

  depends_on = [google_project_service.apis]
}

module "cloud_run_langfuse" {
  source        = "./modules/cloud_run_langfuse"
  project_id    = var.project_id
  region        = var.region
  vpc_connector = module.network.vpc_connector
  database_url = format(
    "postgresql://%s:%s@%s:5432/langfuse",
    module.cloudsql.langfuse_user,
    urlencode(data.google_secret_manager_secret_version.langfuse_db_password.secret_data),
    module.cloudsql.private_ip,
  )
  secret_nextauth       = "langfuse-nextauth-secret"
  secret_salt           = "langfuse-salt"
  secret_encryption_key = "langfuse-encryption-key"

  depends_on = [module.cloudsql]
}

# ---------------------------------------------------------------------------
# Load balancer + CDN.
# ---------------------------------------------------------------------------
module "lb_cdn" {
  source               = "./modules/lb_cdn"
  project_id           = var.project_id
  region               = var.region
  domain               = var.domain
  frontend_bucket_name = module.gcs_static.bucket_name
  images_bucket_name   = module.gcs_images.bucket_name
  api_service_name     = "api"

  depends_on = [
    module.cloud_run_api,
    module.gcs_images,
    module.gcs_static,
  ]
}

output "lb_ip" {
  value       = module.lb_cdn.lb_ip
  description = "Point your registrar's A record at this IP at cutover."
}

output "api_service_url" {
  value = module.cloud_run_api.service_url
}

output "langfuse_service_url" {
  value = module.cloud_run_langfuse.service_url
}

output "scheduler_sa_email" {
  value = module.cloud_scheduler.service_account_email
}
