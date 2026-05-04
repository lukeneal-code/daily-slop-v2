variable "project_id" { type = string }
variable "domain" { type = string }
variable "frontend_bucket_name" { type = string }
variable "images_bucket_name" { type = string }
variable "api_service_name" { type = string }
variable "region" { type = string }

# Backend bucket for the SPA.
resource "google_compute_backend_bucket" "frontend" {
  project     = var.project_id
  name        = "frontend-backend"
  bucket_name = var.frontend_bucket_name
  enable_cdn  = true

  cdn_policy {
    cache_mode  = "CACHE_ALL_STATIC"
    default_ttl = 3600
    max_ttl     = 86400
    client_ttl  = 3600
  }
}

# Backend bucket for images (immutable).
resource "google_compute_backend_bucket" "images" {
  project     = var.project_id
  name        = "images-backend"
  bucket_name = var.images_bucket_name
  enable_cdn  = true

  cdn_policy {
    cache_mode  = "CACHE_ALL_STATIC"
    default_ttl = 31536000
    max_ttl     = 31536000
    client_ttl  = 31536000
  }
}

# Serverless NEG pointing at the api Cloud Run service.
resource "google_compute_region_network_endpoint_group" "api" {
  project               = var.project_id
  name                  = "api-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = var.api_service_name
  }
}

resource "google_compute_backend_service" "api" {
  project               = var.project_id
  name                  = "api-backend"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.api.id
  }
}

resource "google_compute_url_map" "main" {
  project         = var.project_id
  name            = "slop-lb"
  default_service = google_compute_backend_bucket.frontend.id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "main"
  }

  path_matcher {
    name            = "main"
    default_service = google_compute_backend_bucket.frontend.id

    path_rule {
      paths   = ["/api/*", "/admin/*", "/healthz"]
      service = google_compute_backend_service.api.id
    }

    path_rule {
      paths   = ["/images/*"]
      service = google_compute_backend_bucket.images.id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "main" {
  project = var.project_id
  name    = "slop-cert"
  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "main" {
  project          = var.project_id
  name             = "slop-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_address" "main" {
  project = var.project_id
  name    = "slop-lb-ip"
}

resource "google_compute_global_forwarding_rule" "main" {
  project               = var.project_id
  name                  = "slop-lb-fwd"
  ip_address            = google_compute_global_address.main.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.main.id
}

# HTTP → HTTPS redirect.
resource "google_compute_url_map" "redirect" {
  project = var.project_id
  name    = "slop-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  project = var.project_id
  name    = "slop-http-proxy"
  url_map = google_compute_url_map.redirect.id
}

resource "google_compute_global_forwarding_rule" "redirect" {
  project               = var.project_id
  name                  = "slop-lb-fwd-http"
  ip_address            = google_compute_global_address.main.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.redirect.id
}

output "lb_ip" { value = google_compute_global_address.main.address }
output "url_map_name" { value = google_compute_url_map.main.name }
