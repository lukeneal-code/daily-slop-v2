variable "project_id" {
  description = "GCP project ID for v2 (e.g. daily-slop-v2)."
  type        = string
}

variable "region" {
  description = "Primary region (london)."
  type        = string
  default     = "europe-west2"
}

variable "domain" {
  description = "Public domain for the site."
  type        = string
  default     = "dailyslop.co.uk"
}

variable "api_image_tag" {
  description = "Image tag (commit sha) for the api Cloud Run service."
  type        = string
  default     = "latest"
}

variable "github_repo" {
  description = "owner/repo for the GitHub repository (used for Workload Identity Federation)."
  type        = string
  default     = "lukeneal/daily-slop-v2"
}

variable "scheduler_cron" {
  description = "Cron expression for the daily generation job (Cloud Scheduler is in --time-zone)."
  type        = string
  default     = "0 6 * * *"
}

variable "linkedin_scheduler_cron" {
  description = "Cron expression for the daily LinkedIn-post job (after generation has finished)."
  type        = string
  default     = "30 7 * * *"
}

variable "scheduler_timezone" {
  description = "Time zone the daily cron runs in."
  type        = string
  default     = "Europe/London"
}

variable "linkedin_org_urn" {
  description = "LinkedIn organization URN for the company page (e.g. urn:li:organization:12345678). Empty disables LinkedIn posting."
  type        = string
  default     = ""
}

variable "extra_audiences" {
  description = "Extra OIDC audiences accepted on /admin/generate, e.g. the Cloud Run service URL while DNS isn't yet pointing at the LB. Comma-separated."
  type        = string
  default     = ""
}

variable "secret_names" {
  description = "Secrets created by bootstrap.sh that Terraform reads via data sources."
  type        = list(string)
  default = [
    "anthropic-api-key",
    "openai-api-key",
    "xai-api-key",
    "langfuse-db-password",
    "langfuse-nextauth-secret",
    "langfuse-salt",
    "langfuse-encryption-key",
    "linkedin-client-id",
    "linkedin-client-secret",
    "linkedin-access-token",
    "linkedin-refresh-token",
  ]
}
